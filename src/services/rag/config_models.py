"""
Pydantic models for RAG configuration management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ProviderConfig(BaseModel):
    """Configuration for a single RAG provider."""

    provider: str = Field(..., description="Provider name (e.g., 'qdrant.internal', 'pinecone.io', 'rag.saas')")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")

    @validator("provider")
    def validate_provider(cls, v):
        """Validate provider name."""
        if not v or not v.strip():
            raise ValueError("Provider name cannot be empty")
        return v.strip()


class RagConfigCreate(BaseModel):
    """Model for creating a new RAG configuration."""

    name: str = Field(..., min_length=1, max_length=255, description="RAG configuration name")
    description: Optional[str] = Field(None, description="RAG configuration description")
    provider_config: ProviderConfig = Field(..., description="RAG provider configuration")
    is_default: bool = Field(False, description="Whether this RAG configuration should be the default")

    @validator("name")
    def validate_name(cls, v):
        """Validate RAG config name."""
        if not v or not v.strip():
            raise ValueError("RAG configuration name cannot be empty")
        return v.strip()


class RagConfigUpdate(BaseModel):
    """Model for updating an existing RAG configuration."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="RAG configuration name")
    description: Optional[str] = Field(None, description="RAG configuration description")
    provider_config: Optional[ProviderConfig] = Field(None, description="RAG provider configuration")
    is_default: Optional[bool] = Field(None, description="Whether this RAG configuration should be the default")
    is_active: Optional[bool] = Field(None, description="Whether this RAG configuration is active")


class RagConfigResponse(BaseModel):
    """Response model for RAG configuration data."""

    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    provider_type: str  # 'vectorbase', 'saas_rag'
    provider: str
    provider_config: Dict[str, Any]
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RagConfigListResponse(BaseModel):
    """Response model for listing RAG configurations."""

    configs: List[RagConfigResponse]
    total: int


class RagConfigRuntime(BaseModel):
    """Runtime configuration model for RAG usage."""

    provider_type: str
    provider: str
    provider_config: Dict[str, Any]

    @classmethod
    def from_rag_config_response(cls, rag_config: RagConfigResponse) -> "RagConfigRuntime":
        """Create RagConfigRuntime from RagConfigResponse."""
        return cls(
            provider_type=rag_config.provider_type,
            provider=rag_config.provider,
            provider_config=rag_config.provider_config,
        )
