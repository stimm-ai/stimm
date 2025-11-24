"""
Deepgram streaming tests for Deepgram STT service integration.

This test suite verifies that the voicebot STT service can properly
connect to and use the Deepgram API for real-time transcription.
"""

import asyncio
import json
import os
import wave
from typing import Dict, Any, List

import numpy as np
import pytest
import pytest_asyncio
import soundfile as sf

from services.stt.stt import STTService

# Constants for WebRTC-like streaming
STREAM_SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 40  # 40ms chunks (typical WebRTC)
CHUNK_SIZE = STREAM_SAMPLE_RATE * CHUNK_DURATION_MS // 1000
CHUNK_BYTES = CHUNK_SIZE * 2  # 16-bit samples (2 bytes per sample)


@pytest.fixture
def audio_file_path():
    """Get the path to the test audio file."""
    return os.path.join(os.path.dirname(__file__), "Enregistrement.wav")


@pytest.fixture
def audio_pcm_data(audio_file_path: str) -> bytes:
    """Load audio data as PCM16 format."""
    return load_pcm16_from_wav(audio_file_path)


@pytest.fixture
def expected_transcription_results(audio_file_path: str) -> Dict[str, Any]:
    """
    Provide expected transcription results for verification.

    Returns:
        Dictionary with expected transcription characteristics
    """
    return {
        "min_length": 1,  # Minimum number of transcripts
        "min_transcript_length": 1,  # Minimum length of transcript text
        "expected_fields": ["transcript", "is_final", "confidence", "provider"]
    }


@pytest.fixture(scope="module")
def test_setup():
    """Setup for all tests in this module."""
    print("Setting up Deepgram test environment...")
    # Verify Deepgram API key is available
    api_key = os.getenv("DEEPGRAM_STT_API_KEY")
    if not api_key:
        pytest.skip("DEEPGRAM_STT_API_KEY environment variable is required for Deepgram tests")
    yield
    print("Tearing down Deepgram test environment...")


def load_pcm16_from_wav(wav_path: str) -> bytes:
    """
    Load PCM16 audio data from a WAV file.

    Args:
        wav_path: Path to the WAV file

    Returns:
        PCM16 audio data as bytes
    """
    with wave.open(wav_path, 'rb') as wav_file:
        # Verify format
        assert wav_file.getnchannels() == 1, "Audio must be mono"
        assert wav_file.getsampwidth() == 2, "Audio must be 16-bit"
        assert wav_file.getframerate() == STREAM_SAMPLE_RATE, f"Audio must be {STREAM_SAMPLE_RATE}Hz"

        # Read all frames
        pcm_data = wav_file.readframes(wav_file.getnframes())

    return pcm_data


def verify_transcription_results(
    transcripts: List[Dict[str, Any]],
    expected: Dict[str, Any]
) -> tuple[bool, str]:
    """
    Verify transcription results against expected criteria.

    Args:
        transcripts: List of transcription results
        expected: Expected criteria for verification

    Returns:
        Tuple of (success, message)
    """
    # Check minimum number of transcripts
    if len(transcripts) < expected["min_length"]:
        return False, f"Expected at least {expected['min_length']} transcripts, got {len(transcripts)}"

    # Check transcript structure and content
    for transcript in transcripts:
        # Check required fields
        for field in expected["expected_fields"]:
            if field not in transcript:
                return False, f"Missing required field '{field}' in transcript"

        # Check transcript content
        if "transcript" in transcript:
            if len(transcript["transcript"]) < expected["min_transcript_length"]:
                return False, f"Transcript text too short: '{transcript['transcript']}'"

    # Check that we have at least one final transcript
    has_final_transcript = any(t.get("is_final", False) for t in transcripts)
    if not has_final_transcript:
        return False, "No final transcript received"

    return True, "All verification passed"


@pytest.mark.asyncio
async def test_deepgram_service_initialization():
    """Test that STT service initializes correctly with deepgram.com provider."""
    # Skip if Deepgram API key is not available
    if not os.getenv("DEEPGRAM_STT_API_KEY"):
        pytest.skip("DEEPGRAM_STT_API_KEY environment variable is required")
    
    stt_service = STTService()
    
    # Verify service is initialized
    assert stt_service is not None
    assert stt_service.provider is not None
    assert stt_service.config.get_provider() == "deepgram.com"


