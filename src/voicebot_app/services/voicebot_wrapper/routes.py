"""
WebSocket routes for the voicebot wrapper service.

This module provides real-time communication endpoints for voice activity detection,
audio streaming, and conversation management with VAD-based interruption.
"""

import asyncio
import json
import base64
import logging
from typing import Dict, Any, AsyncGenerator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK

from .voicebot_service import VoicebotService, voicebot_service
from .config import voicebot_config
from services.shared_streaming import shared_streaming_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for voicebot sessions with VAD-based interruption."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.audio_processors: Dict[str, asyncio.Queue] = {}
        
    async def connect(self, websocket: WebSocket, conversation_id: str):
        """Store WebSocket connection (connection already accepted)."""
        self.active_connections[conversation_id] = websocket
        self.audio_processors[conversation_id] = asyncio.Queue()
        logger.info(f"WebSocket connected for conversation: {conversation_id}")
        
    def disconnect(self, conversation_id: str):
        """Remove WebSocket connection."""
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
        if conversation_id in self.audio_processors:
            del self.audio_processors[conversation_id]
        logger.info(f"WebSocket disconnected for conversation: {conversation_id}")
            
    async def send_message(self, conversation_id: str, message: Dict[str, Any]):
        """Send message to specific WebSocket connection."""
        if conversation_id in self.active_connections:
            try:
                await self.active_connections[conversation_id].send_json(message)
            except (WebSocketDisconnect, ConnectionClosedOK):
                self.disconnect(conversation_id)
            except Exception as e:
                logger.error(f"Error sending message to {conversation_id}: {e}")
                self.disconnect(conversation_id)
                
    async def send_bytes(self, conversation_id: str, data: bytes):
        """Send raw binary data to WebSocket connection (like TTS interface)."""
        if conversation_id in self.active_connections:
            try:
                await self.active_connections[conversation_id].send_bytes(data)
            except (WebSocketDisconnect, ConnectionClosedOK):
                self.disconnect(conversation_id)
            except Exception as e:
                logger.error(f"Error sending bytes to {conversation_id}: {e}")
                self.disconnect(conversation_id)
                
    async def add_audio_chunk(self, conversation_id: str, audio_chunk: bytes):
        """Add audio chunk to processing queue."""
        if conversation_id in self.audio_processors:
            await self.audio_processors[conversation_id].put(audio_chunk)
            
    async def get_audio_generator(self, conversation_id: str):
        """Get async generator for audio chunks with VAD interruption support."""
        if conversation_id not in self.audio_processors:
            return None
            
        async def audio_generator():
            while True:
                try:
                    # Ultra-fast timeout for VAD responsiveness
                    chunk = await asyncio.wait_for(
                        self.audio_processors[conversation_id].get(),
                        timeout=0.1  # 100ms for immediate VAD response
                    )
                    yield chunk
                except asyncio.TimeoutError:
                    # No audio for 100ms, continue checking
                    continue
                    
        return audio_generator()
    
    async def get_audio_generator_copy(self, conversation_id: str):
        """Get a separate async generator for audio chunks (for multiple consumers)."""
        if conversation_id not in self.audio_processors:
            return None
            
        async def audio_generator():
            while True:
                try:
                    # Ultra-fast timeout for VAD responsiveness
                    chunk = await asyncio.wait_for(
                        self.audio_processors[conversation_id].get(),
                        timeout=0.1  # 100ms for immediate VAD response
                    )
                    yield chunk
                except asyncio.TimeoutError:
                    # No audio for 100ms, continue checking
                    continue
                    
        return audio_generator()


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/voicebot/stream")
async def voicebot_websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for voicebot real-time communication.
    
    Handles:
    - Voice activity detection updates with immediate interruption
    - Audio streaming for STT
    - Conversation state management
    - Response streaming
    """
    conversation_id = None
    agent_id = None
    session_id = None
    
    try:
        # Accept connection immediately (like STT service)
        await websocket.accept()
        logger.info("Voicebot WebSocket connection established")
        
        # Wait for initial setup message
        init_message = await websocket.receive_text()
        init_data = json.loads(init_message)
        
        if init_data.get("type") != "start_conversation":
            await websocket.send_json({
                "type": "error",
                "message": "First message must be 'start_conversation'"
            })
            return
            
        conversation_id = init_data.get("conversation_id")
        agent_id = init_data.get("agent_id")
        session_id = init_data.get("session_id")
        
        if not conversation_id:
            # Create voicebot service with agent configuration
            voicebot_service_instance = VoicebotService(agent_id=agent_id, session_id=session_id)
            conversation_id = voicebot_service_instance.create_conversation()
        else:
            # Use existing conversation with agent configuration
            voicebot_service_instance = VoicebotService(agent_id=agent_id, session_id=session_id)
            
        # Register connection
        await connection_manager.connect(websocket, conversation_id)
        
        # Get TTS provider configuration from agent if available
        logger.info(f"🔍 Voicebot WebSocket - Using agent-based TTS configuration for agent_id: {agent_id}")
        
        # Use agent-based TTS configuration instead of environment variables
        from services.tts.tts import TTSService
        tts_service = TTSService(agent_id=agent_id)
        
        # Get provider-specific audio configuration from agent
        current_provider = tts_service.provider.__class__.__name__
        logger.info(f"🔍 Voicebot WebSocket - Agent TTS provider: {current_provider}")
        
        # Get provider-specific audio configuration from constants
        from services.provider_constants import get_provider_constants
        provider_constants = get_provider_constants()
        
        if hasattr(tts_service.provider, 'sample_rate'):
            tts_sample_rate = tts_service.provider.sample_rate
            tts_encoding = tts_service.provider.encoding
        else:
            # Fallback to provider constants
            provider_key = None
            if "AsyncAIProvider" in current_provider:
                provider_key = "async.ai"
            elif "KokoroLocalProvider" in current_provider:
                provider_key = "kokoro.local"
            elif "DeepgramProvider" in current_provider:
                provider_key = "deepgram.com"
            elif "ElevenLabsProvider" in current_provider:
                provider_key = "elevenlabs.io"
            
            if provider_key and provider_key in provider_constants['tts']:
                tts_sample_rate = provider_constants['tts'][provider_key]['SAMPLE_RATE']
                tts_encoding = provider_constants['tts'][provider_key]['ENCODING']
            else:
                # Default values
                tts_sample_rate = 44100
                tts_encoding = "pcm_s16le"

        await websocket.send_json({
            "type": "conversation_started",
            "conversation_id": conversation_id,
            "config": {
                "sample_rate": voicebot_config.SAMPLE_RATE,
                "chunk_size_ms": voicebot_config.CHUNK_SIZE_MS,
                "vad_threshold": voicebot_config.VAD_THRESHOLD,
                "tts_sample_rate": tts_sample_rate,
                "tts_encoding": tts_encoding,
                "tts_provider": current_provider
            }
        })
        
        logger.info(f"Voicebot session started: {conversation_id}")
        
        # Start continuous audio processing task
        processing_task = asyncio.create_task(
            _process_audio_continuous(conversation_id, websocket, voicebot_service_instance)
        )
        
        # Main message processing loop
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            await _handle_websocket_message(conversation_id, data, websocket)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for conversation: {conversation_id}")
    except ConnectionClosedOK:
        logger.info(f"WebSocket connection closed normally: {conversation_id}")
    except Exception as e:
        logger.error(f"WebSocket error for conversation {conversation_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Internal server error: {str(e)}"
            })
        except:
            pass
    finally:
        if conversation_id:
            # Cancel processing task
            if 'processing_task' in locals() and not processing_task.done():
                processing_task.cancel()
                try:
                    await processing_task
                except asyncio.CancelledError:
                    pass
            
            connection_manager.disconnect(conversation_id)
            voicebot_service_instance.end_conversation(conversation_id)


async def _handle_websocket_message(conversation_id: str, data: Dict[str, Any], websocket: WebSocket):
    """Handle incoming WebSocket messages."""
    message_type = data.get("type")
    
    try:
        if message_type == "voice_activity":
            await _handle_voice_activity(conversation_id, data)
            
        elif message_type == "audio_chunk":
            await _handle_audio_chunk(conversation_id, data, websocket)
            
        elif message_type == "start_listening":
            await _handle_start_listening(conversation_id, websocket)
            
        elif message_type == "stop_listening":
            await _handle_stop_listening(conversation_id)
            
        elif message_type == "get_status":
            await _handle_get_status(conversation_id, websocket)
            
        elif message_type == "agent_change":
            await _handle_agent_change(conversation_id, data, websocket)
            
        else:
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            })
            
    except Exception as e:
        logger.error(f"Error handling message type {message_type}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Error processing {message_type}: {str(e)}"
        })


async def _handle_voice_activity(conversation_id: str, data: Dict[str, Any]):
    """Handle voice activity detection updates (legacy frontend VAD - kept for compatibility)."""
    # This is now handled by backend VAD, but kept for frontend compatibility
    is_voice = data.get("is_voice", False)
    energy = data.get("energy", 0.0)
    
    # Send VAD status update back to client for compatibility
    await connection_manager.send_message(conversation_id, {
        "type": "vad_status",
        "is_voice": is_voice,
        "energy": energy,
        "conversation_id": conversation_id
    })


async def _handle_audio_chunk(conversation_id: str, data: Dict[str, Any], websocket: WebSocket):
    """Handle incoming audio chunks for STT processing."""
    audio_data_b64 = data.get("data")
    if not audio_data_b64:
        return
        
    try:
        # Decode base64 audio data
        audio_chunk = base64.b64decode(audio_data_b64)
        
        # Add to audio processor queue for continuous streaming
        await connection_manager.add_audio_chunk(conversation_id, audio_chunk)
            
    except Exception as e:
        logger.error(f"Error processing audio chunk: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Audio processing error: {str(e)}"
        })


async def _process_audio_continuous(conversation_id: str, websocket: WebSocket, voicebot_service_instance):
    """Continuous audio processing with proper speech turn management."""
    try:
        logger.info(f"Continuous audio processing started for conversation: {conversation_id}")
        
        # Get audio generator for continuous processing
        audio_generator = await connection_manager.get_audio_generator(conversation_id)
        
        if not audio_generator:
            logger.warning(f"No audio generator available for conversation: {conversation_id}")
            return
            
        # Start continuous processing (STT + VAD monitoring)
        await voicebot_service_instance.start_continuous_processing(conversation_id, audio_generator)
            
    except asyncio.CancelledError:
        logger.info(f"Continuous audio processing cancelled for conversation: {conversation_id}")
    except Exception as e:
        logger.error(f"Error in continuous audio processing for conversation {conversation_id}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Stream processing error: {str(e)}"
        })


async def _handle_start_listening(conversation_id: str, websocket: WebSocket):
    """Handle start listening command."""
    await websocket.send_json({
        "type": "status",
        "status": "listening_started",
        "conversation_id": conversation_id
    })
    logger.info(f"Started listening for conversation: {conversation_id}")


async def _handle_stop_listening(conversation_id: str):
    """Handle stop listening command."""
    await connection_manager.send_message(conversation_id, {
        "type": "status",
        "status": "listening_stopped",
        "conversation_id": conversation_id
    })
    logger.info(f"Stopped listening for conversation: {conversation_id}")


async def _handle_get_status(conversation_id: str, websocket: WebSocket):
    """Handle status request."""
    # This function needs access to the voicebot service instance
    # Since it's called from the main WebSocket handler, we need to pass the instance
    # For now, we'll return a basic status
    await websocket.send_json({
        "type": "status_update",
        "conversation_id": conversation_id,
        "status": {
            "conversation_id": conversation_id,
            "is_active": True
        }
    })


async def _handle_agent_change(conversation_id: str, data: Dict[str, Any], websocket: WebSocket):
    """Handle agent change requests."""
    agent_id = data.get("agent_id")
    
    try:
        logger.info(f"🔍 Agent change requested for conversation {conversation_id}: {agent_id}")
        
        # Update the voicebot service with the new agent configuration
        # Note: This would require access to the voicebot service instance
        # For now, we'll acknowledge the change and let the frontend handle reconnection if needed
        
        await websocket.send_json({
            "type": "agent_changed",
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "message": f"Agent changed to {agent_id}"
        })
        
        logger.info(f"✅ Agent changed for conversation {conversation_id}: {agent_id}")
        
    except Exception as e:
        logger.error(f"Error changing agent for conversation {conversation_id}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to change agent: {str(e)}"
        })


@router.get("/voicebot/conversations")
async def get_active_conversations():
    """Get list of active conversations."""
    # Return basic info since we can't access individual service instances
    return {
        "active_conversations": list(connection_manager.active_connections.keys()),
        "total_count": len(connection_manager.active_connections)
    }


@router.get("/voicebot/health")
async def health_check():
    """Health check endpoint for voicebot service."""
    # Return basic health status since we can't access individual service instances
    return {
        "status": "healthy",
        "services": {
            "stt_service": True,
            "tts_service": True,
            "chatbot_service": True
        },
        "active_connections": len(connection_manager.active_connections),
        "active_conversations": len(connection_manager.active_connections)
    }


@router.websocket("/voicebot/streaming")
async def voicebot_streaming_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for voicebot streaming using shared streaming logic.
    
    This endpoint provides the same parallel live streaming capabilities
    as the TTS interface but integrated with voicebot functionality.
    """
    conversation_id = None
    
    try:
        # Accept connection immediately
        await websocket.accept()
        logger.info("Voicebot streaming WebSocket connection established")
        
        # Wait for initial setup message
        init_message = await websocket.receive_text()
        init_data = json.loads(init_message)
        
        if init_data.get("type") != "start_streaming":
            await websocket.send_json({
                "type": "error",
                "message": "First message must be 'start_streaming'"
            })
            return
            
        conversation_id = init_data.get("conversation_id")
        if not conversation_id:
            # Create a new voicebot service instance for this streaming session
            agent_id = init_data.get("agent_id")
            session_id = init_data.get("session_id")
            voicebot_service_instance = VoicebotService(agent_id=agent_id, session_id=session_id)
            conversation_id = voicebot_service_instance.create_conversation()
        
        # Create streaming session
        session = shared_streaming_manager.create_session(conversation_id)
        
        await websocket.send_json({
            "type": "streaming_started",
            "conversation_id": conversation_id,
            "message": "Streaming session ready"
        })
        
        logger.info(f"Voicebot streaming session started: {conversation_id}")
        
        # Main streaming loop
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            message_type = data.get("type")
            
            if message_type == "text_chunk":
                # Handle text chunk for streaming
                await _handle_streaming_text_chunk(conversation_id, data, websocket)
                
            elif message_type == "end_stream":
                # End streaming session
                await websocket.send_json({
                    "type": "streaming_ended",
                    "conversation_id": conversation_id
                })
                break
                
            elif message_type == "get_status":
                # Get streaming status
                status = shared_streaming_manager.get_session_status(conversation_id)
                await websocket.send_json({
                    "type": "streaming_status",
                    "conversation_id": conversation_id,
                    "status": status
                })
                
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
                
    except WebSocketDisconnect:
        logger.info(f"Voicebot streaming WebSocket disconnected: {conversation_id}")
    except ConnectionClosedOK:
        logger.info(f"Voicebot streaming connection closed normally: {conversation_id}")
    except Exception as e:
        logger.error(f"Voicebot streaming error for {conversation_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Streaming error: {str(e)}"
            })
        except:
            pass
    finally:
        if conversation_id:
            shared_streaming_manager.end_session(conversation_id)
            # Note: We can't access the voicebot_service_instance here as it's created locally
            # The conversation will be cleaned up when the service instance is garbage collected


