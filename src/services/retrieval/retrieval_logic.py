"""
Retrieval Service Core Logic

This module contains the core retrieval logic including dense and lexical search.
"""

import asyncio
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple, AsyncIterator
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import CrossEncoder, SentenceTransformer

from .config import retrieval_config
from .retrieval_models import RetrievalCandidate, StoredDocument

# Cache for embeddings and retrieval results
_embedding_cache = {}
_retrieval_cache = {}


def _get_query_hash(text: str) -> str:
    """Generate a hash for query caching"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


@lru_cache(maxsize=1000)
def _cached_embedding(embedder: SentenceTransformer, text: str) -> List[float]:
    """Cache embeddings for common queries"""
    return embedder.encode(
        [text],
        show_progress_bar=False,
        normalize_embeddings=EMBED_NORMALIZE,
    )[0].tolist()

# Configuration constants
QDRANT_COLLECTION = retrieval_config.qdrant_collection
EMBED_MODEL_NAME = retrieval_config.embed_model_name
EMBED_BATCH_SIZE = retrieval_config.embed_batch_size
EMBED_NORMALIZE = retrieval_config.embed_normalize
DEFAULT_TOP_K = retrieval_config.default_top_k
MAX_TOP_K = retrieval_config.max_top_k
RAG_DENSE_CANDIDATE_COUNT = retrieval_config.dense_candidate_count
RAG_LEXICAL_CANDIDATE_COUNT = retrieval_config.lexical_candidate_count
RAG_RERANKER_MODEL = retrieval_config.reranker_model
RAG_ENABLE_RERANKER = retrieval_config.enable_reranker
RAG_RERANK_MAX_CANDIDATES = retrieval_config.rerank_max_candidates
RAG_RERANK_MAX_CHARS = retrieval_config.rerank_max_chars

_TOKEN_PATTERN = retrieval_config._token_pattern


def _tokenize(text: str) -> List[str]:
    """Tokenize text using the configured pattern."""
    return _TOKEN_PATTERN.findall(text.lower())


def _dense_candidates(
    embedder: SentenceTransformer,
    client: QdrantClient,
    text: str,
    top_k: int,
    namespace: Optional[str],
) -> List[RetrievalCandidate]:
    """Retrieve candidates using dense vector search."""
    if not text:
        return []
    dense_limit = max(top_k, RAG_DENSE_CANDIDATE_COUNT)
    vector = embedder.encode(
        [text],
        show_progress_bar=False,
        normalize_embeddings=EMBED_NORMALIZE,
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

    results = client.search(
        collection_name=QDRANT_COLLECTION,
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
    lexical_index: Any,
    documents: Dict[str, StoredDocument],
    text: str,
    top_k: int,
    namespace: Optional[str],
) -> List[RetrievalCandidate]:
    """Retrieve candidates using lexical BM25 search."""
    if not text:
        return []
    lexical_limit = max(top_k, RAG_LEXICAL_CANDIDATE_COUNT)
    results = lexical_index.search(text, namespace, lexical_limit)
    candidates: List[RetrievalCandidate] = []
    for doc_id, score in results:
        document = documents.get(doc_id)
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


def _combine_candidates(*candidate_lists: List[RetrievalCandidate]) -> List[RetrievalCandidate]:
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


def _truncate_for_reranker(text: str) -> str:
    """Truncate text for reranker input."""
    if len(text) <= RAG_RERANK_MAX_CHARS:
        return text
    truncated = text[:RAG_RERANK_MAX_CHARS]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip() + " ..."


async def _apply_reranker(
    reranker: Optional[CrossEncoder],
    question: str,
    candidates: List[RetrievalCandidate],
) -> List[RetrievalCandidate]:
    """Apply cross-encoder reranker to candidates."""
    ordered = sorted(candidates, key=lambda c: c.initial_score, reverse=True)
    if not ordered or not reranker or not RAG_ENABLE_RERANKER:
        return ordered

    limit = min(len(ordered), RAG_RERANK_MAX_CANDIDATES)
    inputs = []
    for candidate in ordered[:limit]:
        snippet = _truncate_for_reranker(candidate.text)
        inputs.append((question, snippet))

    loop = asyncio.get_running_loop()
    raw_scores = await loop.run_in_executor(None, lambda: reranker.predict(inputs))
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
    embedder: SentenceTransformer,
    client: QdrantClient,
    lexical_index: Any,
    documents: Dict[str, StoredDocument],
    text: str,
    top_k: int,
    namespace: Optional[str],
) -> Tuple[List[RetrievalCandidate], List[RetrievalCandidate]]:
    """Run dense and lexical search in parallel"""
    loop = asyncio.get_running_loop()
    
    # Run both searches in parallel
    dense_task = loop.run_in_executor(
        None, _dense_candidates, embedder, client, text, top_k, namespace
    )
    lexical_task = loop.run_in_executor(
        None, _lexical_candidates, lexical_index, documents, text, top_k, namespace
    )
    
    dense_candidates, lexical_candidates = await asyncio.gather(dense_task, lexical_task)
    return dense_candidates, lexical_candidates


async def _retrieve_contexts(
    embedder: SentenceTransformer,
    client: QdrantClient,
    reranker: Optional[CrossEncoder],
    lexical_index: Any,
    documents: Dict[str, StoredDocument],
    text: str,
    top_k: int,
    namespace: Optional[str],
) -> List[Any]:
    """Retrieve contexts using both dense and lexical search with reranking."""
    from services.rag.rag_models import QueryContext
    
    # Check cache first
    query_hash = _get_query_hash(text)
    if query_hash in _retrieval_cache:
        cached_time, cached_result = _retrieval_cache[query_hash]
        if time.time() - cached_time < 300:  # 5 minute TTL
            return cached_result

    # Run parallel retrieval
    dense_candidates, lexical_candidates = await _retrieve_parallel(
        embedder, client, lexical_index, documents, text, top_k, namespace
    )
    combined_candidates = _combine_candidates(dense_candidates, lexical_candidates)

    reranked = await _apply_reranker(reranker, text, combined_candidates)
    limited = reranked[:top_k]

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
                score=(
                    candidate.final_score
                    if candidate.final_score is not None
                    else candidate.initial_score
                ),
                metadata=metadata,
            )
        )
    
    # Cache the result
    _retrieval_cache[query_hash] = (time.time(), contexts)
    
    return contexts


async def _ensure_collection(embedder: SentenceTransformer, client: QdrantClient) -> None:
    """Ensure the Qdrant collection exists."""
    existing = client.get_collections()
    names = {collection.name for collection in existing.collections}
    if QDRANT_COLLECTION in names:
        return
    dim = embedder.get_sentence_embedding_dimension()
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
    )


def _bootstrap_documents(client: QdrantClient, lexical_index: Any, documents: Dict[str, StoredDocument]) -> None:
    """Bootstrap documents from Qdrant into the lexical index."""
    if not client:
        return

    documents.clear()
    lexical_index.clear()
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=QDRANT_COLLECTION,
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
                documents[document.id] = document
                lexical_index.upsert(document)
        if offset is None:
            break


async def _ultra_fast_retrieve_contexts(
    embedder: SentenceTransformer,
    client: QdrantClient,
    lexical_index: Any,
    documents: Dict[str, StoredDocument],
    text: str,
    namespace: Optional[str],
) -> List[Any]:
    """Ultra-fast context retrieval optimized for voicebot latency requirements"""
    from services.rag.rag_models import QueryContext
    
    # Check cache first with ultra-fast lookup
    query_hash = _get_query_hash(text)
    if query_hash in _retrieval_cache:
        cached_time, cached_result = _retrieval_cache[query_hash]
        if time.time() - cached_time < 300:  # 5 minute TTL
            return cached_result
    
    # Use ultra-minimal configuration for speed
    top_k = retrieval_config.ultra_top_k
    dense_limit = retrieval_config.ultra_dense_candidates
    
    # Fast embedding with minimal processing
    try:
        vector = embedder.encode(
            [text],
            show_progress_bar=False,
            normalize_embeddings=False,  # Skip normalization for speed
        )[0].tolist()
    except Exception:
        # Fallback: return empty contexts if embedding fails
        return []
    
    # Fast dense search only (skip lexical for ultra-low latency)
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
        results = client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vector,
            limit=dense_limit,
            query_filter=search_filter,
        )
    except Exception:
        # Fallback: return empty contexts if search fails
        return []
    
    contexts: List[QueryContext] = []
    for point in results[:top_k]:  # Take only top_k results
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
    _retrieval_cache[query_hash] = (time.time(), contexts)
    
    return contexts


async def _streaming_first_rag(
    embedder: SentenceTransformer,
    client: QdrantClient,
    lexical_index: Any,
    documents: Dict[str, StoredDocument],
    text: str,
    namespace: Optional[str],
) -> AsyncIterator[Any]:
    """Streaming-first RAG that starts LLM generation immediately while RAG processes in background"""
    from services.rag.rag_models import QueryContext
    
    # Start LLM generation immediately with minimal context
    yield QueryContext(
        text="",  # Empty context to start LLM immediately
        score=0.0,
        metadata={"retrieval_sources": ["streaming_first"]}
    )
    
    # Process RAG in background
    try:
        contexts = await _ultra_fast_retrieve_contexts(
            embedder, client, lexical_index, documents, text, namespace
        )
        
        # Yield actual contexts when ready
        for context in contexts:
            yield context
    except Exception:
        # If RAG fails, continue with empty context
        pass