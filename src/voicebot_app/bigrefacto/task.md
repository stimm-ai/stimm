# Task: Modernize Voicebot with Custom LiveKit-Inspired Architecture

## ✅ Phase 1: Silero VAD Implementation (COMPLETE)
- [x] Add dependencies (`onnxruntime`, `numpy`)
- [x] Create [SileroVADService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/vad/silero_service.py#17-212) class
- [x] Add unit tests
- [x] Rebuild Docker container and run tests

## ✅ Phase 2: Pipeline Integration (COMPLETE)
- [x] Modify [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py) to use [SileroVADService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/vad/silero_service.py#17-212)
- [x] Verify VAD performance (via integration tests)

## ✅ Phase 3: Central Event Loop & Audio Harmonization (COMPLETE)

### ✅ Implementation
- [x] **Audio Optimization**: Switch to Binary WebSocket & Standardize 16kHz
- [x] Design Audio Harmonization strategy (Binary WS, Sample Rate Standardization)
- [x] Analyze Orchestration patterns (Flag-based vs Event-loop)
- [x] Create [event_loop.py](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/event_loop.py) with state machine
- [x] Implement VAD-gated STT with pre-speech buffering
- [x] Create event-driven [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py)
- [x] Create [EVENT_LOOP_GUIDE.md](file:///home/etienne/repos/voicebot/src/voicebot_app/bigrefacto/EVENT_LOOP_GUIDE.md) documentation
- [x] Create integration examples

### ✅ Integration & Testing
- [x] Replace old VoicebotService with event-driven implementation
- [x] Fix class naming (VoicebotServiceV2 → VoicebotService)
- [x] Test with Docker Compose
- [x] Verify Silero VAD tests pass (2 passed, 1 skipped) ✓
- [x] Verify VAD integration tests pass (1 passed) ✓
- [x] Verify imports work correctly ✓

### 🔲 Remaining Tasks
- [x] **Frontend Testing** <!-- id: 28 -->
    - [x] Test with real frontend WebSocket connection
    - [x] Verify VAD events are properly triggered in UI
    - [x] Test interruption latency (speak while bot is responding)
    - [ ] Validate audio quality and responsiveness


## 🔮 Phase 4: WebRTC Migration (FUTURE)
- [ ] Add `aiortc` to requirements.txt
- [ ] Create `services/webrtc/signaling.py` (FastAPI routes for SDP exchange)
- [ ] Create `services/webrtc/media_handler.py` to wrap VAD/STT/TTS
- [ ] Update Frontend to use `RTCPeerConnection` instead of `WebSocket`
- [ ] Verify Echo Cancellation works natively in the browser

- [ ] **Performance Optimization** <!-- id: 32 -->
    - [ ] Measure and compare V1 vs V2 interruption latency
    - [ ] Tune pre-speech buffer size (currently 500ms)
    - [ ] Monitor STT API call reduction (target: ~60% less)
    - [ ] Profile CPU/memory usage improvements
    - [ ] Adjust VAD threshold if needed (currently 0.5)

- [ ] **Documentation** <!-- id: 38 -->
    - [ ] Update main README with event-driven architecture info
    - [ ] Document performance benchmarks
    - [ ] Add troubleshooting guide for common issues

---

## 📊 Current Status Summary

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Silero VAD | ✅ Complete | 100% |
| Phase 2: Pipeline Integration | ✅ Complete | 100% |
| Phase 3: Event Loop | ✅ Complete | 100% |
| Phase 4: WebRTC | 🔮 Future | 0% |

## 🎯 Test Results

### Docker Tests (Latest Run)
```
✓ test_silero_vad.py: 2 passed, 1 skipped
✓ test_vad_integration.py: 1 passed
✓ Imports: VoicebotService, VoicebotEventLoop
```

**Status**: All core tests passing! Event-driven architecture is live and validated.

## 📝 Next Steps

1. **Frontend Integration** - Test with real WebSocket client
2. **Performance Measurement** - Benchmark interruption latency
3. **Production Validation** - Monitor in real usage scenarios
