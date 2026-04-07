import io
import logging
from google import genai
from google.genai import types
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dotenv import load_dotenv
import threading
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ai_handler.log")
    ]
)

# Load API keys (rotation uses GEMINI_API_KEY_1, _2, _3)
load_dotenv()


def _collect_gemini_api_keys():
    keys = []
    for env_name in ("GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        v = (os.getenv(env_name) or "").strip()
        if v and v != "YOUR_API_KEY_HERE":
            keys.append(v)
    return keys


API_KEYS = _collect_gemini_api_keys()
API_KEY = API_KEYS[0] if API_KEYS else None

if not API_KEYS:
    logging.critical(
        "FATAL: No API key loaded. The application will not work. "
        "Please set GEMINI_API_KEY_1 (and optionally GEMINI_API_KEY_2, GEMINI_API_KEY_3) in your environment."
    )
else:
    logging.info("Loaded %d API key(s).", len(API_KEYS))

# Track which key is currently active
current_key_index = 0

# --- Rate Limiting ---
# Lock to ensure only one request runs at a time
request_lock = threading.Lock()
# Track the time of the last request to enforce a minimum delay
last_request_time = 0
# Minimum seconds to wait between requests to avoid hitting basic rate limits
MIN_REQUEST_DELAY = float(os.getenv("GEMINI_MIN_DELAY_SECONDS", "1.0"))

# Request tuning for cloud deployments like Render
KEY_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "45"))
KEY_RETRIES = int(os.getenv("GEMINI_RETRIES_PER_KEY", "3"))
RETRY_DELAY = float(os.getenv("GEMINI_RETRY_DELAY_SECONDS", "1.5"))
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
# 2.5 / flash-latest often have separate quota from 2.0 when free tier is exhausted
MODEL_CANDIDATES_RAW = os.getenv(
    "GEMINI_MODEL_CANDIDATES",
    "gemini-2.0-flash,gemini-2.5-flash,gemini-flash-latest",
)
MODEL_CANDIDATES = [m.strip() for m in MODEL_CANDIDATES_RAW.split(",") if m.strip()]
if PRIMARY_MODEL not in MODEL_CANDIDATES:
    MODEL_CANDIDATES.insert(0, PRIMARY_MODEL)
USE_REST_FALLBACK = os.getenv("GEMINI_USE_REST_FALLBACK", "1") == "1"

# System prompt to get short, voice-friendly responses
SYSTEM_PROMPT = """You are a helpful voice assistant. 
Keep your answers SHORT and CONVERSATIONAL (2-3 sentences max).
Do NOT use markdown, bullet points, numbered lists, or any special formatting.
Speak naturally as if you are talking to someone.
Be concise and direct."""

def clean_for_speech(text):
    """Remove markdown and special characters so pyttsx3 can speak cleanly."""
    text = re.sub(r'\*+', '', text)        # Remove asterisks (bold/italic)
    text = re.sub(r'#+\s*', '', text)      # Remove headings
    text = re.sub(r'`+', '', text)         # Remove code backticks
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Links -> just text
    text = re.sub(r'\n+', '. ', text)      # Newlines -> periods
    text = re.sub(r'\s+', ' ', text)       # Collapse whitespace
    return text.strip()


def _is_quota_error(error_text):
    lower = error_text.lower()
    return (
        "resource_exhausted" in lower
        or "quota exceeded" in lower
        or "rest http 429" in lower
        or "exceeded your current quota" in lower
    )


def _is_model_not_found_error(error_text):
    lower = error_text.lower()
    return (
        "rest http 404" in lower
        or "is not found for api version" in lower
        or "not supported for generatecontent" in lower
    )


def _extract_retry_seconds(error_text):
    text = error_text.lower()

    # Handle: "retryDelay": "35s"
    m = re.search(r'retrydelay"\s*:\s*"(\d+)s"', text)
    if m:
        return int(m.group(1))

    # Handle: "Please retry in 9.99s" or "retry in 9s"
    m = re.search(r'retry(?:\s+in)?\s+(\d+(?:\.\d+)?)s', text)
    if m:
        return max(1, int(float(m.group(1))))

    return None


