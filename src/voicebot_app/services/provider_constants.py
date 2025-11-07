"""
Immutable provider-level constants.

This module contains immutable constants that providers should always use.
These are NOT fallback defaults - they are fixed values that define provider behavior.

Scope:
- ONLY truly global, shared, non-agent-specific constants (URLs, paths, sample rates, encodings, etc.).
- NO agent-specific or secret values (api_key, voice_id, model_id, model, language, etc.).
- Stable across environments; these values should never change at runtime.

Usage:
- Import from this module in provider implementations (LLM, TTS, STT) to use fixed provider constants.
- Providers should use these constants directly, not as fallbacks for missing configuration.
- Agents only configure non-constant values (API keys, models, etc.).
"""


# ======================================================================
# TTS PROVIDERS
# ======================================================================

class DeepgramTTSConstants:
    """Immutable constants for Deepgram TTS provider."""
    BASE_URL: str = "https://api.deepgram.com"
    SAMPLE_RATE: int = 16000
    ENCODING: str = "linear16"


class ElevenLabsTTSConstants:
    """Immutable constants for ElevenLabs TTS provider."""
    SAMPLE_RATE: int = 22050
    ENCODING: str = "pcm_s16le"
    OUTPUT_FORMAT: str = "pcm_22050"


class AsyncAITTSConstants:
    """Immutable constants for Async.AI TTS provider."""
    URL: str = "wss://api.async.ai/text_to_speech/websocket/ws"
    SAMPLE_RATE: int = 44100
    ENCODING: str = "pcm_s16le"
    CONTAINER: str = "raw"


class KokoroLocalTTSConstants:
    """Immutable constants for Kokoro Local TTS provider."""
    URL: str = "ws://kokoro-tts:5000/ws/tts/stream"
    SAMPLE_RATE: int = 22050
    ENCODING: str = "pcm_s16le"
    CONTAINER: str = "raw"
    SPEED: float = 0.8


# ======================================================================
# STT PROVIDERS
# ======================================================================

class DeepgramSTTConstants:
    """Immutable constants for Deepgram STT provider."""
    BASE_URL: str = "https://api.deepgram.com"
    SAMPLE_RATE: int = 16000


class WhisperLocalSTTConstants:
    """Immutable constants for Whisper Local STT provider."""
    URL: str = "ws://whisper-stt:8003"
    PATH: str = "/api/stt/stream"


# ======================================================================
# LLM PROVIDERS
# ======================================================================

class GroqLLMConstants:
    """Immutable constants for Groq LLM provider."""
    API_URL: str = "https://api.groq.com"
    COMPLETIONS_PATH: str = "/openai/v1/chat/completions"


class MistralLLMConstants:
    """Immutable constants for Mistral.ai LLM provider."""
    API_URL: str = "https://api.mistral.ai/v1"
    COMPLETIONS_PATH: str = "/chat/completions"


class OpenRouterLLMConstants:
    """Immutable constants for OpenRouter.ai LLM provider."""
    API_URL: str = "https://openrouter.ai/api/v1"
    COMPLETIONS_PATH: str = "/chat/completions"


class LlamaCppLLMConstants:
    """Immutable constants for llama-cpp.local LLM provider."""
    API_URL: str = "http://llama-cpp-server:8002"
    COMPLETIONS_PATH: str = "/v1/chat/completions"