# Implementation Plan: Custom LiveKit-Inspired Voicebot

## Goal
Modernize the [voicebot](file:///home/etienne/repos/voicebot/src/voicebot_app/main.py#178-182) repository by implementing a **custom Silero VAD** and an **Event-Driven Orchestrator**, inspired by LiveKit Agents, while retaining the existing WebSocket/FastAPI architecture.

## User Review Required
> [!IMPORTANT]
> **Custom Implementation**: We are NOT using `livekit-agents` SDK directly. We are building a custom `SileroVADService` and `AgentLoop` that mimics its behavior.

> [!NOTE]
> **Echo Cancellation (SIP/VoIP)**: 
> - **Standard**: We enforce Client-side AEC for Web/Mobile clients.
> - **SIP**: For SIP endpoints without AEC, we recommend enabling DSP on the SIP Gateway or using a noise suppression plugin. Building custom server-side AEC over WebSocket is **not recommended** due to latency/sync issues.

## Proposed Changes

### 1. New Component: `SileroVADService`
- **Why Silero?**: It uses a neural network (vs WebRTC's statistical model), offering superior noise immunity and accuracy, which is critical for a voicebot to avoid interrupting on background noise.
- **Location**: `src/voicebot_app/services/vad/silero_service.py`
- **Dependency**: `onnxruntime`, `numpy`.
- **Functionality**:
    - Load Silero VAD ONNX model.
    - Process raw PCM audio chunks.
    - Maintain internal state/buffer.
    - Return probability and speech start/end events.

### 2. Refactor: [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#87-682) -> `EventDrivenVoicebot`
- **Location**: [src/voicebot_app/services/voicebot_wrapper/voicebot_service.py](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py)
- **Changes**:
    - Remove [AudioSplitter](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#166-213).
    - Implement an `AsyncIterator` loop that processes audio.
    - **State Machine**:
        - `WAITING_FOR_SPEECH` -> (VAD Start) -> `LISTENING`
        - `LISTENING` -> (VAD End) -> `THINKING`
        - `THINKING` -> (LLM Stream) -> `SPEAKING`
        - `SPEAKING` -> (VAD Start) -> `INTERRUPTED` -> `LISTENING`

### 3. Audio Pipeline Optimization
- **Current**: Audio -> Splitter -> (STT, VAD).
- **New**: Audio -> VAD Buffer -> (Gate Open) -> STT.
- **Benefit**: STT only receives valid speech segments, reducing hallucinations and cost.

### 4. Architecture Upgrade: WebSocket -> WebRTC (`aiortc`)
- **Goal**: Replace custom WebSocket transport with standard WebRTC.
- **Library**: `aiortc` (Python).
- **Components**:
    - **Signaling Server**: New HTTP/WS endpoint to exchange SDP offers/answers.
    - **MediaHandler**: Receives `AudioStreamTrack` (Opus/PCM), performs VAD/STT, and sends back `AudioStreamTrack` (TTS).
- **Benefits**:
    - **UDP Transport**: Lower latency, no head-of-line blocking.
    - **Standard AEC**: Browsers enable AEC automatically for WebRTC tracks.
    - **Opus Codec**: Better quality at lower bandwidth than raw PCM.

## Implementation Steps

### Phase 1: Silero VAD Implementation
- [ ] Add `onnxruntime` and `numpy` to [requirements.txt](file:///home/etienne/repos/voicebot/src/voicebot_app/requirements.txt).
- [ ] Download Silero VAD model (or include in docker build).
- [ ] Create `SileroVADService` class.
- [ ] Create unit tests with `tests/Enregistrement.wav`.

### Phase 2: Pipeline Integration (WebSocket)
- [ ] Modify [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#87-682) to use `SileroVADService` instead of [WebRTCVADService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/vad_service.py#17-179).
- [ ] Verify VAD performance (latency/accuracy) via WebSocket logs.

### Phase 3: Central Event Loop & Audio Harmonization
- [x] **Audio Optimization**:
    - [x] Switch WebSocket from JSON (Base64) to **Binary Mode** for audio chunks.
    - [x] Standardize internal audio passing to `16kHz / 16-bit Mono`.
- [ ] **Event Loop Implementation**:
    - Create `VoicebotEventLoop` class.
    - Implement `async for event in vad_stream:` pattern.
    - **Latency Focus**: Ensure `START_OF_SPEECH` event triggers `tts_task.cancel()` **synchronously** (or immediately awaited) to match current responsiveness. Avoid intermediate queues where possible.
- [ ] **VAD-Gated STT**:
    - Only forward audio to STT when VAD is active (reduces load).
    - *Optimization*: Keep a small "pre-speech" buffer (e.g. 200ms) to ensure STT catches the first syllable, but don't buffer more than necessary.

### Phase 4: WebRTC Migration (`aiortc`)
- [ ] Add `aiortc` to [requirements.txt](file:///home/etienne/repos/voicebot/src/voicebot_app/requirements.txt).
- [ ] Create `services/webrtc/signaling.py` (FastAPI routes for SDP exchange).
- [ ] Create `services/webrtc/media_handler.py` to wrap VAD/STT/TTS in `MediaStreamTrack`.
- [ ] Update Frontend ([voicebot.js](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/static/voicebot.js)) to use `RTCPeerConnection` instead of `WebSocket`.
- [ ] Verify Echo Cancellation works natively in the browser.

## Verification Plan

### Automated Tests
- **VAD Accuracy**: Run `SileroVADService` against test audio and verify it detects speech segments correctly.
- **Latency**: Measure processing time per frame.

### Manual Verification
- **Real-time Interaction**: Speak to the bot and verify:
    - It detects speech start quickly (Interruption).
    - It detects speech end correctly (Turn taking).
    - It doesn't respond to background noise (Silero advantage).
