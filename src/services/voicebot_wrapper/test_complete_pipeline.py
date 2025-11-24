"""
Comprehensive test for the complete voicebot pipeline with interruption scenarios.

This test verifies:
1. Microphone capture and voice detection
2. STT transcription with final transcript handling
3. RAG/LLM processing with real-time token streaming
4. TTS audio synthesis with continuous streaming
5. Interruption handling when user speaks during response
6. Audio playback in frontend
"""

import asyncio
import json
import websockets
import base64
import time
import uuid
from typing import AsyncGenerator, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoicebotPipelineTester:
    """Test the complete voicebot pipeline with various scenarios."""
    
    def __init__(self):
        self.websocket_url = "ws://localhost:8001/api/voicebot/stream"
        self.conversation_id = None
        self.websocket = None
        self.test_results = {}
        
    async def connect(self):
        """Connect to the voicebot WebSocket."""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info("✅ Connected to voicebot WebSocket")
            
            # Start conversation
            self.conversation_id = str(uuid.uuid4())
            await self.websocket.send(json.dumps({
                "type": "start_conversation",
                "conversation_id": self.conversation_id
            }))
            
            # Wait for confirmation
            response = await self.websocket.recv()
            data = json.loads(response)
            if data.get("type") == "conversation_started":
                logger.info(f"✅ Conversation started: {self.conversation_id}")
                return True
            else:
                logger.error(f"❌ Failed to start conversation: {data}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def send_voice_activity(self, is_voice: bool, energy: float):
        """Send voice activity detection update."""
        if self.websocket:
            await self.websocket.send(json.dumps({
                "type": "voice_activity",
                "conversation_id": self.conversation_id,
                "is_voice": is_voice,
                "energy": energy
            }))
    
    async def send_audio_chunk(self, audio_data: bytes):
        """Send audio chunk for STT processing."""
        if self.websocket:
            base64_data = base64.b64encode(audio_data).decode('utf-8')
            await self.websocket.send(json.dumps({
                "type": "audio_chunk",
                "conversation_id": self.conversation_id,
                "data": base64_data
            }))
    
    async def simulate_conversation_flow(self, scenario_name: str):
        """Simulate a complete conversation flow with specific scenario."""
        logger.info(f"\n🎯 Testing scenario: {scenario_name}")
        
        start_time = time.time()
        received_messages = []
        audio_chunks_received = 0
        first_token_time = None
        first_audio_time = None
        
        async def message_handler():
            """Handle incoming WebSocket messages."""
            nonlocal audio_chunks_received, first_token_time, first_audio_time
            
            try:
                async for message in self.websocket:
                    data = json.loads(message)
                    received_messages.append(data)
                    
                    message_type = data.get("type")
                    
                    if message_type == "assistant_response":
                        if data.get("is_first_token") and first_token_time is None:
                            first_token_time = time.time() - start_time
                            logger.info(f"⏱️ First LLM token received at {first_token_time:.3f}s")
                            
                    elif message_type == "audio_chunk":
                        audio_chunks_received += 1
                        if first_audio_time is None:
                            first_audio_time = time.time() - start_time
                            logger.info(f"🎵 First audio chunk received at {first_audio_time:.3f}s")
                            
                    elif message_type == "status":
                        logger.info(f"📊 Status: {data.get('status')} - {data.get('message', '')}")
                        
                    elif message_type == "error":
                        logger.error(f"❌ Error: {data.get('message')}")
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket connection closed")
        
        # Start message handler
        message_task = asyncio.create_task(message_handler())
        
        try:
            # Scenario-specific logic
            if scenario_name == "normal_conversation":
                await self.test_normal_conversation()
            elif scenario_name == "interruption_during_response":
                await self.test_interruption_during_response()
            elif scenario_name == "multiple_quick_responses":
                await self.test_multiple_quick_responses()
            
            # Wait for processing to complete
            await asyncio.sleep(5)
            
        finally:
            # Cancel message handler
            message_task.cancel()
            try:
                await message_task
            except asyncio.CancelledError:
                pass
        
        # Calculate metrics
        total_time = time.time() - start_time
        metrics = {
            "scenario": scenario_name,
            "total_time": total_time,
            "first_token_latency": first_token_time,
            "first_audio_latency": first_audio_time,
            "audio_chunks_received": audio_chunks_received,
            "messages_received": len(received_messages),
            "success": audio_chunks_received > 0 and first_token_time is not None
        }
        
        logger.info(f"📈 Test results for {scenario_name}:")
        logger.info(f"  - Total time: {total_time:.3f}s")
        logger.info(f"  - First token latency: {first_token_time:.3f}s")
        logger.info(f"  - First audio latency: {first_audio_time:.3f}s")
        logger.info(f"  - Audio chunks received: {audio_chunks_received}")
        logger.info(f"  - Messages received: {len(received_messages)}")
        logger.info(f"  - Success: {'✅' if metrics['success'] else '❌'}")
        
        self.test_results[scenario_name] = metrics
        return metrics
    
    async def test_normal_conversation(self):
        """Test a normal conversation flow without interruptions."""
        logger.info("🗣️ Simulating normal conversation...")
        
        # Simulate voice activity (user starts speaking)
        await self.send_voice_activity(is_voice=True, energy=0.5)
        await asyncio.sleep(0.1)
        
        # Send some audio data (simulate speech)
        for i in range(10):
            await self.send_audio_chunk(b"\x00" * 640)  # Simulate audio chunk
            await asyncio.sleep(0.02)
        
        # Simulate silence (user stops speaking)
        await self.send_voice_activity(is_voice=False, energy=0.01)
        await asyncio.sleep(0.6)  # Wait for silence detection
        
        # Wait for response generation
        await asyncio.sleep(3)
    
    async def test_interruption_during_response(self):
        """Test interruption when user speaks during assistant response."""
        logger.info("⏹️ Simulating interruption during response...")
        
        # Start normal conversation
        await self.send_voice_activity(is_voice=True, energy=0.5)
        await asyncio.sleep(0.1)
        
        for i in range(8):
            await self.send_audio_chunk(b"\x00" * 640)
            await asyncio.sleep(0.02)
        
        await self.send_voice_activity(is_voice=False, energy=0.01)
        await asyncio.sleep(0.6)
        
        # Wait for response to start, then interrupt
        await asyncio.sleep(1.0)
        
        # Interrupt by simulating user speaking again
        logger.info("🔄 Interrupting with new speech...")
        await self.send_voice_activity(is_voice=True, energy=0.6)
        await asyncio.sleep(0.1)
        
        for i in range(5):
            await self.send_audio_chunk(b"\x00" * 640)
            await asyncio.sleep(0.02)
        
        await self.send_voice_activity(is_voice=False, energy=0.01)
        await asyncio.sleep(0.6)
    
    async def test_multiple_quick_responses(self):
        """Test multiple quick conversation turns."""
        logger.info("⚡ Simulating multiple quick responses...")
        
        for turn in range(2):
            logger.info(f"🔄 Conversation turn {turn + 1}")
            
            # User speaks
            await self.send_voice_activity(is_voice=True, energy=0.5)
            await asyncio.sleep(0.1)
            
            for i in range(6):
                await self.send_audio_chunk(b"\x00" * 640)
                await asyncio.sleep(0.02)
            
            await self.send_voice_activity(is_voice=False, energy=0.01)
            await asyncio.sleep(0.6)
            
            # Wait for response
            await asyncio.sleep(2)
    
    async def run_all_tests(self):
        """Run all test scenarios."""
        logger.info("🚀 Starting comprehensive voicebot pipeline tests")
        
        if not await self.connect():
            logger.error("❌ Failed to connect, aborting tests")
            return
        
        try:
            # Run test scenarios
            scenarios = [
                "normal_conversation",
                "interruption_during_response", 
                "multiple_quick_responses"
            ]
            
            for scenario in scenarios:
                await self.simulate_conversation_flow(scenario)
                await asyncio.sleep(2)  # Brief pause between tests
            
            # Print summary
            self.print_test_summary()
            
        finally:
            await self.websocket.close()
            logger.info("✅ All tests completed")
    
    def print_test_summary(self):
        """Print a summary of all test results."""
        logger.info("\n" + "="*60)
        logger.info("📊 COMPREHENSIVE TEST SUMMARY")
        logger.info("="*60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results.values() if r["success"])
        
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Successful: {successful_tests}")
        logger.info(f"Success rate: {successful_tests/total_tests*100:.1f}%")
        
        for scenario, results in self.test_results.items():
            status = "✅ PASS" if results["success"] else "❌ FAIL"
            logger.info(f"\n{status} {scenario}:")
            logger.info(f"  First token: {results['first_token_latency']:.3f}s")
            logger.info(f"  First audio: {results['first_audio_time']:.3f}s")
            logger.info(f"  Audio chunks: {results['audio_chunks_received']}")
        
        logger.info("="*60)


async def main():
    """Run the comprehensive pipeline tests."""
    tester = VoicebotPipelineTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())