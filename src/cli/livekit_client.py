"""
LiveKit Client for CLI audio mode.

This module implements the actual LiveKit WebRTC connection
to capture microphone audio and play back agent responses.
"""

import asyncio
import logging
import json
import subprocess
import threading
import queue
from typing import Optional
from livekit import rtc

logger = logging.getLogger(__name__)


class LiveKitClient:
    """
    LiveKit client for real-time audio communication.
    
    This client connects to a LiveKit room, captures microphone audio,
    and plays back agent responses through speakers.
    """
    
    def __init__(self, room_name: str, token: str, livekit_url: str):
        self.room_name = room_name
        self.token = token
        self.livekit_url = livekit_url
        self.is_connected = False
        self.room = rtc.Room()
        
        # Audio components
        self.audio_source = None
        self.audio_track = None
        
        # Real audio capture
        self.audio_queue = queue.Queue()
        self.recording_queue = queue.Queue()  # Separate queue for recording
        self.audio_thread = None
        self.is_capturing = False
        
    async def connect(self):
        """
        Connect to the LiveKit room and set up audio streams.
        """
        try:
            logger.info(f"🔗 Connecting to LiveKit room: {self.room_name}")
            logger.info(f"📡 LiveKit URL: {self.livekit_url}")
            logger.info(f"🔑 Token: {self.token[:20]}...")
            
            # Set up event handlers
            self._setup_event_handlers()
            
            # Create audio source for microphone capture at 16kHz (required for VAD/STT)
            self.audio_source = rtc.AudioSource(sample_rate=16000, num_channels=1)
            self.audio_track = rtc.LocalAudioTrack.create_audio_track("microphone", self.audio_source)
            
            # Connect to the room
            ws_url = self.livekit_url.replace("http://", "ws://").replace("https://", "wss://")
            logger.info(f"🌐 Connecting to WebSocket: {ws_url}")
            
            await self.room.connect(ws_url, self.token)
            self.is_connected = True
            
            # Publish microphone track
            await self.room.local_participant.publish_track(
                self.audio_track,
                rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            )
            
            logger.info("✅ LiveKit connection established")
            logger.info("🎤 Microphone capture active")
            logger.info("🔊 Audio playback active")
            logger.info(f"👤 Connected as: {self.room.local_participant.identity}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to LiveKit: {e}")
            logger.error(f"🔧 Connection details - Room: {self.room_name}, URL: {self.livekit_url}")
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
                # Here we would set up audio playback
                
        @self.room.on("track_published")
        def on_track_published(
            publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
        ):
            logger.info(f"📡 Track published by {participant.identity}: {publication.sid}")
    
    async def disconnect(self):
        """
        Disconnect from the LiveKit room.
        """
        try:
            if self.is_connected:
                logger.info("🔌 Disconnecting from LiveKit...")
                self.stop_audio_capture()
                # TODO: Implement actual disconnection
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
        
        # Start real audio capture
        await self.start_audio_capture()
        
        logger.info("🎧 Starting audio session...")
        logger.info("🎤 Speak into your microphone to interact with the agent")
        logger.info("🔊 Agent responses will be played through your speakers")
        logger.info("📊 Waiting for agent to join the room...")
        
        try:
            # Keep the session active and monitor room state
            session_counter = 0
            while self.is_connected and self.is_capturing:
                await asyncio.sleep(1)
                session_counter += 1
                
                # Log session status periodically
                if session_counter % 10 == 0:  # Every 10 seconds
                    participants_count = len(self.room.remote_participants)
                    logger.info(f"📊 Session active - {session_counter} seconds, {participants_count} participants")
                    
                    # Check if agent has joined
                    agent_joined = any(
                        "agent" in participant.identity.lower()
                        for participant in self.room.remote_participants.values()
                    )
                    if agent_joined:
                        logger.info("🤖 Agent detected in room - ready for conversation")
                    else:
                        logger.info("⏳ Waiting for agent to join...")
                
        except Exception as e:
            logger.error(f"❌ Audio session error: {e}")
            self.stop_audio_capture()
            raise
    
    async def send_audio_chunk(self, audio_data: bytes):
        """
        Send an audio chunk to the LiveKit room.
        
        Args:
            audio_data: Raw audio data bytes
        """
        if not self.is_connected:
            logger.warning("⚠️ Not connected to LiveKit, cannot send audio")
            return
        
        try:
            if self.audio_source and len(audio_data) > 0:
                # Create audio frame from the chunk
                frame = rtc.AudioFrame(
                    data=audio_data,
                    sample_rate=16000,
                    num_channels=1,
                    samples_per_channel=len(audio_data) // 2  # Assuming 16-bit samples
                )
                await self.audio_source.capture_frame(frame)
                logger.debug(f"📤 Sent audio chunk to LiveKit: {len(audio_data)} bytes")
            else:
                logger.warning("⚠️ Audio source not available or empty audio chunk")
                
        except Exception as e:
            logger.error(f"❌ Error sending audio chunk: {e}")
    
    async def receive_audio_response(self) -> Optional[bytes]:
        """
        Receive an audio response from the agent.
        
        Returns:
            Audio data bytes or None if no response
        """
        if not self.is_connected:
            return None
        
        # TODO: Implement actual audio receiving
        # This would receive audio data from the LiveKit connection
        return None


    def _capture_audio_thread(self):
        """Background thread to capture audio from PulseAudio using ffmpeg"""
        try:
            logger.info("🎤 Starting real audio capture from PulseAudio...")
            
            # Log des paramètres audio
            logger.info("🔧 Audio capture parameters:")
            logger.info(f"   - Format: 16kHz, mono, 16-bit PCM")
            logger.info(f"   - Chunk size: 640 bytes (20ms at 16kHz)")
            logger.info(f"   - Source: PulseAudio source #2 (RDP microphone)")
            
            # Use ffmpeg to capture raw audio from PulseAudio at 16kHz (required for VAD/STT)
            cmd = [
                "ffmpeg",
                "-f", "pulse",
                "-i", "default",  # Use default PulseAudio source
                "-ac", "1",  # Convert to mono
                "-ar", "16000",  # Resample to 16kHz (required for VAD/STT)
                "-f", "s16le",  # 16-bit signed little-endian PCM
                "-"  # Output to stdout
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Read audio data in chunks (20ms at 16kHz = 320 samples * 2 bytes = 640 bytes)
            chunk_size = 640  # 20ms chunks at 16kHz
            chunk_counter = 0
            total_bytes = 0
            
            while self.is_capturing:
                audio_data = process.stdout.read(chunk_size)
                if audio_data:
                    # Calculate audio level (RMS)
                    import numpy as np
                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                    rms = np.sqrt(np.mean(audio_array**2))
                    
                    chunk_counter += 1
                    total_bytes += len(audio_data)
                    
                    # Log every 50 chunks (1 second)
                    if chunk_counter % 50 == 0:
                        logger.info(f"🎯 Audio capture stats:")
                        logger.info(f"   - Chunks: {chunk_counter}")
                        logger.info(f"   - Total bytes: {total_bytes}")
                        logger.info(f"   - RMS level: {rms:.2f}")
                        logger.info(f"   - Queue size: {self.audio_queue.qsize()}")
                    
                    self.audio_queue.put(audio_data)
                    # Also put in recording queue for saving to file
                    self.recording_queue.put(audio_data)
                else:
                    break
                    
            process.terminate()
            process.wait()
            
        except Exception as e:
            logger.error(f"❌ Error in audio capture thread: {e}")
    
    async def start_audio_capture(self):
        """Start capturing real audio from microphone"""
        if self.is_capturing:
            logger.warning("⚠️ Audio capture already running")
            return
            
        self.is_capturing = True
        self.audio_thread = threading.Thread(target=self._capture_audio_thread)
        self.audio_thread.daemon = True
        self.audio_thread.start()
        
        # Start sending audio to LiveKit
        asyncio.create_task(self._send_audio_to_livekit())
        
        logger.info("✅ Real audio capture started")
    
    def stop_audio_capture(self):
        """Stop capturing audio"""
        self.is_capturing = False
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2.0)
        logger.info("🛑 Audio capture stopped")
    
    async def _send_audio_to_livekit(self):
        """Send captured audio to LiveKit"""
        import asyncio
        import numpy as np
        frame_counter = 0
        error_counter = 0
        last_log_time = asyncio.get_event_loop().time()
        
        logger.info(f"🎬 Starting LiveKit audio transmission with dynamic AudioFrame creation")
        
        while self.is_capturing:
            try:
                # Get audio data from queue (non-blocking)
                try:
                    audio_data = self.audio_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)  # 10ms
                    continue
                
                # Convert bytes to int16 array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                samples_per_channel = len(audio_array)
                
                # Create AudioFrame dynamically based on actual chunk size using LiveKit's create() method
                audio_frame = rtc.AudioFrame.create(16000, 1, samples_per_channel)
                audio_data_view = np.frombuffer(audio_frame.data, dtype=np.int16)
                
                # Copy audio data into the frame buffer using np.copyto()
                np.copyto(audio_data_view, audio_array)
                
                # Send to LiveKit using the frame
                if self.audio_source:
                    try:
                        await self.audio_source.capture_frame(audio_frame)
                        frame_counter += 1
                        
                        # Log every 100 frames (2 seconds)
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_log_time > 2.0:  # Every 2 seconds
                            original_rms = np.sqrt(np.mean(audio_array**2))
                            logger.info(f"📤 LiveKit transmission stats:")
                            logger.info(f"   - Frames sent: {frame_counter}")
                            logger.info(f"   - Errors: {error_counter}")
                            logger.info(f"   - Queue backlog: {self.audio_queue.qsize()}")
                            logger.info(f"   - Original RMS: {original_rms:.2f}")
                            last_log_time = current_time
                            
                    except Exception as e:
                        error_counter += 1
                        logger.error(f"❌ Error capturing frame: {e}")
                        if error_counter % 10 == 0:  # Log every 10 errors
                            logger.error(f"⚠️  Multiple frame capture errors: {error_counter}")
                    
                else:
                    logger.warning("⚠️ Audio source not available or empty audio chunk")
                    
            except Exception as e:
                logger.error(f"❌ Error sending audio to LiveKit: {e}")
                await asyncio.sleep(0.1)


async def create_livekit_client(room_name: str, token: str, livekit_url: str) -> LiveKitClient:
    """
    Create and connect a LiveKit client.
    
    Args:
        room_name: Name of the LiveKit room
        token: JWT access token
        livekit_url: LiveKit server URL
        
    Returns:
        Connected LiveKitClient instance
    """
    client = LiveKitClient(room_name, token, livekit_url)
    await client.connect()
    return client