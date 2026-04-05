// ============================================
// AI Voice Assistant - Frontend Logic
// ============================================

let isListening = false;
let currentVoice = 'girl';
let recognition = null;

// Initialize Speech Recognition (Web Speech API)
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-IN';

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        stopListening();
        addMessage(transcript, 'user');
        processMessage(transcript);
    };

    recognition.onerror = (event) => {
        console.error('Speech error:', event.error);
        stopListening();
        updateMicStatus("Couldn't hear you. Try again.");
        setTimeout(() => updateMicStatus('Tap to speak'), 2000);
    };

    recognition.onend = () => {
        if (isListening) stopListening();
    };
}

// Toggle Microphone
function toggleMic() {
    if (isListening) {
        recognition.stop();
        stopListening();
    } else {
        startListening();
    }
}

function startListening() {
    if (!recognition) {
        alert('Speech recognition is not supported in this browser. Please use Chrome.');
        return;
    }
    isListening = true;
    const micBtn = document.getElementById('micBtn');
    micBtn.classList.add('listening');
    document.getElementById('micIcon').textContent = 'mic_off';
    updateMicStatus('Listening...');
    recognition.start();
}

function stopListening() {
    isListening = false;
    const micBtn = document.getElementById('micBtn');
    micBtn.classList.remove('listening');
    document.getElementById('micIcon').textContent = 'mic';
    updateMicStatus('Tap to speak');
}

function updateMicStatus(text) {
    document.getElementById('micStatus').textContent = text;
}

// Send text message
function sendText() {
    const input = document.getElementById('textInput');
    const message = input.value.trim();
    if (!message) return;
    
    input.value = '';
    addMessage(message, 'user');
    processMessage(message);
}

// Quick action buttons
function sendQuick(message) {
    addMessage(message, 'user');
    processMessage(message);
}

// Process message with backend
async function processMessage(message) {
    // Hide welcome msg
    const welcomeMsg = document.getElementById('welcomeMsg');
    if (welcomeMsg) welcomeMsg.style.display = 'none';

    // Check voice toggle command
    if (message.toLowerCase().includes('change') && message.toLowerCase().includes('voice')) {
        await toggleVoiceAPI();
        return;
    }

    // Show typing indicator
    showTyping();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        const data = await response.json();
        removeTyping();

        if (data.response) {
            addMessage(data.response, 'ai');
            await speakResponse(data.response);
        }
    } catch (error) {
        removeTyping();
        addMessage('Sorry, something went wrong. Please try again.', 'ai');
    }
}

// Add message bubble to chat
function addMessage(text, sender, manualTime = null) {
    const chatArea = document.getElementById('chatArea');
    const time = manualTime 
        ? new Date(manualTime).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) 
        : new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', sender);
    
    const icon = sender === 'user' ? 'person' : 'smart_toy';
    
    msgDiv.innerHTML = `
        <div class="message-avatar">
            <span class="material-icons-round">${icon}</span>
        </div>
        <div>
            <div class="message-content">${text}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    chatArea.appendChild(msgDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
}

// Typing indicator
function showTyping() {
    const chatArea = document.getElementById('chatArea');
    const typingDiv = document.createElement('div');
    typingDiv.classList.add('message', 'ai');
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <span class="material-icons-round">smart_toy</span>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
        </div>
    `;
    chatArea.appendChild(typingDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
}

function removeTyping() {
    const typing = document.getElementById('typingIndicator');
    if (typing) typing.remove();
}

// Speak response using backend Edge TTS
async function speakResponse(text) {
    try {
        updateMicStatus('🔊 Speaking...');
        
        const response = await fetch('/api/speak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, voice: currentVoice })
        });

        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        audio.onended = () => {
            updateMicStatus('Tap to speak');
            URL.revokeObjectURL(audioUrl);
        };
        
        await audio.play();
    } catch (error) {
        console.error('Speech error:', error);
        updateMicStatus('Tap to speak');
    }
}

// Voice toggle
document.getElementById('voiceSwitch').addEventListener('change', async (e) => {
    currentVoice = e.target.checked ? 'boy' : 'girl';
    const label = currentVoice === 'boy' ? '👦 Boy' : '👩 Girl';
    
    // Visual feedback
    document.getElementById('voiceLabel').style.opacity = currentVoice === 'girl' ? '1' : '0.4';
    document.getElementById('voiceLabelBoy').style.opacity = currentVoice === 'boy' ? '1' : '0.4';
    
    // Speak confirmation
    const confirmText = `Voice changed to ${currentVoice === 'boy' ? "boy's" : "girl's"} voice.`;
    addMessage(confirmText, 'ai');
    await speakResponse(confirmText);
});

