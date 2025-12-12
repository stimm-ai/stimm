"""
Integration tests for STT (Speech-to-Text) streaming functionality.

These tests verify STT streaming works correctly across all available providers.
Tests are parametrized to run against multiple providers (Deepgram, Whisper, etc.)
and will automatically skip if required API keys are not available.
"""

import asyncio

import numpy as np
import pytest

from tests.conftest import CHUNK_SIZE, STREAM_SAMPLE_RATE
from tests.fixtures.test_utils import verify_transcription_results


@pytest.mark.requires_provider("stt")
class TestSTTStreaming:
    """Test suite for STT streaming across all providers."""

    @pytest.mark.asyncio
    async def test_deepgram_service_initialization(self, deepgram_config):
        """Test that STT service initializes correctly with Deepgram provider."""
        if not deepgram_config:
            pytest.skip("DEEPGRAM_STT_API_KEY environment variable is required")

        # Create a test agent configuration (would normally come from database)
        # For now, we'll test direct provider initialization
        from services.stt.providers.deepgram.deepgram_provider import DeepgramProvider

        provider = DeepgramProvider(deepgram_config)

        assert provider is not None
        assert provider.api_key == deepgram_config["api_key"]
        assert provider.model == deepgram_config["model"]

    @pytest.mark.asyncio
    async def test_whisper_service_initialization(self, whisper_config):
        """Test that STT service initializes correctly with Whisper provider."""
        from services.stt.providers.whisper_local.whisper_local import WhisperLocalProvider

        provider = WhisperLocalProvider(whisper_config)

        assert provider is not None
        assert provider.full_url is not None

    @pytest.mark.asyncio
    async def test_deepgram_streaming_transcription(self, deepgram_config, audio_file_path: str, expected_transcription_results):
        """
        Test WebRTC-like streaming to the Deepgram STT service.

        This test:
        1. Loads the WAV file
        2. Streams audio chunks in real-time
        3. Collects transcription results
        4. Verifies the connection works
        5. Verifies transcription results meet expected criteria
        """
        if not deepgram_config:
            pytest.skip("DEEPGRAM_STT_API_KEY environment variable is required")

        from services.stt.providers.deepgram.deepgram_provider import DeepgramProvider

        provider = DeepgramProvider(deepgram_config)

        try:
            # Create a generator that streams audio in real-time
            async def audio_chunk_generator():
                import soundfile as sf

                # Load audio file
                audio_data, sample_rate = sf.read(audio_file_path, dtype="float32")

                # Convert to mono if stereo
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.mean(axis=1)

                # Resample to 16kHz if needed
                if sample_rate != STREAM_SAMPLE_RATE:
                    from scipy import signal

                    audio_data = signal.resample(audio_data, int(len(audio_data) * STREAM_SAMPLE_RATE / sample_rate))

                # Convert to PCM16
                audio_data = (audio_data * 32767).astype(np.int16)

                # Calculate chunk size in samples
                chunk_samples = CHUNK_SIZE

                # Stream audio in real-time
                for i in range(0, len(audio_data), chunk_samples):
                    chunk = audio_data[i : i + chunk_samples].tobytes()
                    yield chunk

                    # Calculate real delay based on audio duration
                    chunk_duration = chunk_samples / STREAM_SAMPLE_RATE
                    await asyncio.sleep(chunk_duration)

            # Stream audio and collect transcripts
            transcripts = []
            async for transcript in provider.stream_audio_chunks(audio_chunk_generator()):
                transcripts.append(transcript)
                print(f"[DEEPGRAM TEST] Received transcript: {transcript}")

            # Verify basic structure
            assert len(transcripts) > 0, "No transcripts received"

            # Verify final transcript structure (use last transcript if no final)
            final_transcript = transcripts[-1]
            assert "transcript" in final_transcript
            assert "is_final" in final_transcript
            assert "provider" in final_transcript
            assert final_transcript["provider"] == "deepgram"
            assert final_transcript["transcript"], "Empty final transcript"

            # Verify against expected results
            success, message = verify_transcription_results(transcripts, expected_transcription_results)
            assert success, message

            print(f"✅ Received {len(transcripts)} transcripts from Deepgram")
            print(f"Final transcript: {final_transcript['transcript']}")

        except Exception as e:
            pytest.fail(f"Deepgram streaming transcription failed: {e}")

    @pytest.mark.asyncio
    async def test_whisper_streaming_transcription(self, whisper_config, audio_file_path: str, expected_transcription_results):
        """
        Test WebRTC-like streaming to the Whisper STT service.

        This test:
        1. Loads the WAV file
        2. Streams audio chunks in real-time
        3. Collects transcription results
        4. Verifies the connection works
        5. Verifies transcription results meet expected criteria
        """
        from services.stt.providers.whisper_local.whisper_local import WhisperLocalProvider

        provider = WhisperLocalProvider(whisper_config)

        try:
            # Create a generator that streams audio in real-time
            async def audio_chunk_generator():
                import soundfile as sf

                # Load audio file
                audio_data, sample_rate = sf.read(audio_file_path, dtype="float32")

                # Convert to mono if stereo
                if len(audio_data.shape) > 1:
                    audio_data = audio_data.mean(axis=1)

                # Resample to 16kHz if needed
                if sample_rate != STREAM_SAMPLE_RATE:
                    from scipy import signal

                    audio_data = signal.resample(audio_data, int(len(audio_data) * STREAM_SAMPLE_RATE / sample_rate))

                # Convert to PCM16
                audio_data = (audio_data * 32767).astype(np.int16)

                # Calculate chunk size in samples
                chunk_samples = CHUNK_SIZE

                # Stream audio in real-time
                for i in range(0, len(audio_data), chunk_samples):
                    chunk = audio_data[i : i + chunk_samples].tobytes()
                    yield chunk

                    # Calculate real delay based on audio duration
                    chunk_duration = chunk_samples / STREAM_SAMPLE_RATE
                    await asyncio.sleep(chunk_duration)

            # Stream audio and collect transcripts
            transcripts = []
            async for transcript in provider.stream_audio_chunks(audio_chunk_generator()):
                transcripts.append(transcript)
                print(f"[WHISPER TEST] Received transcript: {transcript}")

            # Verify basic structure
            assert len(transcripts) > 0, "No transcripts received"

            # Verify final transcript structure (use last transcript if no final)
            final_transcript = transcripts[-1]
            assert "transcript" in final_transcript
            assert "is_final" in final_transcript
            assert final_transcript["transcript"], "Empty final transcript"

            # Verify against expected results
            success, message = verify_transcription_results(transcripts, expected_transcription_results)
            assert success, message

            print(f"✅ Received {len(transcripts)} transcripts from Whisper")
            print(f"Final transcript: {final_transcript['transcript']}")

        except Exception as e:
            pytest.fail(f"Whisper streaming transcription failed: {e}")

    @pytest.mark.asyncio
    async def test_deepgram_empty_chunks_handling(self, deepgram_config):
        """Test that the Deepgram provider handles empty chunks gracefully."""
        if not deepgram_config:
            pytest.skip("DEEPGRAM_STT_API_KEY environment variable is required")

        from services.stt.providers.deepgram.deepgram_provider import DeepgramProvider

        provider = DeepgramProvider(deepgram_config)

        # Generator with some empty chunks
        async def audio_with_empty_chunks():
            yield b"chunk1" + b"\x00" * 1280  # Some data
            yield b""  # Empty chunk
            yield b"chunk3" + b"\x00" * 1280  # More data
            yield b""  # Another empty chunk

        try:
            # This should not raise an exception
            async for transcript in provider.stream_audio_chunks(audio_with_empty_chunks()):
                pass  # Just verify it doesn't crash

        except Exception as e:
            # If the Deepgram connection fails, this might be expected
            if "Connection" in str(e) or "API" in str(e):
                pytest.skip(f"Deepgram connection issue: {e}")
            else:
                raise  # Re-raise other exceptions
