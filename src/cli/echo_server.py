#!/usr/bin/env python3
"""
LiveKit Echo Server Optimisé - Version avec VAD Silero et architecture officielle LiveKit
"""

import asyncio
import logging
import os
import signal
import numpy as np
from dotenv import load_dotenv
from livekit import api, rtc

# Import our existing VAD service
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.vad.silero_service import SileroVADService

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("echo-server-optimized")

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = "echo-test"
AGENT_IDENTITY = "echo-bot"

class VADEventType:
    START_OF_SPEECH = "speech_start"
    END_OF_SPEECH = "speech_end"

class OptimizedEchoServer:
    def __init__(self):
        self.room = None
        self.source = None
        self.shutdown_event = asyncio.Event()
        
        # State management
        self.is_speaking = False
        
        # VAD setup - normal threshold now that resampling is fixed
        self.vad_service = SileroVADService(threshold=0.5)
        self.vad_stream = self.vad_service.create_stream()
        
        # Resampler for VAD input
        self._resampler = None

    async def main(self):
        """Main entry point for optimized echo server"""
        logger.info(f"🚀 Starting optimized echo server for room: {ROOM_NAME}")
        
        # 1. Generate Token
        token = api.AccessToken(API_KEY, API_SECRET) \
            .with_identity(AGENT_IDENTITY) \
            .with_name("Echo Bot") \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=ROOM_NAME,
                can_publish=True,
                can_subscribe=True
            )).to_jwt()

        # 2. Connect to Room
        self.room = rtc.Room()
        
        @self.room.on("participant_connected")
        def on_participant_connected(participant):
            logger.info(f"Participant connected: {participant.identity}")

        @self.room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            logger.info(f"Subscribed to track {track.kind} from {participant.identity}")
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                asyncio.create_task(self._process_audio_stream(track, participant.identity))

        logger.info(f"Connecting to {LIVEKIT_URL}...")
        try:
            await self.room.connect(LIVEKIT_URL, token)
            logger.info(f"✅ Connected to room: {self.room.name}")
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return

        # 3. Publish Echo Track
        self.source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        track = rtc.LocalAudioTrack.create_audio_track("echo-out", self.source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        
        await self.room.local_participant.publish_track(track, options)
        logger.info("📢 Published echo track")

        # 4. Setup signal handling
        self.setup_signal_handlers()

        # 5. Keep running until interrupted
        logger.info("🚀 Optimized echo bot running. Press Ctrl+C to exit.")
        await self.shutdown_event.wait()
        
        # 6. Clean shutdown
        logger.info("Shutting down...")
        
        await self.room.disconnect()
        logger.info("✅ Echo server shutdown complete")

    async def _process_audio_stream(self, remote_track, participant_identity):
        """Process incoming audio stream"""
        logger.info(f"🎵 Starting audio processing for {participant_identity}")
        stream = rtc.AudioStream(remote_track)
        
        frame_count = 0
        try:
            async for event in stream:
                frame_count += 1
                
                if event.frame and len(event.frame.data) > 0:
                    # 1. Echo immediately (Instant Echo)
                    await self.source.capture_frame(event.frame)

                    # 2. Process VAD in parallel (for events/logging)
                    # Initialize resampler if needed
                    if self._resampler is None:
                        self._resampler = rtc.AudioResampler(
                            input_rate=event.frame.sample_rate,
                            output_rate=16000,
                            quality=rtc.AudioResamplerQuality.QUICK
                        )

                    # Resample for VAD
                    resampled_frames = self._resampler.push(event.frame)
                    for resampled_frame in resampled_frames:
                        vad_events = await self.vad_stream.process_audio_chunk(resampled_frame.data)
                        
                        for vad_event in vad_events:
                            if vad_event["type"] == VADEventType.START_OF_SPEECH:
                                logger.info("🎯 VAD detected SPEECH START")
                                self.is_speaking = True
                            elif vad_event["type"] == VADEventType.END_OF_SPEECH:
                                logger.info("🎯 VAD detected SPEECH END")
                                self.is_speaking = False
                
                # Log stats every 500 frames
                if frame_count % 500 == 0:
                    logger.info(f"📊 Processing stats - Frames: {frame_count}, Speaking: {self.is_speaking}")
                    
        except Exception as e:
            logger.error(f"Audio stream processing error: {e}")
        finally:
            logger.info(f"Audio processing ended for {participant_identity}")

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler():
            logger.info("Received shutdown signal")
            self.shutdown_event.set()
        
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

async def main():
    server = OptimizedEchoServer()
    await server.main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise