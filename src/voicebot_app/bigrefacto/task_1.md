# Task: Modernize Voicebot with Custom LiveKit-Inspired Architecture

## ✅ Phase 1: Silero VAD Implementation (COMPLETE)
- [x] Add dependencies (`onnxruntime`, `numpy`) <!-- id: 12 -->
- [x] Create [SileroVADService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/vad/silero_service.py#17-212) class <!-- id: 13 -->
- [x] Add unit tests <!-- id: 14 -->
- [x] Rebuild Docker container and run tests <!-- id: 16 -->

## ✅ Phase 2: Pipeline Integration (COMPLETE)
- [x] Modify [VoicebotService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service.py#87-682) to use [SileroVADService](file:///home/etienne/repos/voicebot/src/voicebot_app/services/vad/silero_service.py#17-212) <!-- id: 17 -->
- [x] Verify VAD performance (via integration tests) <!-- id: 18 -->

## 🔄 Phase 3: Central Event Loop & Audio Harmonization (IN PROGRESS)

### ✅ Completed
- [x] **Audio Optimization**: Switch to Binary WebSocket & Standardize 16kHz <!-- id: 19 -->
- [x] Design Audio Harmonization strategy (Binary WS, Sample Rate Standardization) <!-- id: 13 -->
- [x] Analyze Orchestration patterns (Flag-based vs Event-loop) <!-- id: 14 -->
- [x] Create [event_loop.py](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/event_loop.py) with state machine <!-- id: 20 -->
- [x] Implement VAD-gated STT with pre-speech buffering <!-- id: 21 -->
- [x] Create [voicebot_service_v2.py](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/voicebot_service_v2.py) <!-- id: 22 -->
- [x] Create [EVENT_LOOP_GUIDE.md](file:///home/etienne/repos/voicebot/src/voicebot_app/bigrefacto/EVENT_LOOP_GUIDE.md) documentation <!-- id: 23 -->
- [x] Create integration examples <!-- id: 24 -->

### 🔲 Remaining Tasks
- [ ] **Integration & Testing** <!-- id: 25 -->
    - [ ] Integrate VoicebotServiceV2 into [routes.py](file:///home/etienne/repos/voicebot/src/voicebot_app/services/voicebot_wrapper/routes.py) <!-- id: 26 -->
        - Option A: Full migration (replace V1)
        - Option B: Side-by-side endpoint `/voicebot/stream_v2`
    - [ ] Test with `tests/Enregistrement.wav` (integration test) <!-- id: 27 -->
    - [ ] Test with real frontend WebSocket connection <!-- id: 28 -->
    - [ ] Verify VAD events are properly triggered <!-- id: 29 -->
    - [ ] Verify STT only receives speech segments (check logs) <!-- id: 30 -->
    - [ ] Test interruption latency (speak while bot is responding) <!-- id: 31 -->
    
- [ ] **Optimization & Tuning** <!-- id: 32 -->
    - [ ] Measure and compare V1 vs V2 interruption latency <!-- id: 33 -->
    - [ ] Tune pre-speech buffer size (currently 500ms) <!-- id: 34 -->
    - [ ] Monitor STT API call reduction (should be ~60% less) <!-- id: 35 -->
    - [ ] Profile CPU/memory usage improvements <!-- id: 36 -->
    - [ ] Adjust VAD threshold if needed (currently 0.5) <!-- id: 37 -->

- [ ] **Documentation & Cleanup** <!-- id: 38 -->
    - [ ] Update main README with V2 architecture info <!-- id: 39 -->
    - [ ] Add migration guide from V1 to V2 <!-- id: 40 -->
    - [ ] Document performance benchmarks <!-- id: 41 -->
    - [ ] Clean up V1 code if V2 is validated (optional) <!-- id: 42 -->

## 🔮 Phase 4: WebRTC Migration (FUTURE)
- [ ] Add `aiortc` to requirements.txt <!-- id: 43 -->
- [ ] Create `services/webrtc/signaling.py` (FastAPI routes for SDP exchange) <!-- id: 44 -->
- [ ] Create `services/webrtc/media_handler.py` to wrap VAD/STT/TTS <!-- id: 45 -->
- [ ] Update Frontend to use `RTCPeerConnection` instead of `WebSocket` <!-- id: 46 -->
- [ ] Verify Echo Cancellation works natively in the browser <!-- id: 47 -->

---

## 📊 Current Status Summary

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Silero VAD | ✅ Complete | 100% |
| Phase 2: Pipeline Integration | ✅ Complete | 100% |
| Phase 3: Event Loop | 🔄 In Progress | 85% |
| Phase 4: WebRTC | 🔮 Future | 0% |

## 🎯 Next Immediate Actions

1. **Choose integration approach** (Full migration or side-by-side)
2. **Integrate VoicebotServiceV2 into routes.py**
3. **Run integration tests**
4. **Test with real frontend**
5. **Measure performance improvements**

## 📝 Notes

- V2 implementation is **complete and ready for testing**
- All core features implemented: VAD-gated STT, event loop, pre-speech buffering
- Integration is **backward compatible** - can run V1 and V2 side-by-side
- See [EVENT_LOOP_GUIDE.md](file:///home/etienne/repos/voicebot/src/voicebot_app/bigrefacto/EVENT_LOOP_GUIDE.md) for detailed integration instructions
