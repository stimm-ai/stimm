"""
Debug test for voicebot audio streaming pipeline.
Tests the complete pipeline: STT → RAG/LLM → TTS
"""

import asyncio
import json
import base64
import websockets
import numpy as np
import soundfile as sf
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class VoicebotAudioTester:
    def __init__(self):
        self.websocket_url = "ws://localhost:8001/api/voicebot/stream"
        self.audio_chunks_sent = 0
        self.audio_chunks_received = 0
        self.transcripts_received = []
        self.websocket = None
        
    async def load_test_audio(self):
        """Load test audio file and convert to PCM16 format"""
        # Use the test audio file from STT tests
        test_audio_path = Path(__file__).parent.parent / "stt" / "tests" / "Enregistrement.wav"
        
        if not test_audio_path.exists():
            logger.error(f"Test audio file not found: {test_audio_path}")
            return None
            
        try:
            # Load audio file
            audio_data, sample_rate = sf.read(test_audio_path, dtype='float32')
            
            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)
            
            # Resample to 16kHz if needed
            if sample_rate != 16000:
                from scipy import signal
                audio_data = signal.resample(audio_data,
                                           int(len(audio_data) * 16000 / sample_rate))
            
            # Convert to PCM16 (16-bit signed integers)
            audio_data = (audio_data * 32767).astype(np.int16)
            
            # Split into 40ms chunks (640 bytes at 16kHz)
            chunk_size = 16000 * 40 // 1000  # 640 samples for 40ms
            chunks = []
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                if len(chunk) == chunk_size:
                    chunks.append(chunk.tobytes())
            
            logger.info(f"Loaded {len(chunks)} audio chunks from {test_audio_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error loading audio file: {e}")
            return None

    async def test_audio_streaming(self):
        """Test the complete audio streaming pipeline"""
        logger.info("🎵 Testing voicebot audio streaming...")
        
        try:
            # Connect to voicebot WebSocket
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info("✅ Connected to voicebot WebSocket")
            
            # Send initialization message first
            init_message = {
                "type": "start_conversation",
                "conversation_id": None  # Let server generate one
            }
            await self.websocket.send(json.dumps(init_message))
            
            # Wait for conversation started response
            response = await self.websocket.recv()
            await self.handle_message(response)
            
            # Load test audio
            audio_chunks = await self.load_test_audio()
            if not audio_chunks:
                logger.error("❌ Failed to load test audio")
                return False
            
            # Start the test
            start_time = asyncio.get_event_loop().time()
            
            # Simulate voice activity detection
            # Send voice activity updates to trigger silence detection
            logger.info("🎤 Simulating voice activity detection...")
            
            # Send audio chunks as JSON messages (not raw binary)
            for i, chunk in enumerate(audio_chunks):
                # Send audio chunk
                audio_message = {
                    "type": "audio_chunk",
                    "data": base64.b64encode(chunk).decode('utf-8')
                }
                await self.websocket.send(json.dumps(audio_message))
                self.audio_chunks_sent += 1
                
                # Simulate voice activity for first 200 chunks (speech)
                if i < 200:
                    # Send voice activity (speech detected)
                    vad_message = {
                        "type": "voice_activity",
                        "is_voice": True,
                        "energy": 0.5  # High energy for speech
                    }
                    await self.websocket.send(json.dumps(vad_message))
                else:
                    # Send silence after chunk 200 (user stopped speaking)
                    vad_message = {
                        "type": "voice_activity",
                        "is_voice": False,
                        "energy": 0.01  # Low energy for silence
                    }
                    await self.websocket.send(json.dumps(vad_message))
                
                # Add small delay to simulate real-time streaming
                await asyncio.sleep(0.04)  # 40ms delay
                
                # Check for responses
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=0.01)
                    await self.handle_message(message)
                except asyncio.TimeoutError:
                    pass  # No message received, continue
                
                # Log progress every 10 chunks
                if (i + 1) % 10 == 0:
                    logger.info(f"📤 Sent {i + 1}/{len(audio_chunks)} audio chunks")
            
            # Wait for natural pipeline completion (no artificial timeout)
            logger.info("⏳ Waiting for natural pipeline completion...")
            
            # Continue receiving until natural completion
            while True:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=2.0)
                    await self.handle_message(message)
                except asyncio.TimeoutError:
                    # Natural completion - no more messages expected
                    logger.info("✅ Pipeline completed naturally")
                    break
            
            # Calculate test duration
            test_duration = asyncio.get_event_loop().time() - start_time
            
            # Print results
            logger.info("\n📊 Test Results:")
            logger.info(f"  - Audio chunks sent: {self.audio_chunks_sent}")
            logger.info(f"  - Audio chunks received: {self.audio_chunks_received}")
            logger.info(f"  - Transcripts received: {len(self.transcripts_received)}")
            logger.info(f"  - Test duration: {test_duration:.2f}s")
            
            # Check success criteria
            if self.audio_chunks_received > 0:
                logger.info("✅ SUCCESS: Audio streaming working!")
                return True
            else:
                logger.info("❌ FAILURE: No audio chunks received")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test failed with error: {e}")
            return False
        finally:
            if self.websocket:
                await self.websocket.close()
                logger.info("🔌 WebSocket closed")

    async def handle_message(self, message):
        """Handle incoming WebSocket messages"""
        try:
            # Check if it's binary audio data
            if isinstance(message, bytes):
                self.audio_chunks_received += 1
                logger.info(f"🎵 Received audio chunk #{self.audio_chunks_received} ({len(message)} bytes)")
                return
            
            # Parse JSON message
            data = json.loads(message)
            message_type = data.get('type', 'unknown')
            
            if message_type == 'conversation_started':
                logger.info(f"✅ Conversation started: {data}")
            elif message_type == 'vad_status':
                logger.info(f"📨 Received message: vad_status")
            elif message_type == 'status':
                status = data.get('status', 'unknown')
                logger.info(f"📊 Status: {status}")
            elif message_type == 'transcript':
                transcript = data.get('text', '')
                is_final = data.get('is_final', False)
                self.transcripts_received.append(transcript)
                logger.info(f"📝 Transcript ({'FINAL' if is_final else 'INTERMEDIATE'}): {transcript}")
            elif message_type == 'assistant_response':
                text = data.get('text', '')
                is_complete = data.get('is_complete', False)
                is_first_token = data.get('is_first_token', False)
                if is_first_token:
                    logger.info(f"🤖 First LLM token: {text}")
                elif is_complete:
                    logger.info(f"🤖 LLM response complete: {text}")
                else:
                    logger.info(f"🤖 LLM token: {text}")
            elif message_type == 'llm_token':
                token = data.get('token', '')
                logger.info(f"🤖 LLM Token: {token}")
            elif message_type == 'error':
                error = data.get('error', 'Unknown error')
                logger.error(f"❌ Error: {error}")
            else:
                logger.info(f"📨 Received message: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")

async def main():
    """Main test function"""
    tester = VoicebotAudioTester()
    success = await tester.test_audio_streaming()
    
    if success:
        logger.info("\n🎉 Voicebot audio streaming test PASSED!")
    else:
        logger.info("\n💥 Voicebot audio streaming test FAILED!")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())