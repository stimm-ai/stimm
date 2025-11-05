"""
Shared Streaming Module

This module provides centralized logic for parallel live streaming that can be used
by both TTS and voicebot interfaces. It encapsulates the core streaming patterns
that enable true parallel live streaming with progress tracking.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import AsyncGenerator, Callable, Optional, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class StreamingSession:
    """Represents a streaming session with progress tracking and state management."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.is_streaming = False
        self.is_playing = False
        self.start_time = None
        self.text_chunks_sent = 0
        self.audio_chunks_received = 0
        self.total_text_chunks = 0
        self.stream_completed = False
        
        # Progress tracking
        self.llm_progress = 0.0  # 0.0 to 1.0
        self.tts_progress = 0.0  # 0.0 to 1.0
        
        # Latency tracking
        self.first_chunk_time = None
        self.playback_start_time = None


class SharedStreamingManager:
    """
    Centralized manager for parallel live streaming operations.
    
    This class encapsulates the streaming logic that enables:
    - True parallel streaming (TTS receiving starts before LLM sending finishes)
    - Real-time audio playback before streaming completes
    - Progress tracking for both LLM and TTS operations
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, StreamingSession] = {}
    
    def create_session(self, session_id: str) -> StreamingSession:
        """Create a new streaming session."""
        session = StreamingSession(session_id)
        self.active_sessions[session_id] = session
        logger.info(f"Created streaming session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[StreamingSession]:
        """Get an existing streaming session."""
        return self.active_sessions.get(session_id)
    
    def end_session(self, session_id: str):
        """End a streaming session."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info(f"Ended streaming session: {session_id}")
    
    async def stream_text_to_audio(
        self,
        websocket: WebSocket,
        text_generator: AsyncGenerator[str, None],
        tts_service,
        session_id: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Core streaming method that enables parallel live streaming.
        
        This method implements the pattern where:
        1. Text chunks are sent to TTS service
        2. Audio chunks are received and sent back in parallel
        3. Progress is tracked for both operations
        4. Audio playback can start before streaming completes
        """
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)
        
        session.is_streaming = True
        session.start_time = asyncio.get_event_loop().time()
        
        # Configuration pour l'enregistrement des chunks
        record_chunks = os.getenv('TTS_RECORD_CHUNKS', 'false').lower() == 'true'
        chunks_dir = os.getenv('TTS_CHUNKS_DIR', '/tmp/tts_chunks_web')
        
        # Créer le dossier d'enregistrement si activé
        if record_chunks:
            os.makedirs(chunks_dir, exist_ok=True)
            # Vider le dossier existant pour un nouvel enregistrement
            for file in os.listdir(chunks_dir):
                file_path = os.path.join(chunks_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            logger.info(f"📁 Enregistrement des chunks audio activé dans: {chunks_dir}")
        
        try:
            # Process synthesis using streaming (like TTS interface)
            audio_chunk_count = 0
            
            async for audio_chunk in tts_service.stream_synthesis(text_generator):
                audio_chunk_count += 1
                session.audio_chunks_received = audio_chunk_count
                
                # Update TTS progress
                if session.total_text_chunks > 0:
                    session.tts_progress = min(1.0, audio_chunk_count / session.total_text_chunks)
                
                # Track first audio chunk latency
                if audio_chunk_count == 1 and session.first_chunk_time is None:
                    session.first_chunk_time = asyncio.get_event_loop().time()
                    first_chunk_latency = (session.first_chunk_time - session.start_time) * 1000
                    logger.info(f"First audio chunk received after {first_chunk_latency:.2f}ms")
                
                logger.info(f"Sending audio chunk {audio_chunk_count}: {len(audio_chunk)} bytes")
                
                # Enregistrer le chunk audio si activé
                if record_chunks:
                    chunk_filename = os.path.join(chunks_dir, f"chunk_{audio_chunk_count:03d}.wav")
                    with open(chunk_filename, 'wb') as f:
                        f.write(audio_chunk)
                    logger.info(f"💾 Chunk audio enregistré: {chunk_filename} ({len(audio_chunk)} bytes)")
                
                # Send audio data as binary (like TTS interface) if websocket is provided
                if websocket:
                    await websocket.send_bytes(audio_chunk)
                yield audio_chunk
            
            logger.info(f"Stream completed: {audio_chunk_count} audio chunks sent")
            
        except Exception as e:
            logger.error(f"Streaming error in session {session_id}: {e}")
            raise
        finally:
            session.is_streaming = False
    
    async def stream_text_to_audio_no_websocket(
        self,
        text_generator: AsyncGenerator[str, None],
        tts_service,
        session_id: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Streaming method for cases where WebSocket sending is handled externally.
        
        This is used by services like voicebot that need to handle WebSocket
        sending manually with additional logic (like interruption detection).
        """
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)
        
        session.is_streaming = True
        session.start_time = asyncio.get_event_loop().time()
        
        # Configuration pour l'enregistrement des chunks
        record_chunks = os.getenv('TTS_RECORD_CHUNKS', 'false').lower() == 'true'
        chunks_dir = os.getenv('TTS_CHUNKS_DIR', '/tmp/tts_chunks_web')
        
        # Créer le dossier d'enregistrement si activé
        if record_chunks:
            os.makedirs(chunks_dir, exist_ok=True)
            # Vider le dossier existant pour un nouvel enregistrement
            for file in os.listdir(chunks_dir):
                file_path = os.path.join(chunks_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            logger.info(f"📁 Enregistrement des chunks audio activé dans: {chunks_dir}")
        
        try:
            # Process synthesis using streaming (like TTS interface)
            audio_chunk_count = 0
            
            async for audio_chunk in tts_service.stream_synthesis(text_generator):
                audio_chunk_count += 1
                session.audio_chunks_received = audio_chunk_count
                
                # Update TTS progress
                if session.total_text_chunks > 0:
                    session.tts_progress = min(1.0, audio_chunk_count / session.total_text_chunks)
                
                # Track first audio chunk latency
                if audio_chunk_count == 1 and session.first_chunk_time is None:
                    session.first_chunk_time = asyncio.get_event_loop().time()
                    first_chunk_latency = (session.first_chunk_time - session.start_time) * 1000
                    logger.info(f"First audio chunk received after {first_chunk_latency:.2f}ms")
                
                logger.info(f"Generated audio chunk {audio_chunk_count}: {len(audio_chunk)} bytes")
                
                # Enregistrer le chunk audio si activé
                if record_chunks:
                    chunk_filename = os.path.join(chunks_dir, f"chunk_{audio_chunk_count:03d}.wav")
                    with open(chunk_filename, 'wb') as f:
                        f.write(audio_chunk)
                    logger.info(f"💾 Chunk audio enregistré: {chunk_filename} ({len(audio_chunk)} bytes)")
                
                yield audio_chunk
            
            logger.info(f"Stream completed: {audio_chunk_count} audio chunks generated")
            
        except Exception as e:
            logger.error(f"Streaming error in session {session_id}: {e}")
            raise
        finally:
            session.is_streaming = False
    
    async def create_text_generator(
        self,
        websocket: WebSocket,
        text_source: AsyncGenerator[str, None],
        session_id: str,
        on_text_chunk: Optional[Callable] = None
    ) -> AsyncGenerator[str, None]:
        """
        Create a text generator that tracks LLM sending progress.
        
        This generator:
        - Yields standardized JSON text chunks to providers
        - Tracks LLM sending progress
        - Allows for custom processing of text chunks
        """
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)
        
        text_chunk_count = 0
        
        async for text_chunk in text_source:
            text_chunk_count += 1
            session.text_chunks_sent = text_chunk_count
            
            # Update LLM progress
            if session.total_text_chunks > 0:
                session.llm_progress = min(1.0, text_chunk_count / session.total_text_chunks)
            
            # Create standardized JSON payload for providers
            standard_payload = {
                "text": text_chunk,
                "try_trigger_generation": True,
                "flush": False  # More text is coming
            }
            json_payload = json.dumps(standard_payload)
            
            logger.info(f"Sending text chunk {text_chunk_count}: '{text_chunk.strip()}'")
            
            # Allow custom processing
            if on_text_chunk:
                await on_text_chunk(text_chunk, text_chunk_count)
            
            yield json_payload
        
        # Signal end of stream with final JSON payload
        final_payload = {
            "text": "",  # Empty string to indicate end
            "try_trigger_generation": True,
            "flush": True  # Flush the buffer - this is the final chunk
        }
        yield json.dumps(final_payload)
        
        logger.info(f"Text streaming completed: {text_chunk_count} chunks sent")
    
    def update_progress(self, session_id: str, llm_progress: Optional[float] = None, tts_progress: Optional[float] = None):
        """Update progress for a streaming session."""
        session = self.get_session(session_id)
        if session:
            if llm_progress is not None:
                session.llm_progress = llm_progress
            if tts_progress is not None:
                session.tts_progress = tts_progress
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Get the current status of a streaming session."""
        session = self.get_session(session_id)
        if session:
            return {
                "session_id": session_id,
                "is_streaming": session.is_streaming,
                "is_playing": session.is_playing,
                "text_chunks_sent": session.text_chunks_sent,
                "audio_chunks_received": session.audio_chunks_received,
                "llm_progress": session.llm_progress,
                "tts_progress": session.tts_progress,
                "stream_completed": session.stream_completed,
                "first_chunk_time": session.first_chunk_time,
                "playback_start_time": session.playback_start_time,
            }
        return {}


# Global instance for shared usage
shared_streaming_manager = SharedStreamingManager()