"""
Test TTS Live Streaming (Async.ai adaptive version)

This test verifies that the Async.AI WebSocket TTS service can handle
live streaming of incrementally generated text, letting the API decide
when to start audio synthesis naturally (no forced buffering flush).
"""

import asyncio
import os
import pytest
import time
import tempfile
import json
from services.tts.tts import TTSService
from services.shared_streaming import shared_streaming_manager

def create_progress_bar(current, total, width=20, prefix=""):
    """Create a simple text-based progress bar"""
    progress = int(width * current / total) if total > 0 else 0
    bar = "█" * progress + "░" * (width - progress)
    percentage = int(100 * current / total) if total > 0 else 0
    return f"{prefix} [{bar}] {percentage}%"

@pytest.mark.asyncio
async def test_tts_live_streaming():
    tts_service = TTSService()

    # Use the current configured provider instead of hardcoding "async.ai"
    current_provider = tts_service.config.get_provider()
    print(f"Testing with provider: {current_provider}")

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
    
    if record_chunks:
        # Create and clean the recording directory
        os.makedirs(chunks_dir, exist_ok=True)
        # Clear existing files for a new recording
        for file in os.listdir(chunks_dir):
            file_path = os.path.join(chunks_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        print(f"📁 Enregistrement des chunks audio activé dans: {chunks_dir}")
    else:
        # Fallback to temporary directory if recording is disabled
        chunks_dir = tempfile.mkdtemp(prefix="tts_chunks_")
        print(f"📁 Saving audio chunks to: {chunks_dir}")

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
        assert sending_complete, f"Sending not complete: {send_progress}/{total_send_chunks}"
        assert receiving_complete, f"Receiving not complete: {chunk_count} chunks"
    else:
        print(f"\n⚠️ Test failed - Sending: {send_progress}/{total_send_chunks}, Receiving: {chunk_count} chunks")
        assert False, f"Streaming incomplete - Sending: {send_progress}/{total_send_chunks}, Receiving: {chunk_count} chunks"

@pytest.mark.asyncio
async def test_tts_service_initialization():
    """Verify that TTS service initializes properly with current configuration"""
    tts_service = TTSService()
    assert tts_service.provider is not None
    current_provider = tts_service.config.get_provider()
    print(f"TTS service initialized with provider: {current_provider}")
    
    # Verify provider-specific configuration based on current provider
    if current_provider == "async.ai":
        assert tts_service.config.async_ai_api_key is not None
        assert tts_service.config.async_ai_url is not None
    elif current_provider == "elevenlabs.io":
        assert tts_service.config.elevenlabs_api_key is not None
        assert tts_service.config.elevenlabs_voice_id is not None
    elif current_provider == "kokoro.local":
        assert tts_service.config.kokoro_local_url is not None
        assert tts_service.config.kokoro_local_voice_id is not None
    elif current_provider == "deepgram.com":
        assert tts_service.config.deepgram_tts_api_key is not None
        assert tts_service.config.deepgram_model is not None
    
    print("✅ TTS service initialized successfully with environment configuration")

if __name__ == "__main__":
    asyncio.run(test_tts_service_initialization())
    asyncio.run(test_tts_live_streaming())
    print("Live streaming tests passed!")
