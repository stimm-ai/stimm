"""
Text-to-Speech Service Module with provider-based streaming support.
"""

import logging
from typing import AsyncGenerator, Optional

from services.agents_admin.agent_manager import get_agent_manager

from .providers.async_ai.async_ai_provider import AsyncAIProvider
from .providers.deepgram.deepgram_provider import DeepgramProvider
from .providers.elevenlabs.elevenlabs_provider import ElevenLabsProvider
from .providers.hume.hume_provider import HumeProvider
from .providers.kokoro_local.kokoro_local_provider import KokoroLocalProvider

logger = logging.getLogger(__name__)


class TTSService:
    """Service for handling Text-to-Speech operations"""

    def __init__(self, agent_id: Optional[str] = None, session_id: Optional[str] = None):
        self.agent_id = agent_id
        self.session_id = session_id
        self.provider = None
        self._initialize_provider()

    def _initialize_provider(self):
        # Always use agent-based configuration
        agent_manager = get_agent_manager()
        if self.agent_id:
            agent_config = agent_manager.get_agent_config(self.agent_id)
        elif self.session_id:
            agent_config = agent_manager.get_session_agent(self.session_id)
        else:
            agent_config = agent_manager.get_agent_config()

        provider_name = agent_config.tts_provider
        provider_config = agent_config.tts_config

        logger.info(f"Initializing TTS provider from agent configuration: {provider_name}")
        logger.info(f"🔍 TTS provider config for {provider_name}: {provider_config}")

        try:
            # Initialize providers - mapping is now handled within each provider
            if provider_name == "async.ai":
                self.provider = AsyncAIProvider(provider_config)
            elif provider_name == "kokoro.local":
                self.provider = KokoroLocalProvider(provider_config)
            elif provider_name == "deepgram.com":
                self.provider = DeepgramProvider(provider_config)
            elif provider_name == "elevenlabs.io":
                self.provider = ElevenLabsProvider(provider_config)
            elif provider_name == "hume.ai":
                self.provider = HumeProvider(provider_config)
            else:
                raise ValueError(f"Unsupported TTS provider: {provider_name}")

            logger.info(f"TTS provider initialized: {type(self.provider).__name__}")
        except Exception as e:
            logger.error(f"Failed to initialize TTS provider '{provider_name}': {e}")
            raise

    async def stream_synthesis(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[bytes, None]:
        """Stream synthesis using the configured provider."""
        if not self.provider:
            raise RuntimeError("TTS provider not initialized")

        # Delegate to the provider's stream_synthesis method
        async for audio_chunk in self.provider.stream_synthesis(text_generator):
            yield audio_chunk
