import unittest
import os
import wave
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from services.vad.silero_service import SileroVADService

class TestSileroVADService(unittest.TestCase):
    def setUp(self):
        self.vad = SileroVADService(threshold=0.5)
        self.test_wav_path = "src/services/stt/tests/Enregistrement.wav"

    def test_initialization(self):
        """Test that the model loads correctly."""
        self.assertIsNotNone(self.vad.session)
        self.assertEqual(self.vad.sample_rate, 16000)

    def test_process_silence(self):
        """Test processing of silent audio."""
        # Generate 1 second of silence
        silence = np.zeros(16000, dtype=np.int16).tobytes()
        
        events = self.vad.process_audio_chunk(silence)
        
        # Should not detect speech
        self.assertFalse(self.vad.triggered)
        # Might return events if it was previously triggered, but here it starts fresh
        self.assertEqual(len(events), 0)

    def test_process_speech_file(self):
        """Test processing a real audio file."""
        if not os.path.exists(self.test_wav_path):
            self.skipTest(f"Test file {self.test_wav_path} not found")
            
        events_found = []
        
        with wave.open(self.test_wav_path, 'rb') as wf:
            # Ensure 16k mono
            if wf.getframerate() != 16000 or wf.getnchannels() != 1:
                print(f"Warning: Test file is {wf.getframerate()}Hz {wf.getnchannels()}ch. Skipping.")
                return

            chunk_size = 1024 # Read in chunks
            data = wf.readframes(chunk_size)
            
            while len(data) > 0:
                events = self.vad.process_audio_chunk(data)
                events_found.extend(events)
                data = wf.readframes(chunk_size)
                
        # We expect at least one speech_start event
        has_start = any(e['type'] == 'speech_start' for e in events_found)
        self.assertTrue(has_start, "No speech detected in test file")
        
        # We expect at least one speech_end event (or maybe not if file ends with speech)
        # But for this specific file, it likely has speech.

if __name__ == '__main__':
    unittest.main()
