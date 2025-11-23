/**
 * Voicebot frontend JavaScript for real-time voice conversation.
 *
 * Features:
 * - Web Audio API microphone capture
 * - Raw audio streaming to backend for WebRTC VAD processing
 * - Real-time WebSocket communication
 * - Gray/green button indicator for backend VAD results
 * - Audio playback for TTS responses using shared AudioStreamer
 */

class VoicebotInterface {
    constructor() {
        // DOM elements with debug logging
        this.voiceButton = document.getElementById('voiceButton');
        this.statusDot = document.getElementById('statusDot');
        this.statusText = document.getElementById('statusText');
        this.transcriptionOutput = document.getElementById('transcriptionOutput');
        this.assistantResponse = document.getElementById('assistantResponse');
        this.energyBar = document.getElementById('energyBar');
        this.debugInfo = document.getElementById('debugInfo');
        this.audioPlayer = document.getElementById('audioPlayer');
        this.errorContainer = document.getElementById('errorContainer');
        this.agentSelect = document.getElementById('agentSelect');

        // Status tracking elements
        this.statusSection = document.getElementById('statusSection');
        this.llmStatus = document.getElementById('llmStatus');
        this.ttsStatus = document.getElementById('ttsStatus');
        this.tokenCount = document.getElementById('tokenCount');
        this.audioChunkCount = document.getElementById('audioChunkCount');
        this.streamTime = document.getElementById('streamTime');
        this.latencySection = document.getElementById('latencySection');
        this.firstChunkLatency = document.getElementById('firstChunkLatency');
        this.playbackStartLatency = document.getElementById('playbackStartLatency');

        // Agent management
        this.currentAgentId = null;
        this.agentSelector = null;

        // Debug logging removed for production

        // Audio context and processing (pour VAD uniquement)
        this.audioContext = null;
        this.audioStream = null;
        this.audioProcessor = null;
        this.scriptProcessor = null;

        // WebSocket connection
        this.websocket = null;
        this.conversationId = null;

        // State management
        this.isListening = false;
        this.isConnected = false;
        this.currentEnergy = 0;
        this.silenceTimeout = null;
        this.lastVoiceTime = 0;
        this.isInSpeechSegment = false;
        this.SPEECH_PAUSE_THRESHOLD = 500; // 500ms pause threshold
        this.lastVadResult = null; // Store last VAD result from backend

        // Progress tracking state
        this.tokenCounter = 0;
        this.audioChunkCounter = 0;
        this.startTime = null;
        this.firstChunkReceived = false;
        this.playbackStarted = false;
        this.firstChunkTime = null;
        this.playbackStartTime = null;

        // Audio configuration for backend WebRTC VAD
        this.audioConfig = {
            sampleRate: 16000,  // WebRTC VAD requires 16kHz
            channelCount: 1,    // Mono audio
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false
        };

        // Audio processing state (pour VAD uniquement)
        this.audioBuffer = [];
        this.chunkSize = 480; // 30ms at 16kHz (WebRTC VAD frame size)

        // Initialiser l'AudioStreamer partagé pour la lecture TTS
        this.audioStreamer = new AudioStreamer({
            sampleRate: 44100, // TTS utilise 44.1kHz
            onPlaybackStart: () => {
                this.playbackStarted = true;
                this.playbackStartTime = Date.now();
                const latency = this.playbackStartTime - this.startTime;
                this.playbackStartLatency.textContent = `${latency}ms`;
                this.playbackStartLatency.className = 'latency-value measured';
                console.log(`🎵 Audio playback started after ${latency}ms`);
            },
            onPlaybackEnd: () => {
                // Reset TTS status when audio playback ends
                this.ttsStatus.classList.remove('active');
                // Debug logging removed for production
            },
            onError: (error) => {
                // Debug logging removed for production
            }
        });

        this.initialize();
    }

    async initialize() {
        try {
            await this.initializeAudioContext();
            this.initializeEventListeners();
            await this.initializeAgentSelector(); // Initialize shared agent selector
            this.updateStatus('ready', 'Ready to connect');
            this.showError(''); // Clear any errors
        } catch (error) {
            console.error('Failed to initialize voicebot:', error);
            this.showError(`Initialization failed: ${error.message}`);
            this.updateStatus('error', 'Initialization failed');
        }
    }

