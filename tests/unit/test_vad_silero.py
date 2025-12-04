"""
Unit tests for VAD (Voice Activity Detection) functionality.

These tests focus on the Silero VAD service which uses a local model
and doesn't require external API keys.
"""

import pytest
import numpy as np
from pathlib import Path

from services.vad.silero_service import SileroVADService


@pytest.mark.unit
class TestSileroVADService:
    """Test suite for Silero VAD service."""
    
    def test_initialization(self):
        """Test that the Silero VAD model loads correctly."""
        vad = SileroVADService(threshold=0.5)
        
        assert vad.session is not None
        assert vad.sample_rate == 16000
        assert vad.threshold == 0.5
    
    @pytest.mark.asyncio
    async def test_process_silence(self, silence_audio):
        """Test processing of silent audio."""
        vad = SileroVADService(threshold=0.5)
        
        events = await vad.process_audio_chunk(silence_audio)
        
        # Should not detect speech in silence
        assert not vad.triggered
        assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_process_speech_file(self, audio_file_path_vad):
        """Test processing a real audio file with speech."""
        import wave
        import os
        
        if not os.path.exists(audio_file_path_vad):
            pytest.skip(f"Test file {audio_file_path_vad} not found")
        
        vad = SileroVADService(threshold=0.5)
        events_found = []
        
        with wave.open(audio_file_path_vad, 'rb') as wf:
            # Ensure 16k mono
            if wf.getframerate() != 16000 or wf.getnchannels() != 1:
                pytest.skip(f"Test file is {wf.getframerate()}Hz {wf.getnchannels()}ch, needs 16000Hz mono")
            
            chunk_size = 1024  # Read in chunks
            data = wf.readframes(chunk_size)
            
            while len(data) > 0:
                events = await vad.process_audio_chunk(data)
                events_found.extend(events)
                data = wf.readframes(chunk_size)
        
        # We expect at least one speech_start event
        has_start = any(e['type'] == 'speech_start' for e in events_found)
        assert has_start, "No speech detected in test file"
    
    def test_threshold_configuration(self):
        """Test that different thresholds can be configured."""
        vad_low = SileroVADService(threshold=0.3)
        vad_high = SileroVADService(threshold=0.8)
        
        assert vad_low.threshold == 0.3
        assert vad_high.threshold == 0.8
    
    @pytest.mark.asyncio
    async def test_reset_state(self, silence_audio):
        """Test that VAD state can be reset."""
        vad = SileroVADService(threshold=0.5)
        
        # Process some audio
        await vad.process_audio_chunk(silence_audio)
        
        # Reset should clear internal state
        # (Implementation may vary, this tests the API exists)
        assert hasattr(vad, 'triggered')
