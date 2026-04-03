# 🤖 AI Voice Assistant

An AI-powered voice assistant built with Python, Gemini AI, and Microsoft Edge TTS. Features a stunning web frontend with a dark glassmorphism theme, fully responsive across all devices.

![AI Voice Assistant](https://img.shields.io/badge/AI-Voice%20Assistant-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-green?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-Web%20App-red?style=for-the-badge&logo=flask)
![Gemini](https://img.shields.io/badge/Gemini-AI-purple?style=for-the-badge)

## ✨ Features

- 🎤 **Voice Conversation** — Speak and get spoken responses
- 🤖 **Gemini AI** — Smart answers powered by Google's Gemini 2.5 Flash
- 🔄 **Voice Toggle** — Switch between Boy and Girl voice anytime
- 🌐 **Web Frontend** — Beautiful dark-themed UI with glassmorphism
- 📱 **Fully Responsive** — Works on Desktop, Tablet, and Phone
- 🔑 **API Key Failover** — Supports up to 3 Gemini API keys
- 📖 **Wikipedia Search** — Quick facts from Wikipedia
- ⏰ **Time & Date** — Ask for the current time or date

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/dravidmathavan707-design/ai_based_vioce.git
cd ai_based_vioce
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup API Key
Create a `.env` file in the root directory:
```
GEMINI_API_KEY_1=your_gemini_api_key_here
GEMINI_API_KEY_2=optional_backup_key
GEMINI_API_KEY_3=optional_backup_key
```
Get a free API key from [Google AI Studio](https://aistudio.google.com/)

### 4. Run the Web App
```bash
python app.py
```
Open **http://127.0.0.1:5000** in Chrome.

### 5. Run Terminal Mode (Optional)
```bash
python main.py
```

## 📁 Project Structure

```
ai_based_vioce/
├── app.py               # Flask web server
├── main.py              # Terminal-based voice assistant
├── speech_engine.py     # Edge TTS voice engine
├── ai_handler.py        # Gemini AI with key failover
├── requirements.txt     # Python dependencies
├── .env                 # API keys (not in repo)
├── .gitignore
├── templates/
│   └── index.html       # Web UI template
└── static/
    ├── style.css        # Dark theme CSS
    └── script.js        # Frontend logic
```

## 🎤 Voice Commands

| Command | Action |
|---------|--------|
| "Change the voice" | Toggle between Boy/Girl voice |
| "What is the time?" | Get current time |
| "What is the date?" | Get current date |
| "Open Google" | Open Google in browser |
| "Open YouTube" | Open YouTube in browser |
| "Wikipedia [topic]" | Search Wikipedia |
| "Exit" / "Stop" | Close the assistant |

## 🛠️ Tech Stack

- **Python 3.10+**
- **Flask** — Web framework
- **Google Gemini AI** — Intelligent responses
- **Edge TTS** — Natural-sounding text-to-speech
- **SpeechRecognition** — Voice input
- **Web Speech API** — Browser-based voice recognition

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
