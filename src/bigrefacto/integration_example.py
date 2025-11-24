"""
Integration example for VoicebotServiceV2 with existing routes.

This file shows how to integrate the event-driven architecture
into the existing WebSocket routes with minimal changes.
"""

# In routes.py, add this import at the top:
from .voicebot_service_v2 import VoicebotServiceV2

# Then modify the _process_audio_continuous function:

async def _process_audio_continuous_v2(conversation_id: str, websocket: WebSocket, voicebot_service_instance):
    """
    Continuous audio processing with event-driven architecture.
    
    This is a drop-in replacement for _process_audio_continuous that uses
    VoicebotServiceV2 instead of VoicebotService.
    """
    try:
        logger.info(f"Event-driven audio processing started for conversation: {conversation_id}")
        
        # Get audio generator for continuous processing
        audio_generator = await connection_manager.get_audio_generator(conversation_id)
        
        if not audio_generator:
            logger.warning(f"No audio generator available for conversation: {conversation_id}")
            return
            
        # Start event-driven processing (replaces start_continuous_processing)
        await voicebot_service_instance.start_event_driven_processing(conversation_id, audio_generator)
            
    except asyncio.CancelledError:
        logger.info(f"Event-driven audio processing cancelled for conversation: {conversation_id}")
    except Exception as e:
        logger.error(f"Error in event-driven audio processing for conversation {conversation_id}: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"Stream processing error: {str(e)}"
        })


# To enable V2, modify the voicebot_websocket_endpoint:

@router.websocket("/voicebot/stream")
async def voicebot_websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for voicebot real-time communication.
    
    Modified to use VoicebotServiceV2 (event-driven architecture).
    """
    conversation_id = None
    agent_id = None
    session_id = None
    
    try:
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
        
        # USE V2 SERVICE HERE
        if not conversation_id:
            voicebot_service_instance = VoicebotServiceV2(agent_id=agent_id, session_id=session_id)
            conversation_id = voicebot_service_instance.create_conversation()
        else:
            voicebot_service_instance = VoicebotServiceV2(agent_id=agent_id, session_id=session_id)
            
        # Register connection
        await connection_manager.connect(websocket, conversation_id)
        
        # ... (TTS configuration code remains the same) ...
        
        await websocket.send_json({
            "type": "conversation_started",
            "conversation_id": conversation_id,
            "config": {
                "sample_rate": voicebot_config.SAMPLE_RATE,
                "chunk_size_ms": voicebot_config.CHUNK_SIZE_MS,
                "vad_threshold": voicebot_config.VAD_THRESHOLD,
                "architecture": "event-driven-v2"  # Add this to indicate V2
            }
        })
        
        logger.info(f"Voicebot session started (V2): {conversation_id}")
        
        # USE V2 PROCESSING FUNCTION
        processing_task = asyncio.create_task(
            _process_audio_continuous_v2(conversation_id, websocket, voicebot_service_instance)
        )
        
        # Main message processing loop (unchanged)
        while True:
            message = await websocket.receive()
            
            if "text" in message:
                data = json.loads(message["text"])
                await _handle_websocket_message(conversation_id, data, websocket)
                
            elif "bytes" in message:
                await connection_manager.add_audio_chunk(conversation_id, message["bytes"])
            
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
            if 'processing_task' in locals() and not processing_task.done():
                processing_task.cancel()
                try:
                    await processing_task
                except asyncio.CancelledError:
                    pass
            
            connection_manager.disconnect(conversation_id)
            await voicebot_service_instance.end_conversation(conversation_id)  # Use await for V2


# Alternative: Create a separate endpoint for V2 testing

@router.websocket("/voicebot/stream_v2")
async def voicebot_websocket_endpoint_v2(websocket: WebSocket):
    """
    V2 endpoint for testing event-driven architecture side-by-side with V1.
    
    This allows gradual migration and A/B testing.
    """
    # Same implementation as above but explicitly for V2
    # This way you can test both architectures simultaneously
    pass
