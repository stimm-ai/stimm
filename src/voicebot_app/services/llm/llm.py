"""
Language Model Service Module
"""

import asyncio
from typing import AsyncIterator
from .config import llm_config
from .providers import create_groq_provider, create_mistral_provider, create_openrouter_provider, create_llama_cpp_provider


class LLMService:
    """Service for handling Language Model operations"""

    def __init__(self):
        self.config = llm_config
        self.provider = self._initialize_provider()

    def _initialize_provider(self):
        """Initialize the appropriate LLM provider based on configuration"""
        provider_name = self.config.get_provider()
        
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