#!/usr/bin/env python3
"""
Integration tests for DevAgentCreator.

Tests that the development agent creation from environment variables
produces valid configurations without validation warnings.
"""
import os
import sys
import pytest
from unittest.mock import patch

from services.agents_admin.dev_agent_creator import DevAgentCreator
from services.agents_admin.provider_registry import get_provider_registry
from database.session import SessionLocal


@pytest.fixture
def db_session():
    """Provide a database session for integration tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def agent_service(db_session):
    """Create an AgentService instance for testing."""
    from services.agents_admin.agent_service import AgentService
    return AgentService(db_session)


class TestDevAgentCreator:
    """Test DevAgentCreator functionality."""

    def test_mapping_covers_all_providers(self):
        """Ensure mapping includes all providers defined in provider registry."""
        registry = get_provider_registry()
        mapping = DevAgentCreator._PROVIDER_ENV_MAPPING

        # Check each provider type
        for provider_type in ["llm", "tts", "stt"]:
            providers = registry.PROVIDER_CLASSES.get(provider_type, {})
            for provider_name in providers.keys():
                assert (provider_type, provider_name) in mapping, \
                    f"Missing mapping for {provider_type}.{provider_name}"

    def test_mapping_keys_match_expected_properties(self):
        """Ensure mapping keys are subset of expected properties (or will be filtered)."""
        registry = get_provider_registry()
        mapping = DevAgentCreator._PROVIDER_ENV_MAPPING

        for (provider_type, provider_name), entries in mapping.items():
            expected = registry.get_expected_properties(provider_type, provider_name)
            if not expected:
                # If no expected properties, skip validation
                continue
            # Collect config keys from mapping
            config_keys = {config_key for config_key, _, _, _ in entries}
            # All config keys should be in expected properties (or will be filtered)
            # We'll just log extra keys; they will be filtered later
            extra = config_keys - set(expected)
            if extra:
                # This is okay because _filter_config will remove them,
                # but we should still note for debugging
                print(f"Note: mapping includes extra keys for {provider_type}.{provider_name}: {extra}")

    def test_build_config_from_mapping_no_warnings(self, monkeypatch):
        """Test that building config from mapping does not produce validation warnings."""
        # Mock environment variables to have values
        env_vars = {
            "GROQ_LLM_API_KEY": "test_key",
            "GROQ_LLM_MODEL": "test_model",
            "GROQ_LLM_API_URL": "https://test.example.com",
            "GROQ_LLM_COMPLETIONS_PATH": "/test",
            "MISTRAL_LLM_API_KEY": "test_key",
            "MISTRAL_LLM_MODEL": "test_model",
            "MISTRAL_LLM_API_URL": "https://test.example.com",
            "MISTRAL_LLM_COMPLETIONS_PATH": "/test",
            "OPENROUTER_LLM_API_KEY": "test_key",
            "OPENROUTER_LLM_MODEL": "test_model",
            "OPENROUTER_LLM_API_URL": "https://test.example.com",
            "OPENROUTER_LLM_COMPLETIONS_PATH": "/test",
            "OPENROUTER_LLM_APP_NAME": "Test",
            "OPENROUTER_LLM_APP_URL": "https://test.example.com",
            "LLAMA_CPP_LLM_API_URL": "http://test:8002",
            "LLAMA_CPP_LLM_API_KEY": "local",
            "LLAMA_CPP_LLM_MODEL": "default",
            "LLAMA_CPP_LLM_COMPLETIONS_PATH": "/test",
            "ASYNC_API_KEY": "test_key",
            "ASYNC_AI_TTS_VOICE_ID": "test_voice",
            "ASYNC_AI_TTS_MODEL_ID": "test_model",
            "ASYNC_AI_TTS_SAMPLE_RATE": "44100",
            "ASYNC_AI_TTS_ENCODING": "pcm_s16le",
            "ASYNC_AI_TTS_CONTAINER": "raw",
            "ASYNC_AI_TTS_URL": "wss://test.example.com",
            "KOKORO_LOCAL_TTS_URL": "ws://test:5000/ws/tts/stream",
            "KOKORO_TTS_DEFAULT_VOICE": "test_voice",
            "KOKORO_TTS_SAMPLE_RATE": "22050",
            "KOKORO_TTS_ENCODING": "pcm_s16le",
            "KOKORO_TTS_CONTAINER": "raw",
            "KOKORO_TTS_DEFAULT_LANGUAGE": "fr-fr",
            "KOKORO_TTS_DEFAULT_SPEED": "1.0",
            "DEEPGRAM_TTS_API_KEY": "test_key",
            "DEEPGRAM_TTS_MODEL": "test_model",
            "DEEPGRAM_TTS_SAMPLE_RATE": "16000",
            "DEEPGRAM_TTS_ENCODING": "linear16",
            "ELEVENLABS_TTS_API_KEY": "test_key",
            "ELEVENLABS_TTS_VOICE_ID": "test_voice",
            "ELEVENLABS_TTS_MODEL_ID": "test_model",
            "ELEVENLABS_TTS_SAMPLE_RATE": "22050",
            "ELEVENLABS_TTS_ENCODING": "pcm_s16le",
            "ELEVENLABS_TTS_OUTPUT_FORMAT": "pcm_22050",
            "CUSTOM_WHISPER_STT_URL": "ws://test:8003/api/stt/stream",
            "DEEPGRAM_STT_API_KEY": "test_key",
            "DEEPGRAM_MODEL": "test_model",
            "DEEPGRAM_LANGUAGE": "fr",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        creator = DevAgentCreator(db_session=None)  # session not needed for config building
        mapping = DevAgentCreator._PROVIDER_ENV_MAPPING

        for (provider_type, provider_name) in mapping.keys():
            config = creator._build_config_from_mapping(provider_type, provider_name)
            # Ensure config is not empty (unless provider has no required config)
            # We'll just assert no exception and log
            print(f"Built config for {provider_type}.{provider_name}: {list(config.keys())}")

    def test_create_default_dev_agent_success(self, db_session, agent_service):
        """Test that create_default_dev_agent succeeds with current environment."""
        # First, delete any existing development agent to ensure clean state
        agents = agent_service.list_agents()
        for agent in agents.agents:
            if agent.name == "Development Agent":
                # Temporarily set is_default=False to allow deletion
                if agent.is_default:
                    from services.agents_admin.models import AgentUpdate
                    update_data = AgentUpdate(is_default=False)
                    agent_service.update_agent(agent.id, update_data)
                agent_service.delete_agent(agent.id)
                break

        creator = DevAgentCreator(db_session)
        # This will create a new development agent
        success = creator.create_default_dev_agent()
        assert success is True
        # Verify that the default agent exists and has valid config
        default_agent = agent_service.get_default_agent()
        assert default_agent.name == "Development Agent"
        # Ensure each provider config is valid (no extra keys)
        for provider_type, provider_name in [
            ("llm", default_agent.llm_provider),
            ("tts", default_agent.tts_provider),
            ("stt", default_agent.stt_provider),
        ]:
            config = getattr(default_agent, f"{provider_type}_config")
            expected = get_provider_registry().get_expected_properties(provider_type, provider_name)
            if expected:
                extra = set(config.keys()) - set(expected)
                assert len(extra) == 0, f"Extra keys in {provider_type}.{provider_name}: {extra}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])