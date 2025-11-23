"""
Main service orchestrator for the voicebot wrapper.

This service integrates STT, RAG/LLM, and TTS services into a complete
real-time voice conversation system with proper speech turn management.
"""

import asyncio
import logging
import uuid
from typing import AsyncGenerator, Dict, Any, Optional

from .config import voicebot_config
from .vad_service import vad_processor
from services.stt.stt import STTService
from services.tts.tts import TTSService
from services.rag.chatbot_service import ChatbotService
from services.shared_streaming import shared_streaming_manager

# Configure logging to reduce noise from websockets binary data
logging.getLogger("websockets.client").setLevel(logging.WARNING)
logging.getLogger("websockets.server").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class ConversationState:
    """Conversation state for proper speech turn management."""
    
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        
        # Transcript management
        self.current_transcript = ""  # Continuously updated by STT
        self.final_transcript = ""    # Set when speech ends
        self.final_transcripts = []   # All final transcripts during speech turn
        self.intermediate_buffer = "" # Buffer for intermediate transcripts
        
        # Speech state
        self.is_user_speaking = False  # VAD speech activity state
        self.is_bot_responding = False # Bot response state
        
        # Task management
        self.stt_continuous_task = None  # Continuous STT processing
        self.vad_monitoring_task = None  # VAD boundary detection
        self.rag_llm_task = None         # RAG/LLM processing
        self.tts_stream_task = None      # TTS playback
        
        # VAD state tracking
        self.vad_results = []
        
    async def stop_all_processing(self):
        """Stop all ongoing processing for conversation cleanup."""
        # Debug logging removed for production
        
        # Cancel all tasks
        tasks = [
            self.stt_continuous_task,
            self.vad_monitoring_task,
            self.rag_llm_task,
            self.tts_stream_task
        ]
        
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Reset state
        self.reset_state()
    
    def reset_state(self):
        """Reset conversation state for new interaction."""
        self.current_transcript = ""
        self.final_transcript = ""
        self.final_transcripts = []
        self.intermediate_buffer = ""
        self.is_user_speaking = False
        self.is_bot_responding = False
        self.vad_results = []
        # Debug logging removed for production


