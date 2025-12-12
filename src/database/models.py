"""
Database models for stimm application.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func

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
    """Agent model representing a stimm configuration."""

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

    # System prompt (instructions)
    system_prompt = Column(Text)

    # RAG configuration (optional)
    rag_config_id = Column(UUID(as_uuid=True), ForeignKey("rag_configs.id", ondelete="SET NULL"), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_agents_user_id", "user_id"),
        Index("idx_agents_is_default", "is_default", postgresql_where=(is_default.is_(True))),
        Index("idx_agents_is_active", "is_active", postgresql_where=(is_active.is_(True))),
        Index("idx_agents_user_default", "user_id", unique=True, postgresql_where=(is_default.is_(True))),
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
            "system_prompt": self.system_prompt,
            "rag_config_id": str(self.rag_config_id) if self.rag_config_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentSession(Base):
    """Agent session model for runtime agent switching."""

    __tablename__ = "agent_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    session_type = Column(String(50), nullable=False)  # 'stimm', 'chat', 'tts', 'stt'
    ip_address = Column(String(45))  # IPv6 support
    user_agent = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_agent_sessions_user_agent", "user_id", "agent_id"),
        Index("idx_agent_sessions_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<AgentSession(id={self.id}, type='{self.session_type}', agent='{self.agent_id}')>"


class RagConfig(Base):
    """RAG configuration model representing a retrievable knowledge base."""

    __tablename__ = "rag_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    provider_type = Column(String(20), nullable=False)  # 'vectorbase', 'saas_rag'
    provider = Column(String(50), nullable=False)  # e.g., 'qdrant.internal', 'pinecone.io', 'rag.saas'
    provider_config = Column(JSONB, nullable=False, default=dict)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_rag_configs_user_id", "user_id"),
        Index("idx_rag_configs_is_default", "is_default", postgresql_where=(is_default.is_(True))),
        Index("idx_rag_configs_user_default", "user_id", unique=True, postgresql_where=(is_default.is_(True))),
    )

    def __repr__(self):
        return f"<RagConfig(id={self.id}, name='{self.name}', provider='{self.provider}')>"

    def to_dict(self):
        """Convert RAG config to dictionary for API responses."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "provider_type": self.provider_type,
            "provider": self.provider,
            "provider_config": self.provider_config,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Document(Base):
    """Document model for tracking ingested documents in RAG configurations."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rag_config_id = Column(UUID(as_uuid=True), ForeignKey("rag_configs.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # 'pdf', 'docx', 'markdown', 'text'
    file_size_bytes = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=False)
    chunk_ids = Column(ARRAY(Text), nullable=False)  # Array of Qdrant point IDs
    namespace = Column(String(255), nullable=True)
    doc_metadata = Column(JSONB, nullable=True)  # Renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_documents_rag_config", "rag_config_id"),
        Index("idx_documents_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', type='{self.file_type}')>"

    def to_dict(self):
        """Convert document to dictionary for API responses."""
        return {
            "id": str(self.id),
            "rag_config_id": str(self.rag_config_id),
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "chunk_count": self.chunk_count,
            "chunk_ids": self.chunk_ids,
            "namespace": self.namespace,
            "metadata": self.doc_metadata,  # Return as 'metadata' in API
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
