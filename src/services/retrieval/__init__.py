"""
Retrieval Service Module

This package provides retrieval services including:
- Document indexing and search
- Vector and lexical retrieval
- Reranking and candidate combination
"""

from .retrieval_models import (
    StoredDocument,
    RetrievalCandidate,
    LexicalNamespaceIndex,
    LexicalIndex,
)
from .retrieval_logic import (
    _tokenize,
    _dense_candidates,
    _lexical_candidates,
    _combine_candidates,
    _truncate_for_reranker,
    _apply_reranker,
    _retrieve_contexts,
    _ultra_fast_retrieve_contexts,
    _ensure_collection,
    _bootstrap_documents,
)

__all__ = [
    "StoredDocument",
    "RetrievalCandidate",
    "LexicalNamespaceIndex",
    "LexicalIndex",
    "_tokenize",
    "_dense_candidates",
    "_lexical_candidates",
    "_combine_candidates",
    "_truncate_for_reranker",
    "_apply_reranker",
    "_retrieve_contexts",
    "_ultra_fast_retrieve_contexts",
    "_ensure_collection",
    "_bootstrap_documents",
]