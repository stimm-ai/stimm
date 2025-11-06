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
from ..config import llm_config
from .openai_compatible_provider import OpenAICompatibleProvider


class LlamaCppProvider(OpenAICompatibleProvider):
    """
    Llama.cpp local LLM provider implementation using OpenAI-compatible API
    
    Llama.cpp provides an OpenAI-compatible API with the following endpoints:
    - Base URL: http://llama-cpp:8002 (default)
    - Chat completions: /v1/chat/completions
    - Authentication: None required for local server
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = llm_config.get_llama_cpp_config()
        super().__init__(config)
    
    def _validate_config(self):
        """Validate that required configuration is present (API key is optional for local server)"""
        if not self.config.get("api_url"):
            raise ValueError(f"{self.__class__.__name__}: API URL is required")
        # API key is optional for local llama.cpp server
    
    def _get_api_url(self) -> str:
        """Get the full API URL for llama.cpp completions"""
        base_url = self.config["api_url"]
        completions_path = self.config["completions_path"]
        
        # Ensure proper URL formatting
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


def create_llama_cpp_provider(config: Optional[Dict[str, Any]] = None) -> LlamaCppProvider:
    """Factory function to create llama.cpp provider"""
    return LlamaCppProvider(config)