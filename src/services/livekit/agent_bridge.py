"""
LiveKit Agent Bridge - Real-time audio connection for voice agents.

This bridge connects our voicebot agents to LiveKit rooms, enabling real-time
audio conversations between users and agents.
"""

import asyncio
import logging
import uuid
from typing import Optional, Dict, Any
from livekit import rtc

from services.agents.voicebot_service import VoicebotService
from services.agents.event_loop import VoicebotEventLoop

logger = logging.getLogger(__name__)


class LiveKitAgentBridge:
    """
    Bridge that connects voicebot agents to LiveKit rooms.
    
    This bridge:
    1. Connects to a LiveKit room as an agent participant
    2. Listens to user audio tracks and sends them to VoicebotService
    3. Receives agent audio responses and publishes them to the room
    4. Manages the conversation lifecycle
    """
    
    def __init__(self, agent_id: str, room_name: str, token: str, livekit_url: str, sample_rate: int = 24000):
        self.agent_id = agent_id
        self.room_name = room_name
        self.token = token
        self.livekit_url = livekit_url
        self.sample_rate = sample_rate
        self.is_connected = False
        
        # LiveKit components
        self.room = rtc.Room()
        self.audio_source = None
        self.audio_track = None
        
        # Voicebot integration
        self.voicebot_service = None
        self.event_loop = None
        self.conversation_id = f"livekit_{agent_id}_{room_name}_{uuid.uuid4().hex[:8]}"
        
        # Track user participants and their audio tracks
        self.user_participants = {}
        self.user_audio_tracks = {}
        
        logger.info(f"🎯 Agent bridge initialized for agent {agent_id} in room {room_name}")
    
    async def connect(self):
        """
        Connect to the LiveKit room as an agent.
        """
        try:
            logger.info(f"🔗 Agent {self.agent_id} connecting to LiveKit room: {self.room_name}")
            logger.info(f"📡 LiveKit URL: {self.livekit_url}")
            logger.info(f"🔑 Token: {self.token[:20]}...")
            
            # Set up event handlers
            self._setup_event_handlers()
            
            # Create audio source for agent responses
            # Use sample rate from configuration
            logger.info(f"🎧 Creating agent audio source with sample rate: {self.sample_rate}Hz")
            self.audio_source = rtc.AudioSource(sample_rate=self.sample_rate, num_channels=1)
            self.audio_track = rtc.LocalAudioTrack.create_audio_track("agent-audio", self.audio_source)
            
            # Connect to the room
            ws_url = self.livekit_url.replace("http://", "ws://").replace("https://", "wss://")
            logger.info(f"🌐 Connecting to WebSocket: {ws_url}")
            
            await self.room.connect(ws_url, self.token)
            self.is_connected = True
            
            # Publish agent audio track
            await self.room.local_participant.publish_track(
                self.audio_track,
                rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            )
            
            logger.info(f"✅ Agent {self.agent_id} connected to LiveKit room {self.room_name}")
            logger.info(f"👤 Connected as: {self.room.local_participant.identity}")
            logger.info("🎤 Agent audio track published")
            logger.info("👂 Listening for user audio")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect agent to LiveKit: {e}")
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
            self._cleanup()
            
        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"👤 Participant connected: {participant.identity}")
            self.user_participants[participant.sid] = participant
            
        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"🔊 Subscribed to audio track from {participant.identity}")
                self._handle_user_audio_track(track, participant)
                    
        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"👤 Participant disconnected: {participant.identity}")
            self.user_participants.pop(participant.sid, None)
            # Remove any audio tracks from this participant
            tracks_to_remove = [track_id for track_id, track_info in self.user_audio_tracks.items()
                              if track_info["participant_sid"] == participant.sid]
            for track_id in tracks_to_remove:
                track_info = self.user_audio_tracks.pop(track_id, None)
                if track_info:
                    # Cancel task and close stream
                    if "task" in track_info:
                        track_info["task"].cancel()
                    if "stream" in track_info:
                        # AudioStream doesn't have a close method, it's closed when track is unsubscribed
                        pass
            
        @self.room.on("track_published")
        def on_track_published(
            publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
        ):
            logger.info(f"📡 Track published by {participant.identity}: {publication.sid}")
            
    def _handle_user_audio_track(self, track: rtc.Track, participant: rtc.RemoteParticipant):
        """
        Handle incoming user audio track.
        
        Args:
            track: Audio track from user participant
            participant: Remote participant who published the track
        """
        # CRITICAL: Only process audio from actual users, not from other agents
        if participant.identity.startswith('agent_'):
            logger.debug(f"⏭️ Skipping audio from agent participant: {participant.identity}")
            return
            
        if not self.voicebot_service:
            logger.warning("⚠️ Voicebot service not connected, cannot process user audio")
            return
            
        logger.info(f"🎤 Setting up audio processing for user {participant.identity}")
        
        # Create audio stream for this track with 16kHz sample rate (required for VAD/STT)
        stream = rtc.AudioStream(track, sample_rate=16000)
        
        async def process_audio_stream():
            try:
                import numpy as np
                frame_count = 0
                
                async for event in stream:
                    # AudioStream yields AudioFrameEvent
                    frame = event.frame
                    frame_count += 1
                    
                    # Log detailed audio information for first few frames
                    if frame_count <= 10:
                        logger.info(f"🎤 Audio frame #{frame_count} from {participant.identity}:")
                        logger.info(f"   - Sample rate: {frame.sample_rate}Hz")
                        logger.info(f"   - Channels: {frame.num_channels}")
                        logger.info(f"   - Samples per channel: {frame.samples_per_channel}")
                    
                    # Convert audio frame to bytes and analyze
                    if hasattr(frame, 'data'):
                        # DIAGNOSTIC: Log the actual type and format of frame.data
                        if frame_count <= 10:
                            logger.info(f"   - frame.data type: {type(frame.data)}")
                            if isinstance(frame.data, memoryview):
                                logger.info(f"   - memoryview format: {frame.data.format}")
                                logger.info(f"   - memoryview itemsize: {frame.data.itemsize}")
                                logger.info(f"   - memoryview nbytes: {frame.data.nbytes}")
                                # Log first few bytes as hex
                                sample_bytes = bytes(frame.data[:20])  # First 20 bytes
                                logger.info(f"   - First 20 bytes (hex): {sample_bytes.hex()}")
                            elif isinstance(frame.data, np.ndarray):
                                logger.info(f"   - frame.data dtype: {frame.data.dtype}")
                                logger.info(f"   - frame.data shape: {frame.data.shape}")
                                logger.info(f"   - frame.data range: [{np.min(frame.data)}, {np.max(frame.data)}]")
                        
                        # Extract audio data properly based on its type
                        if isinstance(frame.data, np.ndarray):
                            # Data is already a numpy array
                            if frame.data.dtype == np.int16:
                                audio_data = frame.data.tobytes()
                            elif frame.data.dtype == np.float32:
                                # Convert float32 [-1, 1] to int16
                                audio_array_int16 = (frame.data * 32768).astype(np.int16)
                                audio_data = audio_array_int16.tobytes()
                            else:
                                logger.warning(f"⚠️ Unexpected dtype: {frame.data.dtype}, converting to bytes directly")
                                audio_data = frame.data.tobytes()
                        else:
                            # Data is bytes/memoryview - need to interpret the format correctly
                            if isinstance(frame.data, memoryview):
                                # Check the format of the memoryview
                                if frame.data.format == 'f':  # float32
                                    # Convert float32 to int16
                                    audio_array_float = np.frombuffer(frame.data, dtype=np.float32)
                                    audio_array_int16 = (audio_array_float * 32768).astype(np.int16)
                                    audio_data = audio_array_int16.tobytes()
                                elif frame.data.format in ('h', 's'):  # int16 or signed short
                                    audio_data = frame.data.tobytes()
                                else:
                                    logger.warning(f"⚠️ Unexpected memoryview format: {frame.data.format}")
                                    audio_data = frame.data.tobytes()
                            else:
                                audio_data = frame.data.tobytes() if hasattr(frame.data, 'tobytes') else frame.data
                        
                        # Analyze audio amplitude before sending to VAD
                        if len(audio_data) > 0:
                            audio_array = np.frombuffer(audio_data, dtype=np.int16)
                            min_val = np.min(audio_array)
                            max_val = np.max(audio_array)
                            rms = np.sqrt(np.mean(audio_array**2))
                            
                            if frame_count <= 10:  # Log first 10 frames
                                logger.info(f"   - Audio stats (after extraction): int16_range=[{min_val}, {max_val}], RMS={rms:.2f}")
                                logger.info(f"   - Data size: {len(audio_data)} bytes")
                        
                        # Send to voicebot service for processing
                        if self.voicebot_service:
                            asyncio.create_task(
                                self.voicebot_service.process_audio(self.conversation_id, audio_data)
                            )
                    else:
                        logger.warning(f"⚠️ Audio frame from {participant.identity} has no data attribute")
            except Exception as e:
                logger.error(f"❌ Error processing audio stream from {participant.identity}: {e}")
            finally:
                logger.info(f"🛑 Audio stream ended for {participant.identity}")

        # Start processing task
        task = asyncio.create_task(process_audio_stream())
        
        # Store track information and task
        self.user_audio_tracks[track.sid] = {
            "track": track,
            "stream": stream,
            "task": task,
            "participant_sid": participant.sid,
            "participant_identity": participant.identity
        }
    
    async def send_agent_audio(self, audio_chunk: bytes):
        """
        Send agent audio response to LiveKit room.
        
        Args:
            audio_chunk: Raw audio data from agent TTS
        """
        if not self.is_connected:
            logger.warning("⚠️ Agent not connected to LiveKit, cannot send response")
            return
            
        try:
            logger.debug(f"🔊 Sending agent audio response: {len(audio_chunk)} bytes")
            
            if self.audio_source and len(audio_chunk) > 0:
                # Create audio frame from the chunk
                frame = rtc.AudioFrame(
                    data=audio_chunk,
                    sample_rate=self.sample_rate,
                    num_channels=1,
                    samples_per_channel=len(audio_chunk) // 2  # Assuming 16-bit samples
                )
                await self.audio_source.capture_frame(frame)
                logger.debug(f"📤 Agent audio response sent to LiveKit: {len(audio_chunk)} bytes")
            else:
                logger.warning("⚠️ Audio source not available or empty audio chunk")
                
        except Exception as e:
            logger.error(f"❌ Error sending agent audio response: {e}")
            logger.error(f"🔧 Audio chunk size: {len(audio_chunk)} bytes")
    
    def set_voicebot_service(self, voicebot_service: VoicebotService):
        """
        Set the voicebot service and create a session.
        
        Args:
            voicebot_service: VoicebotService instance
        """
        self.voicebot_service = voicebot_service
        
        # Create voicebot session for this conversation
        asyncio.create_task(self._create_voicebot_session())
        
        logger.info(f"🔧 Agent bridge connected to voicebot service for {self.agent_id}")
    
    async def _create_voicebot_session(self):
        """Create a voicebot session and set up event handlers"""
        try:
            # Create session
            self.event_loop = await self.voicebot_service.create_session(
                conversation_id=self.conversation_id,
                session_id=f"livekit_{self.agent_id}"
            )
            
            # Set up event handler for agent audio responses
            self.voicebot_service.register_event_handler(
                "audio_chunk",
                self._handle_agent_audio_response
            )
            
            logger.info(f"🎙️ Voicebot session created for conversation {self.conversation_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create voicebot session: {e}")
    
    async def _handle_agent_audio_response(self, event: Dict[str, Any]):
        """
        Handle agent audio response from voicebot service.
        
        Args:
            event: Event containing audio chunk data
        """
        try:
            audio_chunk = event.get("data")
            if audio_chunk and isinstance(audio_chunk, bytes):
                logger.debug(f"🔊 Received agent audio chunk: {len(audio_chunk)} bytes")
                await self.send_agent_audio(audio_chunk)
            else:
                logger.warning("⚠️ Invalid audio chunk in agent response event")
                
        except Exception as e:
            logger.error(f"❌ Error handling agent audio response: {e}")
    
    async def disconnect(self):
        """
        Disconnect from the LiveKit room and cleanup.
        """
        try:
            if self.is_connected:
                logger.info(f"🔌 Agent {self.agent_id} disconnecting from LiveKit...")
                
                # Close voicebot session
                if self.voicebot_service and self.conversation_id:
                    await self.voicebot_service.close_session(self.conversation_id)
                
                # Disconnect from room
                self.is_connected = False
                self._cleanup()
                
                logger.info(f"✅ Agent {self.agent_id} disconnected from LiveKit")
                
        except Exception as e:
            logger.error(f"❌ Error disconnecting agent from LiveKit: {e}")
    
    def _cleanup(self):
        """Clean up resources"""
        self.user_participants.clear()
        
        if self.voicebot_service:
            self.voicebot_service.unregister_event_handler("audio_chunk")
    
    async def start_session(self):
        """
        Start the agent session in the LiveKit room.
        This keeps the connection alive and monitors the session.
        """
        if not self.is_connected:
            await self.connect()
        
        logger.info(f"🎧 Agent {self.agent_id} starting session in room {self.room_name}")
        logger.info("🔄 Session monitoring started - agent is ready for conversation")
        
        try:
            # Keep the session active and log periodic status
            session_counter = 0
            while self.is_connected:
                await asyncio.sleep(5)  # Check every 5 seconds
                session_counter += 1
                
                # Log session status periodically
                if session_counter % 6 == 0:  # Every 30 seconds
                    participants_count = len(self.user_participants)
                    logger.info(f"📊 Agent session active - {session_counter * 5} seconds elapsed")
                    logger.info(f"🎯 {participants_count} user(s) in room {self.room_name}")
                    logger.info("👂 Waiting for user audio input...")
                
        except Exception as e:
            logger.error(f"❌ Agent session error: {e}")
            logger.error(f"🔧 Session details - Room: {self.room_name}, Agent: {self.agent_id}")
            raise


async def create_agent_bridge(agent_id: str, room_name: str, token: str, livekit_url: str, sample_rate: int = 24000) -> LiveKitAgentBridge:
    """
    Create and connect an agent bridge.
    
    Args:
        agent_id: ID of the agent
        room_name: Name of the LiveKit room
        token: JWT access token for the agent
        livekit_url: LiveKit server URL
        sample_rate: Audio sample rate for TTS playback
        
    Returns:
        Connected LiveKitAgentBridge instance
    """
    bridge = LiveKitAgentBridge(agent_id, room_name, token, livekit_url, sample_rate)
    await bridge.connect()
    return bridge