from flask import Flask, render_template, request, jsonify, send_file
from ai_handler import get_ai_response
import edge_tts
import asyncio
import os
import tempfile
import datetime

app = Flask(__name__)

# Voice settings
VOICES = {
    "girl": "en-IN-NeerjaNeural",
    "boy": "en-IN-PrabhatNeural"
}
current_voice = "girl"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process user message and return AI response."""
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Handle special commands
    if 'the time' in user_message.lower():
        response = f"The time is {datetime.datetime.now().strftime('%I:%M %p')}"
    elif 'the date' in user_message.lower():
        response = f"Today's date is {datetime.datetime.now().strftime('%B %d, %Y')}"
    else:
        response = get_ai_response(user_message)
    
    return jsonify({'response': response})

@app.route('/api/speak', methods=['POST'])
def speak():
    """Convert text to speech and return audio file."""
    data = request.json
    text = data.get('text', '')
    voice_type = data.get('voice', current_voice)
    
    voice = VOICES.get(voice_type, VOICES["girl"])
    temp_file = os.path.join(tempfile.gettempdir(), "web_voice.mp3")
    
    async def generate():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_file)
    
    asyncio.run(generate())
    return send_file(temp_file, mimetype='audio/mpeg')

@app.route('/api/toggle_voice', methods=['POST'])
def toggle_voice():
    """Toggle between boy and girl voice."""
    global current_voice
    current_voice = "boy" if current_voice == "girl" else "girl"
    return jsonify({'voice': current_voice})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
