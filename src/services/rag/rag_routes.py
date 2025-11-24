"""
RAG Service FastAPI Routes

This module contains the FastAPI route definitions for the RAG service.
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import CrossEncoder, SentenceTransformer

from .config import rag_config
from services.retrieval.config import retrieval_config
from .rag_models import (
    BulkIngestRequest,
    ConversationStateResponse,
    ConversationUpdateRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    StoredDocument,
)
from services.retrieval import _bootstrap_documents, _ensure_collection, _retrieve_contexts
from .rag_service import _touch_conversation, _prune_conversations
from .rag_state import RagState
from .chatbot_routes import router as chatbot_router

LOGGER = logging.getLogger("rag_service")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# Configuration constants
EMBED_MODEL_NAME = retrieval_config.embed_model_name
EMBED_BATCH_SIZE = retrieval_config.embed_batch_size
EMBED_NORMALIZE = retrieval_config.embed_normalize
DEFAULT_TOP_K = retrieval_config.default_top_k
RAG_ENABLE_RERANKER = retrieval_config.enable_reranker
RAG_RERANKER_MODEL = retrieval_config.reranker_model
QDRANT_COLLECTION = retrieval_config.qdrant_collection
CONV_MAX_RETURN_MESSAGES = rag_config.conv_max_return_messages


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan manager for RAG service initialization and cleanup."""
    LOGGER.info("Loading embedding model %s", EMBED_MODEL_NAME)
    embedder = SentenceTransformer(EMBED_MODEL_NAME)

    LOGGER.info("Connecting to Qdrant at %s:%d", retrieval_config.qdrant_host, retrieval_config.qdrant_port)
    client = QdrantClient(
        host=retrieval_config.qdrant_host,
        port=retrieval_config.qdrant_port,
        https=retrieval_config.qdrant_use_tls,
        api_key=retrieval_config.qdrant_api_key,
    )

    reranker: CrossEncoder | None = None
    if RAG_ENABLE_RERANKER:
        try:
            LOGGER.info("Loading reranker model %s", RAG_RERANKER_MODEL)
            reranker = CrossEncoder(RAG_RERANKER_MODEL)
        except Exception as exc:
            LOGGER.warning("Failed to load reranker model %s: %s", RAG_RERANKER_MODEL, exc)
            reranker = None

    rag_state: RagState = app.state.rag
    rag_state.embedder = embedder
    rag_state.client = client
    rag_state.reranker = reranker
    await _ensure_collection(rag_state.embedder, rag_state.client)
    try:
        _bootstrap_documents(rag_state.client, rag_state.lexical_index, rag_state.documents)
        LOGGER.info("Bootstrapped %d document chunks into lexical index", len(rag_state.documents))
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning("Failed to bootstrap lexical index from Qdrant: %s", exc)
    LOGGER.info("RAG service ready")

    yield

    rag_state.embedder = None
    rag_state.client = None
    rag_state.reranker = None
    rag_state.conversations.clear()
    rag_state.clear_documents()


app = FastAPI(title="Voicebot RAG Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.rag = RagState()

# Include chatbot routes
app.include_router(chatbot_router, prefix="/rag", tags=["chatbot"])


@app.post("/knowledge/documents", response_model=IngestResponse)
async def ingest_documents(request: BulkIngestRequest) -> IngestResponse:
    """Ingest documents into the knowledge base."""
    if not request.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    rag_state: RagState = app.state.rag
    async with rag_state.lock:
        await rag_state.ensure_ready()
        assert rag_state.embedder and rag_state.client
        texts = [doc.text for doc in request.documents]
        vectors = rag_state.embedder.encode(
            texts,
            batch_size=EMBED_BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=EMBED_NORMALIZE,
        )
        points = []
        stored_documents: List[StoredDocument] = []
        for doc, vector in zip(request.documents, vectors):
            point_id = doc.id or str(uuid.uuid4())
            payload = dict(doc.metadata)
            payload.update({"text": doc.text})
            if doc.namespace:
                payload["namespace"] = doc.namespace
            points.append(
                qmodels.PointStruct(id=point_id, vector=vector.tolist(), payload=payload)
            )

        rag_state.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
        for doc, point in zip(request.documents, points):
            payload = dict(point.payload or {})
            text = (payload.get("text") or "").strip()
            if not text:
                continue
            metadata = {k: v for k, v in payload.items() if k != "text"}
            stored_documents.append(
                StoredDocument(
                    id=str(point.id),
                    text=text,
                    namespace=doc.namespace or metadata.get("namespace"),
                    metadata=metadata,
                )
            )
        rag_state.register_documents(stored_documents)
    return IngestResponse(inserted=len(points))


@app.post("/rag/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest) -> QueryResponse:
    """Query the RAG service for relevant contexts."""
    rag_state: RagState = app.state.rag
    async with rag_state.lock:
        await rag_state.ensure_ready()
        conversation_messages: List[Dict[str, Any]] = []
        if request.conversation_id:
            message = {
                "role": "user",
                "content": request.question,
                "metadata": {},
                "created_at": time.time(),
            }
            conversation_messages = await _touch_conversation(
                rag_state, request.conversation_id, message
            )
        contexts = await _retrieve_contexts(
            rag_state.embedder,
            rag_state.client,
            rag_state.reranker,
            rag_state.lexical_index,
            rag_state.documents,
            text=request.question,
            top_k=request.top_k or DEFAULT_TOP_K,
            namespace=request.namespace,
        )

    return QueryResponse(
        question=request.question,
        conversation_id=request.conversation_id,
        conversation=conversation_messages,
        contexts=contexts,
    )


@app.post("/conversation/message", response_model=ConversationStateResponse)
async def append_conversation(request: ConversationUpdateRequest) -> ConversationStateResponse:
    """Append a message to a conversation."""
    if not request.conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")

    rag_state: RagState = app.state.rag
    async with rag_state.lock:
        await rag_state.ensure_ready()
        message = {
            "role": request.message.role,
            "content": request.message.content,
            "metadata": request.message.metadata,
            "created_at": time.time(),
        }
        messages = await _touch_conversation(rag_state, request.conversation_id, message)
    return ConversationStateResponse(conversation_id=request.conversation_id, messages=messages)


@app.get("/conversation/{conversation_id}", response_model=ConversationStateResponse)
async def get_conversation(conversation_id: str) -> ConversationStateResponse:
    """Get the current state of a conversation."""
    rag_state: RagState = app.state.rag
    async with rag_state.lock:
        await rag_state.ensure_ready()
        await _prune_conversations(rag_state)
        entry = rag_state.conversations.get(conversation_id)
        messages = entry.messages[-CONV_MAX_RETURN_MESSAGES:] if entry else []
    return ConversationStateResponse(conversation_id=conversation_id, messages=messages)


@app.delete("/conversation/{conversation_id}", response_model=ConversationStateResponse)
async def reset_conversation(conversation_id: str) -> ConversationStateResponse:
    """Reset a conversation (clear all messages)."""
    rag_state: RagState = app.state.rag
    async with rag_state.lock:
        await rag_state.ensure_ready()
        rag_state.conversations.pop(conversation_id, None)
    return ConversationStateResponse(conversation_id=conversation_id, messages=[])