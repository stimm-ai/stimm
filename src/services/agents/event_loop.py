"""
Central Event Loop for Stimm Orchestration.

This module implements an event-driven architecture inspired by LiveKit Agents.
It manages the agent's state (LISTENING, THINKING, SPEAKING) and orchestrates
the flow of data between VAD, STT, LLM, and TTS services.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional

from .metrics import TurnState, VADState

logger = logging.getLogger(__name__)


class AgentState(Enum):
    LISTENING = "listening"
    WAITING_FOR_TRANSCRIPT = "waiting_for_transcript"
    THINKING = "thinking"
    SPEAKING = "speaking"


class StimmEventLoop:
    """
    Central event loop for managing stimm interaction.

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
        session_id: str = None,
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

        # RAG State (initialized lazily but persisted)
        self.rag_state = None

        # State
        self.state = AgentState.LISTENING
        self.turn_state = TurnState()
        self.transcript_buffer = []
        self.current_sentence = ""
        self.last_speech_end_time = 0

        # Audio Buffering for VAD-gated STT
        self.audio_buffer = []  # Circular buffer for pre-speech context
        self.is_recording = False
        self.speech_buffer = []  # Buffer for current speech segment
        self.max_pre_speech_buffer_size = 15  # ~500ms at 32ms/chunk

        # TTS Buffering
        from .config import stimm_config

        self.buffering_level = stimm_config.PRE_TTS_BUFFERING_LEVEL
        self.text_buffer = ""
        self.punctuation_chars = ".!?;:"

        # Tasks
        self.processing_task: Optional[asyncio.Task] = None
        self.stt_task: Optional[asyncio.Task] = None
        self.llm_task: Optional[asyncio.Task] = None
        self.tts_task: Optional[asyncio.Task] = None

        # Queues
        self.event_queue = asyncio.Queue()
        self.stt_audio_queue = asyncio.Queue()
        self.tts_text_queue = asyncio.Queue()  # Queue for LLM tokens -> TTS

        # DEBUG: Track audio processing
        self.audio_chunks_received = 0
        self.audio_chunks_sent_to_stt = 0
        self.vad_events_logged = []
        self.last_transcript_received = None

        logger.info(f"🎙️ StimmEventLoop initialized for conversation {conversation_id}")
        logger.debug(f"🔧 Agent ID: {agent_id}, Session ID: {session_id}")
        logger.debug(f"🎤 STT Service: {stt_service.provider.__class__.__name__ if stt_service.provider else 'None'}")
        logger.debug(f"🔊 TTS Service: {tts_service.provider.__class__.__name__ if tts_service.provider else 'None'}")
        logger.debug(f"👁️ VAD Service: {vad_service.__class__.__name__}")

    async def start(self):
        """Start the event loop."""
        logger.info(f"Starting event loop for {self.conversation_id}")
        self.processing_task = asyncio.create_task(self._process_events())

        # Start STT stream processor
        self.stt_task = asyncio.create_task(self._process_stt_stream())

        # RAG is now preloaded via REST API before connection (on agent selection)

    async def _preload_rag(self):
        """
        Preload RAG state using the global unified preloader.

        This delegates to rag_preloader to avoid code duplication and ensure
        consistent behavior across CLI and web interface paths.
        """
        try:
            if self.rag_state is None:
                # Notify frontend: RAG loading started
                await self.output_queue.put({"type": "rag_loading_start", "message": "Initialisation du système RAG..."})

                logger.info("🚀 Getting RAG state from unified preloader...")
                from services.rag.rag_preloader import rag_preloader

                # Get agent-specific RAG state from preloader (single source of truth)
                self.rag_state = await rag_preloader.get_rag_state_for_agent(agent_id=self.agent_id)

                # Notify frontend: RAG loading complete
                await self.output_queue.put({"type": "rag_loading_complete"})

                logger.info("✅ RAG state obtained from preloader")
        except Exception as e:
            logger.warning(f"⚠️ RAG preloading failed: {e}")

            # Notify frontend: RAG loading error
            await self.output_queue.put({"type": "rag_loading_error", "error": str(e)})

            # Create empty state with skip_retrieval=True as safe fallback
            from services.rag.rag_state import RagState

            self.rag_state = RagState()
            self.rag_state.skip_retrieval = True

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
        Process incoming audio chunk through VAD and STT.

        This implements continuous STT streaming with VAD gating:
        1. All audio goes through VAD first
        2. ALL audio is sent to STT (no gating)
        3. VAD events trigger state transitions and UI updates
        4. STT processes continuously and we filter results based on VAD
        """
        # DEBUG: Track audio chunks
        self.audio_chunks_received += 1
        if self.audio_chunks_received % 50 == 0:  # Log every 50 chunks
            logger.debug(f"🎤 Received {self.audio_chunks_received} audio chunks")

        # Process chunk through Silero VAD
        # SileroVADService.process_audio_chunk returns a list of events
        events = await self.vad_service.process_audio_chunk(chunk)

        # Check current VAD state
        is_speech = self.vad_service.triggered
        probability = self.vad_service.current_probability

        # Update telemetry
        self.turn_state.vad_energy = probability
        self.turn_state.vad_state = VADState.SPEAKING if is_speech else VADState.SILENCE
        # We don't push telemetry on every chunk to avoid flooding, only on significant changes
        # But for energy visualization we might need frequent updates.
        # Let's send it with the vad_update event which is already throttled or used for UI.

        # CRITICAL FIX: Always send audio to STT, regardless of VAD state
        # This is the main fix - STT needs continuous audio to work properly
        try:
            await self.stt_audio_queue.put(chunk)
            self.audio_chunks_sent_to_stt += 1

            if self.audio_chunks_sent_to_stt % 50 == 0:  # Log every 50 chunks
                logger.debug(f"📤 Sent {self.audio_chunks_sent_to_stt}/{self.audio_chunks_received} chunks to STT")

        except Exception as e:
            logger.error(f"❌ Failed to send audio to STT queue: {e}")

        # Handle VAD events (speech_start, speech_end) for state management
        if events:
            logger.debug(f"🎯 VAD: Received {len(events)} events: {[e['type'] for e in events]}")

        for event in events:
            event_type = event["type"]
            self.vad_events_logged.append({"type": event_type, "timestamp": time.time(), "probability": probability, "is_speech": is_speech})

            # Keep only last 10 events
            if len(self.vad_events_logged) > 10:
                self.vad_events_logged.pop(0)

            if event_type == "speech_start":
                # Speech detected - transition to recording
                if not self.is_recording:
                    self.is_recording = True
                    logger.info(f"🗣️ VAD: Speech started (prob={probability:.2f}) - Total chunks sent to STT: {self.audio_chunks_sent_to_stt}")
                    await self.push_event("vad_start")

            elif event_type == "speech_end":
                # Speech ended - stop recording
                if self.is_recording:
                    self.is_recording = False
                    logger.info(f"🤫 VAD: Speech ended (prob={probability:.2f})")
                    await self.push_event("vad_end")

        # Send VAD status to client for UI updates
        # Also include telemetry data
        self.turn_state.calculate_metrics()
        await self.output_queue.put(
            {
                "type": "vad_update",
                "energy": probability,
                "state": "speaking" if is_speech else "silence",
                "telemetry": self.turn_state.to_dict(),
            }
        )

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
                        timeout=5.0,  # 5 second timeout
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
            logger.info("🎤 Starting STT stream processing")
            transcript_count = 0

            async for transcript in self.stt_service.transcribe_streaming(audio_generator()):
                if not self.turn_state.stt_streaming_started:
                    self.turn_state.stt_streaming_started = True
                    await self._push_telemetry_update()

                transcript_count += 1
                self.last_transcript_received = transcript

                # Log transcript reception
                transcript_text = transcript.get("transcript", "")
                is_final = transcript.get("is_final", False)

                if is_final:
                    logger.info(f"📝 STT Final Transcript: '{transcript_text}'")
                else:
                    logger.debug(f"📝 STT Partial Transcript #{transcript_count}: '{transcript_text[:50]}...'")

                await self.push_event("transcript_update", transcript)

                if is_final:
                    self.turn_state.stt_streaming_ended = True
                    await self._push_telemetry_update()

                # Log every 10 transcripts
                if transcript_count % 10 == 0:
                    logger.debug(f"📊 STT Processing Stats: {transcript_count} transcripts received, {self.audio_chunks_sent_to_stt} chunks sent")

        except asyncio.CancelledError:
            logger.info("STT stream processing cancelled")
        except Exception as e:
            logger.error(f"STT stream error: {e}")
            # Don't re-raise to prevent stopping the entire event loop
            await self.push_event("error", {"service": "stt", "error": str(e)})

    async def push_event(self, event_type: str, data: Any = None):
        """Push an external event to the loop."""
        await self.event_queue.put({"type": event_type, "data": data, "timestamp": time.time()})

    async def _push_telemetry_update(self):
        """Push telemetry update to client."""
        # Calculate derived metrics before sending
        self.turn_state.calculate_metrics()

        await self.output_queue.put({"type": "telemetry_update", "data": self.turn_state.to_dict()})

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
        # Reset turn state for new turn
        self.turn_state.reset()
        self.turn_state.vad_speech_detected = True
        await self._push_telemetry_update()

        # Always attempt to interrupt pending audio on new speech
        # This handles cases where TTS finished generation (state=LISTENING)
        # but audio is still buffered/playing.
        logger.info("User speech detected - ensuring audio playback is interrupted")
        await self.push_event("interrupt")

        self.state = AgentState.LISTENING
        # Notify client
        await self.output_queue.put({"type": "speech_start"})

    async def _handle_vad_end(self):
        """Handle speech end event."""
        self.turn_state.vad_end_of_speech_detected = True
        self.turn_state.vad_end_of_speech_detected_time = time.time()
        await self._push_telemetry_update()

        # Notify client
        await self.output_queue.put({"type": "speech_end"})
        self.last_speech_end_time = time.time()

        # Check if we have enough context to trigger LLM
        if self.transcript_buffer:
            await self._trigger_llm_processing()
        else:
            # Wait for transcript to arrive (fix for first turn drop)
            logger.info("⏳ Speech ended but no transcript yet - waiting...")
            self.state = AgentState.WAITING_FOR_TRANSCRIPT

            # Start a timeout task to reset state if no transcript arrives
            asyncio.create_task(self._transcript_timeout_check())

    async def _transcript_timeout_check(self):
        """Check if we've waited too long for a transcript."""
        wait_start = time.time()
        try:
            await asyncio.sleep(2.0)  # Wait 2 seconds
            if self.state == AgentState.WAITING_FOR_TRANSCRIPT and time.time() - wait_start >= 2.0:
                logger.warning("⏰ Timeout waiting for transcript after speech end")
                self.state = AgentState.LISTENING
        except asyncio.CancelledError:
            pass

    async def _trigger_llm_processing(self):
        """Trigger the LLM processing pipeline."""
        full_text = " ".join(self.transcript_buffer)
        logger.info(f"🧠 AI Thinking... Input: '{full_text}'")

        # Clear buffer
        self.transcript_buffer = []

        # Start LLM processing
        self.state = AgentState.THINKING
        await self.output_queue.put({"type": "bot_responding_start"})

        self.llm_task = asyncio.create_task(self._process_llm_response(full_text))

    async def _handle_transcript_update(self, transcript_data: Dict[str, Any]):
        """Handle STT transcript update."""
        text = transcript_data.get("transcript", "")  # STTService returns 'transcript' key
        is_final = transcript_data.get("is_final", False)

        if not text:
            return

        # Forward to client
        await self.output_queue.put({"type": "transcript_update", "text": text, "is_final": is_final})

        if is_final:
            self.transcript_buffer.append(text)

            # If we were waiting for this transcript to trigger LLM
            if self.state == AgentState.WAITING_FOR_TRANSCRIPT:
                logger.info(f"📝 Received final transcript while waiting: '{text}'")
                await self._trigger_llm_processing()

    async def _handle_interruption(self):
        """Handle interruption logic."""
        logger.info("🛑 Handling Interruption: Stopping playback and cancelling tasks")

        # Reset state
        self.state = AgentState.LISTENING
        self.text_buffer = ""  # Clear text buffer
        self.transcript_buffer = []  # Clear any accumulated user input from previous turn

        # Cancel LLM/TTS tasks
        tasks_cancelled = 0
        if self.llm_task and not self.llm_task.done():
            self.llm_task.cancel()
            tasks_cancelled += 1
        if self.tts_task and not self.tts_task.done():
            self.tts_task.cancel()
            tasks_cancelled += 1

        logger.debug(f"Cancelled {tasks_cancelled} tasks")

        # Clear internal queues
        # Clear TTS text queue
        while not self.tts_text_queue.empty():
            try:
                self.tts_text_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Clear output queue of any pending AUDIO chunks
        # We need to be careful not to remove other important events, but for interruption
        # priority is silence.
        # Since we can't easily filter asyncio.Queue, and output_queue is consumed by
        # WebRTCMediaHandler/Websocket, sending a clear signal is safer.

        # Send explicit interrupt signal to output queue
        # This will be picked up by WebRTCMediaHandler to clear ITS audio buffer
        await self.output_queue.put({"type": "interrupt"})

        # Also send client notification
        await self.output_queue.put({"type": "bot_response_interrupted"})

    async def _process_llm_response(self, text: str):
        """Process text with LLM and feed TTS."""
        try:
            logger.debug(f"🔄 Starting LLM processing for: '{text[:50]}...'")

            self.turn_state.llm_streaming_started = False
            self.turn_state.llm_streaming_ended = False
            self.turn_state.tts_streaming_started = False
            self.turn_state.tts_streaming_ended = False
            self.turn_state.webrtc_streaming_agent_audio_response_started = False
            self.turn_state.webrtc_streaming_agent_audio_response_ended = False
            await self._push_telemetry_update()

            # Initialize RAG state if not already done
            if self.rag_state is None:
                try:
                    logger.info("🔧 Initializing RAG state via unified preloader...")
                    from services.rag.rag_preloader import rag_preloader

                    # Get agent-specific RAG state from preloader (single source of truth)
                    self.rag_state = await rag_preloader.get_rag_state_for_agent(agent_id=self.agent_id)

                    logger.info("✅ RAG state obtained from preloader")

                except Exception as e:
                    logger.error(f"⚠️ Failed to initialize RagState: {e}")
                    from services.rag.rag_state import RagState

                    self.rag_state = RagState()
                    self.rag_state.skip_retrieval = True  # Skip retrieval on failure

            # CRITICAL FIX: Add timeout and debugging
            async def process_with_timeout():
                # Start TTS task
                self.tts_task = asyncio.create_task(self._process_tts_stream())

                response_count = 0
                last_chunk_time = time.time()

                try:
                    async for response_chunk in self.chatbot_service.process_chat_message(
                        text,
                        self.conversation_id,
                        rag_state=self.rag_state,
                        agent_id=self.agent_id,
                        session_id=self.session_id,
                    ):
                        # Reset inactivity timer on each chunk
                        last_chunk_time = time.time()
                        response_count += 1
                        logger.debug(f"📨 Received response chunk #{response_count}: {response_chunk.get('type')}")

                        chunk_type = response_chunk.get("type")
                        content = response_chunk.get("content", "")

                        if content:
                            logger.debug(f"📝 Content: '{content[:30]}...'")

                        if chunk_type in ["first_token", "chunk"]:
                            if not self.turn_state.llm_streaming_started:
                                self.turn_state.llm_streaming_started = True
                                await self._push_telemetry_update()

                            if content:
                                # Apply buffering logic before sending to TTS
                                self.text_buffer += content

                                # Process buffer based on configured level
                                self.text_buffer = await self._process_buffer_by_level(self.text_buffer)

                                # Also notify client of text (always send raw text to UI immediately)
                                await self.output_queue.put({"type": "assistant_response", "text": content, "is_complete": False})
                        elif chunk_type == "complete":
                            logger.info("✅ Chatbot response complete")

                            self.turn_state.llm_streaming_ended = True
                            await self._push_telemetry_update()

                            # Send remaining buffer
                            if self.text_buffer:
                                await self.tts_text_queue.put(self.text_buffer)
                                self.text_buffer = ""

                            await self.tts_text_queue.put(None)  # End of stream
                            await self.output_queue.put({"type": "assistant_response", "text": "", "is_complete": True})
                            break
                        elif chunk_type == "error":
                            logger.error(f"❌ Chatbot error: {content}")
                            await self.tts_text_queue.put(None)
                            break

                        # Safety: Check for inactivity timeout (10 seconds without new chunks)
                        current_time = time.time()
                        if current_time - last_chunk_time > 10.0:
                            logger.warning("⚠️ LLM stream inactive for 10+ seconds, stopping")
                            await self.output_queue.put({"type": "error", "message": "Response stream stalled - please try again"})
                            await self.tts_text_queue.put(None)
                            break

                except asyncio.TimeoutError:
                    logger.error("⏰ LLM stream inactivity timeout (10s) - stopping")
                    await self.output_queue.put({"type": "error", "message": "Response timeout - please try again"})
                    await self.tts_text_queue.put(None)

                logger.info(f"✅ LLM processing completed: {response_count} chunks received")
                return response_count

            # Add timeout to prevent hanging
            try:
                result = await asyncio.wait_for(process_with_timeout(), timeout=30.0)
                logger.info(f"🎉 LLM processing successful: {result} chunks")
            except asyncio.TimeoutError:
                logger.error("⏰ LLM processing timeout (30s) - stopping TTS")
                await self.output_queue.put({"type": "error", "message": "Response timeout - please try again"})
                await self.tts_text_queue.put(None)

        except asyncio.CancelledError:
            logger.info("LLM processing cancelled")
            await self.tts_text_queue.put(None)
        except Exception as e:
            logger.error(f"❌ LLM processing error: {e}")
            import traceback

            traceback.print_exc()
            await self.output_queue.put({"type": "error", "message": f"Processing error: {str(e)}"})
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
            async for audio_chunk in shared_streaming_manager.stream_text_to_audio_no_websocket(text_generator(), self.tts_service, self.conversation_id):
                if not self.turn_state.tts_streaming_started:
                    self.turn_state.tts_streaming_started = True
                    await self._push_telemetry_update()

                await self.push_event("tts_chunk", audio_chunk)

            self.turn_state.tts_streaming_ended = True
            await self._push_telemetry_update()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"TTS streaming error: {e}")
        finally:
            self.state = AgentState.LISTENING  # Back to listening after TTS
            await self.output_queue.put({"type": "audio_stream_end"})
            await self.output_queue.put({"type": "bot_responding_end"})

    async def _handle_llm_token(self, token: str):
        """Handle LLM token generation (Unused if using direct queue)."""
        pass

    async def _handle_tts_chunk(self, audio_chunk: bytes):
        """Handle TTS audio chunk."""
        self.state = AgentState.SPEAKING

        if not self.turn_state.webrtc_streaming_agent_audio_response_started:
            self.turn_state.webrtc_streaming_agent_audio_response_started = True
            self.turn_state.webrtc_streaming_agent_audio_response_started_time = time.time()
            # Calculate metrics now that we have the start time
            self.turn_state.calculate_metrics()
            await self._push_telemetry_update()

        # Send audio to client
        await self.output_queue.put({"type": "audio_chunk", "data": audio_chunk})

    async def _process_buffer_by_level(self, text_buffer: str) -> str:
        """
        Process text buffer based on buffering level and send complete chunks to TTS.

        Returns:
            Updated text buffer (containing remaining text)
        """
        if self.buffering_level == "NONE":
            # Send everything immediately
            if text_buffer:
                await self.tts_text_queue.put(text_buffer)
                return ""

        elif self.buffering_level == "LOW":
            # Buffer until word completion (space)
            if text_buffer.endswith(" "):
                # Send the complete word to TTS
                await self.tts_text_queue.put(text_buffer)
                return ""
            elif " " in text_buffer:
                # If there's a space in the buffer, split and send complete words
                parts = text_buffer.rsplit(" ", 1)
                if len(parts) > 1:
                    # Send all complete words (everything before the last space)
                    await self.tts_text_queue.put(parts[0] + " ")
                    # Keep the last incomplete word in buffer
                    return parts[1]

        elif self.buffering_level == "MEDIUM":
            # Buffer until 4 words OR punctuation
            words = text_buffer.split()
            if len(words) >= 4:
                # Send first 4 words
                # Find the position of the 4th space to split correctly
                split_pos = 0
                space_count = 0
                for i, char in enumerate(text_buffer):
                    if char == " ":
                        space_count += 1
                        if space_count == 4:
                            split_pos = i + 1
                            break

                if split_pos > 0:
                    text_to_send = text_buffer[:split_pos]
                    await self.tts_text_queue.put(text_to_send)
                    return text_buffer[split_pos:]

            # Check for punctuation
            for char in self.punctuation_chars:
                if char in text_buffer:
                    # Find the last punctuation position
                    last_punct_pos = max(text_buffer.rfind(char) for char in self.punctuation_chars)
                    if last_punct_pos != -1:
                        # Send up to and including punctuation
                        text_to_send = text_buffer[: last_punct_pos + 1]
                        await self.tts_text_queue.put(text_to_send)
                        # Keep text after punctuation
                        return text_buffer[last_punct_pos + 1 :]

        elif self.buffering_level == "HIGH":
            # Buffer until punctuation
            for char in self.punctuation_chars:
                if char in text_buffer:
                    # Find the last punctuation position
                    last_punct_pos = max(text_buffer.rfind(char) for char in self.punctuation_chars)
                    if last_punct_pos != -1:
                        # Send up to and including punctuation
                        text_to_send = text_buffer[: last_punct_pos + 1]
                        await self.tts_text_queue.put(text_to_send)
                        # Keep text after punctuation
                        return text_buffer[last_punct_pos + 1 :]

        # If no condition met, return the buffer unchanged
        return text_buffer
