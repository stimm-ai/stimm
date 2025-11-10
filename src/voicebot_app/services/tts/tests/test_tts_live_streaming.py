"""
Test TTS Live Streaming (Agent-based version)

This test verifies that the TTS service can handle live streaming of
incrementally generated text using agent configurations from the database.
It can run with the default agent or a specific agent by ID or name.
"""

import asyncio
import os
import pytest
import time
import tempfile
import json
import argparse
import sys
import wave
import struct
from uuid import UUID
from services.tts.tts import TTSService
from services.shared_streaming import shared_streaming_manager
from services.agent.agent_manager import get_agent_manager
from services.agent.agent_service import AgentService

def create_progress_bar(current, total, width=20, prefix=""):
    """Create a simple text-based progress bar"""
    progress = int(width * current / total) if total > 0 else 0
    bar = "█" * progress + "░" * (width - progress)
    percentage = int(100 * current / total) if total > 0 else 0
    return f"{prefix} [{bar}] {percentage}%"

def get_agent_config(agent_id=None, agent_name=None):
    """Get agent configuration by ID or name."""
    agent_manager = get_agent_manager()
    
    if agent_id:
        try:
            return agent_manager.get_agent_config(UUID(agent_id))
        except Exception as e:
            print(f"❌ Error getting agent by ID {agent_id}: {e}")
            sys.exit(1)
    elif agent_name:
        try:
            return agent_manager.get_agent_config_by_name(agent_name)
        except Exception as e:
            print(f"❌ Error getting agent by name '{agent_name}': {e}")
            sys.exit(1)
    else:
        # Use default agent
        return agent_manager.get_agent_config()

def list_available_agents():
    """List all available agents for selection."""
    agent_service = AgentService()
    agents = agent_service.list_agents(active_only=True)
    
    print("Available agents:")
    print("-" * 80)
    for agent in agents.agents:
        print(f"ID: {agent.id}")
        print(f"Name: {agent.name}")
        print(f"Description: {agent.description or 'No description'}")
        print(f"TTS Provider: {agent.tts_provider}")
        print(f"LLM Provider: {agent.llm_provider}")
        print(f"STT Provider: {agent.stt_provider}")
        print(f"Default: {'Yes' if agent.is_default else 'No'}")
        print("-" * 80)
    
def add_wav_header_to_chunk(raw_audio_data, sample_rate=22050, sample_width=2, channels=1):
    """Add WAV header to raw PCM audio data to make it playable."""
    # Calculate data size
    data_size = len(raw_audio_data)
    
    # WAV header structure
    # RIFF header
    riff_header = b'RIFF'
    file_size = data_size + 36  # 36 = header size minus RIFF header and file size
    riff_chunk = riff_header + struct.pack('<I', file_size) + b'WAVE'
    
    # fmt chunk
    fmt_header = b'fmt '
    fmt_chunk_size = 16
    audio_format = 1  # PCM
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width
    bits_per_sample = sample_width * 8
    
    fmt_chunk = (fmt_header +
                struct.pack('<IHHIIHH', fmt_chunk_size, audio_format, channels, sample_rate,
                           byte_rate, block_align, bits_per_sample))
    
    # data chunk
    data_header = b'data'
    data_chunk = data_header + struct.pack('<I', data_size) + raw_audio_data
    
    # Combine all parts
    wav_data = riff_chunk + fmt_chunk + data_chunk
    return wav_data

def make_chunks_playable(chunks_dir):
    """Convert raw audio chunks to proper WAV files with headers."""
    chunk_files = sorted([f for f in os.listdir(chunks_dir) if f.startswith("chunk_") and f.endswith(".wav")])
    
    if not chunk_files:
        print("⚠️ No audio chunks found to convert")
        return False
    
    converted_count = 0
    for chunk_file in chunk_files:
        chunk_path = os.path.join(chunks_dir, chunk_file)
        
        try:
            # Read raw audio data
            with open(chunk_path, 'rb') as f:
                raw_audio_data = f.read()
            
            # Add WAV header
            wav_data = add_wav_header_to_chunk(raw_audio_data)
            
            # Write back with proper WAV header
            with open(chunk_path, 'wb') as f:
                f.write(wav_data)
            
            converted_count += 1
            
        except Exception as e:
            print(f"❌ Error converting {chunk_file}: {e}")
    
    if converted_count > 0:
        print(f"🎵 Converted {converted_count} chunks to playable WAV format")
        return True
    else:
        print("❌ Failed to convert any audio chunks")
        return False

