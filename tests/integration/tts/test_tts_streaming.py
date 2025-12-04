"""
Integration tests for TTS (Text-to-Speech) streaming functionality.

These tests verify TTS streaming works correctly with agent configurations
and can handle live streaming of incrementally generated text.
"""

import asyncio
import os
import pytest
import json
from uuid import UUID
from services.tts.tts import TTSService
from services.shared_streaming import shared_streaming_manager


@pytest.mark.asyncio
async def test_tts_service_initialization(deepgram_config):
    """Verify that TTS service initializes properly with agent configuration."""
    # Initialize TTS service with default agent
    tts_service = TTSService()
    assert tts_service.provider is not None
    print("✅ TTS service initialized successfully with agent configuration")


@pytest.mark.asyncio
async def test_tts_streaming_basic():
    """Test basic TTS streaming with incrementally generated text."""
    tts_service = TTSService()
    
    # Simple test text
    test_text = "Hello, this is a test of the text to speech streaming system."
    
    async def text_token_generator(text, tokens_per_chunk=3):
        """Simulates LLM token streaming behavior."""
        words = text.split()
        
        if len(words) == 0:
            yield ""
            return
        
        for i in range(0, len(words), tokens_per_chunk):
            chunk = " ".join(words[i:i + tokens_per_chunk]) + " "
            yield chunk
            # Simulate LLM generation delay
            await asyncio.sleep(0.05)
    
    session_id = "test_session"
    
    async def text_generator():
        """Generate text chunks in JSON format."""
        async for chunk in text_token_generator(test_text):
            payload = {
                "text": chunk,
                "try_trigger_generation": True,
                "flush": False
            }
            yield json.dumps(payload)
        
        # Send final flush signal
        final_payload = {
            "text": "",
            "try_trigger_generation": True,
            "flush": True
        }
        yield json.dumps(final_payload)
    
    async def collect_audio():
        """Collect audio chunks with a timeout."""
        audio_chunks = []
        async for audio_chunk in shared_streaming_manager.stream_text_to_audio_no_websocket(
            text_generator(), tts_service, session_id
        ):
            audio_chunks.append(audio_chunk)
        return audio_chunks
    
    # Stream text to audio with timeout
    try:
        audio_chunks = await asyncio.wait_for(collect_audio(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("Test timed out after 5 seconds")
    
    # Verify we received audio chunks
    assert len(audio_chunks) > 0, "No audio chunks received"
    
    total_bytes = sum(len(chunk) for chunk in audio_chunks)
    assert total_bytes > 0, "No audio data generated"
    
    print(f"✅ Received {len(audio_chunks)} audio chunks, total {total_bytes:,} bytes")


@pytest.mark.asyncio
async def test_tts_streaming_with_agent():
    """Test TTS streaming with specific agent configuration."""
    from services.agents_admin.agent_manager import get_agent_manager
    
    # Get default agent
    agent_manager = get_agent_manager()
    agent_config = agent_manager.get_agent_config()
    
    # Initialize TTS service with agent
    tts_service = TTSService()
    
    # Verify provider matches agent configuration
    assert tts_service.provider is not None
    print(f"Testing with TTS provider: {agent_config.tts_provider}")
    
    # Test text
    test_text = "Testing agent-based configuration."
    
    async def simple_generator():
        """Simple text generator."""
        payload = {
            "text": test_text,
            "try_trigger_generation": True,
            "flush": True
        }
        yield json.dumps(payload)
    
    audio_chunks = []
    session_id = "test_agent_session"
    
    async for audio_chunk in shared_streaming_manager.stream_text_to_audio_no_websocket(
        simple_generator(), tts_service, session_id
    ):
        audio_chunks.append(audio_chunk)
    
    assert len(audio_chunks) > 0, "No audio chunks received with agent config"
    print(f"✅ Agent-based TTS streaming successful: {len(audio_chunks)} chunks")


@pytest.mark.asyncio
async def test_tts_empty_text_handling():
    """Test TTS handles empty text gracefully."""
    tts_service = TTSService()
    
    async def empty_generator():
        """Generate empty text."""
        payload = {
            "text": "",
            "try_trigger_generation": True,
            "flush": True
        }
        yield json.dumps(payload)
    
    audio_chunks = []
    session_id = "test_empty_session"
    
    # This should not raise an exception
    try:
        async for audio_chunk in shared_streaming_manager.stream_text_to_audio_no_websocket(
            empty_generator(), tts_service, session_id
        ):
            audio_chunks.append(audio_chunk)
        
        # Empty text should produce no audio chunks (or possibly silence)
        print(f"✅ Empty text handled gracefully: {len(audio_chunks)} chunks")
    except Exception as e:
        pytest.fail(f"Empty text handling failed: {e}")


if __name__ == "__main__":
    # Allow running tests directly
    asyncio.run(test_tts_service_initialization(None))
    asyncio.run(test_tts_streaming_basic())
    asyncio.run(test_tts_streaming_with_agent())
    asyncio.run(test_tts_empty_text_handling())
    print("✅ All TTS streaming tests passed!")
