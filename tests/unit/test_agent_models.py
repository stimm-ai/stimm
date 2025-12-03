"""
Unit tests for agent management Pydantic models.

These tests verify that Pydantic models for the agent management API
work correctly, including validation and serialization.
"""

import pytest
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from services.agents_admin.models import (
    ProviderConfig,
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentConfig,
    AgentSessionCreate,
)


@pytest.mark.unit
class TestProviderConfig:
    """Test suite for ProviderConfig model."""
    
    def test_provider_config_creation(self):
        """Test creating a valid ProviderConfig."""
        config = ProviderConfig(
            provider="groq.com",
            config={"api_key": "test_key", "model": "llama-3"}
        )
        
        assert config.provider == "groq.com"
        assert config.config["api_key"] == "test_key"
        assert config.config["model"] == "llama-3"
    
    def test_provider_config_default_config(self):
        """Test ProviderConfig with default empty config."""
        config = ProviderConfig(provider="async.ai")
        
        assert config.provider == "async.ai"
        assert config.config == {}
    
    def test_provider_name_validation_strips_whitespace(self):
        """Test that provider name whitespace is stripped."""
        config = ProviderConfig(provider="  groq.com  ")
        
        assert config.provider == "groq.com"
    
    def test_provider_name_validation_empty(self):
        """Test that empty provider name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderConfig(provider="")
        
        assert "Provider name cannot be empty" in str(exc_info.value)
    
    def test_provider_name_validation_whitespace_only(self):
        """Test that whitespace-only provider name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ProviderConfig(provider="   ")
        
        assert "Provider name cannot be empty" in str(exc_info.value)


