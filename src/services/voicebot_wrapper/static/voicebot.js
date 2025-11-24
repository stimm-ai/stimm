/**
 * Voicebot UI Controller
 * Manages UI interactions and connects WebRTCClient.
 */

document.addEventListener('DOMContentLoaded', () => {
    const voiceButton = document.getElementById('voiceButton');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const audioPlayer = document.getElementById('audioPlayer');
    const agentSelect = document.getElementById('agentSelect');
    const transcriptionOutput = document.getElementById('transcriptionOutput');
    const assistantResponse = document.getElementById('assistantResponse');

    let webrtcClient = null;
    let isConnected = false;

    // Initialize WebRTC Client
    webrtcClient = new WebRTCClient();

    // Setup Event Handlers
    webrtcClient.onConnectionStateChange = (state) => {
        updateStatus(state);
    };

    webrtcClient.onAudioTrack = (stream) => {
        console.log('Attaching remote stream to audio player');
        audioPlayer.srcObject = stream;
        audioPlayer.play().catch(e => console.error('Audio play failed:', e));
    };

    // Button Click Handler
    voiceButton.addEventListener('click', async () => {
        if (!isConnected) {
            // Connect
            try {
                setButtonState('connecting');
                const agentId = agentSelect.value;
                await webrtcClient.start(agentId);
                isConnected = true;
                setButtonState('connected');
            } catch (error) {
                console.error('Connection failed:', error);
                setButtonState('error');
                statusText.textContent = 'Connection Failed';
            }
        } else {
            // Disconnect
            webrtcClient.stop();
            isConnected = false;
            setButtonState('disconnected');
        }
    });

    // Helper Functions
    function updateStatus(state) {
        statusText.textContent = state.charAt(0).toUpperCase() + state.slice(1);

        statusDot.className = 'status-dot'; // Reset
        if (state === 'connected') {
            statusDot.classList.add('connected');
        } else if (state === 'failed' || state === 'closed') {
            statusDot.classList.add('error');
            if (state === 'closed') {
                isConnected = false;
                setButtonState('disconnected');
            }
        }
    }

    function setButtonState(state) {
        if (state === 'connecting') {
            voiceButton.disabled = true;
            voiceButton.textContent = '⏳ Connecting...';
            voiceButton.className = 'voice-btn gray';
        } else if (state === 'connected') {
            voiceButton.disabled = false;
            voiceButton.textContent = '🛑 Stop Conversation';
            voiceButton.className = 'voice-btn red';
        } else if (state === 'disconnected' || state === 'error') {
            voiceButton.disabled = false;
            voiceButton.textContent = '🎤 Start Conversation';
            voiceButton.className = 'voice-btn green';
        }
    }

    // Load Agents (Mock for now or fetch from API)
    async function loadAgents() {
        try {
            const response = await fetch('/api/agents');
            if (response.ok) {
                const agents = await response.json();
                agentSelect.innerHTML = '';
                agents.forEach(agent => {
                    const option = document.createElement('option');
                    option.value = agent.id;
                    option.textContent = agent.name;
                    agentSelect.appendChild(option);
                });
            } else {
                agentSelect.innerHTML = '<option value="">Default Agent</option>';
            }
        } catch (e) {
            console.warn('Failed to load agents:', e);
            agentSelect.innerHTML = '<option value="">Default Agent</option>';
        }
    }

    loadAgents();

    // Initial State
    setButtonState('disconnected');
});