def create_audio_playback_instructions(chunks_dir):
    """Create instructions for playing the audio files."""
    instructions_file = os.path.join(chunks_dir, "playback_instructions.txt")
    
    with open(instructions_file, 'w') as f:
        f.write("Audio Playback Instructions\n")
        f.write("=" * 40 + "\n\n")
        f.write("Individual chunks:\n")
        f.write("- Each chunk_*.wav file is a separate audio segment\n")
        f.write("- Files have proper WAV headers for easy playback\n")
        f.write("- Play them in order to hear the complete text\n\n")
        f.write("Recommended players:\n")
        f.write("- VLC Media Player (works best)\n")
        f.write("- Windows Media Player\n")
        f.write("- QuickTime (macOS)\n")
        f.write("- Audacity (for detailed analysis)\n\n")
        f.write("Note: Audio is saved as 22050 Hz, 16-bit, mono PCM\n")
    
    return instructions_file

@pytest.mark.asyncio
async def test_tts_live_streaming(agent_id=None, agent_name=None):
    """Test TTS live streaming with optional agent selection."""
    
    # Get agent configuration
    agent_config = get_agent_config(agent_id, agent_name)
    
    # Initialize TTS service with the selected agent
    tts_service = TTSService()
    
    # Verify the provider matches the agent configuration
    current_provider = agent_config.tts_provider
    print(f"Testing with agent: {agent_config.tts_provider}")
    print(f"Agent TTS configuration: {agent_config.tts_config}")

    # Use the environment variable for the test text
    text = os.getenv("TTS_INTERFACE_TEXT", "Cette démonstration met en avant la diffusion en temps réel des jetons d’un modèle de langage. Merci d'avoir écouté ce texte. Ce test permer, grâce à des sliders de visualisation, de vérifier si la réception de chunks auidio se fait bien en parrallèlle avec l'envoie des tokens issue du LLM. J'éspère que cela vous aidera. A bientôt pour de nouvelles aventures. Et surtout prenez soin de vous. Au revoir.")

    async def llm_token_generator(text, tokens_per_chunk=2):
        """Simulates LLM token streaming behavior"""
        words = text.split()
        total_chunks = (len(words) + tokens_per_chunk - 1) // tokens_per_chunk

        for i in range(0, len(words), tokens_per_chunk):
            chunk = " ".join(words[i:i + tokens_per_chunk]) + " "
            current_chunk = i // tokens_per_chunk + 1
            yield chunk
            # Simulate LLM generation delay (50-150ms per token)
            await asyncio.sleep(0.05 + (0.1 * (i % 3)))

    audio_chunks = []
    chunk_count = 0
    words = text.split()
    total_send_chunks = (len(words) + 2 - 1) // 2  # tokens_per_chunk=2, ceiling division
    send_progress = 0
    # Create a shared counter for sending progress
    send_counter = 0
    text_gen = llm_token_generator(text)

    print("🎵 Starting LLM token streaming test...")
    print("🔄 LLM Sending | 🔊 TTS Receiving")
    print("-" * 60)

    # Use the same recording system as the web interface
    record_chunks = os.getenv('TTS_RECORD_CHUNKS', 'false').lower() == 'true'
    chunks_dir = os.getenv('TTS_CHUNKS_DIR', '/tmp/tts_chunks_web')
    
    # If recording is enabled, use a directory that's accessible from the host
    if record_chunks:
        # Use a directory within /app that maps to the host filesystem
        accessible_chunks_dir = '/app/services/tts/tests/audio_chunks'
        os.makedirs(accessible_chunks_dir, exist_ok=True)
        # Clear existing files for a new recording
        for file in os.listdir(accessible_chunks_dir):
            file_path = os.path.join(accessible_chunks_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        chunks_dir = accessible_chunks_dir
        print(f"📁 Audio chunk recording ENABLED - saving to: {chunks_dir}")
        print(f"   Audio files are accessible from host at: src/voicebot_app/services/tts/tests/audio_chunks/")
        print(f"   Set TTS_RECORD_CHUNKS=false to disable recording")
    else:
        # Fallback to temporary directory if recording is disabled
        chunks_dir = tempfile.mkdtemp(prefix="tts_chunks_")
        print(f"📁 Audio chunk recording DISABLED - using temporary directory: {chunks_dir}")
        print(f"   Set TTS_RECORD_CHUNKS=true to enable persistent recording")

    async def consume_stream():
        nonlocal chunk_count, send_progress, send_counter

        # Use the shared streaming manager like the web interface does
        session_id = "test_session"
        
        async def text_generator():
            async for chunk in text_gen:
                # Convert to standardized JSON format like the web interface
                payload = {
                    "text": chunk,
                    "try_trigger_generation": True,
                    "flush": False
                }
                yield json.dumps(payload)
            # Send final signal
            final_payload = {
                "text": "",
                "try_trigger_generation": True,
                "flush": True
            }
            yield json.dumps(final_payload)

        async for audio_chunk in shared_streaming_manager.stream_text_to_audio_no_websocket(
            text_generator(), tts_service, session_id
        ):
            audio_chunks.append(audio_chunk)
            chunk_count += 1
            
            # Save each chunk to a file for analysis using the same system as web interface
            chunk_filename = os.path.join(chunks_dir, f"chunk_{chunk_count:03d}.wav")
            with open(chunk_filename, 'wb') as f:
                f.write(audio_chunk)
            print(f"💾 Saved chunk {chunk_count} to {chunk_filename} ({len(audio_chunk)} bytes)")
            
            # Create a readable summary file with chunk information
            summary_file = os.path.join(chunks_dir, "chunks_summary.txt")
            with open(summary_file, 'w') as f:
                f.write("TTS Audio Chunks Summary\n")
                f.write("=" * 50 + "\n")
                f.write(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Agent: {agent_config.tts_provider}\n")
                f.write(f"Text: {text[:100]}...\n\n")
                f.write("Chunk Details:\n")
                f.write("-" * 30 + "\n")
                for i, chunk in enumerate(audio_chunks, 1):
                    f.write(f"Chunk {i:03d}: {len(chunk):,} bytes\n")
                f.write(f"\nTotal chunks: {len(audio_chunks)}\n")
                f.write(f"Total bytes: {sum(len(c) for c in audio_chunks):,}\n")
            
            # Update send_progress from the shared counter
            send_progress = send_counter

            # Show both progress bars on the same line
            send_bar = create_progress_bar(send_progress, total_send_chunks, prefix="🔄 LLM Sending")
            receive_bar = create_progress_bar(chunk_count, max(chunk_count + 5, total_send_chunks), prefix="🔊 TTS Receiving")
            print(f"\r{send_bar} | {receive_bar}", end="", flush=True)

    # Track sending progress by counting the chunks sent
    async def track_sending():
        nonlocal send_counter
        async for _ in llm_token_generator(text):
            send_counter += 1

    # Run both tasks concurrently
    send_task = asyncio.create_task(track_sending())

    # Timeout global de 15s to ensure both sending and receiving complete
    try:
        await asyncio.wait_for(consume_stream(), timeout=15)
    except asyncio.TimeoutError:
        print("\n⚠️ Timeout reached — stopping stream gracefully")
    finally:
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass

    # Show final progress at 100%
    send_bar = create_progress_bar(total_send_chunks, total_send_chunks, prefix="🔄 LLM Sending")
    receive_bar = create_progress_bar(chunk_count, chunk_count, prefix="🔊 TTS Receiving")
    print(f"\r{send_bar} | {receive_bar}")

    # Verify both sending and receiving completed successfully
    sending_complete = (send_progress == total_send_chunks)
    receiving_complete = (chunk_count > 0)

    if audio_chunks and sending_complete and receiving_complete:
        total = sum(len(c) for c in audio_chunks)
        print(f"\n✅ {len(audio_chunks)} chunks received, total {total:,} bytes")
        
        # Final summary message
        if record_chunks:
            # Convert chunks to playable WAV format
            if make_chunks_playable(chunks_dir):
                print(f"🔊 Audio chunks converted to playable WAV format")
            
            # Create playback instructions
            instructions_file = create_audio_playback_instructions(chunks_dir)
            summary_file = os.path.join(chunks_dir, "chunks_summary.txt")
            print(f"📄 Readable summary saved to: {summary_file}")
            print(f"📋 Playback instructions: {instructions_file}")
            print(f"� Audio chunks saved to: {chunks_dir}")
        else:
            print(f"📁 Audio chunks saved to temporary directory: {chunks_dir}")
            print(f"   Set TTS_RECORD_CHUNKS=true to enable persistent recording")
            
        assert sending_complete, f"Sending not complete: {send_progress}/{total_send_chunks}"
        assert receiving_complete, f"Receiving not complete: {chunk_count} chunks"
    else:
        print(f"\n⚠️ Test failed - Sending: {send_progress}/{total_send_chunks}, Receiving: {chunk_count} chunks")
        assert False, f"Streaming incomplete - Sending: {send_progress}/{total_send_chunks}, Receiving: {chunk_count} chunks"

@pytest.mark.asyncio
async def test_tts_service_initialization(agent_id=None, agent_name=None):
    """Verify that TTS service initializes properly with agent configuration"""
    # Get agent configuration
    agent_config = get_agent_config(agent_id, agent_name)
    
    # Initialize TTS service
    tts_service = TTSService()
    assert tts_service.provider is not None
    
    current_provider = agent_config.tts_provider
    print(f"TTS service initialized with provider: {current_provider}")
    print(f"Agent TTS configuration: {agent_config.tts_config}")
    
    # Verify provider-specific configuration based on current provider
    if current_provider == "async.ai":
        assert agent_config.tts_config.get("api_key") is not None
        # async.ai doesn't require URL in config, it's hardcoded in the provider
    elif current_provider == "elevenlabs.io":
        assert agent_config.tts_config.get("api_key") is not None
        assert agent_config.tts_config.get("voice") is not None
    elif current_provider == "kokoro.local":
        assert agent_config.tts_config.get("url") is not None
        assert agent_config.tts_config.get("voice_id") is not None
    elif current_provider == "deepgram.com":
        assert agent_config.tts_config.get("api_key") is not None
        assert agent_config.tts_config.get("model") is not None
    
    print("✅ TTS service initialized successfully with agent configuration")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test TTS Live Streaming with Agent Selection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  TTS_RECORD_CHUNKS     - Set to 'true' to save audio chunks to files (default: false)
  TTS_CHUNKS_DIR        - Directory to save audio chunks (default: /tmp/tts_chunks_web)
  TTS_INTERFACE_TEXT    - Text to use for TTS synthesis (can be overridden with --text)

Examples:
  # Test with default agent
  python test_tts_live_streaming.py

  # Test with specific agent by name
  python test_tts_live_streaming.py --agent-name "whisper-groq-elevenlabs"

  # Test with specific agent by ID
  python test_tts_live_streaming.py --agent-id "87b5b8ca-027c-4f97-95e8-74f77d7c1ca8"

  # List available agents
  python test_tts_live_streaming.py --list-agents

  # Test with custom text
  python test_tts_live_streaming.py --text "Hello, this is a test"
        """
    )
    parser.add_argument("--agent-id", help="Test with specific agent ID")
    parser.add_argument("--agent-name", help="Test with specific agent name")
    parser.add_argument("--list-agents", action="store_true", help="List available agents and exit")
    parser.add_argument("--text", help="Custom text for TTS (overrides TTS_INTERFACE_TEXT env var)")
    return parser.parse_args()

async def main():
    """Main function to run the test with optional agent selection."""
    args = parse_arguments()
    
    if args.list_agents:
        list_available_agents()
        return
    
    # Override text if provided
    if args.text:
        os.environ["TTS_INTERFACE_TEXT"] = args.text
    
    print("🎵 Starting TTS Live Streaming Test")
    print("=" * 60)
    
    if args.agent_id:
        print(f"🔧 Using agent ID: {args.agent_id}")
    elif args.agent_name:
        print(f"🔧 Using agent name: {args.agent_name}")
    else:
        print("🔧 Using default agent")
    
    # Run service initialization test with selected agent
    await test_tts_service_initialization(args.agent_id, args.agent_name)
    
    # Run live streaming test with selected agent
    await test_tts_live_streaming(args.agent_id, args.agent_name)
    
    print("✅ Live streaming tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
