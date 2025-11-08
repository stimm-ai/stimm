"""
Speech-to-Text Service Module
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from .providers.whisper_local import WhisperLocalProvider
from .providers.deepgram_provider import DeepgramProvider
from services.agent.agent_manager import get_agent_manager

logger = logging.getLogger(__name__)


class STTService:
    """Service for handling Speech-to-Text operations"""

    def __init__(self, agent_id: Optional[str] = None, session_id: Optional[str] = None):
        self.agent_id = agent_id
        self.session_id = session_id
        self.provider = None
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the configured STT provider"""
        # Always use agent-based configuration
        agent_manager = get_agent_manager()
        if self.session_id:
            agent_config = agent_manager.get_session_agent(self.session_id)
        elif self.agent_id:
            agent_config = agent_manager.get_agent_config(self.agent_id)
        else:
            agent_config = agent_manager.get_agent_config()
            
        provider_name = agent_config.stt_provider
        provider_config = agent_config.stt_config
        logger.info(f"Initialized STT provider from agent configuration: {provider_name}")
        
        if provider_name == "whisper.local":
            self.provider = WhisperLocalProvider(provider_config)
        elif provider_name == "deepgram.com":
            self.provider = DeepgramProvider(provider_config)
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