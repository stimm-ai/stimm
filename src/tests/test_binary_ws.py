import asyncio
import websockets
import json
import numpy as np
import unittest

class TestBinaryWebSocket(unittest.IsolatedAsyncioTestCase):
    async def test_binary_audio_streaming(self):
        uri = "ws://localhost:8001/api/voicebot/stream"
        
        try:
            async with websockets.connect(uri) as websocket:
                # 1. Start conversation
                await websocket.send(json.dumps({
                    "type": "start_conversation",
                    "agent_id": "default",
                    "session_id": "test-session"
                }))
                
                # Receive conversation_started
                response = await websocket.recv()
                data = json.loads(response)
                self.assertEqual(data["type"], "conversation_started")
                conversation_id = data["conversation_id"]
                print(f"Conversation started: {conversation_id}")
                
                # 2. Send binary audio chunks
                # Generate 1 second of silence (16kHz 16-bit mono)
                # 32 chunks of 1024 bytes (512 samples)
                chunk = np.zeros(512, dtype=np.int16).tobytes()
                
                for _ in range(10):
                    await websocket.send(chunk)
                    await asyncio.sleep(0.01)
                    
                # If we get here without error/disconnect, it works
                print("Successfully sent binary chunks")
                
        except ConnectionRefusedError:
            self.skipTest("Voicebot server not running on localhost:8001")
        except Exception as e:
            self.fail(f"WebSocket test failed: {e}")

if __name__ == '__main__':
    unittest.main()
