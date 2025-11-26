import asyncio
import logging
import os
import signal
from dotenv import load_dotenv
from livekit import api, rtc

# Import the new environment configuration
from environment_config import get_livekit_url

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo-client")

# Configuration - use environment-aware LiveKit URL
LIVEKIT_URL = os.getenv("LIVEKIT_URL", get_livekit_url())
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
            asyncio.create_task(echo_audio(room, track, source))

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
    # Use SOURCE_UNKNOWN instead of SOURCE_MICROPHONE to avoid audio processing
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_UNKNOWN)
    
    await room.local_participant.publish_track(track, options)
    logger.info("📢 Published echo track")

    # 4. Echo Logic - pass source as parameter
    async def echo_audio(room, remote_track, echo_source=source):
        logger.info("🔁 Starting echo loop...")
        stream = rtc.AudioStream(remote_track)
        frame_count = 0
        error_count = 0
        last_log_time = asyncio.get_event_loop().time()
        
        try:
            async for event in stream:
                frame_count += 1
                try:
                    # Validate that we have valid frame data
                    if event.frame and len(event.frame.data) > 0:
                        # Use SOURCE_UNKNOWN to capture frame without audio processing
                        await echo_source.capture_frame(event.frame)
                    else:
                        logger.debug(f"Skipping empty frame #{frame_count}")
                        
                except Exception as e:
                    error_count += 1
                    logger.warning(f"Frame capture error #{error_count}: {e}")
                    
                    # Log detailed info periodically
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_log_time > 5.0:  # Every 5 seconds
                        logger.info(f"Echo stats - Frames: {frame_count}, Errors: {error_count}, Error rate: {error_count/frame_count*100:.1f}%")
                        last_log_time = current_time
                        
                    # Reset source if too many errors
                    if error_count > 10:
                        logger.warning("Too many frame capture errors, attempting to reset source...")
                        try:
                            # Try to reinitialize the source
                            echo_source = rtc.AudioSource(sample_rate=48000, num_channels=1)
                            track = rtc.LocalAudioTrack.create_audio_track("echo-out-reset", echo_source)
                            await room.local_participant.publish_track(track, options)
                            error_count = 0
                            logger.info("Audio source reset successfully")
                        except Exception as reset_error:
                            logger.error(f"Failed to reset audio source: {reset_error}")
                            break
                    
                    # Brief pause on error to avoid overwhelming the system
                    await asyncio.sleep(0.01)
                    
        except Exception as e:
            logger.error(f"Echo loop error: {e}")
            raise
        finally:
            logger.info(f"Echo loop ended - Total frames: {frame_count}, Total errors: {error_count}")

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
