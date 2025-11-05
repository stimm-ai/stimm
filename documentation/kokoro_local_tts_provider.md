# Kokoro Local TTS Provider

This document describes the Kokoro local TTS provider implementation for the voicebot application.

## Overview

The Kokoro local TTS provider enables real-time text-to-speech synthesis using a self-hosted Kokoro ONNX model. It provides async.ai compatible WebSocket streaming for seamless integration with the existing TTS service architecture.

## Architecture

### Provider Structure

```
src/voicebot_app/services/tts/providers/kokoro_local/
├── __init__.py          # Package exports
└── kokoro_local_provider.py  # Main provider implementation
```

### Key Components

1. **KokoroLocalProvider Class**: Main provider that implements the `stream_synthesis` method
2. **WebSocket Streaming**: Uses async.ai compatible protocol for real-time audio streaming
3. **Configuration**: Loads settings from environment variables via TTSConfig

## Configuration

### Environment Variables

The following environment variables are used by the Kokoro local provider:

```bash
# TTS Provider Selection
TTS_PROVIDER=kokoro.local

# Kokoro Local Configuration
KOKORO_LOCAL_TTS_URL=ws://kokoro-tts:5000/ws/tts/stream
KOKORO_TTS_DEFAULT_VOICE=af_sarah
KOKORO_TTS_SAMPLE_RATE=22050
KOKORO_TTS_ENCODING=pcm_s16le
KOKORO_TTS_CONTAINER=raw
```

### Default Values

- **URL**: `ws://kokoro-tts:5000/ws/tts/stream`
- **Voice**: `af_sarah`
- **Sample Rate**: `24000`
- **Encoding**: `pcm_s16le`
- **Container**: `raw`

## Integration

### TTS Service Integration

The provider is automatically loaded by the [`TTSService`](../src/voicebot_app/services/tts/tts.py) when `TTS_PROVIDER` is set to `"kokoro.local"`:

```python
def _initialize_provider(self):
    provider_name = self.config.get_provider()

    if provider_name == "async.ai":
        self.provider = AsyncAIProvider()
    elif provider_name == "kokoro.local":
        self.provider = KokoroLocalProvider()
    else:
        raise ValueError(f"Unsupported TTS provider: {provider_name}")
```

### WebSocket Protocol

The provider uses an async.ai compatible WebSocket protocol:

1. **Initialization**: Send initialization message with voice and format settings
2. **Text Streaming**: Send text chunks via `{"transcript": "text "}` messages
3. **Audio Streaming**: Receive base64-encoded PCM audio chunks
4. **Stream Completion**: Send empty transcript to signal end of stream

## Kokoro Service Enhancements

The Kokoro service has been enhanced with a new WebSocket endpoint at `/ws/tts/stream` that supports:

- **Real-time Streaming**: Text chunking and buffering for live synthesis
- **PCM Output**: Raw PCM audio output compatible with async.ai
- **Base64 Encoding**: Audio chunks encoded in base64 for WebSocket transport
- **Error Handling**: Proper error responses and connection management

## Testing

A test script is available to verify the integration:

```bash
python test_kokoro_integration.py
```

This script will:
1. Initialize the TTSService with Kokoro provider
2. Stream test text chunks
3. Receive and count audio chunks
4. Report success or failure

## Usage

### Setting Up the Service

1. Ensure the Kokoro service is running in Docker:
   ```bash
   docker-compose up kokoro-tts
   ```

2. Set environment variables:
   ```bash
   export TTS_PROVIDER=kokoro.local
   ```

3. Use the TTS service as normal - the provider will be automatically selected

### Switching Providers

To switch between TTS providers, simply change the `TTS_PROVIDER` environment variable:

```bash
# Use Kokoro local
export TTS_PROVIDER=kokoro.local

# Use Async.ai
export TTS_PROVIDER=async.ai
```

## Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure Kokoro service is running on port 5000
2. **No Audio Received**: Check Kokoro service logs for synthesis errors
3. **Protocol Errors**: Verify WebSocket URL and initialization format

### Logging

Enable debug logging for detailed provider operation:

```bash
export LOG_LEVEL=DEBUG
```

## Performance

- **Latency**: Real-time streaming with minimal buffering
- **Throughput**: Supports concurrent text chunk processing
- **Resource Usage**: Local GPU acceleration via Kokoro ONNX model