#!/usr/bin/env python3
"""
Simple LiveKit audio client for testing echo agent.
Connects to a room and sends/receives audio without requiring backend agent.
"""
import asyncio
import logging
import os
import signal
from dotenv import load_dotenv
from livekit import api, rtc

# Import the new environment configuration
from environment_config import get_livekit_url, get_voicebot_api_url

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test-client")

# Use environment-aware LiveKit URL
LIVEKIT_URL = os.getenv("LIVEKIT_URL", get_livekit_url())
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = "echo-test"

async def main():
    # Generate Token
    logger.info(f"Generating token for room: {ROOM_NAME}")
    token = api.AccessToken(API_KEY, API_SECRET) \
        .with_identity("test-user") \
        .with_name("Test User") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=ROOM_NAME,
            can_publish=True,
            can_subscribe=True
        )).to_jwt()

    # Connect to Room
    room = rtc.Room()
    
    @room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"👤 Participant connected: {participant.identity}")

    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        logger.info(f"🔊 Subscribed to {track.kind} track from {participant.identity}")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info("🎧 Audio track received - you should hear the echo!")

    logger.info(f"Connecting to {LIVEKIT_URL}...")
    await room.connect(LIVEKIT_URL, token)
    logger.info(f"✅ Connected to room: {room.name}")

    # Publish Microphone Audio
    logger.info("🎤 Starting microphone capture...")
    from cli.livekit_client import LiveKitClient
    
    # Use existing audio capture logic
    client = LiveKitClient(ROOM_NAME, token, LIVEKIT_URL)
    await client.connect()
    await client.start_audio_capture()
    
    logger.info("🚀 Audio session active!")
    logger.info("🗣️  Speak into your microphone - you should hear yourself echoed back!")
    logger.info("Press Ctrl+C to exit")

    # Keep running
    shutdown_event = asyncio.Event()
    def signal_handler():
        shutdown_event.set()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    await shutdown_event.wait()
    
    logger.info("Shutting down...")
    client.stop_audio_capture()
    await room.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
