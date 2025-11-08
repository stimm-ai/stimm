"""
Property Mapper for standardized frontend names to provider-specific API requirements.

This module handles the mapping between standardized frontend field names
and provider-specific API requirements to maintain backward compatibility
while providing a clean, standardized interface.
"""

from typing import Dict, Any, Optional


class PropertyMapper:
    """Maps standardized frontend properties to provider-specific API requirements."""
    
    # Provider-specific property mappings
    # Format: {provider_name: {standardized_field: provider_specific_field}}
    PROVIDER_MAPPINGS = {
        "tts": {
            "elevenlabs.io": {
                "voice": "voice_id",  # ElevenLabs uses voice_id
                "model": "model_id"   # ElevenLabs uses model_id
            },
            "async.ai": {
                "voice": "voice_id",    # Async.ai uses voice_id (or voice as fallback)
                "model": "model_id"     # Async.ai uses model_id
            },
            "kokoro.local": {
                "voice": "voice_id",    # Kokoro uses voice_id
                "model": "model"        # Kokoro uses model directly
            },
            "deepgram.com": {
                "voice": "voice",       # Deepgram uses voice directly
                "model": "model"        # Deepgram uses model directly
            }
        },
        "llm": {
            "groq.com": {
                "model": "model"        # Groq uses model directly
            },
            "mistral.ai": {
                "model": "model"        # Mistral uses model directly
            },
            "openrouter.ai": {
                "model": "model"        # OpenRouter uses model directly
            },
            "llama-cpp.local": {
                "model": "model"        # Llama.cpp uses model directly
            }
        },
        "stt": {
            "deepgram.com": {
                "model": "model"        # Deepgram uses model directly
            },
            "whisper.local": {
                "model": "model"        # Whisper uses model directly
            }
        }
    }
    
    @classmethod
    def to_provider_format(cls, provider_type: str, provider_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert standardized frontend config to provider-specific format.
        
        Args:
            provider_type: Type of provider ('llm', 'tts', 'stt')
            provider_name: Name of the provider (e.g., 'elevenlabs.io')
            config: Standardized configuration dictionary
            
        Returns:
            Provider-specific configuration dictionary
        """
        if provider_type not in cls.PROVIDER_MAPPINGS:
            return config.copy()
            
        provider_mappings = cls.PROVIDER_MAPPINGS[provider_type].get(provider_name, {})
        provider_config = config.copy()
        
        # Apply mappings for this specific provider
        for standardized_field, provider_field in provider_mappings.items():
            if standardized_field in provider_config:
                provider_config[provider_field] = provider_config.pop(standardized_field)
        
        return provider_config
    
    @classmethod
    def from_provider_format(cls, provider_type: str, provider_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert provider-specific config to standardized frontend format.
        
        Args:
            provider_type: Type of provider ('llm', 'tts', 'stt')
            provider_name: Name of the provider (e.g., 'elevenlabs.io')
            config: Provider-specific configuration dictionary
            
        Returns:
            Standardized configuration dictionary
        """
        if provider_type not in cls.PROVIDER_MAPPINGS:
            return config.copy()
            
        provider_mappings = cls.PROVIDER_MAPPINGS[provider_type].get(provider_name, {})
        standardized_config = config.copy()
        
        # Apply reverse mappings for this specific provider
        for standardized_field, provider_field in provider_mappings.items():
            if provider_field in standardized_config:
                standardized_config[standardized_field] = standardized_config.pop(provider_field)
        
        return standardized_config
    
    @classmethod
    def get_standardized_fields(cls, provider_type: str) -> Dict[str, Dict[str, str]]:
        """
        Get the standardized field definitions for a provider type.
        
        Args:
            provider_type: Type of provider ('llm', 'tts', 'stt')
            
        Returns:
            Dictionary of standardized field definitions
        """
        field_definitions = {
            "llm": {
                "model": {"type": "text", "label": "Model", "required": True},
                "api_key": {"type": "password", "label": "API Key", "required": True}
            },
            "tts": {
                "voice": {"type": "text", "label": "Voice", "required": True},
                "model": {"type": "text", "label": "Model", "required": False},
                "api_key": {"type": "password", "label": "API Key", "required": True}
            },
            "stt": {
                "model": {"type": "text", "label": "Model", "required": True},
                "api_key": {"type": "password", "label": "API Key", "required": True}
            }
        }
        
        return field_definitions.get(provider_type, {})