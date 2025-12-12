"""
Language Model Service Module with Agent Support
"""

import logging
from typing import AsyncIterator, Optional
from uuid import UUID

from ..agents_admin.agent_manager import get_agent_manager
from .providers import (
    create_groq_provider,
    create_llama_cpp_provider,
    create_mistral_provider,
    create_openrouter_provider,
)

logger = logging.getLogger(__name__)


class LLMService:
    """Service for handling Language Model operations with agent support"""

    def __init__(self, agent_id: Optional[UUID] = None, session_id: Optional[str] = None):
        """
        Initialize LLM Service with agent support.

        Args:
            agent_id: Specific agent ID to use (if None, uses default agent)
            session_id: Session ID for agent resolution
        """
        self.agent_manager = get_agent_manager()
        self.agent_id = agent_id
        self.session_id = session_id
        self.agent_config = None
        self.provider = self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the appropriate LLM provider based on agent configuration"""
        # Get agent configuration
        agent_config = None

        if self.session_id:
            try:
                # Verify if session_id is a valid UUID before querying
                UUID(self.session_id)
                agent_config = self.agent_manager.get_session_agent(self.session_id)
            except (ValueError, Exception) as e:
                logger.warning(f"Invalid session_id '{self.session_id}', falling back to agent_id: {e}")

        if not agent_config and self.agent_id:
            agent_config = self.agent_manager.get_agent_config(self.agent_id)

        if not agent_config:
            agent_config = self.agent_manager.get_agent_config()

        # Store agent configuration for later use (e.g., system prompt)
        self.agent_config = agent_config

        provider_name = agent_config.llm_provider
        provider_config = agent_config.llm_config

        logger.debug(f"Initializing LLM provider: {provider_name} with agent configuration")
        logger.debug(f"🔍 LLM provider config for {provider_name}: {provider_config}")

        # Initialize provider - mapping is now handled within each provider
        if provider_name == "groq.com":
            return create_groq_provider(provider_config)
        elif provider_name == "mistral.ai":
            return create_mistral_provider(provider_config)
        elif provider_name == "openrouter.ai":
            return create_openrouter_provider(provider_config)
        elif provider_name == "llama-cpp.local":
            return create_llama_cpp_provider(provider_config)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text using the configured LLM provider

        Args:
            prompt: Input text prompt
            **kwargs: Additional parameters for the provider

        Returns:
            str: Generated text
        """
        return await self.provider.generate(prompt, **kwargs)

    async def generate_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """
        Stream text generation using the configured LLM provider

        Args:
            prompt: Input text prompt
            **kwargs: Additional parameters for the provider

        Yields:
            str: Generated text chunks
        """
        async for chunk in self.provider.generate_stream(prompt, **kwargs):
            yield chunk

    async def close(self):
        """Close the provider session"""
        if hasattr(self.provider, "close"):
            await self.provider.close()
