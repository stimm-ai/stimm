"""
Retrieval Service Data Models

This module contains data models for the retrieval service.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from rank_bm25 import BM25Okapi


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


class LexicalNamespaceIndex:
    """Namespace-scoped BM25 index."""

    def __init__(self) -> None:
        self.doc_ids: List[str] = []
        self.tokens: List[List[str]] = []
        self._bm25: Optional[BM25Okapi] = None

    def _rebuild(self) -> None:
        """Rebuild the BM25 index."""
        self._bm25 = BM25Okapi(self.tokens) if self.tokens else None

    def upsert(self, doc_id: str, tokens: List[str]) -> None:
        """Upsert a document into the index."""
        for idx, existing_id in enumerate(self.doc_ids):
            if existing_id == doc_id:
                self.tokens[idx] = tokens
                self._rebuild()
                return
        self.doc_ids.append(doc_id)
        self.tokens.append(tokens)
        self._rebuild()

    def remove(self, doc_id: str) -> None:
        """Remove a document from the index."""
        for idx, existing_id in enumerate(self.doc_ids):
            if existing_id == doc_id:
                self.doc_ids.pop(idx)
                self.tokens.pop(idx)
                self._rebuild()
                return

    def search(self, query_tokens: List[str], limit: int) -> List[Tuple[str, float]]:
        """Search the index with query tokens."""
        if not self._bm25 or not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(
            ((self.doc_ids[i], float(scores[i])) for i in range(len(scores))),
            key=lambda item: item[1],
            reverse=True,
        )
        results: List[Tuple[str, float]] = []
        for doc_id, score in ranked:
            if score <= 0:
                continue
            results.append((doc_id, score))
            if len(results) >= limit:
                break
        return results

    def clear(self) -> None:
        """Clear the index."""
        self.doc_ids.clear()
        self.tokens.clear()
        self._bm25 = None


class LexicalIndex:
    """Maintains BM25 indices per namespace for lexical recall."""

    _DEFAULT_NAMESPACE = "__default__"

    def __init__(self) -> None:
        self._namespaces: Dict[str, LexicalNamespaceIndex] = {}

    def _key(self, namespace: Optional[str]) -> str:
        """Get the namespace key."""
        return namespace or self._DEFAULT_NAMESPACE

    def upsert(self, document: StoredDocument) -> None:
        """Upsert a document into the appropriate namespace index."""
        from .retrieval_logic import _tokenize
        tokens = _tokenize(document.text)
        if not tokens:
            return
        index = self._namespaces.setdefault(self._key(document.namespace), LexicalNamespaceIndex())
        index.upsert(document.id, tokens)

    def remove(self, doc_id: str, namespace: Optional[str]) -> None:
        """Remove a document from the appropriate namespace index."""
        index = self._namespaces.get(self._key(namespace))
        if index:
            index.remove(doc_id)

    def search(self, text: str, namespace: Optional[str], limit: int) -> List[Tuple[str, float]]:
        """Search across namespaces for matching documents."""
        from .retrieval_logic import _tokenize
        tokens = _tokenize(text)
        if not tokens:
            return []
        namespaces = [self._key(namespace)] if namespace else list(self._namespaces.keys())
        combined: Dict[str, float] = {}
        for key in namespaces:
            index = self._namespaces.get(key)
            if not index:
                continue
            for doc_id, score in index.search(tokens, limit):
                if doc_id not in combined or score > combined[doc_id]:
                    combined[doc_id] = score
        ranked = sorted(combined.items(), key=lambda item: item[1], reverse=True)
        return ranked[:limit]

    def clear(self) -> None:
        """Clear all namespace indices."""
        for index in self._namespaces.values():
            index.clear()
        self._namespaces.clear()