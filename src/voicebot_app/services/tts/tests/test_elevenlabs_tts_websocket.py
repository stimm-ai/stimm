"""
Test ElevenLabs TTS WebSocket Integration

Test the ElevenLabs TTS provider with WebSocket streaming functionality.
"""

import asyncio
import os
import sys
import logging
from typing import AsyncGenerator

# Add the parent directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from services.tts.providers.elevenlabs.elevenlabs_provider import ElevenLabsProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def text_generator(texts: list[str]) -> AsyncGenerator[str, None]:
    """Generator that yields text chunks for testing."""
    for text in texts:
        yield text
        await asyncio.sleep(0.1)  # Small delay between chunks


async def test_elevenlabs_provider_initialization():
    """Test ElevenLabs provider initialization and configuration."""
    logger.info("🧪 Testing ElevenLabs provider initialization...")
    
    try:
        provider = ElevenLabsProvider()
        
        # Check configuration
        assert hasattr(provider, 'api_key'), "Provider should have api_key attribute"
        assert hasattr(provider, 'voice_id'), "Provider should have voice_id attribute"
        assert hasattr(provider, 'model_id'), "Provider should have model_id attribute"
        assert hasattr(provider, 'sample_rate'), "Provider should have sample_rate attribute"
        assert hasattr(provider, 'encoding'), "Provider should have encoding attribute"
        
        logger.info(f"   • Voice ID: {provider.voice_id}")
        logger.info(f"   • Model ID: {provider.model_id}")
        logger.info(f"   • Sample Rate: {provider.sample_rate}Hz")
        logger.info(f"   • Encoding: {provider.encoding}")
        
        logger.info("✅ Provider initialization test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Provider initialization test failed: {e}")
        return False


async def test_elevenlabs_tts_streaming():
    """Test ElevenLabs TTS streaming with real WebSocket connection."""
    logger.info("🧪 Testing ElevenLabs TTS WebSocket streaming...")
    
    if not os.getenv("ELEVENLABS_TTS_API_KEY"):
        logger.warning("⚠️  Skipping streaming test - ELEVENLABS_TTS_API_KEY not set")
        return True
    
    try:
        provider = ElevenLabsProvider()
        
        # Test text
        test_texts = [
            "Hello, this is a test of ElevenLabs TTS.",
            "Does it work with the WebSocket streaming?",
            "Let's see if we get audio chunks back."
        ]
        
        logger.info("📡 Connecting to ElevenLabs TTS WebSocket and streaming audio...")
        
        total_audio_bytes = 0
        audio_chunks = []
        chunk_count = 0
        
        async for audio_chunk in provider.stream_synthesis(text_generator(test_texts)):
            chunk_size = len(audio_chunk)
            total_audio_bytes += chunk_size
            audio_chunks.append(audio_chunk)
            chunk_count += 1
            logger.info(f"   • Received audio chunk {chunk_count}: {chunk_size:,} bytes (total: {total_audio_bytes:,} bytes)")
        
        logger.info(f"✅ Streaming test completed: {chunk_count} chunks, {total_audio_bytes:,} total bytes")
        
        # Basic validation
        if chunk_count > 0 and total_audio_bytes > 0:
            logger.info("✅ Audio streaming validation passed")
            return True
        else:
            logger.error("❌ No audio chunks received")
            return False
            
    except Exception as e:
        logger.error(f"❌ Streaming test failed: {e}")
        return False


async def test_elevenlabs_error_handling():
    """Test ElevenLabs provider error handling."""
    logger.info("🧪 Testing ElevenLabs error handling...")
    
    try:
        # Test without API key
        original_key = os.environ.get("ELEVENLABS_TTS_API_KEY")
        if original_key:
            del os.environ["ELEVENLABS_TTS_API_KEY"]
        
        provider = ElevenLabsProvider()
        
        # This should raise an error
        try:
            async for _ in provider.stream_synthesis(text_generator(["test"])):
                pass
            logger.error("❌ Error handling test failed - should have raised ValueError")
            return False
        except ValueError as e:
            logger.info(f"✅ Correctly caught ValueError: {e}")
            return True
        finally:
            # Restore API key
            if original_key:
                os.environ["ELEVENLABS_TTS_API_KEY"] = original_key
                
    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        return False


async def main():
    """Run all ElevenLabs TTS integration tests."""
    print("=" * 60)
    print("ElevenLabs TTS Integration Test")
    print("=" * 60)
    
    # Test 1: Provider initialization
    init_success = await test_elevenlabs_provider_initialization()
    
    # Test 2: Real WebSocket streaming (only if API key is available)
    streaming_success = True
    if os.getenv("ELEVENLABS_TTS_API_KEY"):
        streaming_success = await test_elevenlabs_tts_streaming()
    else:
        logger.warning("⚠️  Skipping WebSocket streaming test - ELEVENLABS_TTS_API_KEY not set")
    
    # Test 3: Error handling
    error_handling_success = await test_elevenlabs_error_handling()
    
    print("=" * 60)
    if init_success and streaming_success and error_handling_success:
        print("✅ ALL TESTS PASSED")
        print("ElevenLabs TTS provider is working correctly!")
    else:
        print("❌ SOME TESTS FAILED")
        print("Check the logs above for details.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())