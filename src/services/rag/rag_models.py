"""
RAG Service Data Models

This module contains all data models and Pydantic schemas for the RAG service.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from services.retrieval.config import retrieval_config

# Configuration constants
MAX_TEXT_LENGTH = retrieval_config.max_text_length
DEFAULT_TOP_K = retrieval_config.default_top_k
MAX_TOP_K = retrieval_config.max_top_k


@dataclass
class ConversationEntry:
    """In-memory representation of a conversation."""

    messages: List[Dict[str, Any]]
    expiry: float


@dataclass
class StoredDocument:
    """Materialised view of a Qdrant payload for fast lexical reranking."""

    id: str
    text: str
    namespace: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class RetrievalCandidate:
    """Container for retrieved chunks before/after reranking."""

    id: str
    text: str
    metadata: Dict[str, Any]
    initial_score: float
    sources: Set[str] = field(default_factory=set)
    final_score: Optional[float] = None


class DocumentPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    id: Optional[str] = Field(default=None)
    namespace: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BulkIngestRequest(BaseModel):
    documents: List[DocumentPayload]


class IngestResponse(BaseModel):
    inserted: int


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    top_k: Optional[int] = Field(default=DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    namespace: Optional[str] = None
    conversation_id: Optional[str] = None


class QueryContext(BaseModel):
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    question: str
    conversation_id: Optional[str]
    conversation: List[Dict[str, Any]]
    contexts: List[QueryContext]


class ConversationMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationUpdateRequest(BaseModel):
    conversation_id: str
    message: ConversationMessage


class ConversationStateResponse(BaseModel):
    conversation_id: str
    messages: List[Dict[str, Any]]