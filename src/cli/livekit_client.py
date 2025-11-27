"""
LiveKit Client for CLI audio mode.

This module implements the actual LiveKit WebRTC connection
to capture microphone audio and play back agent responses.
Refactored to use PyAudio (PortAudio) for robust, low-latency audio I/O.
"""

import asyncio
import logging
import threading
import time
import pyaudio
import numpy as np
from typing import Optional
from livekit import rtc

logger = logging.getLogger(__name__)

# Audio Configuration
SAMPLE_RATE = 48000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 960  # 20ms at 48kHz (matches LiveKit typical frame size)


class LiveKitClient:
    """
    LiveKit client for real-time audio communication.
    
    This client connects to a LiveKit room, captures microphone audio via PyAudio,
    and plays back agent responses through speakers via PyAudio.
    """
    
    def __init__(self, room_name: str, token: str, livekit_url: str):
        self.room_name = room_name
        self.token = token
        self.livekit_url = livekit_url
        self.is_connected = False
        self.room = rtc.Room()
        
        # Audio Engine (PyAudio)
        self._pa = pyaudio.PyAudio()
        self._input_stream = None
        self._output_stream = None
        self._running = False
        self._loop = None
        
        # LiveKit Audio Source
        self.audio_source = None
        self.audio_track = None
        self.mic_source = None
        self.mic_track = None
        
    async def connect(self):
        """
        Connect to the LiveKit room and set up audio streams.
        """
        try:
            logger.info(f"🔗 Connecting to LiveKit room: {self.room_name}")
            logger.info(f"📡 LiveKit URL: {self.livekit_url}")
            
            # Set up event handlers
            self._setup_event_handlers()
            
            # Create audio source for microphone capture
            self.mic_source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=CHANNELS)
            self.mic_track = rtc.LocalAudioTrack.create_audio_track("microphone", self.mic_source)
            
            # Connect to the room
            ws_url = self.livekit_url.replace("http://", "ws://").replace("https://", "wss://")
            logger.info(f"🌐 Connecting to WebSocket: {ws_url}")
            
            await self.room.connect(ws_url, self.token)
            self.is_connected = True
            
            # Publish track
            # Using SOURCE_MICROPHONE applies AGC which is generally good for voice
            await self.room.local_participant.publish_track(
                self.mic_track,
                rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            )
            
            logger.info("✅ LiveKit connection established")
            logger.info("🎤 Microphone capture active")
            logger.info("🔊 Audio playback active")
            logger.info(f"👤 Connected as: {self.room.local_participant.identity}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to LiveKit: {e}")
            raise
    
    def _setup_event_handlers(self):
        """Set up LiveKit room event handlers"""
        
        @self.room.on("connected")
        def on_connected():
            logger.info("✅ Successfully connected to LiveKit room")
            
        @self.room.on("disconnected")
        def on_disconnected():
            logger.info("🔌 Disconnected from LiveKit room")
            self.is_connected = False
            
        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"👤 Participant connected: {participant.identity}")
            
        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"👤 Participant disconnected: {participant.identity}")
            
        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"🔊 Subscribed to audio track from {participant.identity}")
                # Start audio playback for this track
                asyncio.create_task(self._handle_audio_track(track))
                
        @self.room.on("track_published")
        def on_track_published(
            publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
        ):
            logger.info(f"📡 Track published by {participant.identity}: {publication.sid}")
    
    async def disconnect(self):
        """
        Disconnect from the LiveKit room and stop audio.
        """
        try:
            if self.is_connected:
                logger.info("🔌 Disconnecting from LiveKit...")
                self.stop_audio_capture()
                await self.room.disconnect()
                self.is_connected = False
                logger.info("✅ Disconnected from LiveKit")
                
        except Exception as e:
            logger.error(f"❌ Error disconnecting from LiveKit: {e}")
    
    async def start_audio_session(self):
        """
        Start the audio session - capture microphone and play responses.
        """
        if not self.is_connected:
            await self.connect()
        
        # Start PyAudio capture
        self._start_audio_engine()
        
        logger.info("🎧 Starting audio session...")
        logger.info("🎤 Speak into your microphone to interact with the agent")
        logger.info("🔊 Agent responses will be played through your speakers")
        
        try:
            # Keep the session active and monitor room state
            while self.is_connected and self._running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Audio session error: {e}")
            self.stop_audio_capture()
            raise

    def _start_audio_engine(self):
        """Start PyAudio input/output streams"""
        self._loop = asyncio.get_event_loop()
        self._running = True
        
        # Input Stream (Microphone)
        self._input_thread = threading.Thread(target=self._input_worker, daemon=True)
        self._input_thread.start()
        
        # Output Stream (Speaker)
        try:
            self._output_stream = self._pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                output=True,
                frames_per_buffer=CHUNK_SIZE
            )
            logger.info("🔊 Output stream started")
        except Exception as e:
            logger.error(f"Failed to open output stream: {e}")

    def stop_audio_capture(self):
        """Stop PyAudio streams"""
        self._running = False
        if self._input_stream:
            try:
                self._input_stream.stop_stream()
                self._input_stream.close()
            except Exception:
                pass
        if self._output_stream:
            try:
                self._output_stream.stop_stream()
                self._output_stream.close()
            except Exception:
                pass
        self._pa.terminate()
        logger.info("🛑 Audio engine stopped")

    def _input_worker(self):
        """Background thread to capture audio from PyAudio"""
        logger.info("🎤 Input thread started")
        try:
            stream = self._pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            self._input_stream = stream
            
            while self._running:
                try:
                    # Blocking read
                    data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    if self._loop and self.mic_source:
                        self._loop.call_soon_threadsafe(self._on_mic_data, data)
                except Exception as e:
                    logger.error(f"Input read error: {e}")
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to start input stream: {e}")

    def _on_mic_data(self, data):
        """Callback from input thread to push data to LiveKit"""
        # Create a new frame
        frame = rtc.AudioFrame.create(SAMPLE_RATE, CHANNELS, len(data) // 2)
        
        # Copy data efficiently using numpy
        frame_data_np = np.frombuffer(frame.data, dtype=np.int16)
        input_np = np.frombuffer(data, dtype=np.int16)
        np.copyto(frame_data_np, input_np)
        
        # Capture frame (async fire-and-forget)
        asyncio.ensure_future(self.mic_source.capture_frame(frame))

    async def _handle_audio_track(self, track: rtc.AudioTrack):
        """Stream audio from LiveKit track to PyAudio output"""
        stream = rtc.AudioStream(track)
        async for event in stream:
            if event.frame and self._output_stream:
                try:
                    # Convert frame to bytes
                    data = np.frombuffer(event.frame.data, dtype=np.int16).tobytes()
                    # Push to audio output (blocking write in executor to avoid blocking event loop)
                    await asyncio.get_event_loop().run_in_executor(
                        None, 
                        self._write_audio, 
                        data
                    )
                except Exception as e:
                    logger.error(f"Playback error: {e}")

    def _write_audio(self, data):
        """Blocking write to PyAudio output stream"""
        if self._output_stream:
            try:
                self._output_stream.write(data)
            except Exception as e:
                logger.error(f"Output write error: {e}")


async def create_livekit_client(room_name: str, token: str, livekit_url: str) -> LiveKitClient:
    """
    Create and connect a LiveKit client.
    """
    client = LiveKitClient(room_name, token, livekit_url)
    await client.connect()
    return client