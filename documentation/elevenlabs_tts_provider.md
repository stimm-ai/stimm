# ElevenLabs TTS Provider Documentation

## Overview

The ElevenLabs TTS provider implements real-time text-to-speech synthesis using ElevenLabs' WebSocket streaming API. This provider follows the same pattern as other TTS providers in the voicebot project and supports full live streaming of text chunks to audio.

## Features

- **Real-time streaming**: Stream text chunks as they become available
- **WebSocket-based**: Uses ElevenLabs WebSocket API for low-latency synthesis
- **Voice customization**: Supports ElevenLabs voice settings (stability, similarity boost, etc.)
- **Multiple output formats**: Configurable audio formats and sample rates
- **Error handling**: Comprehensive error handling and logging
- **Integration**: Seamlessly integrates with existing TTSService

## Configuration

### Environment Variables

```bash
# Required
ELEVENLABS_TTS_API_KEY=your_api_key_here

# Optional (with defaults)
TTS_PROVIDER=elevenlabs.io
ELEVENLABS_TTS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_TTS_SAMPLE_RATE=44100
ELEVENLABS_TTS_ENCODING=pcm_s16le
ELEVENLABS_TTS_OUTPUT_FORMAT=pcm_44100
```

### Voice Settings

The provider supports the following voice settings (configurable in the provider code):

- **stability**: 0.0-1.0 (default: 0.5) - Lower values = more expressive
- **similarity_boost**: 0.0-1.0 (default: 0.75) - Higher values = more similar to original voice
- **style**: 0.0-1.0 (default: 0.0) - Higher values = more dramatic
- **use_speaker_boost**: boolean (default: True)

## Usage

### Basic Usage with TTSService

```python
import os
os.environ['TTS_PROVIDER'] = 'elevenlabs.io'
os.environ['ELEVENLABS_TTS_API_KEY'] = 'your_api_key'

from services.tts.tts import TTSService

async def text_generator():
    yield "Hello, this is a test."
    yield "This text is streamed in chunks."

service = TTSService()
async for audio_chunk in service.stream_synthesis(text_generator()):
    # Process audio chunk
    print(f"Received {len(audio_chunk)} bytes of audio")
```

### Direct Provider Usage

```python
from services.tts.providers.elevenlabs.elevenlabs_provider import ElevenLabsProvider

async def text_generator():
    yield "Hello from ElevenLabs!"
    yield "Streaming text to speech."

provider = ElevenLabsProvider()
async for audio_chunk in provider.stream_synthesis(text_generator()):
    # Handle audio data
    process_audio(audio_chunk)
```

## API Integration Details

### WebSocket Endpoint
- **URL**: `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`
- **Authentication**: `xi-api-key` header

### Message Flow

1. **InitializeConnection**: Send initialization with voice settings
2. **SendText**: Stream text chunks with optional generation trigger
3. **AudioOutput**: Receive base64-encoded audio chunks
4. **FinalOutput**: Receive completion signal
5. **CloseConnection**: Send empty text to close connection

### Message Formats

#### InitializeConnection
```json
{
  "text": " ",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": true
  },
  "xi-api-key": "your_api_key"
}
```

#### SendText
```json
{
  "text": "Your text chunk here",
  "try_trigger_generation": true
}
```

#### AudioOutput
```json
{
  "audio": "base64_encoded_audio_data",
  "normalizedAlignment": {...},
  "alignment": {...}
}
```

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
# In the Docker container
docker exec voicebot-app python -c "
import os
os.environ['TTS_PROVIDER'] = 'elevenlabs.io'
from services.tts.tests.test_elevenlabs_tts_websocket import main
import asyncio
asyncio.run(main())
"
```

### Example Script

Use the example script to test basic functionality:

```bash
docker exec voicebot-app python services/tts/providers/elevenlabs/example_elevenlabs_usage.py
```

## Error Handling

The provider includes comprehensive error handling for:

- Missing API key
- WebSocket connection failures
- Invalid message formats
- Network timeouts
- Authentication errors

## Performance Considerations

- **Latency**: WebSocket streaming provides low-latency audio generation
- **Buffering**: Some buffering occurs for consistent audio quality
- **Chunk size**: Smaller text chunks may result in more responsive audio
- **Network**: Stable internet connection required for real-time streaming

## Comparison with Other Providers

| Feature | ElevenLabs | Async.AI | Deepgram | Kokoro Local |
|---------|------------|----------|----------|--------------|
| Streaming | ✅ | ✅ | ✅ | ✅ |
| Voice Customization | ✅ | ✅ | ✅ | ✅ |
| Alignment Data | ✅ | ❌ | ❌ | ❌ |
| Multilingual | ✅ | ✅ | ✅ | ✅ |
| Self-hosted | ❌ | ❌ | ❌ | ✅ |

## Troubleshooting

### Common Issues

1. **Authentication Error**: Check your `ELEVENLABS_TTS_API_KEY` environment variable
2. **No Audio Received**: Verify text chunks are being sent and check network connectivity
3. **Connection Timeout**: Ensure stable internet connection and check firewall settings
4. **Invalid Voice ID**: Verify the voice ID exists in your ElevenLabs account

### Debugging

Enable debug logging for detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## References

- [ElevenLabs API Documentation](https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input)
- [Voicebot TTS Architecture](../project_architecture.md)
- [Async.AI Provider Documentation](./async_ai_tts_provider.md)