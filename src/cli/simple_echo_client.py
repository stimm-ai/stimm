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
        room="echo-test"
    )
    token = AccessToken(
        api_key="devkey",
        api_secret="secret"
    ).with_identity("test-client").with_name("Test Client").with_grants(grants).to_jwt()
    
    logger.info(f"Connecting to {url}")
    await room.connect(url, token)
    logger.info("✅ Connected to room")
    
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
        if track.kind == rtc.TrackKind.KIND_AUDIO and participant.identity.startswith("agent-"):
            logger.info(f"🎧 Audio track from {participant.identity}")
            asyncio.create_task(play_audio(track))
    
    logger.info("🚀 Echo client running! Speak and you should hear yourself!")
    
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
                
                # Log every 500 frames
                if frame_count % 500 == 0:
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
                
                # Log every 500 frames
                if frame_count % 500 == 0:
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