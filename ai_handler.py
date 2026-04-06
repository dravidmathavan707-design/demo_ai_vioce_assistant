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

# Load API Keys
load_dotenv()
API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]
# Filter out empty/placeholder keys
API_KEYS = [k for k in API_KEYS if k and k != "YOUR_SECOND_API_KEY_HERE" and k != "YOUR_THIRD_API_KEY_HERE"]

print(f"Loaded {len(API_KEYS)} API key(s)")

# Track which key is currently active
current_key_index = 0

# Request tuning for cloud deployments like Render
KEY_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
KEY_RETRIES = int(os.getenv("GEMINI_RETRIES_PER_KEY", "3"))
RETRY_DELAY = float(os.getenv("GEMINI_RETRY_DELAY_SECONDS", "1.5"))
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MODEL_CANDIDATES_RAW = os.getenv("GEMINI_MODEL_CANDIDATES", "gemini-2.0-flash,gemini-1.5-flash")
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


def _generate_with_rest(api_key, model_name, prompt):
    """Fallback path using Gemini REST API when SDK calls fail or time out."""
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model_name, safe='')}:generateContent?key={api_key}"
    )

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

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=KEY_TIMEOUT) as response:
        body = json.loads(response.read().decode("utf-8"))

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"No candidates in Gemini REST response: {body}")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text_chunks = [p.get("text", "") for p in parts if p.get("text")]
    text = " ".join(text_chunks).strip()
    if not text:
        raise RuntimeError(f"Empty text in Gemini REST response: {body}")
    return text

def get_ai_response(prompt):
    """Gets a response from Gemini AI with per-key retries and key rotation."""
    global current_key_index

    if not API_KEYS:
        return "No API keys configured. Please add keys in your .env file."

    total_keys = len(API_KEYS)
    last_error = None

    for attempt in range(total_keys):
        key_num = current_key_index + 1
        key = API_KEYS[current_key_index]

        for retry_index in range(KEY_RETRIES):
            try:
                print(
                    f"Attempt {attempt + 1}/{total_keys}, retry {retry_index + 1}/{KEY_RETRIES} "
                    f"- Key {key_num} (timeout: {KEY_TIMEOUT}s, models: {','.join(MODEL_CANDIDATES)})"
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
                        print(f"SDK model {model_name} failed for Key {key_num}: {last_model_error}")

                        if _is_quota_error(last_model_error):
                            retry_after = _extract_retry_seconds(last_model_error)
                            if retry_after:
                                return (
                                    "Gemini API quota is exhausted right now. "
                                    f"Please try again after about {retry_after} seconds."
                                )
                            return "Gemini API quota is exhausted right now. Please try again later."

                        if _is_model_not_found_error(last_model_error):
                            print(f"Skipping unsupported model: {model_name}")
                            continue

                        if USE_REST_FALLBACK:
                            try:
                                rest_text = _generate_with_rest(key, model_name, prompt)

                                elapsed = round(time.time() - start_time, 2)
                                print(
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
                                print(
                                    f"REST model {model_name} failed for Key {key_num}: "
                                    f"{last_model_error}"
                                )

                                if _is_quota_error(last_model_error):
                                    retry_after = _extract_retry_seconds(last_model_error)
                                    if retry_after:
                                        return (
                                            "Gemini API quota is exhausted right now. "
                                            f"Please try again after about {retry_after} seconds."
                                        )
                                    return "Gemini API quota is exhausted right now. Please try again later."

                                if _is_model_not_found_error(last_model_error):
                                    print(f"Skipping unsupported model in REST fallback: {model_name}")
                                    continue
                            except Exception as rest_error:
                                last_model_error = str(rest_error)
                                print(
                                    f"REST model {model_name} failed for Key {key_num}: "
                                    f"{last_model_error}"
                                )

                if response is None:
                    raise RuntimeError(last_model_error or "All configured models failed")

                elapsed = round(time.time() - start_time, 2)
                print(f"API Key {key_num} succeeded in {elapsed}s")
                return clean_for_speech(response.text)

            except Exception as e:
                elapsed = round(time.time() - start_time, 2)
                error_msg = str(e).lower()

                if "timeout" in error_msg or "timed out" in error_msg:
                    print(f"API Key {key_num} timed out after {elapsed}s")
                    last_error = f"Key {key_num} timed out after {KEY_TIMEOUT}s"
                else:
                    print(f"API Key {key_num} failed: {str(e)}")
                    last_error = str(e)

                if retry_index < KEY_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (retry_index + 1))

        # Switch to next key
        old_key = current_key_index + 1
        current_key_index = (current_key_index + 1) % total_keys
        new_key = current_key_index + 1
        print(f"Switching from Key {old_key} to Key {new_key}...")

    if last_error and "timed out" in last_error.lower():
        return (
            "The AI service is taking too long to respond right now. "
            "Please try again in a few seconds."
        )

    return f"All {total_keys} API keys failed. Last error: {last_error}"
