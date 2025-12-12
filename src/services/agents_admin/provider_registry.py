"""
Provider Registry System

This module provides a registry for discovering and managing provider classes
across LLM, TTS, and STT services. It enables dynamic loading of provider
metadata including expected properties.
"""

import importlib
import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for discovering and managing provider classes.

    This class provides dynamic discovery of provider implementations
    and access to their metadata including expected properties.
    """

    # Provider type to module mapping
    PROVIDER_MODULES = {
        "llm": "services.llm.providers",
        "tts": "services.tts.providers",
        "stt": "services.stt.providers",
        "rag": "services.rag.providers",
    }

    # Provider name to class name mapping
    PROVIDER_CLASSES = {
        "llm": {
            "groq.com": "groq.GroqProvider",
            "mistral.ai": "mistral.MistralProvider",
            "openrouter.ai": "openrouter.OpenRouterProvider",
            "llama-cpp.local": "llama_cpp.LlamaCppProvider",
        },
        "tts": {
            "deepgram.com": "deepgram.DeepgramProvider",
            "elevenlabs.io": "elevenlabs.ElevenLabsProvider",
            "async.ai": "async_ai.AsyncAIProvider",
            "kokoro.local": "kokoro_local.KokoroLocalProvider",
            "hume.ai": "hume.HumeProvider",
        },
        "stt": {"deepgram.com": "deepgram.DeepgramProvider", "whisper.local": "whisper_local.WhisperLocalProvider"},
        "rag": {
            "qdrant.internal": "qdrant_internal.QdrantInternalProvider",
            "pinecone.io": "pinecone_io.PineconeProvider",
            "rag.saas": "rag_saas.RagSaaSProvider",
        },
    }

    def __init__(self):
        self._cache = {}

    def get_provider_class(self, provider_type: str, provider_name: str) -> Optional[Type]:
        """
        Get provider class for a given provider type and name.

        Args:
            provider_type: Type of provider ('llm', 'tts', 'stt')
            provider_name: Name of provider (e.g., 'groq.com', 'kokoro.local')

        Returns:
            Provider class or None if not found
        """
        cache_key = f"{provider_type}.{provider_name}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Get module and class name
            module_name = self.PROVIDER_MODULES.get(provider_type)
            class_path = self.PROVIDER_CLASSES.get(provider_type, {}).get(provider_name)

            if not module_name or not class_path:
                logger.warning(f"Provider not found: {provider_type}.{provider_name}")
                return None

            # Handle submodule imports (e.g., "groq.GroqProvider")
            if "." in class_path:
                submodule_name, class_name = class_path.split(".", 1)
                full_module_name = f"{module_name}.{submodule_name}"
            else:
                full_module_name = module_name
                class_name = class_path

            # Import module and get class
            module = importlib.import_module(full_module_name)
            provider_class = getattr(module, class_name, None)

            if provider_class:
                self._cache[cache_key] = provider_class
                return provider_class
            else:
                logger.warning(f"Provider class {class_name} not found in module {full_module_name}")
                return None

        except ImportError as e:
            logger.error(f"Failed to import provider module for {provider_type}.{provider_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading provider {provider_type}.{provider_name}: {e}")
            return None

    def get_expected_properties(self, provider_type: str, provider_name: str) -> List[str]:
        """
        Get expected properties for a provider.

        Args:
            provider_type: Type of provider ('llm', 'tts', 'stt')
            provider_name: Name of provider (e.g., 'groq.com', 'kokoro.local')

        Returns:
            List of expected property names
        """
        provider_class = self.get_provider_class(provider_type, provider_name)

        if not provider_class:
            logger.warning(f"Cannot get expected properties for unknown provider: {provider_type}.{provider_name}")
            return []

        try:
            # Check if provider has get_expected_properties method
            if hasattr(provider_class, "get_expected_properties"):
                return provider_class.get_expected_properties()
            else:
                logger.warning(f"Provider {provider_type}.{provider_name} does not implement get_expected_properties()")
                return []

        except Exception as e:
            logger.error(f"Error getting expected properties for {provider_type}.{provider_name}: {e}")
            return []

    def get_provider_field_definitions(self, provider_type: str, provider_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get field definitions for a provider.

        Args:
            provider_type: Type of provider ('llm', 'tts', 'stt')
            provider_name: Name of provider (e.g., 'groq.com', 'kokoro.local')

        Returns:
            Dictionary of field definitions with type, label, and required status
        """
        provider_class = self.get_provider_class(provider_type, provider_name)

        if not provider_class:
            logger.warning(f"Cannot get field definitions for unknown provider: {provider_type}.{provider_name}")
            return {}

        try:
            # Check if provider has get_field_definitions method
            if hasattr(provider_class, "get_field_definitions"):
                return provider_class.get_field_definitions()
            else:
                # Fallback: if provider only has get_expected_properties, create basic field definitions
                expected_properties = self.get_expected_properties(provider_type, provider_name)
                field_definitions = {}

                for prop in expected_properties:
                    # Create basic field definition
                    field_definitions[prop] = {
                        "type": "text",
                        "label": prop.replace("_", " ").title(),
                        "required": True,
                    }

                return field_definitions

        except Exception as e:
            logger.error(f"Error getting field definitions for {provider_type}.{provider_name}: {e}")
            return {}

    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all available providers with their metadata.

        Returns:
            Dictionary with provider types as keys and provider metadata as values
        """
        result = {}

        for provider_type in self.PROVIDER_MODULES.keys():
            providers = []
            field_definitions = {}

            for provider_name in self.PROVIDER_CLASSES.get(provider_type, {}).keys():
                # Get provider label (human-readable name)
                label = provider_name.replace(".com", "").replace(".ai", "").replace(".local", "").replace(".io", "").title()

                providers.append({"value": provider_name, "label": label})

                # Get field definitions for this provider
                provider_fields = self.get_provider_field_definitions(provider_type, provider_name)
                field_definitions[provider_name] = provider_fields

            result[provider_type] = {"providers": providers, "field_definitions": field_definitions}

        return result


# Global registry instance
_provider_registry = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()
    return _provider_registry
