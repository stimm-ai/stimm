# WebRTC Voice Interface Testing Guide

## 🔍 Test Scenarios

### 1. Basic Connection Test
- **URL**: http://localhost:3000/voicebot
- **Steps**:
  1. Select an agent from dropdown
  2. Click "🎤 Start Conversation" 
  3. Monitor connection status and ICE state
- **Expected**: WebRTC connection establishes successfully

### 2. VAD Visualization Test
- **Test**: Speak and verify energy level updates
- **Expected**: VAD energy bar responds to voice input

### 3. Audio Quality Test  
- **Test**: Record and play back voice samples
- **Expected**: Clear audio with echo cancellation working

### 4. STT Integration Test
- **Test**: Speak test phrases and verify transcription
- **Expected**: Real-time transcription appears in UI

### 5. TTS Integration Test
- **Test**: Trigger TTS response from agent
- **Expected**: Audio plays through WebRTC audio track

### 6. Interruption Test
- **Test**: Speak while TTS is playing
- **Expected**: VAD detects speech and interrupts response

## 🐛 Known Issues

### Resolved
- ✅ Frontend Select component empty value error (fixed)
- ✅ WebRTC signaling backend connectivity (fixed)
- ✅ Missing dependencies (aiortc, av installed)
- ✅ Docker container communication URLs (voicebot-app)

### Potential Issues to Monitor
- 🔍 ICE connectivity between Docker containers
- 🔍 Audio quality in production environment
- 🔍 VAD sensitivity threshold calibration
- 🔍 STT/TTS service timeout handling

## 📊 Performance Metrics

- **Connection Time**: Target < 2 seconds
- **VAD Latency**: Target < 100ms
- **STT Response**: Target < 500ms for short phrases
- **Interruption Latency**: Target < 200ms

## 🛠️ Troubleshooting

### Connection Fails
1. Check Docker network connectivity
2. Verify ICE servers configuration
3. Monitor backend logs for signaling errors

### Poor Audio Quality
1. Check microphone permissions
2. Verify WebRTC audio constraints
3. Monitor network bandwidth

### VAD Not Triggering
1. Check microphone input levels
2. Verify VAD threshold configuration
3. Monitor console for VAD events