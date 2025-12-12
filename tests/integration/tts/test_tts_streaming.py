"""
Integration tests for TTS (Text-to-Speech) streaming functionality.

These tests verify TTS streaming works correctly with agent configurations
and can handle live streaming of incrementally generated text.
"""

import asyncio
import json

import pytest


@pytest.mark.requires_provider("tts")
class TestTTSStreaming:
    """Test suite for TTS streaming across all providers."""

    @pytest.mark.asyncio
    async def test_async_ai_service_initialization(self, async_ai_config):
        """Test that TTS service initializes correctly with AsyncAI provider."""
        if not async_ai_config:
            pytest.skip("ASYNC_API_KEY environment variable is required")

        from services.tts.providers.async_ai.async_ai_provider import AsyncAIProvider

        provider = AsyncAIProvider(async_ai_config)

        assert provider is not None
        assert provider.api_key == async_ai_config["api_key"]
        assert provider.voice_id == async_ai_config["voice"]
        assert provider.model_id == async_ai_config["model"]

    @pytest.mark.asyncio
    async def test_deepgram_service_initialization(self, deepgram_tts_config):
        """Test that TTS service initializes correctly with Deepgram provider."""
        if not deepgram_tts_config:
            pytest.skip("DEEPGRAM_TTS_API_KEY environment variable is required")

        from services.tts.providers.deepgram.deepgram_provider import DeepgramProvider

        provider = DeepgramProvider(deepgram_tts_config)

        assert provider is not None
        assert provider.provider_config == deepgram_tts_config

    @pytest.mark.asyncio
    async def test_elevenlabs_service_initialization(self, elevenlabs_config):
        """Test that TTS service initializes correctly with ElevenLabs provider."""
        if not elevenlabs_config:
            pytest.skip("ELEVENLABS_TTS_API_KEY environment variable is required")

        from services.tts.providers.elevenlabs.elevenlabs_provider import ElevenLabsProvider

        provider = ElevenLabsProvider(elevenlabs_config)

        assert provider is not None
        assert provider.api_key == elevenlabs_config["api_key"]
        assert provider.voice_id == elevenlabs_config["voice"]
        assert provider.model_id == elevenlabs_config["model"]

    @pytest.mark.asyncio
    async def test_hume_service_initialization(self, hume_config):
        """Test that TTS service initializes correctly with Hume.ai provider."""
        if not hume_config:
            pytest.skip("HUME_TTS_ACCESS_TOKEN environment variable is required")

        from services.tts.providers.hume.hume_provider import HumeProvider

        provider = HumeProvider(hume_config)

        assert provider is not None
        assert provider.api_key == hume_config["api_key"]
        assert provider.voice_id == hume_config["voice"]
        assert provider.version == hume_config["version"]

    @pytest.mark.asyncio
    async def test_kokoro_service_initialization(self, kokoro_local_config):
        """Test that TTS service initializes correctly with Kokoro provider."""
        from services.tts.providers.kokoro_local.kokoro_local_provider import KokoroLocalProvider

        provider = KokoroLocalProvider(kokoro_local_config)

        assert provider is not None
        assert provider.voice_id == kokoro_local_config["voice"]
        assert provider.language == kokoro_local_config["language"]

    @pytest.mark.asyncio
    async def test_async_ai_streaming_synthesis(
        self,
        async_ai_config,
    ):
        """
        Test WebRTC-like streaming to the AsyncAI TTS service.

        This test:
        1. Generates text chunks in real-time
        2. Streams text to the provider
        3. Collects audio chunks
        4. Verifies the connection works
        5. Verifies audio chunks are received
        """
        if not async_ai_config:
            pytest.skip("ASYNC_API_KEY environment variable is required")

        from services.tts.providers.async_ai.async_ai_provider import AsyncAIProvider

        provider = AsyncAIProvider(async_ai_config)

        try:
            # Simple test text
            test_text = "Hello, this is a test of the text to speech streaming system."

            async def text_token_generator(text, tokens_per_chunk=3):
                """Simulates LLM token streaming behavior."""
                words = text.split()

                if len(words) == 0:
                    yield ""
                    return

                for i in range(0, len(words), tokens_per_chunk):
                    chunk = " ".join(words[i : i + tokens_per_chunk]) + " "
                    yield chunk
                    # Simulate LLM generation delay
                    await asyncio.sleep(0.05)

            async def text_generator():
                """Generate text chunks in JSON format."""
                async for chunk in text_token_generator(test_text):
                    payload = {"text": chunk, "try_trigger_generation": True, "flush": False}
                    yield json.dumps(payload)

                # Send final flush signal
                final_payload = {"text": "", "try_trigger_generation": True, "flush": True}
                yield json.dumps(final_payload)

            # Stream text to audio and collect chunks
            audio_chunks = []
            async for audio_chunk in provider.stream_synthesis(text_generator()):
                audio_chunks.append(audio_chunk)
                print(f"[ASYNC.AI TEST] Received audio chunk: {len(audio_chunk)} bytes")

            # Verify basic structure
            assert len(audio_chunks) > 0, "No audio chunks received"

            total_bytes = sum(len(chunk) for chunk in audio_chunks)
            assert total_bytes > 0, "No audio data generated"

            print(f"✅ Received {len(audio_chunks)} audio chunks from AsyncAI, total {total_bytes:,} bytes")

        except Exception as e:
            # If the AsyncAI connection fails, this might be expected
            if "Connection" in str(e) or "API" in str(e) or "quota" in str(e).lower():
                pytest.skip(f"AsyncAI connection issue: {e}")
            else:
                pytest.fail(f"AsyncAI streaming synthesis failed: {e}")

    @pytest.mark.asyncio
    async def test_deepgram_streaming_synthesis(
        self,
        deepgram_tts_config,
    ):
        """
        Test WebRTC-like streaming to the Deepgram TTS service.
        """
        if not deepgram_tts_config:
            pytest.skip("DEEPGRAM_TTS_API_KEY environment variable is required")

        from services.tts.providers.deepgram.deepgram_provider import DeepgramProvider

        provider = DeepgramProvider(deepgram_tts_config)

        try:
            test_text = "Hello, this is a test of the text to speech streaming system."

            async def text_token_generator(text, tokens_per_chunk=3):
                words = text.split()
                if len(words) == 0:
                    yield ""
                    return
                for i in range(0, len(words), tokens_per_chunk):
                    chunk = " ".join(words[i : i + tokens_per_chunk]) + " "
                    yield chunk
                    await asyncio.sleep(0.05)

            async def text_generator():
                async for chunk in text_token_generator(test_text):
                    # Deepgram expects plain text chunks, not JSON
                    yield chunk
                # Send empty string to signal end
                yield ""

            audio_chunks = []
            async for audio_chunk in provider.stream_synthesis(text_generator()):
                audio_chunks.append(audio_chunk)
                print(f"[DEEPGRAM TEST] Received audio chunk: {len(audio_chunk)} bytes")

            assert len(audio_chunks) > 0, "No audio chunks received"
            total_bytes = sum(len(chunk) for chunk in audio_chunks)
            assert total_bytes > 0, "No audio data generated"

            print(f"✅ Received {len(audio_chunks)} audio chunks from Deepgram, total {total_bytes:,} bytes")

        except Exception as e:
            # If the Deepgram connection fails, this might be expected
            if "Connection" in str(e) or "API" in str(e) or "quota" in str(e).lower():
                pytest.skip(f"Deepgram connection issue: {e}")
            else:
                pytest.fail(f"Deepgram streaming synthesis failed: {e}")

    @pytest.mark.asyncio
    async def test_elevenlabs_streaming_synthesis(
        self,
        elevenlabs_config,
    ):
        """
        Test WebRTC-like streaming to the ElevenLabs TTS service.
        """
        if not elevenlabs_config:
            pytest.skip("ELEVENLABS_TTS_API_KEY environment variable is required")

        from services.tts.providers.elevenlabs.elevenlabs_provider import ElevenLabsProvider

        provider = ElevenLabsProvider(elevenlabs_config)

        try:
            test_text = "Hello, this is a test of the text to speech streaming system."

            async def text_token_generator(text, tokens_per_chunk=3):
                words = text.split()
                if len(words) == 0:
                    yield ""
                    return
                for i in range(0, len(words), tokens_per_chunk):
                    chunk = " ".join(words[i : i + tokens_per_chunk]) + " "
                    yield chunk
                    await asyncio.sleep(0.05)

            async def text_generator():
                async for chunk in text_token_generator(test_text):
                    payload = {"text": chunk, "try_trigger_generation": True, "flush": False}
                    yield json.dumps(payload)
                # Final flush
                final_payload = {"text": "", "try_trigger_generation": True, "flush": True}
                yield json.dumps(final_payload)

            audio_chunks = []

            # Simple approach: collect first audio chunk to verify streaming works
            # This is economical and prevents hanging
            async for audio_chunk in provider.stream_synthesis(text_generator()):
                audio_chunks.append(audio_chunk)
                print(f"[ELEVENLABS TEST] Received audio chunk: {len(audio_chunk)} bytes")
                # Stop after receiving the first audio chunk - that's enough to validate streaming works
                break

            assert len(audio_chunks) > 0, "No audio chunks received"
            total_bytes = sum(len(chunk) for chunk in audio_chunks)
            assert total_bytes > 0, "No audio data generated"

            print(f"✅ Received {len(audio_chunks)} audio chunks from ElevenLabs, total {total_bytes:,} bytes")

        except Exception as e:
            # If the ElevenLabs connection fails, this might be expected
            if "Connection" in str(e) or "API" in str(e):
                pytest.skip(f"ElevenLabs connection issue: {e}")
            else:
                pytest.fail(f"ElevenLabs streaming synthesis failed: {e}")

    @pytest.mark.asyncio
    async def test_kokoro_streaming_synthesis(
        self,
        kokoro_local_config,
    ):
        """
        Test WebRTC-like streaming to the Kokoro local TTS service.
        """
        from services.tts.providers.kokoro_local.kokoro_local_provider import KokoroLocalProvider

        provider = KokoroLocalProvider(kokoro_local_config)

        try:
            test_text = "Hello, this is a test of the text to speech streaming system."

            async def text_token_generator(text, tokens_per_chunk=3):
                words = text.split()
                if len(words) == 0:
                    yield ""
                    return
                for i in range(0, len(words), tokens_per_chunk):
                    chunk = " ".join(words[i : i + tokens_per_chunk]) + " "
                    yield chunk
                    await asyncio.sleep(0.05)

            async def text_generator():
                async for chunk in text_token_generator(test_text):
                    # Kokoro expects plain text chunks
                    yield chunk
                # Send empty string to signal end
                yield ""

            audio_chunks = []
            async for audio_chunk in provider.stream_synthesis(text_generator()):
                audio_chunks.append(audio_chunk)
                print(f"[KOKORO TEST] Received audio chunk: {len(audio_chunk)} bytes")

            assert len(audio_chunks) > 0, "No audio chunks received"
            total_bytes = sum(len(chunk) for chunk in audio_chunks)
            assert total_bytes > 0, "No audio data generated"

            print(f"✅ Received {len(audio_chunks)} audio chunks from Kokoro, total {total_bytes:,} bytes")

        except Exception as e:
            # If the Kokoro connection fails, this might be expected
            if "Connection" in str(e) or "API" in str(e) or "quota" in str(e).lower():
                pytest.skip(f"Kokoro connection issue: {e}")
            else:
                pytest.fail(f"Kokoro streaming synthesis failed: {e}")

    @pytest.mark.asyncio
    async def test_hume_streaming_synthesis(
        self,
        hume_config,
    ):
        """
        Test WebRTC-like streaming to the Hume.ai TTS service.
        """
        if not hume_config:
            pytest.skip("HUME_TTS_API_KEY environment variable is required")

        from services.tts.providers.hume.hume_provider import HumeProvider

        provider = HumeProvider(hume_config)

        try:
            test_text = "Hello, this is a test of the text to speech streaming system."

            async def text_token_generator(text, tokens_per_chunk=3):
                words = text.split()
                if len(words) == 0:
                    yield ""
                    return
                for i in range(0, len(words), tokens_per_chunk):
                    chunk = " ".join(words[i : i + tokens_per_chunk]) + " "
                    yield chunk
                    await asyncio.sleep(0.05)

            async def text_generator():
                async for chunk in text_token_generator(test_text):
                    # Hume.ai expects JSON payload similar to ElevenLabs
                    payload = {"text": chunk, "try_trigger_generation": True, "flush": False}
                    yield json.dumps(payload)
                # Final flush
                final_payload = {"text": "", "try_trigger_generation": True, "flush": True}
                yield json.dumps(final_payload)

            audio_chunks = []

            # Simple approach: collect first audio chunk to verify streaming works
            # This is economical and prevents hanging
            async for audio_chunk in provider.stream_synthesis(text_generator()):
                audio_chunks.append(audio_chunk)
                print(f"[HUME TEST] Received audio chunk: {len(audio_chunk)} bytes")
                # Stop after receiving the first audio chunk - that's enough to validate streaming works
                break

            assert len(audio_chunks) > 0, "No audio chunks received"
            total_bytes = sum(len(chunk) for chunk in audio_chunks)
            assert total_bytes > 0, "No audio data generated"

            print(f"✅ Received {len(audio_chunks)} audio chunks from Hume.ai, total {total_bytes:,} bytes")

        except Exception as e:
            # If the Hume.ai connection fails, this might be expected
            if "Connection" in str(e) or "API" in str(e) or "quota" in str(e).lower() or "timed out" in str(e).lower():
                pytest.skip(f"Hume.ai connection issue: {e}")
            else:
                pytest.fail(f"Hume.ai streaming synthesis failed: {e}")

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, async_ai_config):
        """Test that TTS handles empty text gracefully."""
        if not async_ai_config:
            pytest.skip("ASYNC_API_KEY environment variable is required")

        from services.tts.providers.async_ai.async_ai_provider import AsyncAIProvider

        provider = AsyncAIProvider(async_ai_config)

        async def empty_generator():
            payload = {"text": "", "try_trigger_generation": True, "flush": True}
            yield json.dumps(payload)

        # This should not raise an exception
        try:
            audio_chunks = []
            async for audio_chunk in provider.stream_synthesis(empty_generator()):
                audio_chunks.append(audio_chunk)

            # Empty text should produce no audio chunks (or possibly silence)
            print(f"✅ Empty text handled gracefully: {len(audio_chunks)} chunks")
        except Exception as e:
            pytest.fail(f"Empty text handling failed: {e}")
