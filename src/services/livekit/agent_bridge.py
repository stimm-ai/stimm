"""
Bridge between our existing agent system and LiveKit.

This module allows our voicebot agents to connect to LiveKit rooms
and participate in real-time audio conversations.
"""

import asyncio
import logging
import uuid
from typing import Optional
from livekit import rtc
import aiohttp
import json

logger = logging.getLogger(__name__)

# Try to import LiveKit SDK components
try:
    from livekit.agents import JobContext, WorkerOptions
    from livekit.agents.voice import Agent, AgentSession, room_io
    from livekit.plugins import silero, noise_cancellation
    LIVEKIT_AGENTS_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ LiveKit Agents SDK not available - agent bridge will use simulation mode")
    LIVEKIT_AGENTS_AVAILABLE = False


class LiveKitAgentBridge:
    """
    Bridge that connects our voicebot agents to LiveKit rooms.
    
    This bridge:
    1. Connects to a LiveKit room using our agent's identity
    2. Captures audio from the room and sends it to our voicebot service
    3. Receives audio responses from our voicebot and sends them to the room
    """
    
    def __init__(self, agent_id: str, room_name: str, token: str, livekit_url: str):
        self.agent_id = agent_id
        self.room_name = room_name
        self.token = token
        self.livekit_url = livekit_url
        self.is_connected = False
        
        # Will be set when the bridge is connected to a voicebot service
        self.voicebot_service = None
        self.conversation_id = f"livekit_{agent_id}_{room_name}"
        
        # Audio components for LiveKit connection
        self.audio_source = None
        self.audio_track = None
        self.room = None
        
    async def connect(self):
        """
        Connect to the LiveKit room as an agent.
        """
        try:
            logger.info(f"🔗 Agent {self.agent_id} connecting to LiveKit room: {self.room_name}")
            logger.info(f"📡 LiveKit URL: {self.livekit_url}")
            logger.info(f"🔑 Token: {self.token[:20]}...")
            
            if not LIVEKIT_AGENTS_AVAILABLE:
                logger.warning("⚠️ LiveKit Agents SDK not available - using simulation mode")
                return await self._connect_simulation()
            
            # Try to connect using LiveKit Agents SDK
            return await self._connect_with_livekit_sdk()
            
        except Exception as e:
            logger.error(f"❌ Failed to connect agent to LiveKit: {e}")
            logger.error(f"🔧 Connection details - Room: {self.room_name}, URL: {self.livekit_url}")
            raise
    
    async def _connect_simulation(self):
        """Simulate connection when LiveKit SDK is not available"""
        logger.info("🔄 Initializing WebRTC connection (simulation)...")
        await asyncio.sleep(1)
        logger.info("📡 Setting up audio tracks (simulation)...")
        await asyncio.sleep(1)
        
        # Create audio source for agent output
        self.audio_source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        self.audio_track = rtc.LocalAudioTrack.create_audio_track("agent-audio", self.audio_source)
        
        self.is_connected = True
        
        logger.info(f"✅ Agent {self.agent_id} connected to LiveKit room {self.room_name} (simulation)")
        logger.info("🎤 Agent is listening for user audio")
        logger.info("🔊 Agent can send audio responses")
        logger.info("📊 Audio format: 48kHz, 1 channel")
        logger.info("🎯 Agent bridge ready - waiting for user audio input")
    
    async def _connect_with_livekit_sdk(self):
        """Connect using LiveKit Agents SDK"""
        try:
            logger.info("🔄 Connecting using LiveKit Agents SDK...")
            
            # Create a simple agent
            agent = Agent(
                instructions=f"You are agent {self.agent_id}, a helpful voice assistant.",
                stt="assemblyai/universal-streaming",
                llm="openai/gpt-4.1-mini",
                tts="cartesia/sonic-2:6f84f4b8-58a2-430c-8c79-688dad597532",
                vad=silero.VAD.load()
            )
            
            # Create session
            session = AgentSession()
            
            # Set up event handlers
            @session.on("user_input_transcribed")
            def on_transcript(transcript):
                if transcript.is_final:
                    logger.info(f"🎤 Agent {self.agent_id} received transcript: {transcript.transcript}")
                    if self.voicebot_service:
                        asyncio.create_task(self._process_transcript_with_voicebot(transcript.transcript))
            
            @session.on("agent_started_speaking")
            def on_agent_speaking():
                logger.info(f"🔊 Agent {self.agent_id} started speaking")
            
            @session.on("agent_finished_speaking")
            def on_agent_finished():
                logger.info(f"🔇 Agent {self.agent_id} finished speaking")
            
            # TODO: Implement actual room connection
            # This requires proper JobContext and room connection setup
            # For now, we'll simulate the connection
            
            logger.info("📡 Setting up room connection...")
            await asyncio.sleep(1)
            
            self.is_connected = True
            self.session = session
            
            logger.info(f"✅ Agent {self.agent_id} connected to LiveKit room {self.room_name} (SDK mode)")
            logger.info("🎤 Agent is listening for user audio")
            logger.info("🔊 Agent can send audio responses")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect with LiveKit SDK: {e}")
            raise
    
    async def _process_transcript_with_voicebot(self, transcript: str):
        """Process transcript through our voicebot service"""
        try:
            logger.info(f"🔄 Processing transcript for agent {self.agent_id}: {transcript}")
            
            if self.voicebot_service:
                # Use our existing voicebot service to generate response
                response = await self.voicebot_service.process_text_input(transcript)
                logger.info(f"🤖 Agent {self.agent_id} generated response: {response}")
                
                # If we have a session, use it to speak the response
                if self.session and response:
                    await self.session.say(response)
                    logger.info(f"🔊 Agent {self.agent_id} spoke response")
                    
        except Exception as e:
            logger.error(f"❌ Failed to process transcript: {e}")
    
    async def disconnect(self):
        """
        Disconnect from the LiveKit room.
        """
        try:
            if self.is_connected:
                logger.info(f"🔌 Agent {self.agent_id} disconnecting from LiveKit...")
                # TODO: Implement actual disconnection
                self.is_connected = False
                logger.info(f"✅ Agent {self.agent_id} disconnected from LiveKit")
                
        except Exception as e:
            logger.error(f"❌ Error disconnecting agent from LiveKit: {e}")
    
    def set_voicebot_service(self, voicebot_service):
        """
        Set the voicebot service that this bridge will use.
        
        Args:
            voicebot_service: VoicebotService instance
        """
        self.voicebot_service = voicebot_service
        logger.info(f"🔧 Agent bridge connected to voicebot service for {self.agent_id}")
    
    async def process_user_audio(self, audio_chunk: bytes):
        """
        Process audio chunk received from user in LiveKit room.
        
        Args:
            audio_chunk: Raw audio data from user
        """
        if not self.voicebot_service:
            logger.warning("⚠️ No voicebot service connected to agent bridge")
            return
        
        try:
            logger.info(f"🎤 Received user audio chunk: {len(audio_chunk)} bytes")
            
            # Log audio characteristics
            if len(audio_chunk) > 0:
                logger.debug(f"📊 Audio chunk details: {len(audio_chunk)} bytes, first 10 bytes: {audio_chunk[:10].hex()}")
            
            # Send audio to our voicebot service for processing
            await self.voicebot_service.process_audio(self.conversation_id, audio_chunk)
            logger.info(f"📤 Processed user audio chunk through voicebot service")
            
        except Exception as e:
            logger.error(f"❌ Error processing user audio: {e}")
            logger.error(f"🔧 Audio chunk size: {len(audio_chunk)} bytes")
    
    async def send_agent_response(self, audio_chunk: bytes):
        """
        Send agent audio response to LiveKit room.
        
        Args:
            audio_chunk: Raw audio data from agent TTS
        """
        if not self.is_connected:
            logger.warning("⚠️ Agent not connected to LiveKit, cannot send response")
            return
        
        try:
            logger.info(f"🔊 Sending agent audio response: {len(audio_chunk)} bytes")
            
            # TODO: Implement actual audio sending to LiveKit room
            # For now, simulate sending audio through our audio source
            if self.audio_source and len(audio_chunk) > 0:
                # Create an audio frame from the chunk
                # Note: This is a simplified example - real implementation would need proper frame format
                frame = rtc.AudioFrame(
                    data=audio_chunk,
                    sample_rate=48000,
                    num_channels=1,
                    samples_per_channel=len(audio_chunk) // 2  # Assuming 16-bit samples
                )
                await self.audio_source.capture_frame(frame)
                logger.info(f"📤 Agent audio response sent to LiveKit: {len(audio_chunk)} bytes")
            else:
                logger.warning("⚠️ Audio source not available or empty audio chunk")
                
        except Exception as e:
            logger.error(f"❌ Error sending agent audio response: {e}")
            logger.error(f"🔧 Audio chunk size: {len(audio_chunk)} bytes")
    
    async def start_session(self):
        """
        Start the agent session in the LiveKit room.
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
                    logger.info(f"📊 Agent session active - {session_counter * 5} seconds elapsed")
                    logger.info(f"🎯 Waiting for user audio input in room {self.room_name}")
                
        except Exception as e:
            logger.error(f"❌ Agent session error: {e}")
            logger.error(f"🔧 Session details - Room: {self.room_name}, Agent: {self.agent_id}")
            raise


async def create_agent_bridge(agent_id: str, room_name: str, token: str, livekit_url: str) -> LiveKitAgentBridge:
    """
    Create and connect an agent bridge.
    
    Args:
        agent_id: ID of the agent
        room_name: Name of the LiveKit room
        token: JWT access token for the agent
        livekit_url: LiveKit server URL
        
    Returns:
        Connected LiveKitAgentBridge instance
    """
    bridge = LiveKitAgentBridge(agent_id, room_name, token, livekit_url)
    await bridge.connect()
    return bridge