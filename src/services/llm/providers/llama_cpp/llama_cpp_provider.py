"""
Llama.cpp Local LLM Provider Adapter

This module provides an implementation for the local llama.cpp LLM provider,
which uses an OpenAI-compatible API format.
"""

import os
import asyncio
import aiohttp
import json
from typing import AsyncIterator, Optional, Dict, Any
from ..openai_compatible_provider import OpenAICompatibleProvider
from services.provider_constants import get_provider_constants


class LlamaCppProvider(OpenAICompatibleProvider):
    """
    Llama.cpp local LLM provider implementation using OpenAI-compatible API
    
    Llama.cpp provides an OpenAI-compatible API with the following endpoints:
    - Base URL: http://llama-cpp:8002 (default)
    - Chat completions: /v1/chat/completions
    - Authentication: None required for local server
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
    
    def _validate_config(self):
        """Validate that required configuration is present (API key is optional for local server)."""
        # Use immutable constants - these values are fixed and not configurable
        constants = get_provider_constants()
        api_url = constants['llm']['llama-cpp.local']['API_URL']
        completions_path = constants['llm']['llama-cpp.local']['COMPLETIONS_PATH']
        if not api_url:
            raise ValueError(f"{self.__class__.__name__}: API URL is required")
        if not completions_path:
            raise ValueError(f"{self.__class__.__name__}: completions path is required")
        # API key remains optional for local llama.cpp server
    
    def _get_api_url(self) -> str:
        """Get the full API URL for llama.cpp completions using immutable constants."""
        constants = get_provider_constants()
        base_url = constants['llm']['llama-cpp.local']['API_URL']
        completions_path = constants['llm']['llama-cpp.local']['COMPLETIONS_PATH']

        if base_url.endswith('/'):
            base_url = base_url[:-1]
        if completions_path.startswith('/'):
            completions_path = completions_path[1:]

        return f"{base_url}/{completions_path}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for llama.cpp API requests"""
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add API key if provided (optional for local server)
        if self.config.get("api_key"):
            headers["Authorization"] = f"Bearer {self.config['api_key']}"
            
        return headers

    @classmethod
    def get_expected_properties(cls) -> list:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return ["model"]

    @classmethod
    def get_field_definitions(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get the field definitions for this provider.
        
        Returns:
            Dictionary mapping field names to field metadata
        """
        return {
            "model": {
                "type": "text",
                "label": "Model",
                "required": True,
                "description": "Llama.cpp model name (e.g., llama-2-7b-chat, codellama-34b-instruct)"
            }
        }


def create_llama_cpp_provider(config: Optional[Dict[str, Any]] = None) -> LlamaCppProvider:
    """Factory function to create llama.cpp provider"""
    return LlamaCppProvider(config)