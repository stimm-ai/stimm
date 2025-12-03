#!/usr/bin/env python3
"""
Test script to validate the WebRTC STT fix.

This script tests the complete audio chain:
1. VAD processing
2. Audio routing to STT
3. STT streaming
4. Data channel communication

Run this to verify the fix is working correctly.
"""

import asyncio
import logging
import time
import numpy as np
from services.vad.silero_service import SileroVADService
from services.stt.stt import STTService
from services.agents.event_loop import VoicebotEventLoop

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockTTSService:
    """Mock TTS service for testing"""
    def __init__(self):
        self.provider = None

class MockChatbotService:
    """Mock chatbot service for testing"""
    async def process_chat_message(self, *args, **kwargs):
        # Return empty generator for testing
        return
        yield

async def test_vad_to_stt_chain():
    """Test the complete VAD -> STT chain"""
    logger.info("🧪 Starting WebRTC STT chain test...")
    
    # Create services
    vad_service = SileroVADService()
    stt_service = STTService()  # Will use default agent
    tts_service = MockTTSService()
    chatbot_service = MockChatbotService()
    
    logger.info("✅ Services created")
    
    # Create output queue and event loop
    output_queue = asyncio.Queue()
    
    event_loop = VoicebotEventLoop(
        conversation_id="test-session",
        output_queue=output_queue,
        stt_service=stt_service,
        chatbot_service=chatbot_service,
        tts_service=tts_service,
        vad_service=vad_service
    )
    
    logger.info("✅ Event loop created")
    
    # Start the event loop
    await event_loop.start()
    logger.info("✅ Event loop started")
    
    # Generate test audio chunks (simulating speech)
    sample_rate = 16000
    chunk_duration = 0.03  # 30ms chunks
    
    # Create test audio data - simulated speech for 2 seconds
    num_chunks = int(2.0 / chunk_duration)  # 2 seconds of audio
    test_audio = []
    
    logger.info(f"🎵 Generating {num_chunks} test audio chunks...")
    
    for i in range(num_chunks):
        # Generate audio chunk (sine wave at 440Hz for speech simulation)
        t = np.linspace(0, chunk_duration, int(sample_rate * chunk_duration))
        
        # Create speech-like audio (multiple frequencies)
        chunk = (
            0.3 * np.sin(2 * np.pi * 440 * t) +  # Base frequency
            0.2 * np.sin(2 * np.pi * 880 * t) +  # Harmonic
            0.1 * np.sin(2 * np.pi * 1320 * t)   # Higher harmonic
        )
        
        # Apply envelope to simulate speech segments
        if i < num_chunks * 0.8:  # Speak for 80% of the time
            envelope = np.exp(-((t - chunk_duration/2) / (chunk_duration/4))**2)
            chunk *= envelope
        
        # Convert to int16
        chunk = (chunk * 32767).astype(np.int16)
        test_audio.append(chunk.tobytes())
    
    logger.info(f"✅ Generated {len(test_audio)} audio chunks ({len(test_audio) * chunk_duration:.1f}s)")
    
    # Process audio chunks through VAD and STT
    logger.info("🎤 Processing audio through VAD -> STT chain...")
    
    start_time = time.time()
    chunk_count = 0
    
    try:
        for audio_chunk in test_audio:
            chunk_count += 1
            
            # Process through event loop (VAD + STT)
            await event_loop.process_audio_chunk(audio_chunk)
            
            # Log progress
            if chunk_count % 50 == 0:
                logger.info(f"📊 Processed {chunk_count}/{len(test_audio)} chunks ({chunk_count/len(test_audio)*100:.1f}%)")
                logger.info(f"📈 Stats: {event_loop.audio_chunks_received} received, {event_loop.audio_chunks_sent_to_stt} sent to STT")
    
    except Exception as e:
        logger.error(f"❌ Error during audio processing: {e}")
        raise
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    logger.info(f"✅ Audio processing completed in {processing_time:.2f}s")
    
    # Check results
    logger.info("📋 Test Results:")
    logger.info(f"   - Audio chunks received: {event_loop.audio_chunks_received}")
    logger.info(f"   - Audio chunks sent to STT: {event_loop.audio_chunks_sent_to_stt}")
    logger.info(f"   - VAD events logged: {len(event_loop.vad_events_logged)}")
    logger.info(f"   - Last transcript: {event_loop.last_transcript_received}")
    
    # Validate the fix
    success = True
    errors = []
    
    if event_loop.audio_chunks_received == 0:
        errors.append("No audio chunks were received")
        success = False
    
    if event_loop.audio_chunks_sent_to_stt == 0:
        errors.append("No audio chunks were sent to STT (THIS WAS THE MAIN BUG)")
        success = False
    
    if event_loop.audio_chunks_sent_to_stt != event_loop.audio_chunks_received:
        errors.append(f"Mismatch: {event_loop.audio_chunks_sent_to_stt} sent but {event_loop.audio_chunks_received} received")
        success = False
    
    if len(event_loop.vad_events_logged) == 0:
        errors.append("No VAD events were logged")
        success = False
    
    if success:
        logger.info("🎉 TEST PASSED: WebRTC STT chain is working correctly!")
        logger.info("✅ The main bug (no audio sent to STT) has been fixed")
    else:
        logger.error("❌ TEST FAILED:")
        for error in errors:
            logger.error(f"   - {error}")
    
    # Stop event loop
    await event_loop.stop()
    logger.info("🧹 Event loop stopped")
    
    return success

async def main():
    """Main test function"""
    logger.info("🚀 Starting WebRTC STT Fix Validation Test")
    logger.info("=" * 60)
    
    try:
        success = await test_vad_to_stt_chain()
        
        logger.info("=" * 60)
        if success:
            logger.info("🎊 ALL TESTS PASSED - WebRTC STT is now functional!")
        else:
            logger.error("💥 TESTS FAILED - WebRTC STT still has issues")
            
        return success
        
    except Exception as e:
        logger.error(f"💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)