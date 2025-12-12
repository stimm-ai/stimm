"""
LiveKit Agent Bridge - Real-time audio connection for voice agents.

This bridge connects our stimm agents to LiveKit rooms, enabling real-time
audio conversations between users and agents.
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from livekit import rtc

from services.agents.stimm_service import StimmService

logger = logging.getLogger(__name__)


class LiveKitAgentBridge:
    """
    Bridge that connects stimm agents to LiveKit rooms.

    This bridge:
    1. Connects to a LiveKit room as an agent participant
    2. Listens to user audio tracks and sends them to StimmService
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

        # Agent audio queue (for sequential non-blocking playback)
        self.agent_audio_queue = asyncio.Queue()
        self.audio_task: Optional[asyncio.Task] = None
        self.interruption_signal = asyncio.Event()  # Event to signal interruption

        # Stimm integration
        self.stimm_service = None
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
            logger.debug(f"📡 LiveKit URL: {self.livekit_url}")
            logger.debug(f"🔑 Token: {self.token[:20]}...")

            # Set up event handlers
            self._setup_event_handlers()

            # Create audio source for agent responses
            # Use sample rate from configuration
            logger.debug(f"🎧 Creating agent audio source with sample rate: {self.sample_rate}Hz")
            # Increase buffer to handle TTS bursts
            self.audio_source = rtc.AudioSource(sample_rate=self.sample_rate, num_channels=1, queue_size_ms=5000)
            self.audio_track = rtc.LocalAudioTrack.create_audio_track("agent-audio", self.audio_source)

            # Connect to the room
            ws_url = self.livekit_url.replace("http://", "ws://").replace("https://", "wss://")
            logger.debug(f"🌐 Connecting to WebSocket: {ws_url}")

            await self.room.connect(ws_url, self.token)
            self.is_connected = True

            # Start background audio task
            self.audio_task = asyncio.create_task(self._process_audio_queue())

            # Publish agent audio track
            await self.room.local_participant.publish_track(self.audio_track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))

            logger.info(f"✅ Agent {self.agent_id} connected to LiveKit room {self.room_name}")
            logger.debug(f"👤 Connected as: {self.room.local_participant.identity}")
            logger.debug("🎤 Agent audio track published")
            logger.debug("👂 Listening for user audio")

        except Exception as e:
            logger.error(f"❌ Failed to connect agent to LiveKit: {e}")
            logger.error(f"🔧 Connection details - Room: {self.room_name}, URL: {self.livekit_url}")
            raise

    def _setup_event_handlers(self):
        """Set up LiveKit room event handlers"""

        @self.room.on("connected")
        def on_connected():
            logger.debug("✅ Successfully connected to LiveKit room")

        @self.room.on("disconnected")
        def on_disconnected():
            logger.debug("🔌 Disconnected from LiveKit room")
            self.is_connected = False
            self._cleanup()

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.debug(f"👤 Participant connected: {participant.identity}")
            self.user_participants[participant.sid] = participant

        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.debug(f"🔊 Subscribed to audio track from {participant.identity}")
                self._handle_user_audio_track(track, participant)

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.debug(f"👤 Participant disconnected: {participant.identity}")
            self.user_participants.pop(participant.sid, None)
            # Remove any audio tracks from this participant
            tracks_to_remove = [track_id for track_id, track_info in self.user_audio_tracks.items() if track_info["participant_sid"] == participant.sid]
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
        def on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.debug(f"📡 Track published by {participant.identity}: {publication.sid}")

    def _handle_user_audio_track(self, track: rtc.Track, participant: rtc.RemoteParticipant):
        """
        Handle incoming user audio track.

        Args:
            track: Audio track from user participant
            participant: Remote participant who published the track
        """
        # CRITICAL: Only process audio from actual users, not from other agents
        if participant.identity.startswith("agent_"):
            logger.debug(f"⏭️ Skipping audio from agent participant: {participant.identity}")
            return

        if not self.stimm_service:
            logger.warning("⚠️ Stimm service not connected, cannot process user audio")
            return

        logger.debug(f"🎤 Setting up audio processing for user {participant.identity}")

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
                    # if frame_count <= 10:
                    #     logger.info(f"🎤 Audio frame #{frame_count} from {participant.identity}:")
                    #     logger.info(f"   - Sample rate: {frame.sample_rate}Hz")
                    #     logger.info(f"   - Channels: {frame.num_channels}")
                    #     logger.info(f"   - Samples per channel: {frame.samples_per_channel}")

                    # Convert audio frame to bytes and analyze
                    if hasattr(frame, "data"):
                        # DIAGNOSTIC: Log the actual type and format of frame.data
                        # if frame_count <= 10:
                        #     logger.info(f"   - frame.data type: {type(frame.data)}")
                        #     if isinstance(frame.data, memoryview):
                        #         logger.info(f"   - memoryview format: {frame.data.format}")
                        #         logger.info(f"   - memoryview itemsize: {frame.data.itemsize}")
                        #         logger.info(f"   - memoryview nbytes: {frame.data.nbytes}")
                        #         # Log first few bytes as hex
                        #         sample_bytes = bytes(frame.data[:20])  # First 20 bytes
                        #         logger.info(f"   - First 20 bytes (hex): {sample_bytes.hex()}")
                        #     elif isinstance(frame.data, np.ndarray):
                        #         logger.info(f"   - frame.data dtype: {frame.data.dtype}")
                        #         logger.info(f"   - frame.data shape: {frame.data.shape}")
                        #         logger.info(f"   - frame.data range: [{np.min(frame.data)}, {np.max(frame.data)}]")

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
                                if frame.data.format == "f":  # float32
                                    # Convert float32 to int16
                                    audio_array_float = np.frombuffer(frame.data, dtype=np.float32)
                                    audio_array_int16 = (audio_array_float * 32768).astype(np.int16)
                                    audio_data = audio_array_int16.tobytes()
                                elif frame.data.format in ("h", "s"):  # int16 or signed short
                                    audio_data = frame.data.tobytes()
                                else:
                                    logger.warning(f"⚠️ Unexpected memoryview format: {frame.data.format}")
                                    audio_data = frame.data.tobytes()
                            else:
                                audio_data = frame.data.tobytes() if hasattr(frame.data, "tobytes") else frame.data

                        # Analyze audio amplitude before sending to VAD
                        # Commented out detailed stats for performance
                        # if len(audio_data) > 0:
                        #     audio_array = np.frombuffer(audio_data, dtype=np.int16)
                        #     min_val = np.min(audio_array)
                        #     max_val = np.max(audio_array)
                        #     rms = np.sqrt(np.mean(audio_array**2))
                        #
                        #     if frame_count <= 10:  # Log first 10 frames
                        #         logger.info(f"   - Audio stats (after extraction): int16_range=[{min_val}, {max_val}], RMS={rms:.2f}")
                        #         logger.info(f"   - Data size: {len(audio_data)} bytes")

                        # Send to stimm service for processing
                        if self.stimm_service:
                            asyncio.create_task(self.stimm_service.process_audio(self.conversation_id, audio_data))
                    else:
                        logger.warning(f"⚠️ Audio frame from {participant.identity} has no data attribute")
            except Exception as e:
                logger.error(f"❌ Error processing audio stream from {participant.identity}: {e}")
            finally:
                logger.debug(f"🛑 Audio stream ended for {participant.identity}")

        # Start processing task
        task = asyncio.create_task(process_audio_stream())

        # Store track information and task
        self.user_audio_tracks[track.sid] = {
            "track": track,
            "stream": stream,
            "task": task,
            "participant_sid": participant.sid,
            "participant_identity": participant.identity,
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
                # Split audio into smaller frames (e.g. 20ms) for smoother streaming
                # 20ms frame size
                bytes_per_sample = 2  # 16-bit
                samples_per_frame = int(self.sample_rate * 0.02)  # 20ms
                bytes_per_frame = samples_per_frame * bytes_per_sample
                frame_duration_s = samples_per_frame / self.sample_rate

                total_bytes = len(audio_chunk)
                offset = 0

                frames_sent = 0
                start_time = asyncio.get_event_loop().time()

                # Burst the first 200ms to fill client buffer quickly
                burst_frames = 10

                while offset < total_bytes:
                    # Check for interruption
                    if self.interruption_signal.is_set():
                        logger.info("🛑 Audio sending interrupted by signal")
                        return

                    # Get next chunk
                    chunk_end = min(offset + bytes_per_frame, total_bytes)
                    frame_data = audio_chunk[offset:chunk_end]

                    frame_len = len(frame_data)
                    samples_in_frame = frame_len // bytes_per_sample

                    frame = rtc.AudioFrame(
                        data=frame_data,
                        sample_rate=self.sample_rate,
                        num_channels=1,
                        samples_per_channel=samples_in_frame,
                    )

                    await self.audio_source.capture_frame(frame)
                    frames_sent += 1
                    offset += frame_len

                    # Pacing logic: match real-time transmission
                    # We allow a small burst at the start, then pace
                    if frames_sent > burst_frames:
                        # Target time is when this frame *should* be finished playing
                        target_time = start_time + (frames_sent * frame_duration_s)
                        current_time = asyncio.get_event_loop().time()
                        delay = target_time - current_time

                        # If we are ahead of schedule, sleep
                        # We multiply by 0.95 to stay slightly ahead (avoid underrun)
                        if delay > 0:
                            await asyncio.sleep(delay * 0.95)
                    else:
                        # Yield during burst to avoid blocking event loop completely
                        await asyncio.sleep(0)

                logger.debug(f"📤 Agent audio response sent: {total_bytes} bytes in {frames_sent} frames")
            else:
                logger.warning("⚠️ Audio source not available or empty audio chunk")

        except Exception as e:
            logger.error(f"❌ Error sending agent audio response: {e}")
            logger.error(f"🔧 Audio chunk size: {len(audio_chunk)} bytes")

    def set_stimm_service(self, stimm_service: StimmService):
        """
        Set the stimm service and create a session.

        Args:
            stimm_service: StimmService instance
        """
        self.stimm_service = stimm_service

        # Create stimm session for this conversation
        asyncio.create_task(self._create_stimm_session())

        logger.debug(f"🔧 Agent bridge connected to stimm service for {self.agent_id}")

    async def _create_stimm_session(self):
        """Create a stimm session and set up event handlers"""
        try:
            # Create session
            self.event_loop = await self.stimm_service.create_session(conversation_id=self.conversation_id, session_id=f"livekit_{self.agent_id}")

            # Set up event handler for agent audio responses
            self.stimm_service.register_event_handler("audio_chunk", self._handle_agent_audio_response)

            # Register handler for interruption
            self.stimm_service.register_event_handler("interrupt", self._handle_interrupt_event)

            # Register handlers for text/data events
            self.stimm_service.register_event_handler("transcript_update", self._handle_data_event)
            self.stimm_service.register_event_handler("assistant_response", self._handle_data_event)
            self.stimm_service.register_event_handler("vad_update", self._handle_data_event)
            self.stimm_service.register_event_handler("speech_start", self._handle_data_event)
            self.stimm_service.register_event_handler("speech_end", self._handle_data_event)
            self.stimm_service.register_event_handler("bot_responding_start", self._handle_data_event)
            self.stimm_service.register_event_handler("bot_responding_end", self._handle_data_event)
            self.stimm_service.register_event_handler("telemetry_update", self._handle_data_event)
            self.stimm_service.register_event_handler("audio_stream_end", self._handle_audio_stream_end)

            logger.debug(f"🎙️ Stimm session created for conversation {self.conversation_id}")

        except Exception as e:
            logger.error(f"❌ Failed to create stimm session: {e}")

    async def _handle_interrupt_event(self, event: Dict[str, Any]):
        """
        Handle interrupt event from stimm service.
        Stop current playback and clear queues.
        """
        logger.info("🛑 Interruption signal received in LiveKit bridge - Stopping playback")

        # 1. Signal any running audio sending loop to stop
        self.interruption_signal.set()

        # 2. Clear audio queue
        dropped_chunks = 0
        while not self.agent_audio_queue.empty():
            try:
                self.agent_audio_queue.get_nowait()
                dropped_chunks += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"🗑️ Flushed {dropped_chunks} pending audio chunks from queue")

        # 3. Forward interrupt to client (UI updates)
        await self._handle_data_event(event)

        # 4. Clear signal after a short delay to allow loops to exit
        # We don't clear immediately because send_agent_audio might still be running
        # The signal will be cleared by send_agent_audio when it exits or by the process loop
        # Actually, let's clear it in _process_audio_queue before processing next chunk?
        # No, send_agent_audio needs to see it.
        # We can clear it after we are sure tasks are stopped?
        # But we don't want to block new audio.
        # Let's rely on the consumer to clear it or use a version counter.
        # Simpler: clear it after a minimal sleep?
        await asyncio.sleep(0.1)
        self.interruption_signal.clear()

    async def _handle_audio_stream_end(self, event: Dict[str, Any]):
        """Handle end of audio stream from stimm."""
        # Put sentinel in queue to mark end of stream
        await self.agent_audio_queue.put(None)

    async def _handle_agent_audio_response(self, event: Dict[str, Any]):
        """
        Handle agent audio response from stimm service.

        Args:
            event: Event containing audio chunk data
        """
        try:
            audio_chunk = event.get("data")
            if audio_chunk and isinstance(audio_chunk, bytes):
                # logger.debug(f"🔊 Received agent audio chunk: {len(audio_chunk)} bytes")

                # 1. Queue audio for background playback (non-blocking)
                await self.agent_audio_queue.put(audio_chunk)

                # 2. Send metadata data packet for UI counters IMMEDIATELY
                # Note: We construct the event manually to avoid sending the heavy binary data
                try:
                    await self._handle_data_event(
                        {
                            "type": "audio_chunk",
                            # "size": len(audio_chunk), # Optional metadata
                            "timestamp": event.get("timestamp"),
                        }
                    )
                except Exception as de:
                    logger.warning(f"Failed to send audio_chunk metadata: {de}")

            else:
                logger.warning("⚠️ Invalid audio chunk in agent response event")

        except Exception as e:
            logger.error(f"❌ Error handling agent audio response: {e}")

    async def _process_audio_queue(self):
        """Process the audio queue to send audio sequentially in background."""
        logger.debug("🎵 Starting background audio processing task")
        try:
            while self.is_connected:
                # Wait for next audio chunk
                try:
                    # Timeout allows checking self.is_connected periodically
                    audio_chunk = await asyncio.wait_for(self.agent_audio_queue.get(), timeout=1.0)

                    if audio_chunk:
                        await self.send_agent_audio(audio_chunk)
                    elif audio_chunk is None:
                        # Sentinel received - stream ended
                        # Send telemetry update to client
                        await self._handle_data_event({"type": "telemetry_update", "data": {"webrtc_streaming_agent_audio_response_ended": True}})

                    self.agent_audio_queue.task_done()

                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

        except asyncio.CancelledError:
            logger.debug("🎵 Audio processing task cancelled")
        except Exception as e:
            logger.error(f"❌ Error in audio processing task: {e}")

    async def _handle_data_event(self, event: Dict[str, Any]):
        """
        Handle non-audio data events and forward as LiveKit Data Packets.
        """
        try:
            import json

            if not self.is_connected:
                logger.warning("⚠️ Cannot send data event: Agent not connected")
                return

            # Clean event payload (remove large binary data if any, though audio_chunk is handled separately)
            payload = {k: v for k, v in event.items() if k != "data" or not isinstance(v, bytes)}

            # Serialize to JSON string then bytes
            json_str = json.dumps(payload)
            data_bytes = json_str.encode("utf-8")

            # Publish to room
            # Use reliable delivery for text, lossy for VAD could be okay but let's stick to reliable for simplicity
            await self.room.local_participant.publish_data(
                data_bytes,
                reliable=True,
                destination_identities=[],  # Broadcast to all
            )
            # logger.debug(f"📤 Published data event: {event.get('type')}")

        except Exception as e:
            logger.error(f"❌ Error publishing data packet: {e}")

    async def disconnect(self):
        """
        Disconnect from the LiveKit room and cleanup.
        """
        try:
            if self.is_connected:
                logger.info(f"🔌 Agent {self.agent_id} disconnecting from LiveKit...")

                # Close stimm session
                if self.stimm_service and self.conversation_id:
                    await self.stimm_service.close_session(self.conversation_id)

                # Disconnect from room
                self.is_connected = False
                self._cleanup()

                logger.info(f"✅ Agent {self.agent_id} disconnected from LiveKit")

        except Exception as e:
            logger.error(f"❌ Error disconnecting agent from LiveKit: {e}")

    def _cleanup(self):
        """Clean up resources"""
        self.user_participants.clear()

        # Cancel audio task
        if self.audio_task and not self.audio_task.done():
            self.audio_task.cancel()

        if self.stimm_service:
            self.stimm_service.unregister_event_handler("audio_chunk")
            self.stimm_service.unregister_event_handler("interrupt")
            self.stimm_service.unregister_event_handler("transcript_update")
            self.stimm_service.unregister_event_handler("assistant_response")
            self.stimm_service.unregister_event_handler("vad_update")
            self.stimm_service.unregister_event_handler("speech_start")
            self.stimm_service.unregister_event_handler("speech_end")
            self.stimm_service.unregister_event_handler("bot_responding_start")
            self.stimm_service.unregister_event_handler("bot_responding_end")
            self.stimm_service.unregister_event_handler("telemetry_update")
            self.stimm_service.unregister_event_handler("audio_stream_end")

    async def start_session(self):
        """
        Start the agent session in the LiveKit room.
        This keeps the connection alive and monitors the session.
        """
        if not self.is_connected:
            await self.connect()

        logger.debug(f"🎧 Agent {self.agent_id} starting session in room {self.room_name}")
        logger.debug("🔄 Session monitoring started - agent is ready for conversation")

        try:
            # Keep the session active and log periodic status
            session_counter = 0
            while self.is_connected:
                await asyncio.sleep(5)  # Check every 5 seconds
                session_counter += 1

                # Log session status periodically
                if session_counter % 6 == 0:  # Every 30 seconds
                    participants_count = len(self.user_participants)
                    logger.debug(f"📊 Agent session active - {session_counter * 5} seconds elapsed")
                    logger.debug(f"🎯 {participants_count} user(s) in room {self.room_name}")
                    logger.debug("👂 Waiting for user audio input...")

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
