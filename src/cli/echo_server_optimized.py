#!/usr/bin/env python3
"""
LiveKit Echo Server Optimisé - Version avec VAD Silero et architecture officielle LiveKit
"""

import asyncio
import logging
import os
import signal
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
    START_OF_SPEECH = "start_of_speech"
    END_OF_SPEECH = "end_of_speech"

class VADStream:
    """Wrapper around SileroVADService to provide stream-like interface"""
    
    def __init__(self, vad_service: SileroVADService):
        self.vad_service = vad_service
        self._queue = asyncio.Queue()
        self._resampler = None
        
    def push_frame(self, frame: rtc.AudioFrame):
        """Process audio frame and detect VAD events"""
        try:
            # Initialize resampler if needed
            if self._resampler is None:
                self._resampler = rtc.AudioResampler(
                    input_rate=frame.sample_rate,
                    output_rate=16000,
                    quality=rtc.AudioResamplerQuality.QUICK  # VAD doesn't need high quality, but needs speed
                )

            # Log frame details once per second roughly
            import random
            if random.random() < 0.01:
                logger.info(f"🎤 Input frame: rate={frame.sample_rate}, channels={frame.num_channels}, samples={frame.samples_per_channel}")

            # Resample using LiveKit's native resampler (better than np.interp)
            resampled_frames = self._resampler.push(frame)
            
            for resampled_frame in resampled_frames:
                # Get raw data
                import numpy as np
                audio_int16 = np.frombuffer(resampled_frame.data, dtype=np.int16)
                
                # Process with VAD
                events = self.vad_service.process_audio_chunk(resampled_frame.data)
                
                for event in events:
                    if event["type"] == "speech_start":
                        logger.info("🎯 VAD detected SPEECH START")
                        self._queue.put_nowait({"type": VADEventType.START_OF_SPEECH})
                    elif event["type"] == "speech_end":
                        logger.info("🎯 VAD detected SPEECH END")
                        self._queue.put_nowait({"type": VADEventType.END_OF_SPEECH})
                    
        except Exception as e:
            logger.error(f"VAD processing error: {e}")
                    
        except Exception as e:
            logger.error(f"VAD processing error: {e}")
    
    async def __aiter__(self):
        """Async iterator for VAD events"""
        while True:
            try:
                event = await self._queue.get()
                yield event
            except asyncio.CancelledError:
                break

class OptimizedEchoServer:
    def __init__(self):
        self.room = None
        self.source = None
        self.shutdown_event = asyncio.Event()
        
        # State management
        self.is_speaking = False
        self.is_echoing = False
        
        # Audio queue (10 seconds buffer)
        self.queue = asyncio.Queue(maxsize=1000)
        
        # VAD setup - normal threshold now that resampling is fixed
        self.vad_service = SileroVADService(threshold=0.3)
        self.vad_stream = VADStream(self.vad_service)

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

        # 4. Start dual async tasks (input processing + VAD processing)
        input_task = asyncio.create_task(self._process_input(), name="input_processor")
        vad_task = asyncio.create_task(self._process_vad(), name="vad_processor")

        # 5. Setup signal handling
        self.setup_signal_handlers()

        # 6. Keep running until interrupted
        logger.info("🚀 Optimized echo bot running. Press Ctrl+C to exit.")
        await self.shutdown_event.wait()
        
        # 7. Clean shutdown
        logger.info("Shutting down...")
        input_task.cancel()
        vad_task.cancel()
        
        try:
            await asyncio.gather(input_task, vad_task, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
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
                    # Process frame through VAD
                    self.vad_stream.push_frame(event.frame)
                    
                    # Add to queue if not currently echoing
                    if not self.is_echoing:
                        try:
                            self.queue.put_nowait(event.frame)
                        except asyncio.QueueFull:
                            # Remove oldest frame to prevent latency
                            try:
                                self.queue.get_nowait()
                                self.queue.put_nowait(event.frame)
                                logger.debug("Queue full, removed oldest frame")
                            except asyncio.QueueEmpty:
                                pass
                
                # Log stats every 500 frames
                if frame_count % 500 == 0:
                    logger.info(f"📊 Processing stats - Frames: {frame_count}, Queue: {self.queue.qsize()}")
                    
        except Exception as e:
            logger.error(f"Audio stream processing error: {e}")
        finally:
            logger.info(f"Audio processing ended for {participant_identity}")

    async def _process_input(self):
        """Main input processing loop"""
        logger.info("🔁 Starting input processor...")
        
        while not self.shutdown_event.is_set():
            try:
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Input processor error: {e}")
                await asyncio.sleep(0.1)

    async def _process_vad(self):
        """Process VAD events and manage echo playback"""
        logger.info("🎯 Starting VAD processor...")
        
        while not self.shutdown_event.is_set():
            try:
                async for vad_event in self.vad_stream:
                    if vad_event["type"] == VADEventType.START_OF_SPEECH:
                        await self._handle_speech_start()
                    elif vad_event["type"] == VADEventType.END_OF_SPEECH:
                        await self._handle_speech_end()
                        
            except Exception as e:
                logger.error(f"VAD processor error: {e}")
                await asyncio.sleep(0.1)

    async def _handle_speech_start(self):
        """Handle speech start event"""
        if self.is_echoing:
            return  # Skip if already echoing
            
        self.is_speaking = True
        logger.info("🗣️ Speech detected, keeping last 100 frames")
        
        # Keep only the last 100 frames (1 second) for context
        frames_to_keep = 100
        frames = []
        
        # Empty the queue and keep only recent frames
        while not self.queue.empty():
            try:
                frame = self.queue.get_nowait()
                frames.append(frame)
            except asyncio.QueueEmpty:
                break
        
        # Put back only the last frames_to_keep frames
        for frame in frames[-frames_to_keep:]:
            try:
                self.queue.put_nowait(frame)
            except asyncio.QueueFull:
                break
                
        logger.info(f"📊 Buffer optimized: kept {min(len(frames), frames_to_keep)}/{len(frames)} frames")

    async def _handle_speech_end(self):
        """Handle speech end event - echo the buffered audio"""
        if self.is_echoing:
            return  # Skip if already echoing
            
        self.is_speaking = False
        self.is_echoing = True
        logger.info("🛑 Speech ended, starting echo playback")
        
        try:
            # Echo all frames in the queue
            frames_echoed = 0
            while not self.queue.empty():
                try:
                    frame = self.queue.get_nowait()
                    await self.source.capture_frame(frame)
                    frames_echoed += 1
                    self.queue.task_done()
                    
                    # Pace the playback to match real-time
                    # Frame duration = samples / sample_rate
                    duration = frame.samples_per_channel / frame.sample_rate
                    await asyncio.sleep(duration)
                    
                except asyncio.QueueEmpty:
                    break
                except Exception as e:
                    logger.warning(f"Frame capture error during echo: {e}")
                    
            logger.info(f"📢 Echoed {frames_echoed} frames")
            
        except Exception as e:
            logger.error(f"Echo playback error: {e}")
        finally:
            self.is_echoing = False
            logger.info("✅ Echo playback completed")

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