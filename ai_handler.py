from google import genai
from google.genai import types
import os
import re
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

# Track which key is currently active
current_key_index = 0

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

def get_ai_response(prompt):
    """Gets a response from Gemini AI, automatically switching API keys on failure."""
    global current_key_index

    if not API_KEYS:
        return "No API keys configured. Please add keys in your .env file."

    # Try each key starting from the current one
    attempts = len(API_KEYS)
    last_error = None
    for _ in range(attempts):
        key = API_KEYS[current_key_index]
        try:
            print(f"Using API Key {current_key_index + 1}...")
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=150
                )
            )
            return clean_for_speech(response.text)
        except Exception as e:
            print(f"API Key {current_key_index + 1} failed: {e}")
            last_error = str(e)
            # Switch to next key
            current_key_index = (current_key_index + 1) % len(API_KEYS)
            print(f"Switching to API Key {current_key_index + 1}...")

    return f"API keys failed. The problem is: {last_error}"
