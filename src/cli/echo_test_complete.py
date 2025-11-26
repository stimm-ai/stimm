#!/usr/bin/env python3
"""
Complete LiveKit echo test client with audio playback.
"""
import asyncio
import logging
import subprocess
import os
from livekit import api, rtc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echo-test")

LIVEKIT_URL = "ws://livekit:7880"
API_KEY = "devkey"
API_SECRET = "secret"
ROOM_NAME = "echo-test"

# FFplay process for audio playback
ffplay_process = None

async def main():
    global ffplay_process
    
    # Generate token
    token = api.AccessToken(API_KEY, API_SECRET) \
        .with_identity("test-user") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=ROOM_NAME,
            can_publish=True,
            can_subscribe=True
        )).to_jwt()

    # Connect to room
    room = rtc.Room()
    
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎧 Audio track from {participant.identity} - Starting playback!")
            asyncio.create_task(play_audio(track))

    logger.info(f"Connecting to {LIVEKIT_URL}...")
    await room.connect(LIVEKIT_URL, token)
    logger.info(f"✅ Connected to room: {room.name}")

    # Publish microphone
    logger.info("🎤 Publishing microphone...")
    source = rtc.AudioSource(sample_rate=16000, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("mic", source)
    await room.local_participant.publish_track(track, rtc.TrackPublishOptions())
    
    # Start mic capture
    asyncio.create_task(capture_mic(source))
    
    logger.info("🚀 Echo test running! Speak and you should hear yourself!")
    logger.info("Press Ctrl+C to exit")
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        if ffplay_process:
            ffplay_process.terminate()
        await room.disconnect()

async def capture_mic(source):
    """Capture microphone using ffmpeg"""
    cmd = [
        "ffmpeg", "-f", "pulse", "-i", "default",
        "-ac", "1", "-ar", "16000", "-f", "s16le", "-"
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    chunk_size = 640  # 20ms at 16kHz
    while True:
        data = process.stdout.read(chunk_size)
        if not data:
            break
        
        # Create audio frame
        frame = rtc.AudioFrame.create(16000, 1, len(data) // 2)
        import numpy as np
        np.copyto(np.frombuffer(frame.data, dtype=np.int16), 
                  np.frombuffer(data, dtype=np.int16))
        await source.capture_frame(frame)

async def play_audio(track):
    """Play received audio using ffplay"""
    global ffplay_process
    
    cmd = [
        "ffplay", "-f", "s16le", "-ar", "48000", 
        "-ac", "1", "-nodisp", "-autoexit", "-"
    ]
    ffplay_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)  # Capture stderr

    # Log ffplay errors in background
    async def log_stderr():
        while ffplay_process and ffplay_process.poll() is None:
            line = await asyncio.to_thread(ffplay_process.stderr.readline)
            if line:
                logger.error(f"ffplay error: {line.decode().strip()}")
    
    asyncio.create_task(log_stderr())
    
    stream = rtc.AudioStream(track)
    async for event in stream:
        frame = event.frame
        # Write audio data to ffplay
        ffplay_process.stdin.write(bytes(frame.data))

if __name__ == "__main__":
    asyncio.run(main())
