"""
Voicebot Service - Main service class for voice assistant functionality.

This service wraps the VoicebotEventLoop and provides a simple interface
for managing voicebot conversations.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable
from .event_loop import VoicebotEventLoop, AgentState

logger = logging.getLogger(__name__)

class VoicebotService:
    """
    Main voicebot service class.
    
    Provides a high-level interface for managing voicebot interactions
    using the event-driven VoicebotEventLoop architecture.
    """
    
    def __init__(
        self,
        stt_service,
        chatbot_service, 
        tts_service,
        vad_service,
        agent_id: str = None
    ):
        self.stt_service = stt_service
        self.chatbot_service = chatbot_service
        self.tts_service = tts_service
        self.vad_service = vad_service
        self.agent_id = agent_id
        
        # Active sessions
        self.active_sessions: Dict[str, VoicebotEventLoop] = {}
        
        # Event handlers for real-time updates
        self.event_handlers: Dict[str, Callable] = {}
        
    async def create_session(
        self, 
        conversation_id: str, 
        session_id: str = None
    ) -> VoicebotEventLoop:
        """
        Create a new voicebot session.
        
        Args:
            conversation_id: Unique identifier for the conversation
            session_id: Optional session identifier
            
        Returns:
            VoicebotEventLoop instance for the new session
        """
        if conversation_id in self.active_sessions:
            logger.warning(f"Session {conversation_id} already exists")
            return self.active_sessions[conversation_id]
            
        # Create output queue for the session
        output_queue = asyncio.Queue()
        
        # Create event loop for the session
        event_loop = VoicebotEventLoop(
            conversation_id=conversation_id,
            output_queue=output_queue,
            stt_service=self.stt_service,
            chatbot_service=self.chatbot_service,
            tts_service=self.tts_service,
            vad_service=self.vad_service,
            agent_id=self.agent_id,
            session_id=session_id
        )
        
        # Start the event loop
        await event_loop.start()
        
        # Store in active sessions
        self.active_sessions[conversation_id] = event_loop
        
        # Start a task to forward events to registered handlers
        asyncio.create_task(self._forward_events(conversation_id, output_queue))
        
        logger.info(f"Created voicebot session: {conversation_id}")
        return event_loop
        
    async def close_session(self, conversation_id: str):
        """
        Close a voicebot session.
        
        Args:
            conversation_id: ID of the session to close
        """
        if conversation_id not in self.active_sessions:
            logger.warning(f"Session {conversation_id} not found")
            return
            
        event_loop = self.active_sessions[conversation_id]
        await event_loop.stop()
        del self.active_sessions[conversation_id]
        
        logger.info(f"Closed voicebot session: {conversation_id}")
        
    async def process_audio(
        self, 
        conversation_id: str, 
        audio_chunk: bytes
    ) -> bool:
        """
        Process audio chunk for a specific session.
        
        Args:
            conversation_id: ID of the conversation
            audio_chunk: Raw audio data bytes
            
        Returns:
            True if processed successfully, False if session not found
        """
        if conversation_id not in self.active_sessions:
            logger.warning(f"Session {conversation_id} not found for audio processing")
            return False
            
        event_loop = self.active_sessions[conversation_id]
        await event_loop.process_audio_chunk(audio_chunk)
        return True
        
    def get_session_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of a session.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            Dictionary with session state or None if session not found
        """
        if conversation_id not in self.active_sessions:
            return None
            
        event_loop = self.active_sessions[conversation_id]
        return {
            "conversation_id": event_loop.conversation_id,
            "state": event_loop.state.value,
            "agent_id": event_loop.agent_id,
            "session_id": event_loop.session_id,
            "is_recording": event_loop.is_recording
        }
        
    def register_event_handler(
        self, 
        event_type: str, 
        handler: Callable[[Dict[str, Any]], None]
    ):
        """
        Register an event handler for real-time updates.
        
        Args:
            event_type: Type of event to handle
            handler: Async function to call when event occurs
        """
        self.event_handlers[event_type] = handler
        
    def unregister_event_handler(self, event_type: str):
        """
        Unregister an event handler.
        
        Args:
            event_type: Type of event to unregister
        """
        self.event_handlers.pop(event_type, None)
        
    async def _forward_events(self, conversation_id: str, output_queue: asyncio.Queue):
        """
        Forward events from output queue to registered handlers.
        
        Args:
            conversation_id: ID of the conversation
            output_queue: Queue to listen for events
        """
        try:
            while True:
                event = await output_queue.get()
                
                # Add conversation context to event
                event["conversation_id"] = conversation_id
                event["timestamp"] = event.get("timestamp", asyncio.get_event_loop().time())
                
                # Forward to registered handlers
                handler = self.event_handlers.get(event["type"])
                if handler:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler for {event['type']}: {e}")
                        
                output_queue.task_done()
                
        except asyncio.CancelledError:
            logger.info(f"Event forwarding cancelled for session {conversation_id}")
        except Exception as e:
            logger.error(f"Error in event forwarding for session {conversation_id}: {e}")
            
    async def cleanup_all_sessions(self):
        """Clean up all active sessions."""
        for conversation_id in list(self.active_sessions.keys()):
            await self.close_session(conversation_id)
            
    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all active sessions.
        
        Returns:
            Dictionary mapping conversation IDs to session info
        """
        return {
            conv_id: self.get_session_state(conv_id)
            for conv_id in self.active_sessions.keys()
        }

# Global voicebot service instance
voicebot_service = None

def get_voicebot_service(
    stt_service=None, 
    chatbot_service=None, 
    tts_service=None, 
    vad_service=None,
    agent_id: str = None
) -> VoicebotService:
    """
    Get or create the global voicebot service instance.
    
    Args:
        stt_service: STT service instance
        chatbot_service: Chatbot service instance  
        tts_service: TTS service instance
        vad_service: VAD service instance
        agent_id: Optional agent ID
        
    Returns:
        VoicebotService instance
    """
    global voicebot_service
    
    if voicebot_service is None:
        voicebot_service = VoicebotService(
            stt_service=stt_service,
            chatbot_service=chatbot_service,
            tts_service=tts_service,
            vad_service=vad_service,
            agent_id=agent_id
        )
        
    return voicebot_service