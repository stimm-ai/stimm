"""
RAG Service State Management

This module handles the application state and conversation management for the RAG service.
"""

import asyncio
from collections import OrderedDict
from typing import Any, Dict, Iterable

from qdrant_client import QdrantClient

from services.embeddings import CrossEncoder, SentenceTransformer

from .rag_models import StoredDocument

# LexicalIndex is imported locally where needed to avoid circular imports


class RagState:
    """Maintains the state of the RAG service including embeddings, client, and conversations."""

    def __init__(self) -> None:
        self.embedder: SentenceTransformer | None = None
        self.client: QdrantClient | None = None
        self.reranker: CrossEncoder | None = None
        from services.retrieval import LexicalIndex

        self.lexical_index = LexicalIndex()
        self.documents: Dict[str, StoredDocument] = {}
        self.conversations: "OrderedDict[str, Any]" = OrderedDict()
        self.lock = asyncio.Lock()
        self.retrieval_engine = None  # Optional RetrievalEngine instance for per‑agent RAG
        self.skip_retrieval = False  # If True, skip retrieval entirely (no RAG config)

    async def ensure_ready(self) -> None:
        """Ensure the RAG service is properly initialized."""
        if self.embedder and self.client:
            return
        raise RuntimeError("RAG service not initialised correctly")

    def register_document(self, document: StoredDocument) -> None:
        """Register a document in the lexical index."""
        self.documents[document.id] = document
        self.lexical_index.upsert(document)

    def register_documents(self, documents: Iterable[StoredDocument]) -> None:
        """Register multiple documents in the lexical index."""
        for document in documents:
            self.register_document(document)

    def clear_documents(self) -> None:
        """Clear all documents from the lexical index."""
        self.documents.clear()
        self.lexical_index.clear()
