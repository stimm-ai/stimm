# Event-Driven Voicebot Architecture (V2)

## Overview

The V2 architecture replaces the flag-based orchestration with a **central event loop** inspired by LiveKit Agents. This provides:

- ✅ **Cleaner state management** via explicit state machine (LISTENING, THINKING, SPEAKING)
- ✅ **Lower-latency interruptions** via event-driven cancellation
- ✅ **VAD-gated STT** to reduce hallucinations and cost
- ✅ **Pre-speech buffering** to capture first syllables
- ✅ **Simplified architecture** - no AudioSplitter needed

## Architecture Comparison

### V1 (Flag-Based)
```
Audio → AudioSplitter → ┬─→ STT (continuous)
                        └─→ VAD → Flags → Check flags in multiple tasks
```

**Issues:**
- Race conditions when checking flags
- Audio duplication (memory overhead)
- Complex debugging (3+ concurrent tasks)

### V2 (Event-Driven)
```
Audio → VAD → Events → Event Loop → State Machine
                ↓
              STT (gated - only during speech)
```

**Benefits:**
- Single source of truth (VAD events)
- No audio duplication
- Clear state transitions
- Immediate interruption handling

## Key Components

### 1. VoicebotEventLoop (`event_loop.py`)

Central orchestrator that:
- Processes audio through VAD first
- Maintains pre-speech buffer (500ms)
- Gates STT based on VAD state
- Manages state transitions via events
- Handles interruptions immediately

**State Machine:**
```
LISTENING ──(VAD Start)──→ LISTENING (recording)
          ──(VAD End)────→ THINKING
          ──(LLM Done)───→ SPEAKING
          ──(VAD Start)──→ INTERRUPTED → LISTENING
```

### 2. VoicebotServiceV2 (`voicebot_service_v2.py`)

Service layer that:
- Creates and manages event loops per conversation
- Initializes services (STT, TTS, LLM, VAD)
- Processes output queue and sends to WebSocket
- Handles conversation lifecycle

### 3. SileroVADService (`services/vad/silero_service.py`)

Neural VAD that:
- Provides superior noise immunity vs WebRTC VAD
- Returns probability + events (speech_start, speech_end)
- Maintains internal state for hysteresis
- Processes 32ms chunks (512 samples @ 16kHz)

## VAD-Gated STT Pattern

### How It Works

1. **All audio goes through VAD first**
   ```python
   events = vad_service.process_audio_chunk(chunk)
   ```

2. **Pre-speech buffer maintains context**
   - Circular buffer of last 15 chunks (~500ms)
   - Flushed to STT when speech starts
   - Ensures STT catches first syllable

3. **Only speech segments sent to STT**
   ```python
   if is_speech and is_recording:
       await stt_audio_queue.put(chunk)
   ```

4. **No post-speech padding**
   - Avoids STT hallucinations on silence
   - Clean cut when speech ends

### Benefits

- **Reduced STT cost**: Only process actual speech
- **Fewer hallucinations**: No silence processing
- **Better accuracy**: Pre-speech context preserved
- **Lower latency**: Immediate VAD response

## Integration Guide

### Option 1: Replace Existing Service

In `routes.py`, change:
```python
from .voicebot_service import VoicebotService, voicebot_service
```

To:
```python
from .voicebot_service_v2 import VoicebotServiceV2 as VoicebotService
from .voicebot_service_v2 import voicebot_service_v2 as voicebot_service
```

And update the processing call:
```python
# Old
await voicebot_service_instance.start_continuous_processing(conversation_id, audio_generator)

# New
await voicebot_service_instance.start_event_driven_processing(conversation_id, audio_generator)
```

### Option 2: Side-by-Side Testing

Create a new endpoint `/voicebot/stream_v2` that uses V2 while keeping V1 for comparison.

## Testing

### Unit Test Example

```python
import pytest
from services.voicebot_wrapper.event_loop import VoicebotEventLoop, AgentState

@pytest.mark.asyncio
async def test_vad_gated_stt():
    """Test that STT only receives audio during speech."""
    output_queue = asyncio.Queue()
    
    # Mock services
    stt_service = MockSTTService()
    vad_service = SileroVADService(threshold=0.5)
    
    event_loop = VoicebotEventLoop(
        conversation_id="test",
        output_queue=output_queue,
        stt_service=stt_service,
        vad_service=vad_service,
        # ... other services
    )
    
    await event_loop.start()
    
    # Send silence - should NOT reach STT
    silence = b'\x00' * 1024
    await event_loop.process_audio_chunk(silence)
    assert stt_service.chunks_received == 0
    
    # Send speech - should reach STT
    speech = generate_speech_audio()
    await event_loop.process_audio_chunk(speech)
    assert stt_service.chunks_received > 0
    
    await event_loop.stop()
```

### Integration Test

Use `tests/Enregistrement.wav` to test the full pipeline:

```python
import wave
import asyncio

async def test_full_pipeline():
    service = VoicebotServiceV2()
    conversation_id = service.create_conversation()
    
    async def audio_generator():
        with wave.open("tests/Enregistrement.wav", "rb") as wf:
            while True:
                frames = wf.readframes(512)
                if not frames:
                    break
                yield frames
    
    await service.start_event_driven_processing(conversation_id, audio_generator())
    
    # Check output queue for events
    # ...
```

## Performance Considerations

### Latency Breakdown

| Component | Latency | Notes |
|-----------|---------|-------|
| VAD Inference | <1ms | Silero on CPU |
| VAD Chunk Size | 32ms | 512 samples @ 16kHz |
| Pre-speech Buffer | 500ms | Flushed on speech start |
| Event Queue | <1ms | In-memory asyncio.Queue |
| **Total VAD Latency** | **~33ms** | Dominated by chunk size |

### Memory Usage

- **V1**: 2x audio buffer (STT + VAD copies)
- **V2**: 1x audio buffer + 500ms pre-speech buffer
- **Savings**: ~50% reduction in audio memory

## Troubleshooting

### Issue: STT not receiving audio

**Check:**
1. VAD threshold too high → Lower `threshold` in SileroVADService
2. Audio format mismatch → Ensure 16kHz, 16-bit PCM mono
3. VAD model not loaded → Check logs for model download errors

### Issue: First syllable cut off

**Fix:**
- Increase `max_pre_speech_buffer_size` in VoicebotEventLoop
- Current: 15 chunks (~500ms)
- Recommended: 15-20 chunks

### Issue: Bot keeps talking during interruption

**Check:**
1. VAD events reaching event loop → Add logging in `_handle_vad_start`
2. Interruption logic → Verify `_handle_interruption` cancels tasks
3. TTS task cancellation → Check if TTS service respects cancellation

## Next Steps

1. **Test with real audio** - Use frontend to validate end-to-end
2. **Measure latency** - Compare V1 vs V2 interruption speed
3. **Optimize buffering** - Tune pre-speech buffer size based on testing
4. **Phase 4: WebRTC** - Migrate from WebSocket to aiortc for lower latency

## References

- [LiveKit Agents Architecture](https://github.com/livekit/agents)
- [Silero VAD Paper](https://arxiv.org/abs/2104.04045)
- [Implementation Plan](./implementation_plan.md)
- [Analysis & Diff](./analysis_and_diff.md)
