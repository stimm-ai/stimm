"""
RAG Chatbot Interface Routes

This module provides a web interface for interacting with the RAG system
through a modern chatbot interface with streaming responses.
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.retrieval import _bootstrap_documents, _ensure_collection
from services.retrieval.config import retrieval_config

from .chatbot_service import chatbot_service
from .rag_state import RagState

LOGGER = logging.getLogger("rag_chatbot")

# Create router
router = APIRouter()

# Global RAG state
rag_state = None


async def initialize_rag_state():
    """Initialize the RAG state for chatbot functionality - uses preloaded state when available"""
    global rag_state

    if rag_state is None:
        # Try to use preloaded RAG state first
        from .rag_preloader import rag_preloader

        if rag_preloader.is_preloaded and rag_preloader.rag_state is not None:
            # Use preloaded state
            rag_state = rag_preloader.rag_state
            LOGGER.info("✅ Using preloaded RAG state")
        else:
            # Fallback to lazy initialization
            LOGGER.warning("⚠️ Using fallback lazy RAG initialization (preloading not available)")
            rag_state = await _lazy_initialize_rag_state()

    return rag_state


async def _lazy_initialize_rag_state():
    """Fallback lazy initialization of RAG state (original implementation)"""
    LOGGER.info("Initializing RAG state for chatbot...")

    try:
        # Import required modules
        from qdrant_client import QdrantClient

        from services.embeddings import CrossEncoder, SentenceTransformer

        # Initialize RAG state
        rag_state = RagState()

        # Load embedding model
        embed_model_name = retrieval_config.embed_model_name
        LOGGER.info(f"Loading embedding model {embed_model_name}")
        rag_state.embedder = SentenceTransformer(embed_model_name)

        # Connect to Qdrant
        LOGGER.info(f"Connecting to Qdrant at {retrieval_config.qdrant_host}:{retrieval_config.qdrant_port}")
        rag_state.client = QdrantClient(
            host=retrieval_config.qdrant_host,
            port=retrieval_config.qdrant_port,
            https=retrieval_config.qdrant_use_tls,
            api_key=retrieval_config.qdrant_api_key,
        )

        # Initialize reranker if enabled
        if retrieval_config.enable_reranker:
            try:
                LOGGER.info(f"Loading reranker model {retrieval_config.reranker_model}")
                rag_state.reranker = CrossEncoder(retrieval_config.reranker_model)
            except Exception as exc:
                LOGGER.warning(f"Failed to load reranker model: {exc}")
                rag_state.reranker = None

        # Ensure collection exists and bootstrap documents
        await _ensure_collection(rag_state.embedder, rag_state.client)
        try:
            _bootstrap_documents(rag_state.client, rag_state.lexical_index, rag_state.documents)
            LOGGER.info(f"Bootstrapped {len(rag_state.documents)} document chunks into lexical index")
        except Exception as exc:
            LOGGER.warning(f"Failed to bootstrap lexical index: {exc}")

        LOGGER.info("RAG state initialized for chatbot")

        # Pre-warm the chatbot service
        LOGGER.info("Pre-warming chatbot service...")
        await chatbot_service.prewarm_models()
        LOGGER.info("Chatbot service pre-warmed successfully")

        return rag_state

    except Exception as e:
        LOGGER.error(f"Failed to initialize RAG state: {e}")
        # Create a minimal RAG state that won't crash the application
        rag_state = RagState()
        rag_state.client = None
        rag_state.embedder = None
        rag_state.reranker = None
        return rag_state


async def get_rag_state() -> RagState:
    """Dependency to get RAG state"""
    return await initialize_rag_state()


class ChatMessage(BaseModel):
    """Model for chat messages"""

    role: str
    content: str
    conversation_id: str = None


class ChatRequest(BaseModel):
    """Model for chat requests"""

    message: str
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None


@router.post("/chat/message")
async def chat_message(request: ChatRequest, rag_state: RagState = Depends(get_rag_state)):
    """
    Process a chat message with RAG context and stream the response
    """
    try:
        LOGGER.info(f"Received chat message: {request.message}, conversation_id: {request.conversation_id}, agent_id: {request.agent_id}")
        conversation_id = request.conversation_id or str(uuid.uuid4())

        async def generate_response():
            async for chunk_data in chatbot_service.process_chat_message(request.message, conversation_id, rag_state, request.agent_id, request.session_id):
                yield f"data: {json.dumps(chunk_data)}\n\n"

        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    except Exception as e:
        LOGGER.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/conversation/{conversation_id}")
async def get_conversation(conversation_id: str, rag_state: RagState = Depends(get_rag_state)):
    """Get conversation history"""
    async with rag_state.lock:
        await rag_state.ensure_ready()
        from .rag_service import _prune_conversations

        await _prune_conversations(rag_state)
        entry = rag_state.conversations.get(conversation_id)
        messages = entry.messages if entry else []

    return {"conversation_id": conversation_id, "messages": messages}


@router.post("/chat/debug")
async def debug_chat_request(request: dict):
    """Debug endpoint to check request format"""
    LOGGER.info(f"Debug request received: {request}")
    return {"received": request}


@router.delete("/chat/conversation/{conversation_id}")
async def reset_conversation(conversation_id: str, rag_state: RagState = Depends(get_rag_state)):
    """Reset a conversation"""
    async with rag_state.lock:
        await rag_state.ensure_ready()
        rag_state.conversations.pop(conversation_id, None)

    return {"status": "success", "conversation_id": conversation_id}
