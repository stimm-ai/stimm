"""
Event-Driven Voicebot Service (V2) - LiveKit-Inspired Architecture.

This service replaces the flag-based orchestration with a central event loop
for cleaner state management and lower-latency interruptions.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, AsyncGenerator

from .config import voicebot_config
from .event_loop import VoicebotEventLoop
from services.stt.stt import STTService
from services.tts.tts import TTSService
from services.rag.chatbot_service import ChatbotService
from services.vad.silero_service import SileroVADService

logger = logging.getLogger(__name__)


class ConversationStateV2:
    """Simplified conversation state for event-driven architecture."""
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.event_loop: Optional[VoicebotEventLoop] = None
        self.output_queue: Optional[asyncio.Queue] = None
        self.output_processor_task: Optional[asyncio.Task] = None
        
    async def stop(self):
        """Stop the conversation and cleanup resources."""
        if self.event_loop:
            await self.event_loop.stop()
            
        if self.output_processor_task and not self.output_processor_task.done():
            self.output_processor_task.cancel()
            try:
                await self.output_processor_task
            except asyncio.CancelledError:
                pass


class VoicebotServiceV2:
    """
    Event-driven voicebot service inspired by LiveKit Agents.
    
    Key differences from V1:
    - Uses VoicebotEventLoop for state management
    - VAD-gated STT (only sends audio to STT when speech is detected)
    - Cleaner interruption handling via events
    - No AudioSplitter (single audio stream processed by VAD first)
    """
    
    def __init__(self, agent_id: str = None, session_id: str = None):
        self.agent_id = agent_id
        self.session_id = session_id
        self.active_conversations: Dict[str, ConversationStateV2] = {}
        
        # Initialize services
        self.stt_service: Optional[STTService] = None
        self.tts_service: Optional[TTSService] = None
        self.chatbot_service: Optional[ChatbotService] = None
        self._initialize_services()
        
    def _initialize_services(self):
        """Initialize the dependent services."""
        try:
            self.stt_service = STTService(agent_id=self.agent_id, session_id=self.session_id)
            logger.info("STT service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize STT service: {e}")
            
        try:
            self.tts_service = TTSService(agent_id=self.agent_id, session_id=self.session_id)
            logger.info("TTS service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize TTS service: {e}")
            
        try:
            self.chatbot_service = ChatbotService()
            logger.info("Chatbot service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize chatbot service: {e}")
    
    def create_conversation(self) -> str:
        """Create a new conversation session."""
        conversation_id = str(uuid.uuid4())
        self.active_conversations[conversation_id] = ConversationStateV2(conversation_id)
        logger.info(f"Created conversation: {conversation_id}")
        return conversation_id
    
    async def end_conversation(self, conversation_id: str):
        """End a conversation session."""
        if conversation_id in self.active_conversations:
            conversation = self.active_conversations[conversation_id]
            await conversation.stop()
            del self.active_conversations[conversation_id]
            logger.info(f"Ended conversation: {conversation_id}")
    
    async def start_event_driven_processing(
        self,
        conversation_id: str,
        audio_generator: AsyncGenerator[bytes, None]
    ):
        """
        Start event-driven processing for a conversation.
        
        This is the main entry point that replaces start_continuous_processing.
        It creates an event loop and processes audio through VAD first.
        """
        if conversation_id not in self.active_conversations:
            logger.warning(f"Conversation not found: {conversation_id}")
            return
            
        conversation = self.active_conversations[conversation_id]
        
        # Create output queue for WebSocket messages
        conversation.output_queue = asyncio.Queue()
        
        # Create VAD service instance for this conversation
        vad_service = SileroVADService(
            threshold=voicebot_config.VAD_THRESHOLD,
            sample_rate=voicebot_config.SAMPLE_RATE
        )
        
        # Create event loop
        conversation.event_loop = VoicebotEventLoop(
            conversation_id=conversation_id,
            output_queue=conversation.output_queue,
            stt_service=self.stt_service,
            chatbot_service=self.chatbot_service,
            tts_service=self.tts_service,
            vad_service=vad_service,
            agent_id=self.agent_id,
            session_id=self.session_id
        )
        
        # Start event loop
        await conversation.event_loop.start()
        
        # Start output processor (sends messages to WebSocket)
        conversation.output_processor_task = asyncio.create_task(
            self._process_output_queue(conversation_id)
        )
        
        # Process audio chunks through the event loop
        try:
            async for audio_chunk in audio_generator:
                if conversation_id not in self.active_conversations:
                    break
                    
                # Feed audio to event loop
                await conversation.event_loop.process_audio_chunk(audio_chunk)
                
        except asyncio.CancelledError:
            logger.info(f"Audio processing cancelled for: {conversation_id}")
        except Exception as e:
            logger.error(f"Error in audio processing for {conversation_id}: {e}")
        finally:
            logger.info(f"Audio processing ended for: {conversation_id}")
    
    async def _process_output_queue(self, conversation_id: str):
        """
        Process output queue and send messages to WebSocket.
        
        This task reads from the event loop's output queue and forwards
        messages to the WebSocket connection via the connection manager.
        """
        if conversation_id not in self.active_conversations:
            return
            
        conversation = self.active_conversations[conversation_id]
        
        try:
            while True:
                message = await conversation.output_queue.get()
                
                # Send to WebSocket
                if message["type"] == "audio_chunk":
                    # Binary audio data
                    await self._send_websocket_bytes(conversation_id, message["data"])
                else:
                    # JSON message
                    await self._send_websocket_message(conversation_id, message)
                    
                conversation.output_queue.task_done()
                
        except asyncio.CancelledError:
            logger.info(f"Output processor cancelled for: {conversation_id}")
        except Exception as e:
            logger.error(f"Error in output processor for {conversation_id}: {e}")
    
    async def _send_websocket_message(self, conversation_id: str, message: Dict[str, Any]):
        """Send message to WebSocket connection for a conversation."""
        try:
            from .routes import connection_manager
            await connection_manager.send_message(conversation_id, message)
        except Exception as e:
            logger.error(f"Error sending message to {conversation_id}: {e}")
    
    async def _send_websocket_bytes(self, conversation_id: str, data: bytes):
        """Send raw binary data to WebSocket connection."""
        try:
            from .routes import connection_manager
            await connection_manager.send_bytes(conversation_id, data)
        except Exception as e:
            logger.error(f"Error sending bytes to {conversation_id}: {e}")
    
    def get_conversation_status(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a conversation."""
        if conversation_id in self.active_conversations:
            conversation = self.active_conversations[conversation_id]
            if conversation.event_loop:
                return {
                    "conversation_id": conversation_id,
                    "state": conversation.event_loop.state.value,
                    "is_recording": conversation.event_loop.is_recording,
                    "transcript_buffer": conversation.event_loop.transcript_buffer
                }
        return None


# Global service instance (V2)
voicebot_service_v2 = VoicebotServiceV2()
