document.addEventListener('DOMContentLoaded', () => {
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');
    const clearBtn = document.getElementById('clear-btn');
    const langSelect = document.getElementById('language-select');
    const modeIndicator = document.getElementById('mode-indicator');
    const voiceStatus = document.getElementById('voice-status');

    const langConfig = {
        'en': { langTag: 'en-IN', placeholder: 'Initiate health inquiry...', welcome: 'Greeting. Intelligence modules active. I am your Quantum Health Assistant.' },
        'hi': { langTag: 'hi-IN', placeholder: 'स्वास्थ्य पूछताछ शुरू करें...', welcome: 'नमस्ते। इंटेलिजेंस मॉड्यूल सक्रिय हैं। मैं आपका क्वांटम हेल्थ असिस्टेंट हूँ।' },
        'kn': { langTag: 'kn-IN', placeholder: 'ಆರೋಗ್ಯ ವಿಚಾರಣೆಯನ್ನು ಪ್ರಾರಂಭಿಸಿ...', welcome: 'ನಮಸ್ಕಾರ. ಇಂಟೆಲಿಜೆನ್ಸ್ ಮಾಡ್ಯೂಲ್ಗಳು ಸಕ್ರಿಯವಾಗಿವೆ. ನಾನು ನಿಮ್ಮ ಕ್ವಾಂಟಮ್ ಆರೋಗ್ಯ ಸಹಾಯಕ.' },
        'te': { langTag: 'te-IN', placeholder: 'ఆరోగ్య విచారణను ప్రారంభించండి...', welcome: 'నమస్కారం. ఇంటెలిజెన్స్ మాడ్యూల్స్ యాక్టివ్‌గా ఉన్నాయి. నేను మీ క్వాంటం హెల్త్ అసిస్టెంట్.' },
        'auto': { langTag: 'en-IN', placeholder: 'Initiate health inquiry...', welcome: 'Greeting. Intelligence modules active.' }
    };

    // Speech Recognition Setup
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let isActive = false;

    // Flag to prevent recursive listening
    let isBotSpeaking = false;

    // Speech Synthesis
    const speak = (text, lang) => {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = lang || 'en-US';
            utterance.rate = 0.95;

            utterance.onstart = () => {
                isBotSpeaking = true;
                if (isActive && recognition) {
                    try { recognition.stop(); } catch (e) { }
                }
            };

            utterance.onend = () => {
                isBotSpeaking = false;
                if (isActive) {
                    setTimeout(() => {
                        if (isActive) startVoice(true);
                    }, 500);
                }
            };

            window.speechSynthesis.speak(utterance);
        }
    };

    const showTypingIndicator = () => {
        const indicator = document.createElement('div');
        indicator.id = 'typing-indicator';
        indicator.className = 'typing-indicator';
        indicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        chatWindow.appendChild(indicator);
        chatWindow.scrollTop = chatWindow.scrollHeight;
        return indicator;
    };

    const removeTypingIndicator = () => {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    };

    const addMessage = (text, sender, data = null) => {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message');
        msgDiv.classList.add(sender === 'user' ? 'user-message' : 'system-message');

        let content = `<div class="message-content">${text}</div>`;

        if (data && data.preventive_measures && data.preventive_measures.length > 0) {
            content += `<ul class="prevention-list">`;
            data.preventive_measures.forEach(point => {
                content += `<li>${point}</li>`;
            });
            content += `</ul>`;
        }

        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        content += `<span class="timestamp">${time}</span>`;

        msgDiv.innerHTML = content;
        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;

        if (sender === 'bot') {
            speak(text, data ? data.language : 'en');
        }
    };

    const sendMessage = async () => {
        const message = userInput.value.trim();
        if (!message) return;

        const selectedLang = langSelect.value;
        addMessage(message, 'user');
        userInput.value = '';

        const typingTimeout = setTimeout(showTypingIndicator, 300);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    language: selectedLang
                })
            });

            const data = await response.json();
            clearTimeout(typingTimeout);
            removeTypingIndicator();

            if (response.ok) {
                modeIndicator.textContent = data.mode.toUpperCase() + " MODE";
                modeIndicator.style.background = data.mode === 'dataset' ? 'var(--primary-soft)' : '#fff7ed';
                modeIndicator.style.color = data.mode === 'dataset' ? 'var(--primary)' : '#c2410c';

                const localizedFallback = langConfig[selectedLang].welcome.split('.')[0] + "...";
                const botReply = data.display_title || (data.disease_name ? `Information: ${data.disease_name}` : localizedFallback);
                addMessage(botReply, 'bot', data);
            } else {
                addMessage("I apologize, but I encountered an issue. Please try again.", 'bot');
            }
        } catch (error) {
            clearTimeout(typingTimeout);
            removeTypingIndicator();
            addMessage("Neural link unstable. Please check your connection.", 'bot');
        }
    };

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    micBtn.addEventListener('click', () => {
        if (!SpeechRecognition) {
            alert("Speech recognition is not supported in this browser.");
            return;
        }
        if (isActive) {
            stopVoice();
        } else {
            isActive = true;
            startVoice();
        }
    });

    let voiceSessionBuffer = ''; // Persistent buffer for the current mic session

    const startVoice = (isAutoResume = false) => {
        if (recognition) {
            try {
                recognition.onend = null; // Detach old handler to prevent loops
                recognition.stop();
            } catch (e) { }
        }

        recognition = new SpeechRecognition();
        const currentRecognition = recognition; // Closure for handlers
        const selectedLang = langSelect.value;
        recognition.lang = langConfig[selectedLang].langTag;
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onstart = () => {
            micBtn.classList.add('recording');
            micBtn.innerHTML = '<i class="fas fa-stop"></i>';
            voiceStatus.textContent = isAutoResume ? "Pulse Active: Streaming Neural Input..." : "Neural Stream Active: Listening...";
            userInput.classList.add('neural-glow');
        };

        recognition.onresult = (event) => {
            let interimTranscript = '';

            // Re-process results from the beginning of the current session
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    voiceSessionBuffer += transcript + ' ';
                } else {
                    interimTranscript += transcript;
                }
            }

            const currentTotal = (voiceSessionBuffer + interimTranscript).trim();
            if (currentTotal) {
                userInput.value = currentTotal;
                voiceStatus.textContent = "Streaming Intelligence: " + currentTotal;
            }

            // Detect pauses for auto-submission
            if (window.voiceSubmitTimeout) clearTimeout(window.voiceSubmitTimeout);
            window.voiceSubmitTimeout = setTimeout(() => {
                if (isActive && !isBotSpeaking && userInput.value.trim()) {
                    sendMessage();
                    voiceSessionBuffer = '';
                    // Stop recognition to flush results buffer for next utterance
                    if (recognition === currentRecognition) {
                        try { recognition.stop(); } catch (e) { }
                    }
                }
            }, 2000);
        };

        recognition.onerror = (e) => {
            if (e.error !== 'no-speech') {
                console.error("Neural Stream Error:", e.error);
                if (!isBotSpeaking) stopVoice();
            }
        };

        recognition.onend = () => {
            if (currentRecognition !== recognition) return; // Ignore old instances

            if (isActive && !isBotSpeaking) {
                // Hard restart to ensure fresh session and clear browser internal buffers
                startVoice(true);
            } else if (!isActive) {
                micBtn.classList.remove('recording');
                micBtn.innerHTML = '<i class="fas fa-microphone-alt"></i>';
                voiceStatus.textContent = "";
                userInput.classList.remove('neural-glow');
                voiceSessionBuffer = '';
            }
        };

        try {
            recognition.start();
        } catch (e) {
            console.error("Neural Link failed to initialize:", e);
        }
    };

    const stopVoice = () => {
        isActive = false;
        if (window.voiceSubmitTimeout) clearTimeout(window.voiceSubmitTimeout);
        if (recognition) {
            try {
                recognition.onend = null;
                recognition.stop();
            } catch (e) { }
        }
        window.speechSynthesis.cancel();

        // Manual UI reset since onend is nullified to prevent loops
        micBtn.classList.remove('recording');
        micBtn.innerHTML = '<i class="fas fa-microphone-alt"></i>';
        voiceStatus.textContent = "";
        userInput.classList.remove('neural-glow');
        voiceSessionBuffer = '';
    };

    langSelect.addEventListener('change', () => {
        const config = langConfig[langSelect.value];
        userInput.placeholder = config.placeholder;
        addMessage(config.welcome, 'bot');
    });

    clearBtn.addEventListener('click', () => {
        chatWindow.innerHTML = '';
        addMessage("Conversation history has been cleared.", 'bot');
    });
});
