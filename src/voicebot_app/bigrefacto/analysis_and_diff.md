# Deep Analysis: Voicebot vs LiveKit Agents

## 1. Architecture Overview

| Feature | Voicebot (Current) | LiveKit Agents (Target Inspiration) |
| :--- | :--- | :--- |
| **Transport** | WebSocket (TCP - Custom Protocol) | WebRTC (UDP - Standard Real-time Media) |
| **Audio Format** | **Current**: PCM wrapped in Base64 JSON (33% overhead). | **Target**: Opus (compressed) or Raw PCM (binary) via MediaTracks. |
| **VAD** | Backend `webrtcvad` (Google) | Backend `Silero VAD` (ONNX) |
| **Orchestration** | [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#87-682) (Background Tasks + Shared State) | `Worker` Loop (Event-driven: `JobContext`, `Agent`) |
| **Interruption** | **Implemented**: Background task cancels TTS on speech start. | **Event-based**: `START_OF_SPEECH` event triggers immediate cancellation in the main loop. |
| **Echo Cancellation** | None (Relies on hardware/browser default) | Client-side AEC (Standard WebRTC feature) |

## 2. Deep Dive: Voice Activity Detection (VAD)

### Voicebot Implementation
- **Library**: `webrtcvad` (Legacy WebRTC VAD).
- **Logic**:
    - [WebRTCVADService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/vad_service.py#17-179) processes 30ms chunks.
    - Uses a simple counter for "consecutive voice frames" to trigger start/end.
    - **Pros**: Fast, lightweight.
    - **Cons**: Less accurate than neural models (Silero), sensitive to noise, strict 16kHz requirement.

### LiveKit Implementation (`livekit-plugins-silero`)
- **Library**: `onnxruntime` running Silero VAD model.
- **Logic**:
    - `VADStream` class wraps the model.
    - Maintains an internal buffer of audio.
    - Probabilistic output (0.0 to 1.0) rather than binary.
    - **Pros**: 
        - **Neural Network based**: Much more robust to background noise than WebRTC's statistical GMM.
        - **Latency**: **Identical to WebRTC**. Both operate on ~30ms audio chunks. Silero's inference time on a modern CPU is <1ms, so the total latency is dominated by the chunk size (30ms), not the processing time.
        - **Accuracy**: Significantly fewer false positives/negatives in noisy environments.
    - **Cons**: Slightly higher CPU usage than `webrtcvad`.

## 3. Deep Dive: SIP & Echo Cancellation

### The Challenge
- **SIP/VoIP**: Often involves PSTN gateways where the "client" is a dumb phone without AEC.
- **WebSocket (TCP)**: 
    - **Pros**: Simple to implement.
    - **Cons**: **Head-of-line blocking** (one lost packet delays everything) causes latency spikes. No built-in AEC or congestion control.
- **WebRTC (UDP)**:
    - **Pros**: **Low Latency** (drops late packets), built-in **AEC**, **Opus** compression (low bandwidth).
    - **Cons**: Complex to implement from scratch (requires ICE, DTLS, SRTP).

### LiveKit's Approach
- **Standard**: Uses **WebRTC** for Transport.
- **Recommendation**: 
    - **Switching to WebRTC** is the "Gold Standard" for voice. It solves many audio quality issues (echo, latency, packet loss).
    - **Implementation**: You can use `aiortc` (Python WebRTC library) to build a custom WebRTC server without LiveKit Cloud, but it is a significant engineering effort.
    - **Decision**: If you stick to WebSocket, you accept TCP latency and lack of standard AEC. If you switch to WebRTC, you gain quality but increase complexity.

## 3. Deep Dive: Agent Loop & Orchestration

### Voicebot Implementation
- **State Machine**: [ConversationState](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#27-85) holds flags like `is_user_speaking`, `is_bot_responding`.
- **Concurrency**:
    - [_process_continuous_stt](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#217-269) runs in one task.
    - [_monitor_speech_boundaries](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#270-336) runs in another.
    - [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#87-682) manually coordinates them.
- **Data Flow**: [AudioSplitter](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#166-213) duplicates the input stream into two queues (one for STT, one for VAD).

### LiveKit Implementation
- **Pattern**: Pipeline / Worker.
- **Concurrency**:
    - `VADStream` is the "source of truth" for turn-taking.
    - The Agent loop `async for event in vad_stream:` waits for events.
    - When `START_OF_SPEECH` is received, the agent *immediately* interrupts any running "Activity" (LLM generation or TTS playback).
- **Data Flow**: Audio frames flow into VAD. VAD events drive the logic. STT is often triggered *after* VAD detects speech (or runs in parallel with VAD gating).

## 4. Deep Dive: Orchestration & State Management

### Current Voicebot: "Concurrent Tasks + Shared Flags"
- **Structure**: You run multiple independent `asyncio.Task`s:
    1.  [_process_continuous_stt](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#217-269): Reads audio, updates `current_transcript`.
    2.  [_monitor_speech_boundaries](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#270-336): Reads audio (via splitter), updates `is_user_speaking` flag.
    3.  [_process_with_rag_llm](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#376-519): Generates text, checks `is_user_speaking` to abort.
- **Pros**: Parallelism is easy to start with.
- **Cons**: 
    - **Race Conditions**: Tasks must constantly check flags (`if conversation.is_user_speaking: break`). If a check is missed or delayed, the bot might keep talking for a split second too long.
    - **Complexity**: Debugging "why did the bot stop?" requires checking the state of 3 different tasks and several flags.
    - **Inefficiency**: [AudioSplitter](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#166-213) duplicates data, doubling memory/CPU for audio handling.

### LiveKit Agents: "Central Event Loop"
- **Structure**: A single "Main Loop" consumes events from the VAD stream.
    ```python
    async for event in vad_stream:
        if event.type == START_OF_SPEECH:
            # 1. Immediate Action: Cancel playback
            current_task.cancel()
            # 2. State Transition: LISTENING
        elif event.type == END_OF_SPEECH:
            # 1. Trigger LLM
            current_task = asyncio.create_task(generate_reply())
            # 2. State Transition: THINKING
    ```
- **Pros**:
    - **Single Source of Truth**: The VAD event *is* the trigger. No polling flags.
    - **Clean State Machine**: Transitions are explicit.
    - **Low Latency**: Interruption happens the millisecond `START_OF_SPEECH` is yielded.

### Recommendation
Refactor [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#87-682) to the **Event Loop** pattern. It simplifies the code significantly and makes "Interruption" a first-class citizen rather than an exception case.
