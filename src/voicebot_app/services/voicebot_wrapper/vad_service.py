"""
Backend VAD service using Silero VAD for real-time voice activity detection.

This service replaces the previous WebRTC VAD implementation with Silero VAD
for superior noise immunity and accuracy.
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional
import numpy as np

# Import Silero service
from services.vad.silero_service import SileroVADService

logger = logging.getLogger(__name__)

class VADProcessor:
    """
    Higher-level VAD processor that integrates Silero VAD with the voicebot pipeline.
    """
    
    def __init__(self, threshold: float = 0.5):
        self.vad_service = SileroVADService(threshold=threshold)
        self.active = False
        
    async def start_vad_processing(
        self, 
        conversation_id: str,
        audio_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start VAD processing for a conversation using Silero VAD.
        
        Args:
            conversation_id: Unique conversation identifier
            audio_generator: Async generator yielding audio chunks
            
        Yields:
            VAD results with conversation context
        """
        self.active = True
        logger.info(f"Starting Silero VAD processing for conversation: {conversation_id}")
        
        # Reset VAD state for new conversation
        self.vad_service.reset()
        
        chunk_count = 0
        
        try:
            async for audio_chunk in audio_generator:
                if not self.active:
                    break
                
                chunk_count += 1
                
                # Process chunk through Silero VAD
                # SileroVADService handles buffering internally
                events = self.vad_service.process_audio_chunk(audio_chunk)
                
                # Get current state
                is_triggered = self.vad_service.triggered
                probability = self.vad_service.current_probability
                
                # Prepare VAD result matching the expected interface
                # We map Silero's 'triggered' state to 'is_voice_active'
                vad_result = {
                    "type": "vad_result",
                    "conversation_id": conversation_id,
                    "is_voice": probability > 0.5, # Instantaneous voice detection
                    "is_voice_active": is_triggered, # Hysteresis-filtered state
                    "voice_probability": float(probability),
                    "timestamp": chunk_count * 0.032, # Approx timestamp (assuming 512 samples @ 16k = 32ms)
                    "events": events # Pass through raw events if needed
                }
                
                yield vad_result
                
        except asyncio.CancelledError:
            logger.info(f"VAD processing cancelled for conversation: {conversation_id}")
        except Exception as e:
            logger.error(f"Error in VAD stream processing: {e}")
            raise
        finally:
            logger.info(f"VAD processing stopped for conversation: {conversation_id}")
    
    def stop_vad_processing(self):
        """Stop VAD processing."""
        self.active = False
        logger.info("VAD processing stopped")

# Global VAD processor instance
vad_processor = VADProcessor(threshold=0.5)