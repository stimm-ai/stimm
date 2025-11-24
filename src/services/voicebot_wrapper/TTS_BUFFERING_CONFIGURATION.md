# TTS Buffering Configuration

This document explains how to configure the TTS buffering levels in the voicebot system.

## Overview

The system now supports configurable buffering levels for TTS (Text-to-Speech) processing. This allows you to balance between real-time responsiveness and audio quality by controlling when text chunks are sent to the TTS service.

## Configuration

### Environment Variable

Set the `PRE_TTS_BUFFERING_LEVEL` environment variable in your `.env` file:

```env
# TTS Buffering Configuration
# Options: NONE, LOW, MEDIUM, HIGH
# NONE = no buffering, send tokens immediately
# LOW = buffer until word completion (space) - current behavior
# MEDIUM = buffer until 4 words OR punctuation (.!?;:)
# HIGH = buffer until punctuation (.!?;:)
PRE_TTS_BUFFERING_LEVEL=LOW
```

### Buffering Levels

#### NONE
- **Behavior**: Send tokens immediately as they arrive from the LLM
- **Use Case**: Maximum real-time responsiveness, but may result in choppy audio for incomplete words
- **Latency**: Lowest

#### LOW (Default)
- **Behavior**: Buffer until word completion (space character)
- **Use Case**: Good balance between responsiveness and audio quality
- **Latency**: Low

#### MEDIUM
- **Behavior**: Buffer until 4 words OR punctuation (.!?;:)
- **Use Case**: Better audio quality for short phrases while maintaining reasonable responsiveness
- **Latency**: Medium

#### HIGH
- **Behavior**: Buffer until punctuation (.!?;:)
- **Use Case**: Best audio quality for complete sentences and phrases
- **Latency**: Highest

## Implementation Details

### Code Location

The buffering logic is implemented in:
- [`voicebot_service.py`](../voicebot_service.py) - Main processing logic
- [`config.py`](../config.py) - Configuration handling

### Key Methods

1. **`_process_buffer_by_level()`** - Core buffering logic
2. **`process_llm_stream()`** - Main LLM stream processing with buffering

### Punctuation Characters

The following punctuation characters trigger buffer flushing in MEDIUM and HIGH levels:
- `.` - Period
- `!` - Exclamation mark  
- `?` - Question mark
- `;` - Semicolon
- `:` - Colon

## Testing

To test different buffering levels:

1. Update the `PRE_TTS_BUFFERING_LEVEL` in your `.env` file
2. Restart the application
3. Use the voicebot interface and observe the TTS behavior
4. Check application logs for buffering level confirmation

## Performance Considerations

- **NONE**: Best for low-latency requirements, but may have audio artifacts
- **LOW**: Good default for most use cases
- **MEDIUM**: Better for conversational applications
- **HIGH**: Best for applications where audio quality is critical

## Troubleshooting

If you encounter issues:

1. Verify the environment variable is set correctly
2. Check application logs for buffering level confirmation
3. Ensure the punctuation detection is working for your language
4. Test with different text inputs to verify behavior

## Example Log Output

When the system starts processing, you should see:
```
INFO:services.voicebot_wrapper.voicebot_service:Using TTS buffering level: LOW