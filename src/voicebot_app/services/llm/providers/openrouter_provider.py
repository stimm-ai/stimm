"""
OpenRouter.ai LLM Provider Adapter

This module provides an implementation for the OpenRouter.ai LLM provider,
which uses an OpenAI-compatible API format with additional headers for tracking.

OpenRouter.ai API documentation: https://openrouter.ai/docs/api-reference/overview
"""

import os
import asyncio
import aiohttp
import json
from typing import AsyncIterator, Optional, Dict, Any
from ..config import llm_config
from .openai_compatible_provider import OpenAICompatibleProvider
from services.provider_constants import get_provider_constants


class OpenRouterProvider(OpenAICompatibleProvider):
    """
    OpenRouter.ai LLM provider implementation using OpenAI-compatible API
    
    OpenRouter.ai provides an OpenAI-compatible API with the following endpoints:
    - Base URL: https://openrouter.ai/api/v1
    - Chat completions: /chat/completions
    - Authentication: Bearer token in Authorization header
    - Additional headers: X-Title, HTTP-Referer for tracking
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = llm_config.get_openrouter_config()
        super().__init__(config)
    
    def _get_api_url(self) -> str:
        """Get the full API URL for OpenRouter.ai completions using immutable constants."""
        constants = get_provider_constants()
        base_url = constants['llm']['openrouter.ai']['API_URL']
        completions_path = constants['llm']['openrouter.ai']['COMPLETIONS_PATH']

        if base_url.endswith('/'):
            base_url = base_url[:-1]
        if completions_path.startswith('/'):
            completions_path = completions_path[1:]

        return f"{base_url}/{completions_path}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for OpenRouter.ai API requests"""
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }
        
        # Add OpenRouter.ai specific headers for tracking
        if self.config.get("app_name"):
            headers["X-Title"] = self.config["app_name"]
        
        if self.config.get("app_url"):
            headers["HTTP-Referer"] = self.config["app_url"]
        
        return headers


def create_openrouter_provider(config: Optional[Dict[str, Any]] = None) -> OpenRouterProvider:
    """Factory function to create OpenRouter.ai provider"""
    return OpenRouterProvider(config)