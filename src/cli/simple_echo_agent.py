import asyncio
import logging
import os
import signal
from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo-client")

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = "echo-test"

async def main():
    # 1. Generate Token
    logger.info(f"Generating token for room: {ROOM_NAME}")
    token = api.AccessToken(API_KEY, API_SECRET) \
        .with_identity("echo-bot") \
        .with_name("Echo Bot") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=ROOM_NAME,
            can_publish=True,
            can_subscribe=True
        )).to_jwt()

    # 2. Connect to Room
    room = rtc.Room()
    
    @room.on("participant_connected")
    def on_participant_connected(participant):
        logger.info(f"Participant connected: {participant.identity}")

    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        logger.info(f"Subscribed to track {track.kind} from {participant.identity}")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(echo_audio(room, track))

    logger.info(f"Connecting to {LIVEKIT_URL}...")
    try:
        await room.connect(LIVEKIT_URL, token)
        logger.info(f"✅ Connected to room: {room.name}")
    except Exception as e:
        logger.error(f"❌ Failed to connect: {e}")
        return

    # 3. Publish Echo Track
    # Create a local audio track that we will push audio into
    source = rtc.AudioSource(sample_rate=48000, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("echo-out", source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    
    await room.local_participant.publish_track(track, options)
    logger.info("📢 Published echo track")

    # 4. Echo Logic
    async def echo_audio(room, remote_track):
        logger.info("🔁 Starting echo loop...")
        stream = rtc.AudioStream(remote_track)
        
        async for event in stream:
            # Capture the frame and send it back through our source
            await source.capture_frame(event.frame)

    # Keep running until interrupted
    logger.info("🚀 Echo bot running. Press Ctrl+C to exit.")
    
    # Handle shutdown
    shutdown_event = asyncio.Event()
    def signal_handler():
        shutdown_event.set()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    await shutdown_event.wait()
    
    logger.info("Shutting down...")
    await room.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
