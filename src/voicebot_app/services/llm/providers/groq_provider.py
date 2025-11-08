"""
Groq.com LLM Provider Adapter
"""

import os
import asyncio
import aiohttp
import json
from typing import AsyncIterator, Optional, Dict, Any
from .openai_compatible_provider import OpenAICompatibleProvider
from services.provider_constants import get_provider_constants


class GroqProvider(OpenAICompatibleProvider):
    """Groq.com LLM provider implementation using OpenAI-compatible API"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
    
    def _get_api_url(self) -> str:
        """Get the full API URL using immutable constants."""
        constants = get_provider_constants()
        base_url = constants['llm']['groq.com']['API_URL']
        completions_path = constants['llm']['groq.com']['COMPLETIONS_PATH']
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        if completions_path.startswith('/'):
            completions_path = completions_path[1:]
        return f"{base_url}/{completions_path}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests"""
        return {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }


def create_groq_provider(config: Optional[Dict[str, Any]] = None) -> GroqProvider:
    """Factory function to create Groq provider"""
    return GroqProvider(config)