@pytest.mark.asyncio
async def test_deepgram_streaming_transcription(
    test_setup,
    audio_file_path: str,
    audio_pcm_data: bytes,
    expected_transcription_results: Dict[str, Any]
):
    """
    Test WebRTC-like streaming to the Deepgram STT service.

    This test:
    1. Loads the WAV file (pre-converted from M4A)
    2. Streams audio chunks via STT service using real streaming with sounddevice
    3. Collects transcription results
    4. Verifies the connection works
    5. Verifies transcription results meet expected criteria
    """
    stt_service = STTService()
    
    # Verify service is initialized with Deepgram provider
    assert stt_service.provider is not None
    assert stt_service.config.get_provider() == "deepgram.com"

    try:
        # Create a generator that streams audio in real-time using sounddevice
        async def audio_chunk_generator():
            import sounddevice as sd
            import soundfile as sf

            # Load audio file
            audio_data, sample_rate = sf.read(audio_file_path, dtype='float32')

            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = audio_data.mean(axis=1)

            # Resample to 16kHz if needed
            if sample_rate != STREAM_SAMPLE_RATE:
                from scipy import signal
                audio_data = signal.resample(audio_data,
                                           int(len(audio_data) * STREAM_SAMPLE_RATE / sample_rate))

            # Convert to PCM16
            audio_data = (audio_data * 32767).astype(np.int16)

            # Calculate chunk size in samples
            chunk_samples = CHUNK_SIZE

            # Stream audio in real-time
            for i in range(0, len(audio_data), chunk_samples):
                chunk = audio_data[i:i + chunk_samples].tobytes()
                yield chunk

                # Calculate real delay based on audio duration
                chunk_duration = chunk_samples / STREAM_SAMPLE_RATE
                await asyncio.sleep(chunk_duration)

        # Stream audio and collect transcripts using real streaming
        transcripts = []
        async for transcript in stt_service.transcribe_streaming(audio_chunk_generator()):
            transcripts.append(transcript)
            print(f"[DEEPGRAM TEST] Received transcript: {transcript}")

        # Verify basic structure
        assert len(transcripts) > 0, "No transcripts received"

        # Verify final transcript structure
        final_transcripts = [t for t in transcripts if t.get("is_final", False)]
        assert len(final_transcripts) > 0, "No final transcripts received"
        
        final_transcript = final_transcripts[-1]
        assert "transcript" in final_transcript
        assert "is_final" in final_transcript
        assert "provider" in final_transcript
        assert final_transcript["provider"] == "deepgram"
        assert final_transcript["transcript"], "Empty final transcript"

        # Verify against expected results
        success, message = verify_transcription_results(transcripts, expected_transcription_results)
        assert success, message

        print(f"Received {len(transcripts)} transcripts from Deepgram")
        print(f"Final transcript: {final_transcript['transcript']}")

    except Exception as e:
        pytest.fail(f"Deepgram streaming transcription failed: {e}")


@pytest.mark.asyncio
async def test_deepgram_empty_chunks_handling():
    """
    Test that the Deepgram provider handles empty chunks gracefully.
    """
    # Skip if Deepgram API key is not available
    if not os.getenv("DEEPGRAM_STT_API_KEY"):
        pytest.skip("DEEPGRAM_STT_API_KEY environment variable is required")
    
    stt_service = STTService()

    # Generator with some empty chunks
    async def audio_with_empty_chunks():
        yield b"chunk1"
        yield b""  # Empty chunk
        yield b"chunk3"
        yield b""  # Another empty chunk

    try:
        # This should not raise an exception
        async for transcript in stt_service.transcribe_streaming(audio_with_empty_chunks()):
            pass  # Just verify it doesn't crash

    except Exception as e:
        # If the Deepgram connection fails, this might be expected
        if "Connection" in str(e) or "API" in str(e):
            # This might be expected if there are network issues
            pytest.skip(f"Deepgram connection issue: {e}")
        else:
            raise  # Re-raise other exceptions


# Note: Additional test cases would include:
# - Testing with different sample rates
# - Testing error handling
# - Testing with silence and noise
# - Testing connection recovery
# - Testing different Deepgram models and languages