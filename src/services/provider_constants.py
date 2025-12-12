"""
Provider constants loader.

This module loads provider constants from the JSON file (single source of truth).
All constants are now stored in provider_constants.json.

Environment variables can override specific URLs for local services:
- CUSTOM_WHISPER_STT_URL: Overrides stt.whisper.local.URL
- CUSTOM_KOKORO_TTS_URL: Overrides tts.kokoro.local.URL
- CUSTOM_LLAMA_CPP_URL: Overrides llm.llama-cpp.local.API_URL
- CUSTOM_QDRANT_URL: Overrides rag.qdrant.internal.URL
"""

import json
import os


def get_provider_constants():
    """Load and return provider constants from JSON file, with environment overrides."""
    json_path = os.path.join(os.path.dirname(__file__), "provider_constants.json")
    with open(json_path, "r") as f:
        constants = json.load(f)

    # Environment variable overrides for local services
    overrides = [
        ("CUSTOM_WHISPER_STT_URL", ["stt", "whisper.local", "URL"]),
        ("CUSTOM_KOKORO_TTS_URL", ["tts", "kokoro.local", "URL"]),
        ("CUSTOM_LLAMA_CPP_URL", ["llm", "llama-cpp.local", "API_URL"]),
        ("CUSTOM_QDRANT_URL", ["rag", "qdrant.internal", "URL"]),
    ]

    for env_var, path in overrides:
        value = os.getenv(env_var)
        if value is not None:
            # Navigate to the nested dict
            d = constants
            for key in path[:-1]:
                d = d.get(key)
                if d is None:
                    break
            if d is not None and isinstance(d, dict):
                d[path[-1]] = value

    return constants