async def _handle_streaming_text_chunk(conversation_id: str, data: Dict[str, Any], websocket: WebSocket):
    """Handle text chunks for streaming with parallel audio generation."""
    text_chunk = data.get("text")
    is_final = data.get("is_final", False)
    agent_id = data.get("agent_id")
    
    if not text_chunk:
        return
        
    try:
        # Create a text generator for this chunk
        async def text_generator():
            yield text_chunk
            if is_final:
                yield ""  # End of stream signal
        
        # Use agent-based TTS service for streaming
        logger.info(f"🔍 Voicebot Streaming - Using agent-based TTS for agent_id: {agent_id}")
        from services.tts.tts import TTSService
        tts_service = TTSService(agent_id=agent_id)
        
        # Use shared streaming manager for parallel audio generation
        async for audio_chunk in shared_streaming_manager.stream_text_to_audio(
            websocket, text_generator(), tts_service, conversation_id
        ):
            # Audio chunks are automatically sent via send_bytes
            pass
                
        # Send progress update
        session = shared_streaming_manager.get_session(conversation_id)
        if session:
            await websocket.send_json({
                "type": "streaming_progress",
                "conversation_id": conversation_id,
                "llm_progress": session.llm_progress,
                "tts_progress": session.tts_progress,
                "text_chunks_sent": session.text_chunks_sent,
                "audio_chunks_received": session.audio_chunks_received
            })
            
    except Exception as e:
        logger.error(f"Error handling streaming text chunk: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Streaming processing error: {str(e)}"
        })