"""
Unit tests for provider constants loading.

These tests verify that provider constants are correctly loaded from JSON
and that environment variable overrides work as expected.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock


@pytest.mark.unit
class TestProviderConstants:
    """Test suite for provider constants functionality."""
    
    def test_get_provider_constants_loads_json(self):
        """Test that provider constants are loaded from JSON file."""
        from services.provider_constants import get_provider_constants
        
        constants = get_provider_constants()
        
        # Verify it returns a dictionary
        assert isinstance(constants, dict)
        
        # Verify expected top-level keys exist
        assert "stt" in constants or "tts" in constants or "llm" in constants
    
    def test_provider_constants_structure(self):
        """Test the structure of loaded provider constants."""
        from services.provider_constants import get_provider_constants
        
        constants = get_provider_constants()
        
        # Check that we have provider categories
        for category in ["stt", "tts", "llm"]:
            if category in constants:
                assert isinstance(constants[category], dict)
    
    @patch.dict(os.environ, {"CUSTOM_WHISPER_STT_URL": "ws://custom-whisper:9000"})
    def test_whisper_url_override(self):
        """Test that CUSTOM_WHISPER_STT_URL overrides the default."""
        from services.provider_constants import get_provider_constants
        
        constants = get_provider_constants()
        
        # Verify the override was applied
        if "stt" in constants and "whisper.local" in constants["stt"]:
            whisper_config = constants["stt"]["whisper.local"]
            if "URL" in whisper_config:
                assert whisper_config["URL"] == "ws://custom-whisper:9000"
    
    @patch.dict(os.environ, {"CUSTOM_KOKORO_TTS_URL": "http://custom-kokoro:8080"})
    def test_kokoro_url_override(self):
        """Test that CUSTOM_KOKORO_TTS_URL overrides the default."""
        from services.provider_constants import get_provider_constants
        
        constants = get_provider_constants()
        
        # Verify the override was applied
        if "tts" in constants and "kokoro.local" in constants["tts"]:
            kokoro_config = constants["tts"]["kokoro.local"]
            if "URL" in kokoro_config:
                assert kokoro_config["URL"] == "http://custom-kokoro:8080"
    
    @patch.dict(os.environ, {"CUSTOM_LLAMA_CPP_URL": "http://custom-llama:5000"})
    def test_llama_cpp_url_override(self):
        """Test that CUSTOM_LLAMA_CPP_URL overrides the default."""
        from services.provider_constants import get_provider_constants
        
        constants = get_provider_constants()
        
        # Verify the override was applied
        if "llm" in constants and "llama-cpp.local" in constants["llm"]:
            llama_config = constants["llm"]["llama-cpp.local"]
            if "API_URL" in llama_config:
                assert llama_config["API_URL"] == "http://custom-llama:5000"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_no_overrides(self):
        """Test that constants load correctly without environment overrides."""
        from services.provider_constants import get_provider_constants
        
        constants = get_provider_constants()
        
        # Should still return valid constants without overrides
        assert isinstance(constants, dict)
        assert len(constants) > 0
    
    @patch.dict(os.environ, {
        "CUSTOM_WHISPER_STT_URL": "ws://test:1111",
        "CUSTOM_KOKORO_TTS_URL": "http://test:2222",
        "CUSTOM_LLAMA_CPP_URL": "http://test:3333"
    })
    def test_multiple_overrides(self):
        """Test that multiple environment overrides work simultaneously."""
        from services.provider_constants import get_provider_constants
        
        constants = get_provider_constants()
        
        # All overrides should be applied
        if "stt" in constants and "whisper.local" in constants["stt"]:
            if "URL" in constants["stt"]["whisper.local"]:
                assert "test:1111" in constants["stt"]["whisper.local"]["URL"]
        
        if "tts" in constants and "kokoro.local" in constants["tts"]:
            if "URL" in constants["tts"]["kokoro.local"]:
                assert "test:2222" in constants["tts"]["kokoro.local"]["URL"]
        
        if "llm" in constants and "llama-cpp.local" in constants["llm"]:
            if "API_URL" in constants["llm"]["llama-cpp.local"]:
                assert "test:3333" in constants["llm"]["llama-cpp.local"]["API_URL"]
    
    def test_json_file_exists(self):
        """Test that the provider_constants.json file exists."""
        # Get the path to the JSON file
        from services import provider_constants
        module_dir = Path(provider_constants.__file__).parent
        json_path = module_dir / "provider_constants.json"
        
        assert json_path.exists(), f"provider_constants.json not found at {json_path}"
        
        # Verify it's valid JSON
        with open(json_path, 'r') as f:
            data = json.load(f)
            assert isinstance(data, dict)
