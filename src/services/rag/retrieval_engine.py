"""
Retrieval Engine for RAG configurations.

This module provides a configurable retrieval engine that can be instantiated
with a specific RAG configuration (provider, collection, embedding model, etc.)
to support per‑agent RAG settings.
"""

import asyncio
import hashlib
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from services.embeddings import CrossEncoder, SentenceTransformer
from services.retrieval.config import retrieval_config as global_retrieval_config
from services.retrieval.retrieval_models import RetrievalCandidate, StoredDocument


class RetrievalEngine:
    """Engine for retrieving contexts using a specific RAG configuration."""

    def __init__(
        self,
        *,
        collection_name: Optional[str] = None,
        embed_model_name: Optional[str] = None,
        embed_normalize: Optional[bool] = None,
        top_k: Optional[int] = None,
        dense_candidate_count: Optional[int] = None,
        lexical_candidate_count: Optional[int] = None,
        reranker_model: Optional[str] = None,
        enable_reranker: Optional[bool] = None,
        rerank_max_candidates: Optional[int] = None,
        rerank_max_chars: Optional[int] = None,
        ultra_low_latency_mode: Optional[bool] = None,
        ultra_top_k: Optional[int] = None,
        ultra_dense_candidates: Optional[int] = None,
        qdrant_host: Optional[str] = None,
        qdrant_port: Optional[int] = None,
        qdrant_use_tls: Optional[bool] = None,
        qdrant_api_key: Optional[str] = None,
    ):
        """
        Initialize retrieval engine with optional overrides.
        Any parameter left as None will fall back to the global retrieval config.
        """
        self.collection_name = collection_name or global_retrieval_config.qdrant_collection
        self.embed_model_name = embed_model_name or global_retrieval_config.embed_model_name
        self.embed_normalize = embed_normalize if embed_normalize is not None else global_retrieval_config.embed_normalize
        self.top_k = top_k or global_retrieval_config.default_top_k
        self.dense_candidate_count = dense_candidate_count or global_retrieval_config.dense_candidate_count
        self.lexical_candidate_count = lexical_candidate_count or global_retrieval_config.lexical_candidate_count
        self.reranker_model = reranker_model or global_retrieval_config.reranker_model
        self.enable_reranker = enable_reranker if enable_reranker is not None else global_retrieval_config.enable_reranker
        self.rerank_max_candidates = rerank_max_candidates or global_retrieval_config.rerank_max_candidates
        self.rerank_max_chars = rerank_max_chars or global_retrieval_config.rerank_max_chars
        self.ultra_low_latency_mode = ultra_low_latency_mode if ultra_low_latency_mode is not None else global_retrieval_config.ultra_low_latency_mode
        self.ultra_top_k = ultra_top_k or global_retrieval_config.ultra_top_k
        self.ultra_dense_candidates = ultra_dense_candidates or global_retrieval_config.ultra_dense_candidates

        # Qdrant connection parameters
        self.qdrant_host = qdrant_host or global_retrieval_config.qdrant_host
        self.qdrant_port = qdrant_port or global_retrieval_config.qdrant_port
        self.qdrant_use_tls = qdrant_use_tls if qdrant_use_tls is not None else global_retrieval_config.qdrant_use_tls
        self.qdrant_api_key = qdrant_api_key or global_retrieval_config.qdrant_api_key

        # Caches
        self._embedding_cache = {}
        self._retrieval_cache = {}
        self._embedder: Optional[SentenceTransformer] = None
        self._client: Optional[QdrantClient] = None
        self._reranker: Optional[CrossEncoder] = None
        self._lexical_index = None
        self._documents: Dict[str, StoredDocument] = {}

    @property
    def embedder(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedder is None:
            self._embedder = SentenceTransformer(self.embed_model_name)
        return self._embedder

    @property
    def client(self) -> QdrantClient:
        """Lazy connect to Qdrant."""
        if self._client is None:
            self._client = QdrantClient(
                host=self.qdrant_host,
                port=self.qdrant_port,
                https=self.qdrant_use_tls,
                api_key=self.qdrant_api_key,
            )
        return self._client

    @property
    def reranker(self) -> Optional[CrossEncoder]:
        """Lazy load the reranker model if enabled."""
        if self._reranker is None and self.enable_reranker and self.reranker_model:
            try:
                self._reranker = CrossEncoder(self.reranker_model)
            except Exception:
                self._reranker = None
        return self._reranker

    @property
    def lexical_index(self):
        """Lazy create a lexical index."""
        if self._lexical_index is None:
            from services.retrieval import LexicalIndex

            self._lexical_index = LexicalIndex()
        return self._lexical_index

    def _get_query_hash(self, text: str) -> str:
        """Generate a hash for query caching."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @lru_cache(maxsize=1000)
    def _cached_embedding(self, text: str) -> List[float]:
        """Cache embeddings for common queries."""
        return self.embedder.encode(
            [text],
            show_progress_bar=False,
            normalize_embeddings=self.embed_normalize,
        )[0].tolist()

    def _dense_candidates(
        self,
        text: str,
        top_k: int,
        namespace: Optional[str],
    ) -> List[RetrievalCandidate]:
        """Retrieve candidates using dense vector search."""
        if not text:
            return []
        dense_limit = max(top_k, self.dense_candidate_count)
        vector = self.embedder.encode(
            [text],
            show_progress_bar=False,
            normalize_embeddings=self.embed_normalize,
        )[0].tolist()

        search_filter: Optional[qmodels.Filter] = None
        if namespace:
            search_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="namespace",
                        match=qmodels.MatchValue(value=namespace),
                    )
                ]
            )

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=dense_limit,
            query_filter=search_filter,
        )

        candidates: List[RetrievalCandidate] = []
        for point in results:
            payload = point.payload or {}
            text_value = (payload.get("text") or "").strip()
            metadata = {k: v for k, v in payload.items() if k != "text"}
            candidates.append(
                RetrievalCandidate(
                    id=str(point.id),
                    text=text_value,
                    metadata=metadata,
                    initial_score=float(point.score or 0.0),
                    sources={"dense"},
                )
            )
        return candidates

    def _lexical_candidates(
        self,
        text: str,
        top_k: int,
        namespace: Optional[str],
    ) -> List[RetrievalCandidate]:
        """Retrieve candidates using lexical BM25 search."""
        if not text:
            return []
        lexical_limit = max(top_k, self.lexical_candidate_count)
        results = self.lexical_index.search(text, namespace, lexical_limit)
        candidates: List[RetrievalCandidate] = []
        for doc_id, score in results:
            document = self._documents.get(doc_id)
            if not document:
                continue
            candidates.append(
                RetrievalCandidate(
                    id=doc_id,
                    text=document.text,
                    metadata=dict(document.metadata),
                    initial_score=score,
                    sources={"lexical"},
                )
            )
        return candidates

    def _combine_candidates(self, *candidate_lists: List[RetrievalCandidate]) -> List[RetrievalCandidate]:
        """Combine and deduplicate candidates from multiple retrieval methods."""
        combined: Dict[str, RetrievalCandidate] = {}
        for candidates in candidate_lists:
            for candidate in candidates:
                existing = combined.get(candidate.id)
                if existing:
                    existing.sources.update(candidate.sources)
                    if candidate.initial_score > existing.initial_score:
                        existing.initial_score = candidate.initial_score
                        existing.metadata = candidate.metadata
                        existing.text = candidate.text
                    continue
                combined[candidate.id] = candidate
        return list(combined.values())

    def _truncate_for_reranker(self, text: str) -> str:
        """Truncate text for reranker input."""
        if len(text) <= self.rerank_max_chars:
            return text
        truncated = text[: self.rerank_max_chars]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated.rstrip() + " ..."

    async def _apply_reranker(
        self,
        question: str,
        candidates: List[RetrievalCandidate],
    ) -> List[RetrievalCandidate]:
        """Apply cross-encoder reranker to candidates."""
        ordered = sorted(candidates, key=lambda c: c.initial_score, reverse=True)
        if not ordered or not self.reranker or not self.enable_reranker:
            return ordered

        limit = min(len(ordered), self.rerank_max_candidates)
        inputs = []
        for candidate in ordered[:limit]:
            snippet = self._truncate_for_reranker(candidate.text)
            inputs.append((question, snippet))

        loop = asyncio.get_running_loop()
        raw_scores = await loop.run_in_executor(None, lambda: self.reranker.predict(inputs))
        if raw_scores is None:
            raw_scores = []
        if hasattr(raw_scores, "tolist"):  # numpy arrays
            scores = raw_scores.tolist()
        elif isinstance(raw_scores, (list, tuple)):
            scores = list(raw_scores)
        else:  # pragma: no cover - defensive fallback
            scores = [raw_scores]

        for idx, score in enumerate(scores[:limit]):
            ordered[idx].final_score = float(score)

        ordered.sort(
            key=lambda c: c.final_score if c.final_score is not None else c.initial_score,
            reverse=True,
        )
        return ordered

    async def _retrieve_parallel(
        self,
        text: str,
        top_k: int,
        namespace: Optional[str],
    ) -> Tuple[List[RetrievalCandidate], List[RetrievalCandidate]]:
        """Run dense and lexical search in parallel."""
        loop = asyncio.get_running_loop()
        dense_task = loop.run_in_executor(None, self._dense_candidates, text, top_k, namespace)
        lexical_task = loop.run_in_executor(None, self._lexical_candidates, text, top_k, namespace)
        dense_candidates, lexical_candidates = await asyncio.gather(dense_task, lexical_task)
        return dense_candidates, lexical_candidates

    async def retrieve_contexts(
        self,
        text: str,
        top_k: Optional[int] = None,
        namespace: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Any]:
        """
        Retrieve contexts using both dense and lexical search with reranking.

        Returns:
            List of QueryContext objects (from services.rag.rag_models).
        """
        from services.rag.rag_models import QueryContext

        effective_top_k = top_k or self.top_k

        # Check cache first
        if use_cache:
            query_hash = self._get_query_hash(text)
            cached = self._retrieval_cache.get(query_hash)
            if cached:
                cached_time, cached_result = cached
                if time.time() - cached_time < 300:  # 5 minute TTL
                    return cached_result

        # Run parallel retrieval
        dense_candidates, lexical_candidates = await self._retrieve_parallel(text, effective_top_k, namespace)
        combined_candidates = self._combine_candidates(dense_candidates, lexical_candidates)

        reranked = await self._apply_reranker(text, combined_candidates)
        limited = reranked[:effective_top_k]

        contexts: List[QueryContext] = []
        for candidate in limited:
            metadata = dict(candidate.metadata)
            metadata.setdefault("doc_id", candidate.id)
            metadata["retrieval_sources"] = sorted(candidate.sources)
            metadata["initial_score"] = candidate.initial_score
            if candidate.final_score is not None:
                metadata["reranker_score"] = candidate.final_score
            contexts.append(
                QueryContext(
                    text=candidate.text,
                    score=(candidate.final_score if candidate.final_score is not None else candidate.initial_score),
                    metadata=metadata,
                )
            )

        # Cache the result
        if use_cache:
            query_hash = self._get_query_hash(text)
            self._retrieval_cache[query_hash] = (time.time(), contexts)

        return contexts

    async def ultra_fast_retrieve_contexts(
        self,
        text: str,
        namespace: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Any]:
        """
        Ultra-fast context retrieval optimized for stimm latency requirements.
        Uses dense search only and skips lexical/reranker.
        """
        from services.rag.rag_models import QueryContext

        # Check cache first
        if use_cache:
            query_hash = self._get_query_hash(text)
            cached = self._retrieval_cache.get(query_hash)
            if cached:
                cached_time, cached_result = cached
                if time.time() - cached_time < 300:
                    return cached_result

        # Fast embedding with minimal processing
        try:
            vector = self.embedder.encode(
                [text],
                show_progress_bar=False,
                normalize_embeddings=False,  # Skip normalization for speed
            )[0].tolist()
        except Exception:
            return []

        # Fast dense search only
        search_filter: Optional[qmodels.Filter] = None
        if namespace:
            search_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="namespace",
                        match=qmodels.MatchValue(value=namespace),
                    )
                ]
            )

        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=self.ultra_dense_candidates,
                query_filter=search_filter,
            )
        except Exception:
            return []

        contexts: List[QueryContext] = []
        for point in results[: self.ultra_top_k]:
            payload = point.payload or {}
            text_value = (payload.get("text") or "").strip()
            if not text_value:
                continue
            metadata = {k: v for k, v in payload.items() if k != "text"}
            metadata.setdefault("doc_id", str(point.id))
            metadata["retrieval_sources"] = ["dense_ultra_fast"]
            metadata["initial_score"] = float(point.score or 0.0)
            contexts.append(
                QueryContext(
                    text=text_value,
                    score=float(point.score or 0.0),
                    metadata=metadata,
                )
            )

        # Cache the result
        if use_cache:
            query_hash = self._get_query_hash(text)
            self._retrieval_cache[query_hash] = (time.time(), contexts)

        return contexts

    async def ensure_collection(self) -> None:
        """Ensure the Qdrant collection exists."""
        existing = self.client.get_collections()
        names = {collection.name for collection in existing.collections}
        if self.collection_name in names:
            return
        dim = self.embedder.get_sentence_embedding_dimension()
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
        )

    def bootstrap_documents(self) -> None:
        """Bootstrap documents from Qdrant into the lexical index."""
        if not self.client:
            return

        self._documents.clear()
        self.lexical_index.clear()
        offset = None
        while True:
            batch, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not batch:
                break
            new_documents: List[StoredDocument] = []
            for point in batch:
                payload = point.payload or {}
                text = (payload.get("text") or "").strip()
                if not text:
                    continue
                metadata = {k: v for k, v in payload.items() if k != "text"}
                new_documents.append(
                    StoredDocument(
                        id=str(point.id),
                        text=text,
                        namespace=metadata.get("namespace"),
                        metadata=metadata,
                    )
                )
            if new_documents:
                for document in new_documents:
                    self._documents[document.id] = document
                    self.lexical_index.upsert(document)
            if offset is None:
                break