    initializeEventListeners() {
        this.voiceButton.addEventListener('click', () => this.toggleListening());

        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && this.isListening) {
                this.stopListening();
            }
        });
    }

    async initializeAudioContext() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.audioConfig.sampleRate
            });

            // Debug logging removed for production

        } catch (error) {
            console.error('Audio context initialization failed:', error);
            throw new Error(`Audio setup failed: ${error.message}`);
        }
    }

    async toggleListening() {
        if (this.isListening) {
            await this.stopListening();
        } else {
            await this.startListening();
        }
    }

    async startListening() {
        if (this.isListening) return;

        try {
            this.updateStatus('connecting', 'Starting microphone...');

            // Ensure audio context is running
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // Get microphone access
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: this.audioConfig
            });

            // Connect to WebSocket
            await this.connectWebSocket();

            // Setup audio processing pipeline
            await this.setupAudioProcessing();

            this.isListening = true;
            this.updateVoiceButton(true);
            this.updateStatus('listening', 'Listening for voice...');
            this.showError(''); // Clear errors

            // Debug logging removed for production

        } catch (error) {
            console.error('Failed to start listening:', error);
            this.showError(`Microphone access failed: ${error.message}`);
            this.updateStatus('error', 'Microphone access failed');
            this.isListening = false;
            this.updateVoiceButton(false);
        }
    }

    async stopListening() {
        if (!this.isListening) return;

        try {
            this.updateStatus('disconnecting', 'Stopping...');

            // Stop audio processing
            if (this.audioStream) {
                this.audioStream.getTracks().forEach(track => track.stop());
                this.audioStream = null;
            }

            // Disconnect audio nodes
            if (this.scriptProcessor) {
                this.scriptProcessor.disconnect();
                this.scriptProcessor = null;
            }

            // Clear audio buffer
            this.audioBuffer = [];

            // Clear silence timeout
            if (this.silenceTimeout) {
                clearTimeout(this.silenceTimeout);
                this.silenceTimeout = null;
            }

            // Close WebSocket if no longer needed
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'stop_listening',
                    conversation_id: this.conversationId
                }));
            }

            // Clean up audio streaming state
            this.cleanupAudioStreaming();

            this.isListening = false;
            this.updateVoiceButton(false);
            this.updateStatus('ready', 'Ready to listen');

            // Debug logging removed for production

        } catch (error) {
            console.error('Error stopping listening:', error);
            this.showError(`Error stopping: ${error.message}`);
        }
    }

    cleanupAudioStreaming() {
        // Nettoyer l'AudioStreamer partagé
        this.audioStreamer.cleanup();

        // Close audio context if exists (pour VAD uniquement)
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
            // Debug logging removed for production
        }

        // Hide audio player (not used for real-time streaming)
        if (this.audioPlayer) {
            this.audioPlayer.style.display = 'none';
        }
    }

    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/voicebot/stream`;

            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                // Debug logging removed for production
                this.isConnected = true;
                this.updateStatus('connected', 'Connected');

                // Start conversation with current agent ID
                this.websocket.send(JSON.stringify({
                    type: 'start_conversation',
                    conversation_id: this.conversationId,
                    agent_id: this.currentAgentId || null
                }));

                resolve();
            };

            this.websocket.onmessage = (event) => {
                // Debug logging removed for production

                // Handle both JSON and binary messages
                if (typeof event.data === 'string') {
                    // JSON message
                    // Debug logging removed for production
                    this.handleWebSocketMessage(JSON.parse(event.data));
                } else {
                    // Binary audio data
                    // Debug logging removed for production
                    this.handleBinaryAudioData(event.data);
                }
            };

            this.websocket.onerror = (error) => {
                // Debug logging removed for production
                this.isConnected = false;
                this.updateStatus('error', 'Connection failed');
                reject(new Error('WebSocket connection failed'));
            };

            this.websocket.onclose = (event) => {
                // Debug logging removed for production
                this.isConnected = false;
                this.updateStatus('disconnected', 'Disconnected');

                if (this.isListening) {
                    this.stopListening();
                }
            };
        });
    }

    async setupAudioProcessing() {
        try {
            // Create audio source from microphone
            const source = this.audioContext.createMediaStreamSource(this.audioStream);

            // Create ScriptProcessorNode for raw audio capture
            // Buffer size of 4096 provides good balance between latency and performance
            this.scriptProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);

            // Handle audio processing
            this.scriptProcessor.onaudioprocess = (event) => {
                this.handleAudioProcess(event);
            };

            // Connect audio nodes
            source.connect(this.scriptProcessor);

            // Create silent destination to avoid audio feedback
            const silentGain = this.audioContext.createGain();
            silentGain.gain.value = 0;
            this.scriptProcessor.connect(silentGain);
            silentGain.connect(this.audioContext.destination);

            // Debug logging removed for production

        } catch (error) {
            console.error('Audio processing setup failed:', error);
            throw new Error(`Audio processing failed: ${error.message}`);
        }
    }

    handleAudioProcess(event) {
        if (!this.isListening) return;

        // Get audio data from input buffer
        const inputBuffer = event.inputBuffer;
        const inputData = inputBuffer.getChannelData(0); // Mono channel

        // Convert Float32 to Int16 PCM for WebRTC VAD
        const pcmData = this.convertFloat32ToInt16(inputData);

        // Accumulate audio data
        for (let i = 0; i < pcmData.length; i++) {
            this.audioBuffer.push(pcmData[i]);
        }

        // Process accumulated audio in WebRTC VAD frame sizes (480 samples = 30ms at 16kHz)
        while (this.audioBuffer.length >= this.chunkSize) {
            const frame = this.audioBuffer.slice(0, this.chunkSize);
            this.audioBuffer = this.audioBuffer.slice(this.chunkSize);

            // Convert to ArrayBuffer for transmission
            const int16Array = new Int16Array(frame);
            const arrayBuffer = int16Array.buffer;

            // Send raw audio chunk to backend for VAD processing
            this.sendRawAudioChunk(arrayBuffer);
        }
    }

    convertFloat32ToInt16(float32Array) {
        const int16Array = new Int16Array(float32Array.length);

        for (let i = 0; i < float32Array.length; i++) {
            // Clip to [-1, 1] and scale to 16-bit integer range
            const sample = Math.max(-1, Math.min(1, float32Array[i]));
            int16Array[i] = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        }

        return int16Array;
    }

    sendRawAudioChunk(audioData) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            // Send raw binary audio chunk directly
            // Backend handles binary frames as audio chunks for the current conversation
            this.websocket.send(audioData);
        }
    }

    handleBackendVADResult(vadResult) {
        // Store the last VAD result for UI updates
        this.lastVadResult = vadResult;

        // Update visual feedback based on backend VAD results
        const isVoice = vadResult.is_voice;
        const isVoiceActive = vadResult.is_voice_active;
        const voiceProbability = vadResult.voice_probability;

        // Update energy visualization (use voice probability as energy indicator)
        this.currentEnergy = voiceProbability;
        this.updateEnergyBar(voiceProbability);

        // Handle speech segment detection with smoothing
        const currentTime = Date.now();

        if (isVoiceActive) {
            // Voice activity detected - update last voice time and mark as in speech segment
            this.lastVoiceTime = currentTime;
            this.isInSpeechSegment = true;

            // Clear any existing silence timeout
            if (this.silenceTimeout) {
                clearTimeout(this.silenceTimeout);
                this.silenceTimeout = null;
            }

            // Stop audio playback immediately when voice is detected
            this.stopAudioPlayback();

            // Reset progress tracking for new conversation turn
            this.resetProgressTracking();

            // Update button to green (active speech)
            this.updateVoiceButton(this.isListening, true);

        } else if (this.isInSpeechSegment) {
            // No voice activity but we're in a speech segment
            const timeSinceLastVoice = currentTime - this.lastVoiceTime;

            if (timeSinceLastVoice < this.SPEECH_PAUSE_THRESHOLD) {
                // Still within pause threshold - keep button green
                this.updateVoiceButton(this.isListening, true);

                // Set timeout to check if pause becomes too long
                if (!this.silenceTimeout) {
                    this.silenceTimeout = setTimeout(() => {
                        // Pause exceeded threshold - end speech segment
                        this.isInSpeechSegment = false;
                        this.updateVoiceButton(this.isListening, false);
                        this.silenceTimeout = null;
                    }, this.SPEECH_PAUSE_THRESHOLD - timeSinceLastVoice);
                }
            } else {
                // Pause exceeded threshold - end speech segment
                this.isInSpeechSegment = false;
                this.updateVoiceButton(this.isListening, false);
            }
        } else {
            // Not in speech segment and no voice - button stays gray
            this.updateVoiceButton(this.isListening, false);
        }

        // Update debug info with backend VAD details
        const timeSinceVoice = this.isInSpeechSegment ? (currentTime - this.lastVoiceTime) : 'N/A';
        this.debugInfo.textContent = `VAD: ${isVoice ? 'voice' : 'silence'} | Active: ${isVoiceActive} | Prob: ${voiceProbability.toFixed(3)} | Segment: ${this.isInSpeechSegment} | Since voice: ${timeSinceVoice}ms`;
    }

    handleWebSocketMessage(data) {
        const messageType = data.type;

        switch (messageType) {
            case 'conversation_started':
                this.conversationId = data.conversation_id;

                // Update AudioStreamer with dynamic TTS configuration
                if (data.config && data.config.tts_sample_rate && data.config.tts_encoding) {
                    this.audioStreamer = new AudioStreamer({
                        sampleRate: data.config.tts_sample_rate,
                        encoding: data.config.tts_encoding,
                        onPlaybackStart: () => {
                            this.playbackStarted = true;
                            this.playbackStartTime = Date.now();
                            const latency = this.playbackStartTime - this.startTime;
                            this.playbackStartLatency.textContent = `${latency}ms`;
                            this.playbackStartLatency.className = 'latency-value measured';
                            console.log(`🎵 Audio playback started after ${latency}ms`);
                        },
                        onPlaybackEnd: () => {
                            this.ttsStatus.classList.remove('active');
                        },
                        onError: (error) => {
                            console.error('AudioStreamer error:', error);
                        }
                    });
                    console.log(`🎵 AudioStreamer reconfigured: ${data.config.tts_sample_rate}Hz, ${data.config.tts_encoding}`);
                }
                break;

            case 'vad_status':
                // Handle legacy backend VAD results
                this.handleBackendVADResult(data);
                break;

            case 'speech_start':
                // Handle new event-driven VAD start
                console.log('🗣️ Speech started');
                this.handleBackendVADResult({
                    is_voice: true,
                    is_voice_active: true,
                    voice_probability: 1.0
                });
                break;

            case 'speech_end':
                // Handle new event-driven VAD end
                console.log('🤫 Speech ended');
                this.handleBackendVADResult({
                    is_voice: false,
                    is_voice_active: false,
                    voice_probability: 0.0
                });
                break;

            case 'bot_response_interrupted':
                // Handle interruption confirmation
                console.log('🛑 Bot response interrupted');
                this.stopAudioPlayback();
                this.updateStatus('listening', 'Interrupted!');
                break;

            case 'transcript_update':
                // Debug logging removed for production
                this.updateTranscription(data.text, data.is_final);
                break;

            case 'assistant_response':
                this.updateAssistantResponse(data.text, data.is_complete, data.is_first_token);
                // Update LLM status when we receive assistant response
                if (data.is_first_token) {
                    this.tokenCounter++;
                    this.llmStatus.classList.add('active');
                } else if (!data.is_complete) {
                    // Increment token counter for streaming tokens
                    this.tokenCounter++;
                } else if (data.is_complete) {
                    // When response is complete, reset LLM status
                    this.llmStatus.classList.remove('active');
                }
                this.updateStats();
                break;

            case 'audio_chunk':
                // This should no longer be used - audio is now sent as binary
                // Debug logging removed for production
                break;

            case 'status':
                this.updateStatus(data.status, data.message || data.status);
                break;

            case 'agent_changed':
                console.log(`✅ Agent changed successfully: ${data.agent_id}`);
                this.showError(''); // Clear any errors
                this.updateStatus('connected', `Agent: ${data.agent_id || 'Default'}`);
                break;

            case 'error':
                // Debug logging removed for production
                this.showError(data.message);
                this.updateStatus('error', data.message);
                break;

            default:
            // Debug logging removed for production
        }
    }

    updateTranscription(text, isFinal) {
        // Debug logging removed for production

        if (!this.transcriptionOutput) {
            // Debug logging removed for production
            return;
        }

        if (isFinal) {
            // Final transcript - replace the entire text
            this.transcriptionOutput.textContent = text;
            this.transcriptionOutput.style.color = '#1f2937'; // Dark gray for final
        } else {
            // Intermediate transcript - show current state
            this.transcriptionOutput.textContent = text;
            this.transcriptionOutput.style.color = '#6b7280'; // Light gray for interim
        }

        // Auto-scroll to bottom
        this.transcriptionOutput.scrollTop = this.transcriptionOutput.scrollHeight;

        // Update debug info with transcription status
        const debugText = this.debugInfo.textContent.split('|')[0];
        this.debugInfo.textContent = `${debugText} | Transcription: ${isFinal ? 'final' : 'interim'}`;

        // Debug logging removed for production
    }

    updateAssistantResponse(text, isComplete, isFirstToken = false) {
        if (isFirstToken) {
            // First token received - clear any previous response and start fresh
            this.assistantResponse.textContent = text;
            // Debug logging removed for production
        } else {
            // Streaming token - update the text
            this.assistantResponse.textContent = text;
        }

        if (isComplete) {
            this.assistantResponse.style.color = '#059669'; // Green for complete
            // Debug logging removed for production
        } else {
            this.assistantResponse.style.color = '#0d9488'; // Teal for streaming
        }

        // Auto-scroll to bottom for real-time viewing
        this.assistantResponse.scrollTop = this.assistantResponse.scrollHeight;

        // Update debug info with streaming status
        const debugText = this.debugInfo.textContent.split('|')[0];
        const streamingStatus = isComplete ? 'complete' : (isFirstToken ? 'first_token' : 'streaming');
        this.debugInfo.textContent = `${debugText} | LLM: ${streamingStatus}`;
    }

    handleBinaryAudioData(audioData) {
        if (!audioData) return;

        try {
            // Track first audio chunk latency
            if (!this.firstChunkReceived) {
                this.firstChunkReceived = true;
                this.firstChunkTime = Date.now();
                const latency = this.firstChunkTime - this.startTime;
                this.firstChunkLatency.textContent = `${latency}ms`;
                this.firstChunkLatency.className = 'latency-value measured';
                console.log(`⏱️ First audio chunk received after ${latency}ms`);
            }

            // Update TTS status
            this.audioChunkCounter++;
            this.ttsStatus.classList.add('active');
            this.updateStats();

            // Utiliser l'AudioStreamer partagé pour gérer la lecture audio TTS
            this.audioStreamer.addAudioChunk(audioData);

        } catch (error) {
            // Debug logging removed for production
        }
    }

    updateVoiceButton(isListening, isVoice = false) {
        if (!isListening) {
            this.voiceButton.className = 'voice-btn gray';
            this.voiceButton.textContent = '🎤 Ready to Listen';
            this.voiceButton.disabled = false;
        } else if (isVoice) {
            this.voiceButton.className = 'voice-btn green';
            this.voiceButton.textContent = '🎤 Voice Detected';
            this.voiceButton.disabled = false;
        } else {
            // Check if we're in a speech segment with a long pause
            const currentTime = Date.now();
            const timeSinceLastVoice = this.isInSpeechSegment ? (currentTime - this.lastVoiceTime) : 0;

            if (this.isInSpeechSegment && timeSinceLastVoice >= this.SPEECH_PAUSE_THRESHOLD) {
                // Long pause detected - show red button
                this.voiceButton.className = 'voice-btn red';
                this.voiceButton.textContent = '🎤 Pause Detected';
                this.voiceButton.disabled = false;
            } else {
                // Normal listening state
                this.voiceButton.className = 'voice-btn gray';
                this.voiceButton.textContent = '🎤 Listening...';
                this.voiceButton.disabled = false;
            }
        }
    }

    updateEnergyBar(energy) {
        // Use voice probability from backend VAD for energy visualization
        const normalizedEnergy = Math.min(energy * 2, 1.0); // Scale probability for better visualization
        const barWidth = Math.min(normalizedEnergy * 100, 100);
        this.energyBar.style.width = `${barWidth}%`;

        // Change color based on voice detection from backend VAD
        if (this.lastVadResult && this.lastVadResult.is_voice) {
            this.energyBar.style.background = '#10B981'; // Green for voice
        } else {
            this.energyBar.style.background = '#6B7280'; // Gray for silence
        }
    }

    updateStatus(status, message) {
        this.statusText.textContent = message;
        this.statusDot.className = 'status-dot';

        switch (status) {
            case 'connected':
            case 'listening':
                this.statusDot.classList.add('connected');
                break;
            case 'error':
                this.statusDot.classList.add('error');
                break;
            // Default: keep gray dot
        }
    }

    showError(message) {
        if (message) {
            this.errorContainer.textContent = message;
            this.errorContainer.style.display = 'block';
        } else {
            this.errorContainer.style.display = 'none';
        }
    }

    // Utility functions for data conversion
    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }

    base64ToArrayBuffer(base64) {
        const binaryString = window.atob(base64);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    }

    stopAudioPlayback() {
        // Debug logging removed for production

        // Utiliser l'AudioStreamer partagé pour arrêter la lecture audio
        this.audioStreamer.stopPlayback();

        // Note: We don't close the main audio context here because it's used for VAD
        // The playback will stop naturally when isPlayingAudio is false and queue is empty
        // Debug logging removed for production
    }

    resetProgressTracking() {
        // Reset all status tracking variables
        this.tokenCounter = 0;
        this.audioChunkCounter = 0;
        this.startTime = Date.now();
        this.firstChunkReceived = false;
        this.playbackStarted = false;
        this.firstChunkTime = null;
        this.playbackStartTime = null;

        // Reset UI elements
        this.llmStatus.classList.remove('active');
        this.ttsStatus.classList.remove('active');
        this.tokenCount.textContent = 'Tokens: 0';
        this.audioChunkCount.textContent = 'Audio Chunks: 0';
        this.streamTime.textContent = 'Time: 0s';
        this.firstChunkLatency.textContent = '-';
        this.firstChunkLatency.className = 'latency-value pending';
        this.playbackStartLatency.textContent = '-';
        this.playbackStartLatency.className = 'latency-value pending';

        // Show status section
        this.statusSection.style.display = 'block';
        this.latencySection.style.display = 'block';

        console.log('🔄 Status tracking reset for new conversation turn');
    }

    updateStats() {
        const elapsedTime = this.startTime ? Math.round((Date.now() - this.startTime) / 1000) : 0;

        this.tokenCount.textContent = `Tokens: ${this.tokenCounter}`;
        this.audioChunkCount.textContent = `Audio Chunks: ${this.audioChunkCounter}`;
        this.streamTime.textContent = `Time: ${elapsedTime}s`;
    }

    // Agent Management Methods
    async initializeAgentSelector() {
        if (!this.agentSelect) {
            console.warn('Agent select element not found');
            return;
        }

        try {
            // Initialize the shared agent selector
            this.agentSelector = new AgentSelector('agentSelect', (agent, agentId) => this.handleAgentChange(agentId));

            // Get the initial agent ID
            this.currentAgentId = this.agentSelector.getCurrentAgentId();

        } catch (error) {
            console.error('Error initializing agent selector:', error);
        }
    }

    async handleAgentChange(agentId) {
        this.currentAgentId = agentId;
        console.log(`Agent changed to: ${agentId}`);

        // If we're currently connected, we need to reconnect with the new agent
        if (this.isConnected && this.isListening) {
            console.log(`🔄 Agent changed while connected - reconnecting with new agent: ${agentId}`);

            // Stop current connection and reconnect with new agent
            await this.stopListening();
            await this.startListening();
        } else {
            // Just update the agent ID for future connections
            console.log(`📝 Agent updated to: ${agentId} (will be used for next connection)`);
        }
    }

    // Cleanup method
    destroy() {
        this.stopListening();

        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }

        // Clean up audio streaming resources
        this.cleanupAudioStreaming();
    }
}

// Initialize voicebot when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.voicebot = new VoicebotInterface();
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoicebotInterface;
}