"""
Speech-to-Text Service Module
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from .config import stt_config
from .providers.whisper_local import WhisperLocalProvider
from .providers.deepgram_provider import DeepgramProvider

logger = logging.getLogger(__name__)


class STTService:
    """Service for handling Speech-to-Text operations"""

    def __init__(self):
        self.config = stt_config
        self.provider = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the configured STT provider"""
        provider_name = self.config.get_provider()
        
        if provider_name == "whisper.local":
            self.provider = WhisperLocalProvider()
            logger.info(f"Initialized STT provider: {provider_name}")
        elif provider_name == "deepgram.com":
            self.provider = DeepgramProvider()
            logger.info(f"Initialized STT provider: {provider_name}")
        else:
            raise ValueError(f"Unsupported STT provider: {provider_name}")



    async def transcribe_streaming(
        self,
        audio_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Transcribe from a streaming audio generator

        Args:
            audio_generator: Async generator yielding audio chunks

        Yields:
            Transcription results
        """
        if not self.provider:
            raise RuntimeError("STT provider not initialized")

        try:
            # Use the provider's streaming method
            async for transcript in self.provider.stream_audio_chunks(audio_generator):
                yield transcript
                    
        except Exception as e:
            logger.error(f"Streaming transcription failed: {e}")
            raise