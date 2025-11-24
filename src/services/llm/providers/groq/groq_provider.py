"""
Groq.com LLM Provider Adapter
"""

import os
import asyncio
import aiohttp
import json
from typing import AsyncIterator, Optional, Dict, Any
from ..openai_compatible_provider import OpenAICompatibleProvider
from services.provider_constants import get_provider_constants


class GroqProvider(OpenAICompatibleProvider):
    """Groq.com LLM provider implementation using OpenAI-compatible API"""
    
    def __init__(self, config: Dict[str, Any]):
        # Apply provider-specific mapping before initializing
        mapped_config = self.to_provider_format(config)
        super().__init__(mapped_config)
    
    @classmethod
    def get_expected_properties(cls) -> list:
        """Get the list of expected properties for Groq provider."""
        return ["model", "api_key"]

    @classmethod
    def get_field_definitions(cls) -> dict:
        """Get field definitions for Groq provider."""
        return {
            "model": {
                "type": "text",
                "label": "Model",
                "required": True,
                "description": "Model name (e.g., llama-3.1-8b-instant)"
            },
            "api_key": {
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Groq API key"
            }
        }
    
    @classmethod
    def to_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert standardized frontend config to provider-specific format.
        
        Groq uses standard field names, so no mapping needed.
        """
        return config.copy()
    
    @classmethod
    def from_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert provider-specific config to standardized frontend format.
        
        Groq uses standard field names, so no mapping needed.
        """
        return config.copy()
    
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