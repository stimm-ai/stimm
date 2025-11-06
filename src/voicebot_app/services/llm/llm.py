"""
Language Model Service Module with Agent Support
"""

import asyncio
import logging
from typing import AsyncIterator, Optional
from uuid import UUID

from .config import llm_config
from .providers import create_groq_provider, create_mistral_provider, create_openrouter_provider, create_llama_cpp_provider
from ..agent.agent_manager import get_agent_manager
from ..agent.models import AgentConfig

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
        self.provider = self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the appropriate LLM provider based on agent configuration"""
        try:
            # Get agent configuration
            if self.session_id:
                agent_config = self.agent_manager.get_session_agent(self.session_id)
            elif self.agent_id:
                agent_config = self.agent_manager.get_agent_config(self.agent_id)
            else:
                agent_config = self.agent_manager.get_agent_config()
            
            provider_name = agent_config.llm_provider
            provider_config = agent_config.llm_config
            
            logger.info(f"Initializing LLM provider: {provider_name} with agent configuration")
            
            # Initialize provider with agent configuration
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
                
        except Exception as e:
            logger.warning(f"Failed to initialize LLM provider with agent configuration: {e}")
            logger.info("Falling back to environment variable configuration")
            
            # Fallback to environment variable configuration
            provider_name = llm_config.get_provider()
            
            if provider_name == "groq.com":
                return create_groq_provider()
            elif provider_name == "mistral.ai":
                return create_mistral_provider()
            elif provider_name == "openrouter.ai":
                return create_openrouter_provider()
            elif provider_name == "llama-cpp.local":
                return create_llama_cpp_provider()
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
        if hasattr(self.provider, 'close'):
            await self.provider.close()