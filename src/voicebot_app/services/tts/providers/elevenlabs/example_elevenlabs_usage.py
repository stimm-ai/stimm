"""
Example usage of ElevenLabs TTS Provider

This script demonstrates how to use the ElevenLabs TTS provider
for real-time text-to-speech synthesis.
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
    """Generator that yields text chunks for streaming."""
    for text in texts:
        yield text
        await asyncio.sleep(0.1)  # Small delay between chunks


async def example_basic_usage():
    """Example of basic ElevenLabs TTS usage."""
    print("=" * 60)
    print("ElevenLabs TTS Provider - Basic Usage Example")
    print("=" * 60)
    
    # Check if API key is available
    if not os.getenv("ELEVENLABS_TTS_API_KEY"):
        print("❌ ELEVENLABS_TTS_API_KEY environment variable is required")
        print("Please set it before running this example:")
        print("export ELEVENLABS_TTS_API_KEY=your_api_key_here")
        return
    
    try:
        # Initialize the provider
        provider = ElevenLabsProvider()
        print(f"✅ Provider initialized with voice: {provider.voice_id}")
        
        # Example text to synthesize
        test_texts = [
            "Hello! This is a demonstration of the ElevenLabs TTS provider.",
            "It supports real-time streaming of text to speech.",
            "You can stream text chunks as they become available.",
            "The audio is returned as raw PCM data chunks."
        ]
        
        print(f"📝 Text to synthesize: {len(test_texts)} chunks")
        for i, text in enumerate(test_texts, 1):
            print(f"   {i}. {text}")
        
        print("\n🎵 Starting audio streaming...")
        
        # Stream synthesis
        total_bytes = 0
        chunk_count = 0
        
        async for audio_chunk in provider.stream_synthesis(text_generator(test_texts)):
            chunk_size = len(audio_chunk)
            total_bytes += chunk_size
            chunk_count += 1
            print(f"   🔊 Chunk {chunk_count}: {chunk_size:,} bytes")
        
        print(f"\n✅ Streaming completed!")
        print(f"   • Total chunks: {chunk_count}")
        print(f"   • Total audio data: {total_bytes:,} bytes")
        print(f"   • Estimated duration: {total_bytes / (provider.sample_rate * 2):.2f} seconds")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def example_custom_voice_settings():
    """Example showing how to use custom voice settings."""
    print("\n" + "=" * 60)
    print("ElevenLabs TTS Provider - Custom Voice Settings")
    print("=" * 60)
    
    # This example shows how you could extend the provider
    # to support custom voice settings
    print("To use custom voice settings, you can modify the init_payload")
    print("in the ElevenLabsProvider.stream_synthesis method:")
    print("""
    init_payload = {
        "text": " ",
        "voice_settings": {
            "stability": 0.3,        # Lower = more expressive
            "similarity_boost": 0.9,  # Higher = more similar to original voice
            "style": 0.8,            # Higher = more dramatic
            "use_speaker_boost": True
        },
        "xi-api-key": self.api_key
    }
    """)
    print("Available voice settings:")
    print("  • stability: 0.0-1.0 (default: 0.5)")
    print("  • similarity_boost: 0.0-1.0 (default: 0.75)")
    print("  • style: 0.0-1.0 (default: 0.0)")
    print("  • use_speaker_boost: boolean (default: True)")


async def main():
    """Run all examples."""
    await example_basic_usage()
    await example_custom_voice_settings()
    
    print("\n" + "=" * 60)
    print("📚 Additional Information")
    print("=" * 60)
    print("Environment variables needed:")
    print("  • ELEVENLABS_TTS_API_KEY: Your ElevenLabs API key")
    print("  • ELEVENLABS_TTS_VOICE_ID: Voice ID (default: '21m00Tcm4TlvDq8ikWAM')")
    print("  • ELEVENLABS_TTS_MODEL_ID: Model ID (default: 'eleven_multilingual_v2')")
    print("  • ELEVENLABS_TTS_SAMPLE_RATE: Sample rate (default: 44100)")
    print("  • ELEVENLABS_TTS_ENCODING: Audio encoding (default: 'pcm_s16le')")
    print("  • ELEVENLABS_TTS_OUTPUT_FORMAT: Output format (default: 'pcm_44100')")
    
    print("\nTo use with TTSService:")
    print("  export TTS_PROVIDER=elevenlabs.io")
    print("  export ELEVENLABS_TTS_API_KEY=your_api_key_here")


if __name__ == "__main__":
    asyncio.run(main())