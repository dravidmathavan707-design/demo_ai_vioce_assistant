from flask import Flask, render_template, request, jsonify, send_file
from ai_handler import get_ai_response
import edge_tts
import asyncio
import os
import tempfile
import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import logging
import traceback

load_dotenv()

app = Flask(__name__)

# Initialize MongoDB
mongo_uri = os.getenv("MONGO_URI")
if mongo_uri:
    try:
        client = MongoClient(mongo_uri)
        db = client.voice_assistant_db
        messages_collection = db.messages
        print("Connected to MongoDB successfully!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        messages_collection = None
else:
    print("MONGO_URI not found in .env file.")
    messages_collection = None

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
    try:
        data = request.get_json(silent=True) or {}
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

        # Save to MongoDB
        if messages_collection is not None:
            try:
                message_doc = {
                    "user_message": user_message,
                    "ai_response": response,
                    "timestamp": datetime.datetime.now(datetime.UTC)
                }
                messages_collection.insert_one(message_doc)
            except Exception as e:
                print(f"Failed to save message to MongoDB: {e}")

        return jsonify({'response': response})
    except Exception as e:
        logging.error(f"An unexpected error occurred in /api/chat: {e}")
        logging.error(traceback.format_exc())
        return jsonify({'error': 'An internal server error occurred.'}), 500

def get_or_create_eventloop():
    """Gets the current asyncio event loop or creates a new one."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError as ex:
        if "There is no current event loop in thread" in str(ex):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return asyncio.get_event_loop()
        raise ex

@app.route('/api/speak', methods=['POST'])
def speak():
    """Convert text to speech and return audio file."""
    data = request.get_json(silent=True) or {}
    text = data.get('text', '')
    voice_type = data.get('voice', current_voice)
    
    voice = VOICES.get(voice_type, VOICES["girl"])
    temp_file = os.path.join(tempfile.gettempdir(), "web_voice.mp3")
    
    try:
        async def generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(temp_file)
        
        # Use a compatible way to run the async function
        loop = get_or_create_eventloop()
        loop.run_until_complete(generate())
        
        return send_file(temp_file, mimetype='audio/mpeg')
    except Exception as e:
        logging.error(f"Failed to generate speech: {e}")
        logging.error(traceback.format_exc())
        return jsonify({'error': 'Failed to generate speech audio.'}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Fetch chat history from MongoDB."""
    if messages_collection is None:
        return jsonify({'error': 'Database not connected', 'history': []}), 500
        
    try:
        # Fetch last 50 messages, sorted by timestamp descending
        cursor = messages_collection.find({}, {'_id': 0}).sort('timestamp', -1).limit(50)
        history = list(cursor)
        # Reverse to get chronological order
        history.reverse()
        
        # Convert datetime to string for JSON serialization
        for msg in history:
            if 'timestamp' in msg and isinstance(msg['timestamp'], datetime.datetime):
                msg['timestamp'] = msg['timestamp'].isoformat() + "Z"
                
        return jsonify({'history': history})
    except Exception as e:
        logging.error(f"Failed to fetch history: {e}")
        logging.error(traceback.format_exc())
        return jsonify({'error': 'Failed to fetch history', 'history': []}), 500

@app.route('/api/toggle_voice', methods=['POST'])
def toggle_voice():
    """Toggle between boy and girl voice."""
    global current_voice
    current_voice = "boy" if current_voice == "girl" else "girl"
    return jsonify({'voice': current_voice})

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log")
        ]
    )
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
