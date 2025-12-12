"""
Unit tests for audio utility functions.

These tests verify audio processing utilities like PCM conversion,
chunking, and format validation.
"""

import wave
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import (
    CHUNK_BYTES,
    CHUNK_DURATION_MS,
    CHUNK_SIZE,
    STREAM_SAMPLE_RATE,
)


@pytest.mark.unit
class TestAudioUtils:
    """Test suite for audio utility functions."""

    def test_audio_constants(self):
        """Test that audio constants are correctly defined."""
        assert STREAM_SAMPLE_RATE == 16000
        assert CHUNK_DURATION_MS == 40
        assert CHUNK_SIZE == 640  # 16000 * 40 / 1000
        assert CHUNK_BYTES == 1280  # 640 * 2 bytes

    def test_pcm16_loading(self, audio_file_path_vad):
        """Test loading PCM16 audio from WAV file."""
        with wave.open(audio_file_path_vad, "rb") as wav_file:
            # Verify format
            assert wav_file.getnchannels() == 1, "Audio must be mono"
            assert wav_file.getsampwidth() == 2, "Audio must be 16-bit"
            assert wav_file.getframerate() == STREAM_SAMPLE_RATE

            # Read audio data
            pcm_data = wav_file.readframes(wav_file.getnframes())

            # Verify data is not empty
            assert len(pcm_data) > 0
            # Verify data length is even (16-bit samples)
            assert len(pcm_data) % 2 == 0

    def test_audio_chunking(self, audio_pcm_data):
        """Test chunking audio data into fixed-size chunks."""
        chunk_size = CHUNK_SIZE * 2  # Convert to bytes
        chunks = []

        for i in range(0, len(audio_pcm_data), chunk_size):
            chunk = audio_pcm_data[i : i + chunk_size]
            chunks.append(chunk)

        # Verify we got chunks
        assert len(chunks) > 0

        # Verify all but last chunk are full size
        for chunk in chunks[:-1]:
            assert len(chunk) == chunk_size

        # Last chunk may be shorter
        assert len(chunks[-1]) <= chunk_size

    def test_silence_generation(self, silence_audio):
        """Test that silence generation produces valid PCM16 data."""
        # Verify length (1 second at 16kHz, 16-bit)
        assert len(silence_audio) == 16000 * 2

        # Verify it's actually silence (all zeros)
        audio_array = np.frombuffer(silence_audio, dtype=np.int16)
        assert np.all(audio_array == 0)

    def test_audio_file_fixture(self, audio_file_path):
        """Test that the audio file fixture provides a valid path."""
        assert Path(audio_file_path).exists()
        assert Path(audio_file_path).suffix == ".wav"

    def test_pcm_data_fixture(self, audio_pcm_data):
        """Test that the PCM data fixture provides valid data."""
        assert isinstance(audio_pcm_data, bytes)
        assert len(audio_pcm_data) > 0
        # Should be even length (16-bit samples)
        assert len(audio_pcm_data) % 2 == 0

        # Convert to numpy array to verify it's valid PCM16
        audio_array = np.frombuffer(audio_pcm_data, dtype=np.int16)
        assert len(audio_array) > 0
