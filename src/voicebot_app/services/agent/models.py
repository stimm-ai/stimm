"""
Pydantic models for agent management API.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class ProviderConfig(BaseModel):
    """Configuration for a single provider."""
    
    provider: str = Field(..., description="Provider name (e.g., 'groq.com', 'async.ai')")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")
    
    @validator('provider')
    def validate_provider(cls, v):
        """Validate provider name."""
        if not v or not v.strip():
            raise ValueError("Provider name cannot be empty")
        return v.strip()


class AgentCreate(BaseModel):
    """Model for creating a new agent."""

    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    llm_config: ProviderConfig = Field(..., description="LLM provider configuration")
    tts_config: ProviderConfig = Field(..., description="TTS provider configuration")
    stt_config: ProviderConfig = Field(..., description="STT provider configuration")
    is_default: bool = Field(False, description="Whether this agent should be the default")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate agent name."""
        if not v or not v.strip():
            raise ValueError("Agent name cannot be empty")
        return v.strip()



class AgentUpdate(BaseModel):
    """Model for updating an existing agent."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    llm_config: Optional[ProviderConfig] = Field(None, description="LLM provider configuration")
    tts_config: Optional[ProviderConfig] = Field(None, description="TTS provider configuration")
    stt_config: Optional[ProviderConfig] = Field(None, description="STT provider configuration")
    is_default: Optional[bool] = Field(None, description="Whether this agent should be the default")
    is_active: Optional[bool] = Field(None, description="Whether this agent is active")


class AgentResponse(BaseModel):
    """Response model for agent data."""
    
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    llm_provider: str
    tts_provider: str
    stt_provider: str
    llm_config: Dict[str, Any]
    tts_config: Dict[str, Any]
    stt_config: Dict[str, Any]
    is_default: bool
    is_active: bool
    is_system_agent: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """Response model for listing agents."""
    
    agents: List[AgentResponse]
    total: int


class AgentConfig(BaseModel):
    """Configuration model for agent runtime usage."""
    
    llm_provider: str
    tts_provider: str
    stt_provider: str
    llm_config: Dict[str, Any]
    tts_config: Dict[str, Any]
    stt_config: Dict[str, Any]
    
    @classmethod
    def from_agent_response(cls, agent: AgentResponse) -> 'AgentConfig':
        """Create AgentConfig from AgentResponse."""
        return cls(
            llm_provider=agent.llm_provider,
            tts_provider=agent.tts_provider,
            stt_provider=agent.stt_provider,
            llm_config=agent.llm_config,
            tts_config=agent.tts_config,
            stt_config=agent.stt_config
        )


class AgentSessionCreate(BaseModel):
    """Model for creating an agent session."""
    
    agent_id: UUID
    session_type: str = Field(..., description="Session type: 'voicebot', 'chat', 'tts', 'stt'")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    
    @validator('session_type')
    def validate_session_type(cls, v):
        """Validate session type."""
        valid_types = {'voicebot', 'chat', 'tts', 'stt'}
        if v not in valid_types:
            raise ValueError(f"Session type must be one of: {', '.join(valid_types)}")
        return v