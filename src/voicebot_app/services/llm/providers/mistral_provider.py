"""
Mistral.ai LLM Provider Adapter

This module provides an implementation for the Mistral.ai LLM provider,
which uses an OpenAI-compatible API format.
"""

import os
import asyncio
import aiohttp
import json
from typing import AsyncIterator, Optional, Dict, Any
from ..config import llm_config
from .openai_compatible_provider import OpenAICompatibleProvider
from services.provider_constants import MistralLLMConstants


class MistralProvider(OpenAICompatibleProvider):
    """
    Mistral.ai LLM provider implementation using OpenAI-compatible API
    
    Mistral.ai provides an OpenAI-compatible API with the following endpoints:
    - Base URL: https://api.mistral.ai/v1
    - Chat completions: /chat/completions
    - Authentication: Bearer token in Authorization header
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = llm_config.get_mistral_config()
        super().__init__(config)
    
    def _get_api_url(self) -> str:
        """Get the full API URL for Mistral.ai completions using immutable constants."""
        base_url = MistralLLMConstants.API_URL
        completions_path = MistralLLMConstants.COMPLETIONS_PATH

        if base_url.endswith('/'):
            base_url = base_url[:-1]
        if completions_path.startswith('/'):
            completions_path = completions_path[1:]

        return f"{base_url}/{completions_path}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Mistral.ai API requests"""
        return {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }


def create_mistral_provider(config: Optional[Dict[str, Any]] = None) -> MistralProvider:
    """Factory function to create Mistral.ai provider"""
    return MistralProvider(config)