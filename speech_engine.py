import speech_recognition as sr
import edge_tts
import pygame
import asyncio
import os
import tempfile

# Initialize pygame mixer for audio playback
pygame.mixer.init()

# ============================================
# VOICE MOODS - Choose your assistant's voice!
# ============================================
VOICE_MOODS = {
    "friendly":  "en-US-JennyNeural",       # Warm, friendly female
    "professional": "en-US-GuyNeural",       # Clear, professional male
    "cheerful":  "en-US-AriaNeural",         # Energetic, cheerful female
    "calm":      "en-US-DavisNeural",        # Calm, relaxed male
    "news":      "en-US-JennyMultilingualNeural",  # News-reader style
    "indian":    "en-IN-NeerjaNeural",       # Indian English female
    "indian_male": "en-IN-PrabhatNeural",    # Indian English male
}

# >>>  SET YOUR PREFERRED VOICE MOOD HERE  <<<
CURRENT_MOOD = "indian"

def toggle_voice():
    """Toggles between girl and boy voice."""
    global CURRENT_MOOD
    if CURRENT_MOOD == "indian":
        CURRENT_MOOD = "indian_male"
    else:
        CURRENT_MOOD = "indian"
    return CURRENT_MOOD

def get_voice():
    """Returns the voice name for the current mood."""
    return VOICE_MOODS.get(CURRENT_MOOD, VOICE_MOODS["friendly"])

async def _speak_async(text):
    """Async function to generate speech using Edge TTS."""
    voice = get_voice()
    temp_file = os.path.join(tempfile.gettempdir(), "assistant_voice.mp3")
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(temp_file)
    
    # Play the audio
    pygame.mixer.music.load(temp_file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    pygame.mixer.music.unload()

def speak(audio):
    """Converts text to natural-sounding speech using Edge TTS."""
    print(f"Assistant [{CURRENT_MOOD}]: {audio}")
    try:
        asyncio.run(_speak_async(audio))
    except Exception as e:
        print(f"Speech error: {e}")

def listen():
    """Listens for user input via microphone and returns recognized text."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)

    try:
        print("Recognizing...")
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}\n")
    except Exception as e:
        print("Say that again please...")
        return "None"
    return query