@pytest.mark.unit
class TestAgentCreate:
    """Test suite for AgentCreate model."""
    
    def test_agent_create_valid(self):
        """Test creating a valid AgentCreate model."""
        agent = AgentCreate(
            name="TestAgent",
            description="Test description",
            system_prompt="You are a helpful assistant",
            llm_config=ProviderConfig(provider="groq.com", config={}),
            tts_config=ProviderConfig(provider="async.ai", config={}),
            stt_config=ProviderConfig(provider="deepgram.com", config={}),
        )
        
        assert agent.name == "TestAgent"
        assert agent.description == "Test description"
        assert agent.system_prompt == "You are a helpful assistant"
        assert agent.is_default is False
    
    def test_agent_create_name_strips_whitespace(self):
        """Test that agent name whitespace is stripped."""
        agent = AgentCreate(
            name="  TestAgent  ",
            llm_config=ProviderConfig(provider="groq.com", config={}),
            tts_config=ProviderConfig(provider="async.ai", config={}),
            stt_config=ProviderConfig(provider="deepgram.com", config={}),
        )
        
        assert agent.name == "TestAgent"
    
    def test_agent_create_empty_name_fails(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreate(
                name="",
                llm_config=ProviderConfig(provider="groq.com", config={}),
                tts_config=ProviderConfig(provider="async.ai", config={}),
                stt_config=ProviderConfig(provider="deepgram.com", config={}),
            )
        
        # Pydantic V2 uses different error format
        error_str = str(exc_info.value)
        assert "validation error" in error_str.lower() or "at least 1 character" in error_str
    
    def test_agent_create_with_rag_config(self):
        """Test AgentCreate with RAG configuration."""
        rag_id = uuid4()
        agent = AgentCreate(
            name="TestAgent",
            llm_config=ProviderConfig(provider="groq.com", config={}),
            tts_config=ProviderConfig(provider="async.ai", config={}),
            stt_config=ProviderConfig(provider="deepgram.com", config={}),
            rag_config_id=rag_id,
        )
        
        assert agent.rag_config_id == rag_id
    
    def test_agent_create_is_default(self):
        """Test AgentCreate with is_default flag."""
        agent = AgentCreate(
            name="DefaultAgent",
            llm_config=ProviderConfig(provider="groq.com", config={}),
            tts_config=ProviderConfig(provider="async.ai", config={}),
            stt_config=ProviderConfig(provider="deepgram.com", config={}),
            is_default=True,
        )
        
        assert agent.is_default is True


@pytest.mark.unit
class TestAgentUpdate:
    """Test suite for AgentUpdate model."""
    
    def test_agent_update_all_fields_optional(self):
        """Test that all fields in AgentUpdate are optional."""
        update = AgentUpdate()
        
        assert update.name is None
        assert update.description is None
        assert update.system_prompt is None
        assert update.llm_config is None
        assert update.tts_config is None
        assert update.stt_config is None
    
    def test_agent_update_partial(self):
        """Test AgentUpdate with only some fields."""
        update = AgentUpdate(
            name="UpdatedName",
            is_active=False
        )
        
        assert update.name == "UpdatedName"
        assert update.is_active is False
        assert update.description is None


@pytest.mark.unit
class TestAgentResponse:
    """Test suite for AgentResponse model."""
    
    def test_agent_response_creation(self):
        """Test creating an AgentResponse."""
        agent_id = uuid4()
        user_id = uuid4()
        now = datetime.utcnow()
        
        response = AgentResponse(
            id=agent_id,
            user_id=user_id,
            name="TestAgent",
            description="Test",
            system_prompt="Test prompt",
            rag_config_id=None,
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={"model": "llama-3"},
            tts_config={},
            stt_config={},
            is_default=False,
            is_active=True,
            is_system_agent=False,
            created_at=now,
            updated_at=now,
        )
        
        assert response.id == agent_id
        assert response.user_id == user_id
        assert response.name == "TestAgent"
        assert response.llm_provider == "groq.com"
    
    def test_agent_response_from_attributes(self):
        """Test that AgentResponse has from_attributes config."""
        # This allows SQLAlchemy ORM models to be converted
        assert AgentResponse.model_config.get("from_attributes") is True


@pytest.mark.unit
class TestAgentConfig:
    """Test suite for AgentConfig model."""
    
    def test_agent_config_creation(self):
        """Test creating an AgentConfig."""
        config = AgentConfig(
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={"model": "llama-3"},
            tts_config={},
            stt_config={},
        )
        
        assert config.llm_provider == "groq.com"
        assert config.tts_provider == "async.ai"
        assert config.stt_provider == "deepgram.com"
    
    def test_agent_config_from_agent_response(self):
        """Test creating AgentConfig from AgentResponse."""
        agent_id = uuid4()
        user_id = uuid4()
        rag_id = uuid4()
        now = datetime.utcnow()
        
        response = AgentResponse(
            id=agent_id,
            user_id=user_id,
            name="TestAgent",
            description="Test",
            system_prompt="Test prompt",
            rag_config_id=rag_id,
            llm_provider="groq.com",
            tts_provider="async.ai",
            stt_provider="deepgram.com",
            llm_config={"model": "llama-3"},
            tts_config={"voice": "test"},
            stt_config={"language": "en"},
            is_default=False,
            is_active=True,
            is_system_agent=False,
            created_at=now,
            updated_at=now,
        )
        
        config = AgentConfig.from_agent_response(response)
        
        assert config.llm_provider == "groq.com"
        assert config.tts_provider == "async.ai"
        assert config.stt_provider == "deepgram.com"
        assert config.system_prompt == "Test prompt"
        assert config.rag_config_id == rag_id
        assert config.llm_config == {"model": "llama-3"}
        assert config.tts_config == {"voice": "test"}
        assert config.stt_config == {"language": "en"}


@pytest.mark.unit
class TestAgentSessionCreate:
    """Test suite for AgentSessionCreate model."""
    
    def test_agent_session_create_valid(self):
        """Test creating a valid AgentSessionCreate."""
        agent_id = uuid4()
        session = AgentSessionCreate(
            agent_id=agent_id,
            session_type="voicebot",
        )
        
        assert session.agent_id == agent_id
        assert session.session_type == "voicebot"
    
    def test_agent_session_create_with_metadata(self):
        """Test AgentSessionCreate with IP and user agent."""
        agent_id = uuid4()
        session = AgentSessionCreate(
            agent_id=agent_id,
            session_type="chat",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Mozilla/5.0"
    
    def test_agent_session_valid_types(self):
        """Test all valid session types."""
        agent_id = uuid4()
        valid_types = ["voicebot", "chat", "tts", "stt"]
        
        for session_type in valid_types:
            session = AgentSessionCreate(
                agent_id=agent_id,
                session_type=session_type,
            )
            assert session.session_type == session_type
    
    def test_agent_session_invalid_type(self):
        """Test that invalid session type raises error."""
        agent_id = uuid4()
        
        with pytest.raises(ValidationError) as exc_info:
            AgentSessionCreate(
                agent_id=agent_id,
                session_type="invalid_type",
            )
        
        assert "Session type must be one of" in str(exc_info.value)
