import datetime
import wikipedia
import webbrowser
import os
from speech_engine import speak, listen, toggle_voice
from ai_handler import get_ai_response

def wish_me():
    """Wishes the user based on the current time."""
    hour = int(datetime.datetime.now().hour)
    if 0 <= hour < 12:
        speak("Good Morning!")
    elif 12 <= hour < 18:
        speak("Good Afternoon!")
    else:
        speak("Good Evening!")
    speak("I am your AI Voice Assistant. How can I help you today?")

def run_assistant():
    """Main loop for the voice assistant."""
    wish_me()
    while True:
        query = listen().lower()

        if query == "none":
            continue

        if 'wikipedia' in query:
            speak('Searching Wikipedia...')
            query = query.replace("wikipedia", "")
            results = wikipedia.summary(query, sentences=2)
            speak("According to Wikipedia")
            speak(results)

        elif 'open google' in query:
            webbrowser.open("google.com")
            speak("Opening Google.")

        elif 'open youtube' in query:
            webbrowser.open("youtube.com")
            speak("Opening Youtube.")

        elif 'the time' in query:
            strTime = datetime.datetime.now().strftime("%H:%M:%S")
            speak(f"The time is {strTime}")

        elif 'change' in query and 'voice' in query:
            new_mood = toggle_voice()
            voice_type = "girl" if new_mood == "indian" else "boy"
            speak(f"Voice changed! I am now using {voice_type}'s voice.")

        elif 'exit' in query or 'stop' in query or 'quit' in query:
            speak("Goodbye! Have a great day.")
            break

        else:
            # Send to Gemini AI for any other questions
            print("Processing with AI...")
            response = get_ai_response(query)
            speak(response)

if __name__ == "__main__":
    run_assistant()
