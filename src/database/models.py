"""
Database models for voicebot application.
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from .session import Base

class User(Base):
    """User model for future IAM support."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Agent(Base):
    """Agent model representing a voicebot configuration."""
    
    __tablename__ = "agents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Provider selections
    llm_provider = Column(String(50), nullable=False)
    tts_provider = Column(String(50), nullable=False)
    stt_provider = Column(String(50), nullable=False)
    
    # Provider configurations
    llm_config = Column(JSONB, nullable=False, default=dict)
    tts_config = Column(JSONB, nullable=False, default=dict)
    stt_config = Column(JSONB, nullable=False, default=dict)
    
    # Agent settings
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_system_agent = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_agents_user_id', 'user_id'),
        Index('idx_agents_is_default', 'is_default', postgresql_where=(is_default.is_(True))),
        Index('idx_agents_is_active', 'is_active', postgresql_where=(is_active.is_(True))),
        Index('idx_agents_user_default', 'user_id', unique=True, 
              postgresql_where=(is_default.is_(True))),
    )

    def __repr__(self):
        return f"<Agent(id={self.id}, name='{self.name}', llm='{self.llm_provider}')>"

    def to_dict(self):
        """Convert agent to dictionary for API responses."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "llm_provider": self.llm_provider,
            "tts_provider": self.tts_provider,
            "stt_provider": self.stt_provider,
            "llm_config": self.llm_config,
            "tts_config": self.tts_config,
            "stt_config": self.stt_config,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "is_system_agent": self.is_system_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentSession(Base):
    """Agent session model for runtime agent switching."""
    
    __tablename__ = "agent_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    session_type = Column(String(50), nullable=False)  # 'voicebot', 'chat', 'tts', 'stt'
    ip_address = Column(String(45))  # IPv6 support
    user_agent = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('idx_agent_sessions_user_agent', 'user_id', 'agent_id'),
        Index('idx_agent_sessions_expires', 'expires_at'),
    )

    def __repr__(self):
        return f"<AgentSession(id={self.id}, type='{self.session_type}', agent='{self.agent_id}')>"