def friendly_ai_failure_message(last_error):
    """
    Short, safe text for the chat UI when all keys/models failed.
    Raw API details stay in server logs only.
    """
    if not last_error:
        return "Sorry, I could not reach the AI service. Please try again in a moment."
    lower = last_error.lower()
    if "timed out" in lower or "handshake" in lower or "_ssl." in lower:
        return (
            "The AI service is taking too long to respond right now. "
            "Please try again in a few seconds."
        )
    if _is_quota_error(last_error):
        return (
            "The AI quota for your account is used up right now. "
            "Try again later, or check usage and billing in Google AI Studio."
        )
    return "Sorry, I could not get a reply right now. Please try again in a moment."


def _rest_model_ids_for_logical_name(model_name):
    """
    REST :generateContent model IDs to try in order.
    Google deprecates IDs over time; gemini-1.5-flash-latest no longer works on v1beta.
    """
    m = (model_name or "").strip()
    if m == "gemini-1.5-flash":
        return [
            "gemini-flash-latest",
            "gemini-2.5-flash",
            "gemini-1.5-flash",
        ]
    return [m]


def _generate_with_rest(api_key, model_name, prompt):
    """Fallback path using Gemini REST API when SDK calls fail or time out."""
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}],
        },
        "contents": [
            {
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 120,
            "temperature": 0.6,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    last_404_msg = None

    for rest_model_name in _rest_model_ids_for_logical_name(model_name):
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib.parse.quote(rest_model_name, safe='')}:generateContent?key={api_key}"
        )
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=KEY_TIMEOUT) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            rest_body = e.read().decode("utf-8", errors="replace")
            err_line = f"REST HTTP {e.code} for {rest_model_name}: {rest_body}"
            if e.code == 404 and _is_model_not_found_error(err_line):
                logging.info(
                    "REST model id %r not available for %r, trying next alias.",
                    rest_model_name,
                    model_name,
                )
                last_404_msg = err_line
                continue
            # Let outer handler parse quota / body again
            raise urllib.error.HTTPError(
                e.url, e.code, e.msg, e.hdrs, io.BytesIO(rest_body.encode("utf-8"))
            ) from None

        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"No candidates in Gemini REST response: {body}")

        parts = (candidates[0].get("content") or {}).get("parts") or []
        text_chunks = [p.get("text", "") for p in parts if p.get("text")]
        text = " ".join(text_chunks).strip()
        if not text:
            raise RuntimeError(f"Empty text in Gemini REST response: {body}")
        if rest_model_name != model_name:
            logging.info(
                "REST succeeded using id %r (logical model %r).",
                rest_model_name,
                model_name,
            )
        return text

    raise RuntimeError(last_404_msg or f"No REST model id worked for {model_name!r}")

def apply_rate_limit():
    """Blocks until it's safe to make another API call."""
    global last_request_time
    with request_lock:
        elapsed = time.time() - last_request_time
        if elapsed < MIN_REQUEST_DELAY:
            wait_time = MIN_REQUEST_DELAY - elapsed
            print(f"Rate limit: waiting {wait_time:.2f}s before next request.")
            time.sleep(wait_time)
        # Update last request time *after* waiting
        last_request_time = time.time()

