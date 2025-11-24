"""
Central Event Loop for Voicebot Orchestration.

This module implements an event-driven architecture inspired by LiveKit Agents.
It manages the agent's state (LISTENING, THINKING, SPEAKING) and orchestrates
the flow of data between VAD, STT, LLM, and TTS services.
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncGenerator
import time

logger = logging.getLogger(__name__)

class AgentState(Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"

class VoicebotEventLoop:
    """
    Central event loop for managing voicebot interaction.
    
    Replaces the previous flag-based orchestration with a state machine.
    """
    
    def __init__(
        self, 
        conversation_id: str, 
        output_queue: asyncio.Queue,
        stt_service,
        chatbot_service,
        tts_service,
        vad_service,
        agent_id: str = None,
        session_id: str = None
    ):
        self.conversation_id = conversation_id
        self.output_queue = output_queue
        self.agent_id = agent_id
        self.session_id = session_id
        
        # Services
        self.stt_service = stt_service
        self.chatbot_service = chatbot_service
        self.tts_service = tts_service
        self.vad_service = vad_service
        
        # State
        self.state = AgentState.LISTENING
        self.transcript_buffer = []
        self.current_sentence = ""
        
        # Audio Buffering for VAD-gated STT
        self.audio_buffer = [] # Circular buffer for pre-speech context
        self.is_recording = False
        self.speech_buffer = [] # Buffer for current speech segment
        self.max_pre_speech_buffer_size = 15 # ~500ms at 32ms/chunk
        
        # Tasks
        self.processing_task: Optional[asyncio.Task] = None
        self.stt_task: Optional[asyncio.Task] = None
        self.llm_task: Optional[asyncio.Task] = None
        self.tts_task: Optional[asyncio.Task] = None
        
        # Queues
        self.event_queue = asyncio.Queue()
        self.stt_audio_queue = asyncio.Queue()
        self.tts_text_queue = asyncio.Queue() # Queue for LLM tokens -> TTS
        
    async def start(self):
        """Start the event loop."""
        logger.info(f"Starting event loop for {self.conversation_id}")
        self.processing_task = asyncio.create_task(self._process_events())
        
        # Start STT stream processor
        self.stt_task = asyncio.create_task(self._process_stt_stream())
        
    async def stop(self):
        """Stop the event loop."""
        logger.info(f"Stopping event loop for {self.conversation_id}")
        
        # Cancel all tasks
        tasks = [self.processing_task, self.stt_task, self.llm_task, self.tts_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
    async def process_audio_chunk(self, chunk: bytes):
        """
        Process incoming audio chunk through VAD and gate STT accordingly.
        
        This implements the VAD-gated STT pattern:
        1. All audio goes through VAD first
        2. Pre-speech buffer maintains context (500ms)
        3. Only speech segments are sent to STT
        4. VAD events trigger state transitions
        """
        # Process chunk through Silero VAD
        # SileroVADService.process_audio_chunk returns a list of events
        events = self.vad_service.process_audio_chunk(chunk)
        
        # Check current VAD state
        is_speech = self.vad_service.triggered
        probability = self.vad_service.current_probability
        
        # Handle VAD events (speech_start, speech_end)
        for event in events:
            if event["type"] == "speech_start":
                # Speech detected - transition to recording
                if not self.is_recording:
                    self.is_recording = True
                    logger.info(f"VAD: Speech started (prob={probability:.2f})")
                    await self.push_event("vad_start")
                    
                    # Flush pre-speech buffer to STT for context
                    # This ensures STT catches the first syllable
                    for buffered_chunk in self.audio_buffer:
                        await self.stt_audio_queue.put(buffered_chunk)
                    self.audio_buffer = []
                    
            elif event["type"] == "speech_end":
                # Speech ended - stop recording
                if self.is_recording:
                    self.is_recording = False
                    logger.info(f"VAD: Speech ended (prob={probability:.2f})")
                    await self.push_event("vad_end")
                    # Note: We don't send post-speech padding to avoid STT hallucinations
        
        # Route audio based on VAD state
        if is_speech and self.is_recording:
            # Active speech - send to STT
            await self.stt_audio_queue.put(chunk)
            
        elif not is_speech and not self.is_recording:
            # Silence - maintain pre-speech buffer (circular buffer)
            self.audio_buffer.append(chunk)
            if len(self.audio_buffer) > self.max_pre_speech_buffer_size:
                self.audio_buffer.pop(0)  # Remove oldest chunk
                
        # If is_recording but not is_speech, we're in the transition period
        # (VAD hysteresis). Keep sending to STT until triggered goes False.

    async def _process_stt_stream(self):
        """
        Process audio queue and send to STT service.
        
        This task continuously reads from stt_audio_queue and feeds it to STT.
        Only audio that passes VAD gating reaches this queue.
        """
        async def audio_generator():
            """Generator that yields audio chunks from the queue."""
            while True:
                try:
                    # Wait for audio chunk with timeout to allow cancellation
                    chunk = await asyncio.wait_for(
                        self.stt_audio_queue.get(),
                        timeout=5.0  # 5 second timeout
                    )
                    yield chunk
                    self.stt_audio_queue.task_done()
                except asyncio.TimeoutError:
                    # No audio for 5 seconds - continue waiting
                    # This allows the task to be cancelled cleanly
                    continue
                except asyncio.CancelledError:
                    # Task cancelled - stop generator
                    break
                    
        try:
            # This assumes STTService.transcribe_streaming takes a generator
            # and yields transcripts.
            async for transcript in self.stt_service.transcribe_streaming(audio_generator()):
                await self.push_event("transcript_update", transcript)
        except asyncio.CancelledError:
            logger.info("STT stream processing cancelled")
        except Exception as e:
            logger.error(f"STT stream error: {e}")

    async def push_event(self, event_type: str, data: Any = None):
        """Push an external event to the loop."""
        await self.event_queue.put({"type": event_type, "data": data, "timestamp": time.time()})
        
    async def _process_events(self):
        """Main event processing loop."""
        while True:
            event = await self.event_queue.get()
            event_type = event["type"]
            data = event["data"]
            
            try:
                if event_type == "vad_start":
                    await self._handle_vad_start()
                elif event_type == "vad_end":
                    await self._handle_vad_end()
                elif event_type == "transcript_update":
                    await self._handle_transcript_update(data)
                elif event_type == "llm_token":
                    await self._handle_llm_token(data)
                elif event_type == "tts_chunk":
                    await self._handle_tts_chunk(data)
                elif event_type == "interrupt":
                    await self._handle_interruption()
                elif event_type == "bot_response_interrupted":
                     # Just notify client, logic handled in interrupt
                     await self.output_queue.put({"type": "bot_response_interrupted"})
                    
            except Exception as e:
                logger.error(f"Error processing event {event_type}: {e}")
            finally:
                self.event_queue.task_done()
                
    async def _handle_vad_start(self):
        """Handle speech start event."""
        if self.state == AgentState.SPEAKING:
            # Interruption!
            logger.info("User interrupted agent speech")
            await self.push_event("interrupt")
            
        self.state = AgentState.LISTENING
        # Notify client
        await self.output_queue.put({"type": "speech_start"})
        
    async def _handle_vad_end(self):
        """Handle speech end event."""
        # Notify client
        await self.output_queue.put({"type": "speech_end"})
        
        # Trigger LLM if we have accumulated transcripts
        if self.transcript_buffer:
            full_text = " ".join(self.transcript_buffer)
            logger.info(f"Triggering LLM with text: {full_text}")
            
            # Clear buffer
            self.transcript_buffer = []
            
            # Start LLM processing
            self.state = AgentState.THINKING
            await self.output_queue.put({"type": "bot_responding_start"})
            
            self.llm_task = asyncio.create_task(self._process_llm_response(full_text))

    async def _handle_transcript_update(self, transcript_data: Dict[str, Any]):
        """Handle STT transcript update."""
        text = transcript_data.get("transcript", "") # STTService returns 'transcript' key
        is_final = transcript_data.get("is_final", False)
        
        if not text:
            return

        # Forward to client
        await self.output_queue.put({
            "type": "transcript_update", 
            "text": text, 
            "is_final": is_final
        })
        
        if is_final:
            self.transcript_buffer.append(text)

    async def _handle_interruption(self):
        """Handle interruption logic."""
        self.state = AgentState.LISTENING
        
        # Cancel LLM/TTS tasks
        if self.llm_task and not self.llm_task.done():
            self.llm_task.cancel()
        if self.tts_task and not self.tts_task.done():
            self.tts_task.cancel()
            
        # Clear queues
        while not self.tts_text_queue.empty():
            try:
                self.tts_text_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            
        # Notify client
        await self.output_queue.put({"type": "bot_response_interrupted"})
        
    async def _process_llm_response(self, text: str):
        """Process text with LLM and feed TTS."""
        try:
            # Get RAG state (mocked or imported)
            # Ideally passed in or fetched via service
            # For now, assume chatbot_service handles it or we pass None
            rag_state = None 
            
            # Start TTS task
            self.tts_task = asyncio.create_task(self._process_tts_stream())
            
            async for response_chunk in self.chatbot_service.process_chat_message(
                text,
                self.conversation_id,
                rag_state=rag_state,
                agent_id=self.agent_id,
                session_id=self.session_id
            ):
                chunk_type = response_chunk.get('type')
                if chunk_type in ['first_token', 'chunk']:
                    content = response_chunk.get('content', '')
                    if content:
                        await self.tts_text_queue.put(content)
                        # Also notify client of text
                        await self.output_queue.put({
                            "type": "assistant_response",
                            "text": content, # This should be accumulated text ideally, or just chunk
                            "is_complete": False
                        })
                elif chunk_type == 'complete':
                    await self.tts_text_queue.put(None) # End of stream
                    await self.output_queue.put({
                        "type": "assistant_response",
                        "text": "",
                        "is_complete": True
                    })
                    break
                elif chunk_type == 'error':
                    logger.error(f"LLM error: {response_chunk.get('content')}")
                    await self.tts_text_queue.put(None)
                    break
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            await self.tts_text_queue.put(None)

    async def _process_tts_stream(self):
        """Process text queue and stream TTS audio."""
        from services.shared_streaming import shared_streaming_manager
        
        async def text_generator():
            while True:
                chunk = await self.tts_text_queue.get()
                if chunk is None:
                    break
                yield chunk
                self.tts_text_queue.task_done()
        
        try:
            # Use shared streaming manager logic
            async for audio_chunk in shared_streaming_manager.stream_text_to_audio_no_websocket(
                text_generator(),
                self.tts_service,
                self.conversation_id
            ):
                await self.push_event("tts_chunk", audio_chunk)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"TTS streaming error: {e}")
        finally:
            self.state = AgentState.LISTENING # Back to listening after TTS
            await self.output_queue.put({"type": "bot_responding_end"})
            
    async def _handle_llm_token(self, token: str):
        """Handle LLM token generation (Unused if using direct queue)."""
        pass
        
    async def _handle_tts_chunk(self, audio_chunk: bytes):
        """Handle TTS audio chunk."""
        self.state = AgentState.SPEAKING
        # Send audio to client
        await self.output_queue.put({"type": "audio_chunk", "data": audio_chunk})