async function toggleVoiceAPI() {
    const voiceSwitch = document.getElementById('voiceSwitch');
    voiceSwitch.checked = !voiceSwitch.checked;
    voiceSwitch.dispatchEvent(new Event('change'));
}

// ============================================
// Sidebar Functions
// ============================================

function goHome() {
    // Clear chat and show welcome message
    const chatArea = document.getElementById('chatArea');
    chatArea.innerHTML = '';
    
    const welcomeHtml = `
        <div class="welcome-message" id="welcomeMsg">
            <div class="welcome-icon">
                <span class="material-icons-round">waving_hand</span>
            </div>
            <h2>Hello! I'm your AI Assistant</h2>
            <p>Press the mic button and start talking, or type your message below.</p>
            <div class="quick-actions">
                <button class="quick-btn" onclick="sendQuick('What is the time?')">
                    <span class="material-icons-round">schedule</span> Time
                </button>
                <button class="quick-btn" onclick="sendQuick('What is the date?')">
                    <span class="material-icons-round">calendar_today</span> Date
                </button>
                <button class="quick-btn" onclick="sendQuick('Tell me a joke')">
                    <span class="material-icons-round">sentiment_very_satisfied</span> Joke
                </button>
                <button class="quick-btn" onclick="sendQuick('Tell me a fun fact')">
                    <span class="material-icons-round">lightbulb</span> Fun Fact
                </button>
            </div>
        </div>
    `;
    chatArea.innerHTML = welcomeHtml;

    // Update active sidebar button
    document.querySelectorAll('.sidebar-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById('homeBtn').classList.add('active');
}

function newChat() {
    // Clear chat and show welcome
    goHome();
    addMessage("Started a new conversation!", 'ai');
    const welcomeMsg = document.getElementById('welcomeMsg');
    if (welcomeMsg) welcomeMsg.style.display = 'none';
}

async function toggleHistory() {
    const welcomeMsg = document.getElementById('welcomeMsg');
    if (welcomeMsg) welcomeMsg.style.display = 'none';

    // Update active sidebar button
    document.querySelectorAll('.sidebar-btn').forEach(btn => btn.classList.remove('active'));
    const historyBtn = document.getElementById('historyBtn');
    if (historyBtn) historyBtn.classList.add('active');

    const chatArea = document.getElementById('chatArea');
    chatArea.innerHTML = '';
    
    showTyping(); // Use typing indicator as loading state

    try {
        const response = await fetch('/api/history');
        const data = await response.json();
        
        chatArea.innerHTML = ''; // Clear loading state
        
        if (data.history && data.history.length > 0) {
            const header = document.createElement('div');
            header.style.textAlign = 'center';
            header.style.color = 'rgba(255, 255, 255, 0.7)';
            header.style.padding = '15px 0 25px 0';
            header.style.fontSize = '0.95rem';
            header.innerHTML = '<span class="material-icons-round" style="vertical-align: middle; font-size: 1.2rem; margin-right: 5px;">history</span> Past Conversations';
            chatArea.appendChild(header);

            data.history.forEach(msg => {
                if (msg.user_message) {
                    addMessage(msg.user_message, 'user', msg.timestamp);
                }
                if (msg.ai_response) {
                    addMessage(msg.ai_response, 'ai', msg.timestamp);
                }
            });
        } else {
            addMessage("No chat history found. Start a new conversation!", 'ai');
        }
    } catch (error) {
        chatArea.innerHTML = '';
        addMessage("Failed to load chat history. Please try again.", 'ai');
        console.error('History error:', error);
    }
}

function toggleSettings() {
    // Show current settings info
    const voiceInfo = currentVoice === 'boy' ? "Boy (PrabhatNeural)" : "Girl (NeerjaNeural)";
    addMessage(`⚙️ Current Settings:\n• Voice: ${voiceInfo}\n• Language: English (India)\n• AI Model: Gemini 2.5 Flash`, 'ai');
    const welcomeMsg = document.getElementById('welcomeMsg');
    if (welcomeMsg) welcomeMsg.style.display = 'none';
}

