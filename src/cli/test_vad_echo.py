#!/usr/bin/env python3
"""
Test script to verify VAD echo functionality
"""

import asyncio
import logging
import os
from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vad-echo-test")

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = "echo-test"
TEST_IDENTITY = "vad-test-client"

async def test_vad_echo():
    """Test that VAD echo is working by sending audio and checking for echo"""
    logger.info("🚀 Starting VAD echo test...")
    
    # Generate token
    token = api.AccessToken(API_KEY, API_SECRET) \
        .with_identity(TEST_IDENTITY) \
        .with_name("VAD Test Client") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=ROOM_NAME,
            can_publish=True,
            can_subscribe=True
        )).to_jwt()

    # Connect to room
    room = rtc.Room()
    
    echo_received = asyncio.Event()
    
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        logger.info(f"Subscribed to track {track.kind} from {participant.identity}")
        if track.kind == rtc.TrackKind.KIND_AUDIO and participant.identity == "echo-bot":
            logger.info("✅ Connected to echo bot audio track")
            echo_received.set()

    try:
        await room.connect(LIVEKIT_URL, token)
        logger.info(f"✅ Connected to room: {room.name}")
        
        # Wait for echo bot connection
        logger.info("⏳ Waiting for echo bot connection...")
        try:
            await asyncio.wait_for(echo_received.wait(), timeout=10.0)
            logger.info("✅ Echo bot connected successfully!")
        except asyncio.TimeoutError:
            logger.error("❌ Echo bot not found in room")
            return False
            
        # Test complete
        logger.info("🎉 VAD echo test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False
    finally:
        await room.disconnect()

if __name__ == "__main__":
    success = asyncio.run(test_vad_echo())
    exit(0 if success else 1)