"""
TTS API Routes with Centralized Streaming Logic
"""

import logging
from fastapi import APIRouter, WebSocket
from .tts import TTSService
from services.shared_streaming import shared_streaming_manager

logger = logging.getLogger(__name__)

router = APIRouter()
# Don't initialize TTSService globally - create instances per request with agent_id

@router.websocket("/tts/ws")
async def tts_websocket(websocket: WebSocket, agent_id: str = None):
    """
    WebSocket endpoint for TTS operations using centralized streaming logic
    Supports agent-based configuration via agent_id parameter
    """
    await websocket.accept()
    
    # Validate and normalize agent_id
    normalized_agent_id = None
    if agent_id and agent_id != "null" and agent_id != "undefined":
        try:
            from uuid import UUID
            normalized_agent_id = UUID(agent_id)
        except ValueError:
            logger.warning(f"Invalid agent_id format: {agent_id}, using default agent")
    
    logger.info(f"✅ TTS WebSocket connected (agent_id: {normalized_agent_id})")
    
    session_id = f"tts_session_{id(websocket)}"
    
    try:
        # Create TTS service instance with agent configuration
        tts_service = TTSService(agent_id=normalized_agent_id)
        
        async def text_generator():
            while True:
                # Receive text data
                data = await websocket.receive_text()
                logger.info(f"📤 Received text: '{data}'")
                if data == "":  # End of stream signal
                    logger.info("📤 End of stream signal received")
                    break
                yield data

        # Use centralized streaming manager for parallel streaming
        audio_chunk_count = 0
        async for audio_chunk in shared_streaming_manager.stream_text_to_audio(
            websocket, text_generator(), tts_service, session_id
        ):
            audio_chunk_count += 1
            logger.info(f"🎵 Sending audio chunk {audio_chunk_count}: {len(audio_chunk)} bytes")
            # Audio chunks are automatically sent via send_bytes in the shared manager

        logger.info(f"✅ Stream completed: {audio_chunk_count} audio chunks sent")

    except Exception as e:
        logger.error(f"❌ TTS WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up session
        shared_streaming_manager.end_session(session_id)
        await websocket.close()
        logger.info("🔌 TTS WebSocket closed")


@router.websocket("/tts/streaming")
async def tts_streaming_websocket(websocket: WebSocket, agent_id: str = None):
    """
    Enhanced WebSocket endpoint for TTS streaming with progress tracking
    using centralized streaming logic.
    Supports agent-based configuration via agent_id parameter
    """
    await websocket.accept()
    
    # Validate and normalize agent_id
    normalized_agent_id = None
    if agent_id and agent_id != "null" and agent_id != "undefined":
        try:
            from uuid import UUID
            normalized_agent_id = UUID(agent_id)
        except ValueError:
            logger.warning(f"Invalid agent_id format: {agent_id}, using default agent")
    
    logger.info(f"✅ TTS Streaming WebSocket connected (agent_id: {normalized_agent_id})")
    
    session_id = f"tts_streaming_{id(websocket)}"
    
    try:
        # Create TTS service instance with agent configuration
        tts_service = TTSService(agent_id=normalized_agent_id)
        
        # Wait for initial setup message
        init_message = await websocket.receive_text()
        init_data = init_message  # Simple text for now
        
        if init_data != "start_streaming":
            await websocket.send_json({
                "type": "error",
                "message": "First message must be 'start_streaming'"
            })
            return
            
        # Create streaming session
        session = shared_streaming_manager.create_session(session_id)
        
        await websocket.send_json({
            "type": "streaming_started",
            "session_id": session_id,
            "message": "TTS streaming session ready"
        })
        
        logger.info(f"TTS streaming session started: {session_id}")
        
        # Main streaming loop
        while True:
            message = await websocket.receive_text()
            
            if message == "end_stream":
                # End streaming session
                await websocket.send_json({
                    "type": "streaming_ended",
                    "session_id": session_id
                })
                break
            elif message == "get_status":
                # Get streaming status
                status = shared_streaming_manager.get_session_status(session_id)
                await websocket.send_json({
                    "type": "streaming_status",
                    "session_id": session_id,
                    "status": status
                })
            else:
                # Handle text chunk for streaming
                async def text_generator():
                    yield message
                
                # Use centralized streaming manager for parallel audio generation
                async for audio_chunk in shared_streaming_manager.stream_text_to_audio(
                    websocket, text_generator(), tts_service, session_id
                ):
                    # Audio chunks are automatically sent via send_bytes
                    pass
                
                # Send progress update
                session = shared_streaming_manager.get_session(session_id)
                if session:
                    await websocket.send_json({
                        "type": "streaming_progress",
                        "session_id": session_id,
                        "llm_progress": session.llm_progress,
                        "tts_progress": session.tts_progress,
                        "text_chunks_sent": session.text_chunks_sent,
                        "audio_chunks_received": session.audio_chunks_received
                    })
                
    except Exception as e:
        logger.error(f"TTS streaming error for {session_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Streaming error: {str(e)}"
            })
        except:
            pass
    finally:
        # Clean up session
        shared_streaming_manager.end_session(session_id)
        await websocket.close()
        logger.info(f"🔌 TTS Streaming WebSocket closed: {session_id}")
