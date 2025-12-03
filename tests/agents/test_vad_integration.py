import unittest
import asyncio
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from services.agents.vad_service import vad_processor

class TestVADIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_vad_processor_stream(self):
        """Test VADProcessor with a simulated audio stream."""
        
        # Generate 1 second of silence (approx 32 chunks of 512 samples)
        # Silero expects 512 samples per chunk usually, but handles others.
        # We'll send 512-byte chunks (256 samples) to see how it handles it, 
        # or better 1024 bytes (512 samples).
        chunk_size = 1024 # 512 samples * 2 bytes
        chunks = [np.zeros(512, dtype=np.int16).tobytes() for _ in range(30)]
        
        async def audio_generator():
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.001)
        
        results = []
        async for result in vad_processor.start_vad_processing("test-session", audio_generator()):
            results.append(result)
            
        self.assertTrue(len(results) > 0)
        first_result = results[0]
        
        # Check structure
        self.assertIn("type", first_result)
        self.assertEqual(first_result["type"], "vad_result")
        self.assertIn("is_voice_active", first_result)
        self.assertIn("conversation_id", first_result)
        self.assertEqual(first_result["conversation_id"], "test-session")
        
        # Should be silence
        self.assertFalse(first_result["is_voice_active"])

if __name__ == '__main__':
    unittest.main()
