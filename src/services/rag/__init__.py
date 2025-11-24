"""
RAG Service Module

This package provides Retrieval-Augmented Generation services including:
- Document ingestion and vector storage
- Context retrieval with semantic and lexical search
- Conversation management
- LLM integration for generation
"""

from .rag_models import (
    ConversationEntry,
    StoredDocument,
    RetrievalCandidate,
    DocumentPayload,
    BulkIngestRequest,
    IngestResponse,
    QueryRequest,
    QueryContext,
    QueryResponse,
    ConversationMessage,
    ConversationUpdateRequest,
    ConversationStateResponse,
)
from .rag_state import RagState
from services.retrieval import (
    _tokenize,
    LexicalNamespaceIndex,
    LexicalIndex,
    _dense_candidates,
    _lexical_candidates,
    _combine_candidates,
    _truncate_for_reranker,
    _apply_reranker,
    _retrieve_contexts,
    _ensure_collection,
    _bootstrap_documents,
)
from .rag_routes import (
    app,
    lifespan,
    ingest_documents,
    query_rag,
    append_conversation,
    get_conversation,
    reset_conversation,
)
from .rag_service import (
    _prune_conversations,
    _touch_conversation,
)

__all__ = [
    "app",
    "lifespan",
    "RagState",
    "ingest_documents",
    "query_rag",
    "append_conversation",
    "get_conversation",
    "reset_conversation",
    "_prune_conversations",
    "_touch_conversation",
]