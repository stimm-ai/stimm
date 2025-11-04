# Deepgram STT Provider Documentation

## Overview

The Deepgram STT provider enables real-time speech-to-text transcription using Deepgram's cloud-based API. This provider integrates seamlessly with the existing voicebot STT service architecture.

## Configuration

### Environment Variables

The Deepgram provider requires the following environment variables:

```bash
# Required: Deepgram API Key
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# Optional: Model selection (default: nova-2)
DEEPGRAM_MODEL=nova-3

# Optional: Language (default: fr)
DEEPGRAM_LANGUAGE=fr

# Required: Set STT provider to deepgram.com
STT_PROVIDER=deepgram.com
```

### Available Models

- `nova-3` - Latest model with multilingual support
- `nova-2` - Recommended for French language (default)
- `nova` - Legacy model
- `enhanced` - Enhanced accuracy model
- `base` - Base model for general use

### Supported Languages

- `fr` - French (default)
- `en` - English
- `es` - Spanish
- `de` - German
- And many more - see Deepgram documentation for full list

## Audio Format Requirements

The Deepgram provider expects audio in the following format:

- **Sample Rate**: 16kHz
- **Format**: Linear16 PCM
- **Channels**: Mono (1 channel)
- **Bit Depth**: 16-bit
- **Chunk Size**: 40ms chunks (typical WebRTC)

## Implementation Details

### Provider Class

The [`DeepgramProvider`](src/voicebot_app/services/stt/providers/deepgram_provider.py) class implements the standard STT provider interface:

```python
class DeepgramProvider:
    async def connect(self) -> None
    async def disconnect(self) -> None
    async def stream_audio_chunks(
        self, 
        audio_chunk_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]
```

### WebSocket Connection

The provider uses Deepgram's WebSocket API directly:

- **URL**: `wss://api.deepgram.com/v1/listen`
- **Authentication**: API key in Authorization header
- **Parameters**: Configured via query string
- **Protocol**: Raw WebSocket with JSON messages

### Message Types Handled

- `Results` - Transcription results with confidence scores
- `UtteranceEnd` - End of speech detection
- `SpeechStarted` - Speech activity detection

## Testing

### Test Files

- [`test_deepgram_streaming.py`](src/voicebot_app/services/stt/tests/test_deepgram_streaming.py) - Comprehensive test suite
- [`Enregistrement.wav`](src/voicebot_app/services/stt/tests/Enregistrement.wav) - Test audio file

### Running Tests

```bash
# Run all Deepgram tests
docker exec -it voicebot-app python -m pytest services/stt/tests/test_deepgram_streaming.py -v

# Run specific test
docker exec -it voicebot-app python -m pytest services/stt/tests/test_deepgram_streaming.py::test_deepgram_service_initialization -v
```

### Web Interface

Access the STT web interface at: `http://localhost:8001/stt/interface`

## Integration with Voicebot

### Service Initialization

The [`STTService`](src/voicebot_app/services/stt/stt.py) automatically initializes the Deepgram provider when configured:

```python
def _initialize_provider(self):
    provider_name = self.config.get_provider()
    
    if provider_name == "deepgram.com":
        self.provider = DeepgramProvider()
        logger.info(f"Initialized STT provider: {provider_name}")
```

### Configuration Integration

The [`STTConfig`](src/voicebot_app/services/stt/config.py) class includes Deepgram-specific configuration:

```python
def get_deepgram_config(self):
    return {
        "api_key": self.deepgram_api_key,
        "model": self.deepgram_model,
        "language": self.deepgram_language
    }
```

## Error Handling

The provider includes comprehensive error handling for:

- Connection failures
- API key validation
- WebSocket timeouts
- Invalid audio format
- Network interruptions

## Performance Characteristics

- **Latency**: Optimized for real-time streaming
- **Accuracy**: High accuracy with Deepgram's advanced models
- **Reliability**: Automatic reconnection and error recovery
- **Scalability**: Cloud-based, no local resource limitations

## Usage Examples

### Basic Usage

```python
from services.stt.stt import STTService

# Initialize with Deepgram provider
stt_service = STTService()

# Stream audio and get transcripts
async for transcript in stt_service.transcribe_streaming(audio_generator):
    print(f"Transcript: {transcript['transcript']}")
    print(f"Confidence: {transcript['confidence']}")
    print(f"Is Final: {transcript['is_final']}")
```

### Custom Configuration

```python
import os

# Set custom configuration
os.environ["DEEPGRAM_MODEL"] = "nova-3"
os.environ["DEEPGRAM_LANGUAGE"] = "en"
os.environ["STT_PROVIDER"] = "deepgram.com"

# Use the service
stt_service = STTService()
```

## Troubleshooting

### Common Issues

1. **API Key Error**: Ensure `DEEPGRAM_API_KEY` is set correctly
2. **Connection Timeout**: Check network connectivity to Deepgram API
3. **Audio Format**: Verify audio is 16kHz, 16-bit, mono PCM
4. **Model Compatibility**: Ensure selected model supports the target language

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
LOG_LEVEL=DEBUG
```

## Dependencies

- `websockets` - WebSocket client library
- `deepgram-sdk` - Deepgram Python SDK (for future enhancements)

## References

- [Deepgram API Documentation](https://developers.deepgram.com/)
- [Deepgram WebSocket API Reference](https://developers.deepgram.com/reference/speech-to-text/listen-streaming)
- [Voicebot STT Service Documentation](../project_architecture.md)