"""
Groq.com LLM Provider Adapter
"""

import os
import asyncio
import aiohttp
import json
from typing import AsyncIterator, Optional, Dict, Any
from ..config import llm_config
from .openai_compatible_provider import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    """Groq.com LLM provider implementation using OpenAI-compatible API"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = llm_config.get_groq_config()
        super().__init__(config)
    
    def _get_api_url(self) -> str:
        """Get the full API URL"""
        base_url = self.config["api_url"]
        completions_path = self.config["completions_path"]
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