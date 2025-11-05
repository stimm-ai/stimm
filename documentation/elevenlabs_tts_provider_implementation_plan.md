# ElevenLabs TTS Provider Implementation Plan

## Overview
Implement a full WebSocket streaming TTS provider for ElevenLabs.io following the existing provider patterns in the voicebot project.

## API Analysis

### WebSocket Endpoint
- **URL**: `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`
- **Authentication**: `xi-api-key` header
- **Protocol**: WebSocket with JSON message exchange

### Message Types

#### Send Messages (Client → Server)
1. **InitializeConnection**
   - Required field: `text` (must be " ")
   - Optional: `voice_settings`, `generation_config`, `pronunciation_dictionary_locators`
   - Authentication: `xi-api-key` or `authorization`

2. **SendText**
   - Required field: `text`
   - Optional: `try_trigger_generation`, `voice_settings`, `generator_config`, `flush`

3. **CloseConnection**
   - Required field: `text` (must be "")

#### Receive Messages (Server → Client)
1. **AudioOutput**
   - Fields: `audio` (base64), `normalizedAlignment`, `alignment`

2. **FinalOutput**
   - Fields: `isFinal` (boolean)

## Configuration Requirements

### Environment Variables
```
# ElevenLabs TTS Provider
ELEVENLABS_TTS_API_KEY=your_api_key_here
ELEVENLABS_TTS_VOICE_ID=default_voice_id
ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_TTS_SAMPLE_RATE=44100
ELEVENLABS_TTS_ENCODING=pcm_s16le
ELEVENLABS_TTS_OUTPUT_FORMAT=pcm_44100
```

### Voice Settings (Optional)
- `stability`: float (0.0-1.0)
- `similarity_boost`: float (0.0-1.0)
- `style`: float (0.0-1.0)
- `use_speaker_boost`: boolean
- `speed`: float (0.5-2.0)

## Implementation Steps

### 1. Update TTS Configuration
Add ElevenLabs configuration to [`src/voicebot_app/services/tts/config.py`](src/voicebot_app/services/tts/config.py)

### 2. Create ElevenLabs Provider
Create [`src/voicebot_app/services/tts/providers/elevenlabs/elevenlabs_provider.py`](src/voicebot_app/services/tts/providers/elevenlabs/elevenlabs_provider.py) with:
- WebSocket connection management
- Concurrent sender/receiver pattern
- Base64 audio decoding
- Error handling and logging

### 3. Update TTSService
Add ElevenLabs provider initialization in [`src/voicebot_app/services/tts/tts.py`](src/voicebot_app/services/tts/tts.py)

### 4. Create Integration Tests
Create [`src/voicebot_app/services/tts/tests/test_elevenlabs_tts_websocket.py`](src/voicebot_app/services/tts/tests/test_elevenlabs_tts_websocket.py)

### 5. Create Example Script
Create [`src/voicebot_app/services/tts/providers/elevenlabs/example_elevenlabs_usage.py`](src/voicebot_app/services/tts/providers/elevenlabs/example_elevenlabs_usage.py)

## Code Structure

### ElevenLabsProvider Class
```python
class ElevenLabsProvider:
    def __init__(self):
        # Configuration from tts_config
        self.api_key = config.elevenlabs_api_key
        self.voice_id = config.elevenlabs_voice_id
        self.model_id = config.elevenlabs_model_id
        self.sample_rate = config.elevenlabs_sample_rate
        self.encoding = config.elevenlabs_encoding
        self.output_format = config.elevenlabs_output_format
    
    async def stream_synthesis(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        # WebSocket connection and streaming implementation
        # Following async.ai provider pattern
```

### WebSocket Message Flow
1. Connect to WebSocket with authentication header
2. Send `InitializeConnection` with voice settings
3. Stream text chunks via `SendText` messages
4. Receive and decode `AudioOutput` messages
5. Send `CloseConnection` when done
6. Handle `FinalOutput` signal

## Testing Strategy

### Unit Tests
- Provider initialization
- Configuration validation
- WebSocket message parsing

### Integration Tests
- Live WebSocket connection (with API key)
- Audio streaming and decoding
- Error handling scenarios

## Dependencies
- `websockets` library (already in project)
- `aiohttp` for WebSocket connections
- `base64` for audio decoding
- `json` for message serialization

## Success Criteria
- [ ] Provider integrates with existing TTSService
- [ ] WebSocket streaming works with real ElevenLabs API
- [ ] Audio chunks are properly decoded and yielded
- [ ] Error handling covers common failure scenarios
- [ ] Comprehensive logging for debugging
- [ ] Tests pass with valid API credentials