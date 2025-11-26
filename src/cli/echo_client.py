#!/usr/bin/env python3
"""
Simple LiveKit Echo Client - Version sans livekit.agents pour éviter les conflits de port
"""

import asyncio
import logging
import subprocess
import os
import time
from dotenv import load_dotenv

from livekit import rtc
from livekit.api import AccessToken, VideoGrants

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple-echo-client")


async def main():
    """Connect to LiveKit and test echo"""
    logger.info("🚀 Starting simple echo client")
    
    # Create LiveKit room
    room = rtc.Room()
    
    # Connect to LiveKit
    url = "ws://localhost:7880"
    grants = VideoGrants(
        room_join=True,
        room="echo-test",
        can_publish=True,
        can_subscribe=True,
    )
    token = AccessToken(
        api_key="devkey",
        api_secret="secret"
    ).with_identity("test-client").with_name("Test Client").with_grants(grants).to_jwt()
    
    logger.info(f"Connecting to {url}")
    
    # Add detailed event handlers for debugging
    @room.on("participant_connected")
    def on_participant_connected(participant):
        logger.debug(f"🔍 Participant connected: {participant.identity}")
        logger.debug(f"   - SID: {participant.sid}")
        logger.debug(f"   - Name: {participant.name}")
        logger.debug(f"   - Tracks: {len(participant.track_publications)}")
        for pub_id, publication in participant.track_publications.items():
            logger.debug(f"     Track {pub_id}: {publication.kind} - {publication.source}")
    
    @room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        logger.debug(f"🔍 Participant disconnected: {participant.identity}")
    
    @room.on("track_published")
    def on_track_published(publication, participant):
        logger.debug(f"📢 Track published by {participant.identity}: {publication.kind} - {publication.source}")
    
    @room.on("track_unpublished")
    def on_track_unpublished(publication, participant):
        logger.debug(f"📢 Track unpublished by {participant.identity}: {publication.kind}")
    
    @room.on("track_subscription_failed")
    def on_track_subscription_failed(track, publication, participant, error):
        logger.error(f"❌ Track subscription failed from {participant.identity}: {error}")
    
    await room.connect(url, token)
    logger.info("✅ Connected to room")
    
    # Log all current participants
    logger.debug(f"📊 Current participants in room:")
    for participant in room.remote_participants.values():
        logger.debug(f"   - {participant.identity} (SID: {participant.sid})")
        for pub_id, publication in participant.track_publications.items():
            logger.debug(f"     Track {pub_id}: {publication.kind} - {publication.source} - Subscribed: {publication._subscribed}")
    
    # Create audio source for microphone
    mic_source = rtc.AudioSource(sample_rate=48000, num_channels=1)
    mic_track = rtc.LocalAudioTrack.create_audio_track("mic", mic_source)
    
    # Publish microphone track
    await room.local_participant.publish_track(
        mic_track,
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
    )
    logger.info("🎤 Published microphone track")
    
    # Start microphone capture
    asyncio.create_task(capture_microphone(mic_source))
    
    # Handle incoming audio from echo agent
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            # Accept audio from echo-bot (or anyone for testing)
            logger.info(f"🎧 Audio track from {participant.identity}")
            asyncio.create_task(play_audio(track))
    
    # Subscribe to echo agent's audio track when it connects
    @room.on("participant_connected")
    def on_participant_connected(participant):
        if participant.identity == "echo-bot":
            logger.info(f"🔍 Echo agent connected: {participant.identity}")
            # Subscribe to all audio tracks from echo agent
            for publication in participant.track_publications.values():
                if publication.kind == rtc.TrackKind.KIND_AUDIO:
                    publication.set_subscribed(True)
                    logger.info(f"✅ Subscribed to audio track from {participant.identity}")
    
    # Also subscribe to existing participants when we connect
    for participant in room.remote_participants.values():
        if participant.identity == "echo-bot":
            logger.info(f"🔍 Found existing echo agent: {participant.identity}")
            for publication in participant.track_publications.values():
                if publication.kind == rtc.TrackKind.KIND_AUDIO:
                    publication.set_subscribed(True)
                    logger.info(f"✅ Subscribed to existing audio track from {participant.identity}")
    
    logger.info("� Echo client running! Speak and you should hear yourself!")
    
    # Keep running
    await asyncio.Event().wait()


async def capture_microphone(source):
    """Capture microphone using ffmpeg"""
    cmd = [
        "ffmpeg", "-f", "pulse", "-i", "default",
        "-ac", "1", "-ar", "48000", "-f", "s16le", "-"
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("🎤 Microphone capture started")
        
        chunk_size = 960  # 20ms at 48kHz
        frame_count = 0
        
        while True:
            try:
                data = process.stdout.read(chunk_size)
                if not data:
                    await asyncio.sleep(0.01)
                    continue
                
                frame_count += 1
                
                # Create audio frame
                frame = rtc.AudioFrame.create(48000, 1, len(data) // 2)
                import numpy as np
                np.copyto(np.frombuffer(frame.data, dtype=np.int16),
                          np.frombuffer(data, dtype=np.int16))
                
                # Send to LiveKit
                await source.capture_frame(frame)
                
                # Log every 2000 frames (reduced frequency for better performance)
                if frame_count % 2000 == 0:
                    logger.info(f"📊 Mic stats - Frames: {frame_count}")
                    
            except Exception as e:
                logger.warning(f"Microphone capture error: {e}")
                await asyncio.sleep(0.01)
                
    except Exception as e:
        logger.error(f"Microphone setup error: {e}")
    finally:
        if process:
            process.terminate()
        logger.info("Microphone capture stopped")


async def play_audio(track):
    """Play received audio using aplay (more stable than ffplay)"""
    cmd = [
        "aplay", "-f", "S16_LE", "-r", "48000",
        "-c", "1", "-q", "-"
    ]
    
    try:
        aplay_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        logger.info("🔊 Audio playback started with aplay")
        
        # Stream audio to aplay
        stream = rtc.AudioStream(track)
        frame_count = 0
        
        try:
            async for event in stream:
                frame = event.frame
                frame_count += 1
                
                # Write audio data to aplay
                try:
                    aplay_process.stdin.write(bytes(frame.data))
                    aplay_process.stdin.flush()
                except BrokenPipeError:
                    logger.warning("aplay broken pipe")
                    break
                except Exception as e:
                    logger.warning(f"Error writing to aplay: {e}")
                    break
                
                # Log every 2000 frames (reduced frequency for better performance)
                if frame_count % 2000 == 0:
                    logger.info(f"📊 Playback stats - Frames: {frame_count}")
                    
        except Exception as e:
            logger.error(f"Audio streaming error: {e}")
        finally:
            logger.info(f"Audio playback ended - Frames: {frame_count}")
            if aplay_process:
                aplay_process.terminate()
                
    except Exception as e:
        logger.error(f"Failed to start aplay: {e}")


if __name__ == "__main__":
    asyncio.run(main())