def get_ai_response(prompt):
    """
    Gets a response from Gemini AI with rate limiting, per-key retries, and key rotation.
    """
    apply_rate_limit()  # Enforce delay and single-threading
    logging.info(f"Received request for prompt: {prompt}")

    global current_key_index

    if not API_KEYS:
        return "No API key configured. Please add a key in your .env file."

    total_keys = len(API_KEYS)
    last_error = None

    # Loop through keys indefinitely, with delays, until a response is received or all keys fail
    while True:
        key_num = current_key_index + 1
        key = API_KEYS[current_key_index]
        logging.info(f"Using API Key #{key_num}")

        for retry_index in range(KEY_RETRIES):
            try:
                logging.info(
                    f"Attempt {retry_index + 1}/{KEY_RETRIES} with Key #{key_num}"
                )
                start_time = time.time()

                # Use SDK-native request timeout to avoid thread issues in web workers
                client = genai.Client(api_key=key, http_options={"timeout": KEY_TIMEOUT})

                response = None
                last_model_error = None
                active_models = list(MODEL_CANDIDATES)

                for model_name in active_models:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=SYSTEM_PROMPT,
                                max_output_tokens=120,
                            ),
                        )
                        break
                    except Exception as model_error:
                        last_model_error = str(model_error)
                        logging.warning(f"SDK model {model_name} failed for Key {key_num}: {last_model_error}")

                        if _is_quota_error(last_model_error):
                            retry_after = _extract_retry_seconds(last_model_error)
                            idx = active_models.index(model_name)
                            if idx < len(active_models) - 1:
                                logging.info(
                                    f"SDK quota on {model_name} for Key {key_num}; "
                                    "trying the next configured model first."
                                )
                                continue
                            if retry_after:
                                logging.info(
                                    f"Quota error for Key {key_num}. "
                                    f"Waiting {retry_after} seconds."
                                )
                                time.sleep(retry_after)
                                continue
                            break

                        if _is_model_not_found_error(last_model_error):
                            logging.warning(f"Skipping unsupported model: {model_name}")
                            continue

                        if USE_REST_FALLBACK:
                            try:
                                rest_text = _generate_with_rest(key, model_name, prompt)

                                elapsed = round(time.time() - start_time, 2)
                                logging.info(
                                    f"API Key {key_num} succeeded via REST fallback "
                                    f"with model {model_name} in {elapsed}s"
                                )
                                return clean_for_speech(rest_text)
                            except urllib.error.HTTPError as http_error:
                                rest_body = ""
                                try:
                                    rest_body = http_error.read().decode("utf-8")
                                except Exception:
                                    rest_body = "<unreadable body>"
                                last_model_error = (
                                    f"REST HTTP {http_error.code} for {model_name}: {rest_body}"
                                )
                                logging.warning(
                                    f"REST model {model_name} failed for Key {key_num}: "
                                    f"{last_model_error}"
                                )

                                if _is_quota_error(last_model_error):
                                    retry_after = _extract_retry_seconds(last_model_error)
                                    idx = active_models.index(model_name)
                                    if idx < len(active_models) - 1:
                                        logging.info(
                                            f"REST quota on {model_name} for Key {key_num}; "
                                            "trying the next configured model first."
                                        )
                                        continue
                                    if retry_after:
                                        logging.info(
                                            f"REST quota error for Key {key_num}. "
                                            f"Waiting {retry_after} seconds."
                                        )
                                        time.sleep(retry_after)
                                        continue
                                    break

                                if _is_model_not_found_error(last_model_error):
                                    logging.warning(f"Skipping unsupported model in REST fallback: {model_name}")
                                    continue
                            except Exception as rest_error:
                                last_model_error = str(rest_error)
                                logging.error(
                                    f"REST model {model_name} failed for Key {key_num}: "
                                    f"{last_model_error}"
                                )

                if response is None:
                    raise RuntimeError(last_model_error or "All configured models failed")

                elapsed = round(time.time() - start_time, 2)
                logging.info(f"API Key {key_num} succeeded in {elapsed}s")
                return clean_for_speech(response.text)

            except Exception as e:
                elapsed = round(time.time() - start_time, 2)
                error_msg = str(e)
                logging.error(f"Exception in get_ai_response with Key #{key_num}: {error_msg}")
                logging.error(traceback.format_exc())


                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    logging.warning(f"API Key {key_num} timed out after {elapsed}s")
                    last_error = f"Key {key_num} timed out after {KEY_TIMEOUT}s"
                else:
                    logging.warning(f"API Key {key_num} failed: {error_msg}")
                    last_error = error_msg

                # If we have a quota error, break the inner retry loop to handle it
                if _is_quota_error(last_error):
                    break

                if retry_index < KEY_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (retry_index + 1))

        # After all retries for a key, check if we need to handle a quota error
        if last_error and _is_quota_error(last_error):
            retry_after = _extract_retry_seconds(last_error)
            if retry_after:
                logging.info(
                    f"Final attempt for Key {key_num} hit quota. "
                    f"Waiting {retry_after} seconds before switching keys."
                )
                time.sleep(retry_after)
            else:
                # Default wait if time is not specified in error
                logging.warning(f"Key {key_num} exhausted. Waiting {RETRY_DELAY}s before switching.")
                time.sleep(RETRY_DELAY)

        # Switch to next key
        old_key_num = current_key_index + 1
        current_key_index = (current_key_index + 1) % total_keys
        new_key_num = current_key_index + 1
        logging.info(f"Switching from Key {old_key_num} to Key {new_key_num}...")

        # If we've looped through all keys once and are back to the start,
        # and there was an error, it means all keys are failing.
        if current_key_index == 0 and last_error:
            logging.critical(f"All {total_keys} API keys are failing. Last error: {last_error}")
            return friendly_ai_failure_message(last_error)