class VoicebotService:
    """Main orchestrator for the complete voicebot pipeline with proper speech turn management."""
    
    def __init__(self, agent_id: str = None, session_id: str = None):
        self.config = voicebot_config
        self.agent_id = agent_id
        self.session_id = session_id
        self.stt_service: Optional[STTService] = None
        self.tts_service: Optional[TTSService] = None
        self.chatbot_service: Optional[ChatbotService] = None
        self.active_conversations: Dict[str, ConversationState] = {}
        
        # Initialize services
        self._initialize_services()
        
    def _initialize_services(self):
        """Initialize the dependent services."""
        try:
            self.stt_service = STTService(agent_id=self.agent_id, session_id=self.session_id)
            # Debug logging removed for production
        except Exception as e:
            logger.error(f"Failed to initialize STT service: {e}")
            
        try:
            self.tts_service = TTSService(agent_id=self.agent_id, session_id=self.session_id)
            # Debug logging removed for production
        except Exception as e:
            logger.error(f"Failed to initialize TTS service: {e}")
            
        try:
            self.chatbot_service = ChatbotService()
            # Debug logging removed for production
        except Exception as e:
            logger.error(f"Failed to initialize chatbot service: {e}")
    
    def create_conversation(self) -> str:
        """Create a new conversation session."""
        conversation_id = str(uuid.uuid4())
        self.active_conversations[conversation_id] = ConversationState(conversation_id)
        # Debug logging removed for production
        return conversation_id
    
    def end_conversation(self, conversation_id: str):
        """End a conversation session."""
        if conversation_id in self.active_conversations:
            del self.active_conversations[conversation_id]
            # Debug logging removed for production
    
    async def start_continuous_processing(
        self,
        conversation_id: str,
        audio_generator: AsyncGenerator[bytes, None]
    ):
        """Start continuous STT and VAD processing for a conversation."""
        if conversation_id not in self.active_conversations:
            return
            
        conversation = self.active_conversations[conversation_id]
        
        # Create separate audio generators for STT and VAD
        stt_audio_generator, vad_audio_generator = self._split_audio_generator(audio_generator)
        
        # Start continuous STT processing
        conversation.stt_continuous_task = asyncio.create_task(
            self._process_continuous_stt(conversation_id, stt_audio_generator)
        )
        
        # Start VAD monitoring for speech boundaries
        conversation.vad_monitoring_task = asyncio.create_task(
            self._monitor_speech_boundaries(conversation_id, vad_audio_generator)
        )
        
        # Debug logging removed for production
    
    def _split_audio_generator(self, audio_generator: AsyncGenerator[bytes, None]):
        """Split audio generator into two separate generators for STT and VAD."""
        import asyncio
        from collections import deque
        
        class AudioSplitter:
            def __init__(self):
                self.stt_queue = deque()
                self.vad_queue = deque()
                self.audio_generator = audio_generator
                self.task = None
                
            async def _consume_audio(self):
                """Consume audio from generator and distribute to both queues."""
                try:
                    async for audio_chunk in self.audio_generator:
                        # Add to both queues
                        self.stt_queue.append(audio_chunk)
                        self.vad_queue.append(audio_chunk)
                except Exception as e:
                    # Debug logging removed for production
                    # Add sentinel values to signal end
                    self.stt_queue.append(None)
                    self.vad_queue.append(None)
            
            async def stt_generator(self):
                """Generator for STT processing."""
                if not self.task:
                    self.task = asyncio.create_task(self._consume_audio())
                
                while True:
                    if self.stt_queue:
                        chunk = self.stt_queue.popleft()
                        if chunk is None:
                            break
                        yield chunk
                    else:
                        await asyncio.sleep(0.001)  # Small delay to avoid busy waiting
            
            async def vad_generator(self):
                """Generator for VAD processing."""
                if not self.task:
                    self.task = asyncio.create_task(self._consume_audio())
                
                while True:
                    if self.vad_queue:
                        chunk = self.vad_queue.popleft()
                        if chunk is None:
                            break
                        yield chunk
                    else:
                        await asyncio.sleep(0.001)  # Small delay to avoid busy waiting
        
        splitter = AudioSplitter()
        return splitter.stt_generator(), splitter.vad_generator()
    
    async def _process_continuous_stt(
        self,
        conversation_id: str,
        audio_generator: AsyncGenerator[bytes, None]
    ):
        """Process continuous STT transcription."""
        try:
            if not self.stt_service:
                # Debug logging removed for production
                return
                
            conversation = self.active_conversations.get(conversation_id)
            if not conversation:
                return
            
            async for transcript_result in self.stt_service.transcribe_streaming(audio_generator):
                if not conversation:
                    break
                    
                if 'transcript' in transcript_result and transcript_result['transcript']:
                    # Update current transcript continuously
                    conversation.current_transcript = transcript_result['transcript']
                    
                    # Send transcript update to frontend
                    is_final = transcript_result.get('is_final', False)
                    # Debug logging removed for production
                    await self._send_websocket_message(conversation_id, {
                        "type": "transcript_update",
                        "text": transcript_result['transcript'],
                        "is_final": is_final
                    })
                    
                    # Handle transcripts based on final status
                    if is_final and conversation.is_user_speaking:
                        # When final transcript arrives, add it to final transcripts and clear buffer
                        conversation.final_transcripts.append(transcript_result['transcript'])
                        conversation.intermediate_buffer = ""  # Clear buffer after final transcript
                        # Debug logging removed for production
                    elif not is_final and conversation.is_user_speaking:
                        # For intermediate transcripts, update the buffer
                        conversation.intermediate_buffer = transcript_result['transcript']
                        # Debug logging removed for production
                    
                    # Only trigger RAG/LLM from VAD speech end detection, not from STT
                    # This prevents multiple triggers
                        
        except asyncio.CancelledError:
            # Debug logging removed for production
            pass
        except Exception as e:
            # Debug logging removed for production
            logger.error(f"Error in continuous STT processing: {e}")
    
    async def _monitor_speech_boundaries(
        self,
        conversation_id: str,
        audio_generator: AsyncGenerator[bytes, None]
    ):
        """Monitor VAD for speech start/end boundaries."""
        try:
            conversation = self.active_conversations.get(conversation_id)
            if not conversation:
                return
            
            previous_speech_state = False
            
            async for vad_result in vad_processor.start_vad_processing(conversation_id, audio_generator):
                if not conversation:
                    break
                
                # Store VAD result
                conversation.vad_results.append(vad_result)
                
                # Track speech state changes
                current_speech_state = vad_result["is_voice_active"]
                
                # Speech start detection
                if current_speech_state and not previous_speech_state:
                    conversation.is_user_speaking = True
                    # Debug logging removed for production
                    await self._send_websocket_message(conversation_id, {
                        "type": "speech_start"
                    })
                    
                    # Interrupt TTS if bot is responding
                    if conversation.is_bot_responding:
                        await self._interrupt_bot_response(conversation)
                
                # Speech end detection  
                elif not current_speech_state and previous_speech_state:
                    conversation.is_user_speaking = False
                    # Debug logging removed for production
                    await self._send_websocket_message(conversation_id, {
                        "type": "speech_end",
                        "final_transcript": conversation.current_transcript
                    })
                    
                    # Trigger RAG/LLM if we have a transcript
                    if conversation.current_transcript:
                        await self._trigger_rag_llm(conversation)
                
                previous_speech_state = current_speech_state
                
                # Send VAD status for frontend display
                await self._send_websocket_message(conversation_id, {
                    "type": "vad_status",
                    "is_voice": vad_result["is_voice"],
                    "is_voice_active": vad_result["is_voice_active"],
                    "voice_probability": vad_result["voice_probability"],
                    "conversation_id": conversation_id,
                    "timestamp": vad_result["timestamp"]
                })
                
        except asyncio.CancelledError:
            logger.info(f"VAD monitoring cancelled for conversation: {conversation_id}")
            # Debug logging removed for production
        except Exception as e:
            # Debug logging removed for production
            logger.error(f"Error in VAD monitoring: {e}")
    
    async def _trigger_rag_llm(self, conversation: ConversationState):
        """Trigger RAG/LLM processing with all final transcripts from the speech turn."""
        if conversation.is_bot_responding:
            # Debug logging removed for production
            return
            
        if not self.chatbot_service:
            # Debug logging removed for production
            return
        
        # Combine all final transcripts and the intermediate buffer
        combined_parts = []
        
        # Add all final transcripts
        if conversation.final_transcripts:
            combined_parts.extend(conversation.final_transcripts)
        
        # Add intermediate buffer if it exists
        if conversation.intermediate_buffer:
            combined_parts.append(conversation.intermediate_buffer)
        
        # Create the final combined transcript
        if combined_parts:
            conversation.final_transcript = " ".join(combined_parts)
            # Debug logging removed for production
        else:
            # Fallback to current transcript if nothing was collected
            conversation.final_transcript = conversation.current_transcript
            # Debug logging removed for production
        
        conversation.is_bot_responding = True
        
        # Debug logging removed for production
        
        # Start RAG/LLM processing task
        conversation.rag_llm_task = asyncio.create_task(
            self._process_with_rag_llm(conversation)
        )
    
    async def _process_with_rag_llm(self, conversation: ConversationState):
        """Process final transcript through RAG/LLM with parallel TTS streaming."""
        try:
            await self._send_websocket_message(conversation.conversation_id, {
                "type": "bot_responding_start"
            })
            
            # Get RAG state
            from services.rag.chatbot_routes import get_rag_state
            rag_state = await get_rag_state()
            
            # Debug logging removed for production
            
            # Process with RAG/LLM and stream tokens
            conversation.response_text = ""
            
            # Create a queue to stream text chunks to TTS
            text_queue = asyncio.Queue()
            tts_streaming_task = None
            
            async def text_chunk_generator():
                """Generator that yields text chunks from the queue."""
                while True:
                    chunk = await text_queue.get()
                    if chunk is None:  # End signal
                        yield ""  # End of stream signal
                        break
                    yield chunk
                    text_queue.task_done()
            
            async def process_llm_stream():
                """Process LLM stream and send chunks to TTS with configurable buffering."""
                try:
                    # Buffer for accumulating tokens based on buffering level
                    text_buffer = ""
                    buffering_level = self.config.PRE_TTS_BUFFERING_LEVEL
                    
                    # Log the buffering level being used
                    logger.info(f"Using TTS buffering level: {buffering_level}")
                    
                    # Define punctuation characters for MEDIUM and HIGH levels
                    punctuation_chars = ".!?;:"
                    
                    async for response_chunk in self.chatbot_service.process_chat_message(
                        conversation.final_transcript,
                        conversation.conversation_id,
                        rag_state=rag_state,
                        agent_id=self.agent_id,
                        session_id=self.session_id
                    ):
                        # Check if user started speaking (interruption)
                        if conversation.is_user_speaking:
                            # Debug logging removed for production
                            break
                        
                        chunk_type = response_chunk.get('type')
                        
                        if chunk_type == 'first_token':
                            content = response_chunk.get('content', '')
                            conversation.response_text = content
                            # Add to buffer
                            text_buffer += content
                            
                            # Process buffer based on buffering level
                            await self._process_buffer_by_level(text_buffer, text_queue, buffering_level, punctuation_chars)
                            
                            await self._send_websocket_message(conversation.conversation_id, {
                                "type": "assistant_response",
                                "text": conversation.response_text,
                                "is_complete": False,
                                "is_first_token": True
                            })
                            
                        elif chunk_type == 'chunk':
                            new_content = response_chunk.get('content', '')
                            conversation.response_text += new_content
                            # Add to buffer
                            text_buffer += new_content
                            
                            # Process buffer based on buffering level
                            text_buffer = await self._process_buffer_by_level(text_buffer, text_queue, buffering_level, punctuation_chars)
                            
                            await self._send_websocket_message(conversation.conversation_id, {
                                "type": "assistant_response",
                                "text": conversation.response_text,
                                "is_complete": False
                            })
                            
                        elif chunk_type == 'complete':
                            # Send any remaining content in buffer
                            if text_buffer:
                                await text_queue.put(text_buffer)
                                text_buffer = ""
                            # Signal end of text stream to TTS
                            await text_queue.put(None)
                            await self._send_websocket_message(conversation.conversation_id, {
                                "type": "assistant_response",
                                "text": conversation.response_text,
                                "is_complete": True
                            })
                            break
                            
                        elif chunk_type == 'error':
                            # Debug logging removed for production
                            await text_queue.put(None)  # Signal end
                            await self._send_websocket_message(conversation.conversation_id, {
                                "type": "error",
                                "message": f"Response generation failed: {response_chunk.get('content')}"
                            })
                            break
                except Exception as e:
                    logger.error(f"Error in LLM stream processing: {e}")
                    await text_queue.put(None)  # Ensure TTS stops
                    raise
            
            # Start TTS streaming in parallel with LLM processing
            if not conversation.is_user_speaking:
                tts_streaming_task = asyncio.create_task(
                    self._stream_tts_audio_with_shared_logic(conversation, text_chunk_generator())
                )
            
            # Process LLM stream (this will feed text chunks to TTS)
            await process_llm_stream()
            
            # Wait for TTS to complete if it's still running
            if tts_streaming_task and not tts_streaming_task.done():
                await tts_streaming_task
            
        except asyncio.CancelledError:
            # Debug logging removed for production
            pass
        except Exception as e:
            # Debug logging removed for production
            logger.error(f"Error in RAG/LLM processing: {e}")
            await self._send_websocket_message(conversation.conversation_id, {
                "type": "error",
                "message": f"Response generation failed: {e}"
            })
        finally:
            conversation.is_bot_responding = False
            await self._send_websocket_message(conversation.conversation_id, {
                "type": "bot_responding_end"
            })
    
    async def _process_buffer_by_level(self, text_buffer: str, text_queue: asyncio.Queue, buffering_level: str, punctuation_chars: str) -> str:
        """Process text buffer based on buffering level and send complete chunks to TTS.
        
        Returns:
            Updated text buffer (may be empty or contain remaining text)
        """
        if buffering_level == "NONE":
            # Send everything immediately
            if text_buffer:
                await text_queue.put(text_buffer)
                return ""
        
        elif buffering_level == "LOW":
            # Current behavior - buffer until word completion (space)
            if text_buffer.endswith(' '):
                # Send the complete word to TTS
                await text_queue.put(text_buffer)
                return ""
            elif ' ' in text_buffer:
                # If there's a space in the buffer, split and send complete words
                parts = text_buffer.rsplit(' ', 1)
                if len(parts) > 1:
                    # Send all complete words (everything before the last space)
                    await text_queue.put(parts[0] + ' ')
                    # Keep the last incomplete word in buffer
                    return parts[1]
        
        elif buffering_level == "MEDIUM":
            # Buffer until 4 words OR punctuation
            words = text_buffer.split()
            if len(words) >= 4:
                # Send first 4 words
                text_to_send = ' '.join(words[:4]) + ' '
                await text_queue.put(text_to_send)
                # Keep remaining words in buffer
                remaining_text = ' '.join(words[4:])
                return remaining_text
            
            # Check for punctuation
            for char in punctuation_chars:
                if char in text_buffer:
                    # Find the last punctuation position
                    last_punct_pos = max(text_buffer.rfind(char) for char in punctuation_chars)
                    if last_punct_pos != -1:
                        # Send up to and including punctuation
                        text_to_send = text_buffer[:last_punct_pos + 1]
                        await text_queue.put(text_to_send)
                        # Keep text after punctuation
                        return text_buffer[last_punct_pos + 1:]
        
        elif buffering_level == "HIGH":
            # Buffer until punctuation
            for char in punctuation_chars:
                if char in text_buffer:
                    # Find the last punctuation position
                    last_punct_pos = max(text_buffer.rfind(char) for char in punctuation_chars)
                    if last_punct_pos != -1:
                        # Send up to and including punctuation
                        text_to_send = text_buffer[:last_punct_pos + 1]
                        await text_queue.put(text_to_send)
                        # Keep text after punctuation
                        return text_buffer[last_punct_pos + 1:]
        
        # If no condition met, return the buffer unchanged
        return text_buffer

    async def _interrupt_bot_response(self, conversation: ConversationState):
        """Interrupt bot response (TTS playback)."""
        # Debug logging removed for production
        
        # Cancel TTS streaming task
        if conversation.tts_stream_task and not conversation.tts_stream_task.done():
            conversation.tts_stream_task.cancel()
            try:
                await conversation.tts_stream_task
            except asyncio.CancelledError:
                pass
            conversation.tts_stream_task = None
        
        # Reset bot response state
        conversation.is_bot_responding = False
        conversation.response_text = ""
        
        await self._send_websocket_message(conversation.conversation_id, {
            "type": "bot_response_interrupted"
        })
    
    
    async def _stream_tts_audio_with_shared_logic(self, conversation: ConversationState, text_generator: AsyncGenerator[str, None]):
        """Stream TTS audio using shared streaming logic for parallel streaming."""
        try:
            # Create a wrapper for sending bytes that checks for interruption
            async def send_bytes_wrapper(conversation_id: str, data: bytes):
                # Check if user started speaking (interruption)
                if conversation.is_user_speaking:
                    # Debug logging removed for production
                    raise asyncio.CancelledError("User interruption")
                
                await self._send_websocket_bytes(conversation_id, data)
            
            # Use shared streaming manager for parallel streaming (without WebSocket)
            async for audio_chunk in shared_streaming_manager.stream_text_to_audio_no_websocket(
                text_generator,
                self.tts_service,
                conversation.conversation_id
            ):
                # Check if user started speaking (interruption)
                if conversation.is_user_speaking:
                    # Debug logging removed for production
                    break
                
                await self._send_websocket_bytes(conversation.conversation_id, audio_chunk)
            
            if not conversation.is_user_speaking:
                await self._send_websocket_message(conversation.conversation_id, {
                    "type": "complete"
                })
                
        except asyncio.CancelledError:
            # Debug logging removed for production
            pass
        except Exception as e:
            # Debug logging removed for production
            logger.error(f"Error in TTS streaming: {e}")
            await self._send_websocket_message(conversation.conversation_id, {
                "type": "error",
                "message": f"Speech synthesis failed: {e}"
            })
    
    async def _send_websocket_message(self, conversation_id: str, message: Dict[str, Any]):
        """Send message to WebSocket connection for a conversation."""
        try:
            from .routes import connection_manager
            await connection_manager.send_message(conversation_id, message)
        except Exception as e:
            logger.error(f"Error sending message to {conversation_id}: {e}")
            # Debug logging removed for production
    
    async def _send_websocket_bytes(self, conversation_id: str, data: bytes):
        """Send raw binary data to WebSocket connection (like TTS interface)."""
        try:
            from .routes import connection_manager
            await connection_manager.send_bytes(conversation_id, data)
        except Exception as e:
            logger.error(f"Error sending bytes to {conversation_id}: {e}")
            # Debug logging removed for production
    
    def get_conversation_status(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a conversation."""
        if conversation_id in self.active_conversations:
            conversation = self.active_conversations[conversation_id]
            return {
                "conversation_id": conversation_id,
                "current_transcript": conversation.current_transcript,
                "final_transcript": conversation.final_transcript,
                "final_transcripts": conversation.final_transcripts,
                "intermediate_buffer": conversation.intermediate_buffer,
                "is_user_speaking": conversation.is_user_speaking,
                "is_bot_responding": conversation.is_bot_responding,
                "response_text": getattr(conversation, 'response_text', '')
            }
        return None


# Global service instance
voicebot_service = VoicebotService()