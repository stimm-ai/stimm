#!/usr/bin/env python3
"""
Integration tests for Agent Provider Configuration validation.

Tests validation of provider configurations for LLM, STT, and TTS providers
to ensure agent configuration integrity.
"""
import sys
import uuid
import pytest
from services.agents_admin.agent_service import AgentService
from services.agents_admin.models import AgentCreate, ProviderConfig
from services.agents_admin.exceptions import AgentValidationError


@pytest.fixture
def agent_service():
    """Create an AgentService instance for testing."""
    return AgentService()


@pytest.fixture
def valid_provider_configs(agent_service):
    """Get valid provider configs from default agent."""
    default_agent = agent_service.get_default_agent()
    return {
        "llm": ProviderConfig(
            provider=default_agent.llm_provider,
            config=default_agent.llm_config
        ),
        "tts": ProviderConfig(
            provider=default_agent.tts_provider,
            config=default_agent.tts_config
        ),
        "stt": ProviderConfig(
            provider=default_agent.stt_provider,
            config=default_agent.stt_config
        ),
    }


def test_llm_provider_validation_groq(agent_service, valid_provider_configs):
    """Test LLM provider validation with Groq configuration."""
    test_name = f"LLM Groq Test {uuid.uuid4().hex[:8]}"
    
    # Valid Groq configuration
    groq_config = ProviderConfig(
        provider="groq.com",
        config={
            "api_key": "test_key",
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.7,
            "max_tokens": 1000
        }
    )
    
    agent_data = AgentCreate(
        name=test_name,
        description="Test Groq LLM",
        llm_config=groq_config,
        tts_config=valid_provider_configs["tts"],
        stt_config=valid_provider_configs["stt"],
        is_default=False
    )
    
    created = agent_service.create_agent(agent_data)
    assert created.llm_provider == "groq.com"
    
    # Cleanup
    agent_service.delete_agent(created.id)
    print("✅ Groq LLM provider validation passed")


def test_stt_provider_validation_deepgram(agent_service, valid_provider_configs):
    """Test STT provider validation with Deepgram configuration."""
    test_name = f"STT Deepgram Test {uuid.uuid4().hex[:8]}"
    
    # Valid Deepgram configuration
    deepgram_config = ProviderConfig(
        provider="deepgram.com",
        config={
            "api_key": "test_key",
            "model": "nova-2",
            "language": "en-US"
        }
    )
    
    agent_data = AgentCreate(
        name=test_name,
        description="Test Deepgram STT",
        llm_config=valid_provider_configs["llm"],
        tts_config=valid_provider_configs["tts"],
        stt_config=deepgram_config,
        is_default=False
    )
    
    created = agent_service.create_agent(agent_data)
    assert created.stt_provider == "deepgram.com"
    
    # Cleanup
    agent_service.delete_agent(created.id)
    print("✅ Deepgram STT provider validation passed")


def test_stt_provider_validation_whisper(agent_service, valid_provider_configs):
    """Test STT provider validation with Whisper Local configuration."""
    test_name = f"STT Whisper Test {uuid.uuid4().hex[:8]}"
    
    # Valid Whisper Local configuration
    whisper_config = ProviderConfig(
        provider="whisper.local",
        config={
            "base_url": "http://localhost:8000",
            "model": "base"
        }
    )
    
    agent_data = AgentCreate(
        name=test_name,
        description="Test Whisper STT",
        llm_config=valid_provider_configs["llm"],
        tts_config=valid_provider_configs["tts"],
        stt_config=whisper_config,
        is_default=False
    )
    
    created = agent_service.create_agent(agent_data)
    assert created.stt_provider == "whisper.local"
    
    # Cleanup
    agent_service.delete_agent(created.id)
    print("✅ Whisper Local STT provider validation passed")


def test_tts_provider_validation_elevenlabs(agent_service, valid_provider_configs):
    """Test TTS provider validation with ElevenLabs configuration."""
    test_name = f"TTS ElevenLabs Test {uuid.uuid4().hex[:8]}"
    
    # Valid ElevenLabs configuration
    elevenlabs_config = ProviderConfig(
        provider="elevenlabs.io",
        config={
            "api_key": "test_key",
            "voice_id": "test_voice",
            "model_id": "eleven_turbo_v2_5"
        }
    )
    
    agent_data = AgentCreate(
        name=test_name,
        description="Test ElevenLabs TTS",
        llm_config=valid_provider_configs["llm"],
        tts_config=elevenlabs_config,
        stt_config=valid_provider_configs["stt"],
        is_default=False
    )
    
    created = agent_service.create_agent(agent_data)
    assert created.tts_provider == "elevenlabs.io"
    
    # Cleanup
    agent_service.delete_agent(created.id)
    print("✅ ElevenLabs TTS provider validation passed")


def test_multiple_provider_combinations(agent_service):
    """Test agent creation with different provider combinations."""
    test_name = f"Multi Provider Test {uuid.uuid4().hex[:8]}"
    
    # Mix of different providers
    agent_data = AgentCreate(
        name=test_name,
        description="Test multiple providers",
        llm_config=ProviderConfig(
            provider="groq.com",
            config={"api_key": "test", "model": "llama-3.3-70b-versatile"}
        ),
        tts_config=ProviderConfig(
            provider="elevenlabs.io",
            config={"api_key": "test", "voice_id": "test", "model_id": "eleven_turbo_v2_5"}
        ),
        stt_config=ProviderConfig(
            provider="deepgram.com",
            config={"api_key": "test", "model": "nova-2"}
        ),
        is_default=False
    )
    
    created = agent_service.create_agent(agent_data)
    
    assert created.llm_provider == "groq.com"
    assert created.tts_provider == "elevenlabs.io"
    assert created.stt_provider == "deepgram.com"
    
    # Cleanup
    agent_service.delete_agent(created.id)
    print("✅ Multiple provider combination validation passed")


def test_provider_config_structure(agent_service, valid_provider_configs):
    """Test that provider configs maintain proper structure."""
    test_name = f"Config Structure Test {uuid.uuid4().hex[:8]}"
    
    agent_data = AgentCreate(
        name=test_name,
        description="Test config structure",
        llm_config=valid_provider_configs["llm"],
        tts_config=valid_provider_configs["tts"],
        stt_config=valid_provider_configs["stt"],
        is_default=False
    )
    
    created = agent_service.create_agent(agent_data)
    
    # Verify provider fields exist and are properly structured
    assert hasattr(created, "llm_provider")
    assert hasattr(created, "llm_config")
    assert hasattr(created, "tts_provider")
    assert hasattr(created, "tts_config")
    assert hasattr(created, "stt_provider")
    assert hasattr(created, "stt_config")
    
    # Verify configs are dictionaries
    assert isinstance(created.llm_config, dict)
    assert isinstance(created.tts_config, dict)
    assert isinstance(created.stt_config, dict)
    
    # Cleanup
    agent_service.delete_agent(created.id)
    print("✅ Provider config structure validation passed")


if __name__ == "__main__":
    print("Running agent provider configuration integration tests...")
    pytest.main([__file__, "-v"])
