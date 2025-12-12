"""
RAG Service Module

This package provides Retrieval-Augmented Generation services including:
- Document ingestion and vector storage
- Context retrieval with semantic and lexical search
- Conversation management
- LLM integration for generation
"""

from services.retrieval import (
    LexicalIndex,
    LexicalNamespaceIndex,
    _apply_reranker,
    _bootstrap_documents,
    _combine_candidates,
    _dense_candidates,
    _ensure_collection,
    _lexical_candidates,
    _retrieve_contexts,
    _tokenize,
    _truncate_for_reranker,
)

from .rag_models import (
    ConversationEntry,
    ConversationMessage,
    ConversationStateResponse,
    ConversationUpdateRequest,
    DocumentPayload,
    QueryContext,
    QueryRequest,
    QueryResponse,
    RetrievalCandidate,
    StoredDocument,
)
from .rag_routes import (
    app,
    append_conversation,
    get_conversation,
    lifespan,
    query_rag,
    reset_conversation,
)
from .rag_service import (
    _prune_conversations,
    _touch_conversation,
)
from .rag_state import RagState

__all__ = [
    "app",
    "lifespan",
    "RagState",
    "query_rag",
    "append_conversation",
    "get_conversation",
    "reset_conversation",
    "_prune_conversations",
    "_touch_conversation",
    # Re-exported from services.retrieval
    "_tokenize",
    "LexicalNamespaceIndex",
    "LexicalIndex",
    "_dense_candidates",
    "_lexical_candidates",
    "_combine_candidates",
    "_truncate_for_reranker",
    "_apply_reranker",
    "_retrieve_contexts",
    "_ensure_collection",
    "_bootstrap_documents",
    # Re-exported from .rag_models (for convenience)
    "ConversationEntry",
    "StoredDocument",
    "RetrievalCandidate",
    "DocumentPayload",
    "QueryRequest",
    "QueryContext",
    "QueryResponse",
    "ConversationMessage",
    "ConversationUpdateRequest",
    "ConversationStateResponse",
]
