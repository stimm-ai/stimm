# Voicebot Wrapper Technical Specification

## 1. Core Service Architecture

### 1.1 VoicebotService Class Structure

```python
class VoicebotService:
    """Main orchestrator for the complete voicebot pipeline"""
    
    def __init__(self):
        self.stt_service = STTService()
        self.tts_service = TTSService() 
        self.chatbot_service = ChatbotService()
        self.conversation_state = ConversationState()
        self.vad_processor = VADProcessor()
        
    async def process_voice_input(self, audio_stream: AsyncGenerator[bytes, None]):
        """Complete pipeline: VAD → STT → RAG/LLM → TTS"""
        pass
        
    async def stream_conversation(self, websocket: WebSocket):
        """Handle real-time conversation streaming"""
        pass
```

### 1.2 Configuration Structure

```python
# config.py
class VoicebotConfig:
    VAD_THRESHOLD = 0.1  # Voice activity detection sensitivity
    SILENCE_TIMEOUT_MS = 1000  # End of speech detection
    MIN_SPEECH_DURATION_MS = 300  # Minimum speech length
    SAMPLE_RATE = 16000  # Audio sample rate
    CHUNK_SIZE_MS = 20   # Audio chunk size in milliseconds
    
    # Service endpoints
    STT_PROVIDER = "whisper.local"
    TTS_PROVIDER = "async.ai" 
    RAG_ENABLED = True
```

## 2. Voice Activity Detection (VAD) Implementation

### 2.1 Web Audio API VAD Processor

```javascript
// audio-processor.js (AudioWorklet)
class VADProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const input = inputs[0][0];
        const energy = this.calculateEnergy(input);
        const isVoice = energy > this.threshold;
        
        this.port.postMessage({
            type: 'vad_result',
            isVoice: isVoice,
            energy: energy,
            timestamp: currentTime
        });
        
        return true;
    }
    
    calculateEnergy(samples) {
        return samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length;
    }
}
```

### 2.2 Frontend VAD Integration

```javascript
// voicebot.js
class VoicebotInterface {
    async initializeVAD() {
        // Setup AudioWorklet for VAD
        await this.audioContext.audioWorklet.addModule('/static/audio-processor.js');
        this.vadNode = new AudioWorkletNode(this.audioContext, 'vad-processor');
        
        this.vadNode.port.onmessage = (event) => {
            const { isVoice, energy } = event.data;
            this.updateVoiceIndicator(isVoice, energy);
        };
    }
    
    updateVoiceIndicator(isVoice, energy) {
        const button = document.getElementById('voiceButton');
        if (isVoice) {
            button.style.backgroundColor = '#10B981'; // Green
            button.textContent = '🎤 Voice Detected';
        } else {
            button.style.backgroundColor = '#6B7280'; // Gray  
            button.textContent = '🎤 Ready to Listen';
        }
    }
}
```

## 3. WebSocket Protocol Design

### 3.1 Client → Server Messages

```json
{
  "type": "start_listening",
  "conversation_id": "uuid",
  "sample_rate": 16000
}

{
  "type": "audio_chunk", 
  "data": "base64_encoded_audio",
  "timestamp": 1234567890
}

{
  "type": "stop_listening"
}
```

### 3.2 Server → Client Messages

```json
{
  "type": "vad_status",
  "is_voice": true,
  "energy": 0.15
}

{
  "type": "interim_transcript",
  "text": "Hello how are",
  "is_final": false
}

{
  "type": "final_transcript", 
  "text": "Hello how are you?",
  "is_final": true
}

{
  "type": "assistant_response",
  "text": "I'm doing well, thank you!",
  "audio_chunk": "base64_encoded_audio"
}

{
  "type": "error",
  "message": "Microphone access denied"
}
```

## 4. File Structure and Dependencies

### 4.1 Required Files

```
src/services/voicebot_wrapper/
├── __init__.py
├── config.py
├── voicebot_service.py
├── vad_processor.py
├── conversation_state.py
├── routes.py
├── static/
│   ├── voicebot.js
│   └── audio-processor.js
└── templates/
    └── voicebot.html
```

### 4.2 Dependencies Integration

- **STT Service**: `from services.stt.stt import STTService`
- **TTS Service**: `from services.tts.tts import TTSService` 
- **RAG Service**: `from services.rag.chatbot_service import ChatbotService`
- **Web Framework**: FastAPI WebSocket endpoints

## 5. Frontend Interface Design

### 5.1 HTML Structure

```html
<!-- voicebot.html -->
<div class="voicebot-container">
    <div class="header">
        <h1>Voicebot Interface</h1>
        <div class="status-indicator">
            <span id="connectionStatus">Connected</span>
        </div>
    </div>
    
    <div class="controls">
        <button id="voiceButton" class="voice-btn gray">
            🎤 Ready to Listen
        </button>
        <div class="vad-visualizer">
            <div class="energy-bar"></div>
        </div>
    </div>
    
    <div class="transcription-panel">
        <h3>Transcription</h3>
        <div id="transcriptionOutput" class="transcription-output"></div>
    </div>
    
    <div class="response-panel">
        <h3>Assistant Response</h3>
        <div id="assistantResponse" class="response-output"></div>
        <audio id="audioPlayer" controls></audio>
    </div>
</div>
```

### 5.2 CSS Styling

```css
.voice-btn {
    padding: 20px 40px;
    border-radius: 50px;
    border: none;
    font-size: 18px;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.3s ease;
}

.voice-btn.gray {
    background-color: #6B7280;
    color: white;
}

.voice-btn.green {
    background-color: #10B981;
    color: white;
    box-shadow: 0 0 20px rgba(16, 185, 129, 0.5);
}

.vad-visualizer {
    margin-top: 10px;
    height: 4px;
    background: #E5E7EB;
    border-radius: 2px;
    overflow: hidden;
}

.energy-bar {
    height: 100%;
    background: #10B981;
    width: 0%;
    transition: width 0.1s ease;
}
```

## 6. Performance Optimization

### 6.1 Latency Targets

- **VAD Processing**: < 20ms
- **Audio Chunk Size**: 20ms frames
- **STT Streaming**: < 200ms end-to-end
- **LLM First Token**: < 500ms
- **TTS First Chunk**: < 100ms

### 6.2 Memory Management

- Audio buffer recycling
- Connection pooling for services
- Streaming response handling
- Proper WebSocket cleanup

## 7. Error Handling Strategy

### 7.1 Common Error Scenarios

- Microphone permission denied
- Network connectivity issues
- Service unavailability (STT/TTS/LLM)
- Audio encoding problems
- WebSocket connection drops

### 7.2 Recovery Mechanisms

- Automatic reconnection with backoff
- Graceful degradation (text-only mode)
- User-friendly error messages
- Service health monitoring

## 8. Testing Strategy

### 8.1 Test Cases

1. **VAD Accuracy**: Test voice detection with various audio samples
2. **End-to-End Flow**: Complete conversation cycle
3. **Error Conditions**: Service failures and network issues
4. **Performance**: Latency and resource usage
5. **Cross-browser**: Chrome, Firefox, Safari compatibility

### 8.2 Integration Testing

```python
# test_voicebot_integration.py
async def test_complete_conversation_flow():
    voicebot = VoicebotService()
    audio_stream = simulate_audio_input("Hello, how are you?")
    
    async for response in voicebot.process_voice_input(audio_stream):
        assert response.type in ['vad_status', 'transcript', 'response']
        
    assert conversation_completed_successfully()
```

This technical specification provides the complete blueprint for implementing the voicebot wrapper. The next step is to switch to Code mode to implement these components.