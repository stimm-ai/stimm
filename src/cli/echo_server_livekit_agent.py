#!/usr/bin/env python3
"""
LiveKit Echo Server - Version utilisant livekit.agents comme l'exemple officiel
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    AgentServer,
    AutoSubscribe,
    JobContext,
    cli,
)

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo-agent")

# Create AgentServer instance
server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """Main entrypoint for the echo agent"""
    logger.info(f"Connecting to room {ctx.room.name}")
    
    # Connect to the room
    await ctx.connect()
    logger.info("✅ Connected to room")

    # Subscribe to all audio tracks in the room
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"Subscribed to audio track from {participant.identity}")
            asyncio.create_task(echo_audio(track, participant.identity))

    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant connected: {participant.identity}")

    # Create audio source for echo output
    source = rtc.AudioSource(sample_rate=48000, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("echo", source)
    
    # Publish the echo track
    await ctx.room.local_participant.publish_track(
        track,
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
    )
    logger.info("📢 Published echo track")

    async def echo_audio(track, participant_identity):
        """Echo audio from a specific participant"""
        logger.info(f"🔁 Starting echo loop for {participant_identity}")
        stream = rtc.AudioStream(track)
        
        frame_count = 0
        error_count = 0
        
        try:
            async for audio_event in stream:
                frame_count += 1
                
                try:
                    if audio_event.frame and len(audio_event.frame.data) > 0:
                        # Echo the frame back immediately
                        await source.capture_frame(audio_event.frame)
                    else:
                        logger.debug(f"Skipping empty frame #{frame_count}")
                        
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:  # Only log first few errors
                        logger.warning(f"Frame capture error #{error_count}: {e}")
                    
                    # Brief pause on error
                    await asyncio.sleep(0.01)
                
                # Log stats every 500 frames
                if frame_count % 500 == 0:
                    error_rate = (error_count / frame_count * 100) if frame_count > 0 else 0
                    logger.info(f"📊 Echo stats for {participant_identity} - Frames: {frame_count}, Errors: {error_count}, Error rate: {error_rate:.1f}%")
                    
        except Exception as e:
            logger.error(f"Echo loop error for {participant_identity}: {e}")
        finally:
            logger.info(f"Echo loop ended for {participant_identity} - Total frames: {frame_count}, Total errors: {error_count}")

    # Keep the agent alive
    try:
        # Wait forever (or until disconnection)
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Agent shutting down")


if __name__ == "__main__":
    # Run the agent server using CLI
    cli.run_app(server)
