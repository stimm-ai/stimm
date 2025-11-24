"""
RAG Preloader Service

This module provides preloading of RAG models and state at server startup
to eliminate the 25+ second delay on first user request.
"""

import asyncio
import logging
import time
from typing import Optional

from .rag_state import RagState
from services.retrieval.config import retrieval_config
from services.retrieval import _ensure_collection, _bootstrap_documents

logger = logging.getLogger("rag_preloader")


class RAGPreloader:
    """
    Preloads RAG models and state at server startup for immediate availability.
    
    This eliminates the 25+ second delay caused by model downloads on first request.
    """
    
    def __init__(self):
        self._rag_state: Optional[RagState] = None
        self._is_preloaded = False
        self._preload_start_time: Optional[float] = None
        self._preload_time: Optional[float] = None
        self._preload_error: Optional[str] = None
        
    async def preload_all(self) -> bool:
        """
        Preload all RAG components at server startup.
        
        Returns:
            bool: True if preloading successful, False otherwise
        """
        if self._is_preloaded:
            logger.info("RAG already preloaded, skipping")
            return True
            
        self._preload_start_time = time.time()
        logger.info("Starting RAG preloading at server startup...")
        
        try:
            # Preload RAG state (models, Qdrant connection, etc.)
            self._rag_state = await self._preload_rag_state()
            
            # Preload chatbot models
            from .chatbot_service import chatbot_service
            await chatbot_service.prewarm_models()
            
            self._preload_time = time.time() - self._preload_start_time
            self._is_preloaded = True
            self._preload_error = None
            
            logger.info(f"✅ RAG preloading completed in {self._preload_time:.2f}s")
            return True
            
        except Exception as e:
            self._preload_time = time.time() - self._preload_start_time
            self._preload_error = str(e)
            logger.error(f"❌ RAG preloading failed after {self._preload_time:.2f}s: {e}")
            return False
    
    async def _preload_rag_state(self) -> RagState:
        """Preload RAG state including models and connections"""
        logger.info("Preloading RAG state...")
        
        try:
            # Import required modules
            from qdrant_client import QdrantClient
            from sentence_transformers import CrossEncoder, SentenceTransformer
            
            # Initialize RAG state
            rag_state = RagState()
            
            # Load embedding model
            logger.info(f"Loading embedding model: {retrieval_config.embed_model_name}")
            embed_start = time.time()
            rag_state.embedder = SentenceTransformer(retrieval_config.embed_model_name)
            embed_time = time.time() - embed_start
            logger.info(f"Embedding model loaded in {embed_time:.2f}s")
            
            # Connect to Qdrant
            logger.info(f"Connecting to Qdrant at {retrieval_config.qdrant_host}:{retrieval_config.qdrant_port}")
            qdrant_start = time.time()
            rag_state.client = QdrantClient(
                host=retrieval_config.qdrant_host,
                port=retrieval_config.qdrant_port,
                https=retrieval_config.qdrant_use_tls,
                api_key=retrieval_config.qdrant_api_key,
            )
            qdrant_time = time.time() - qdrant_start
            logger.info(f"Qdrant connected in {qdrant_time:.2f}s")
            
            # Initialize reranker if enabled
            if retrieval_config.enable_reranker:
                try:
                    logger.info(f"Loading reranker model: {retrieval_config.reranker_model}")
                    rerank_start = time.time()
                    rag_state.reranker = CrossEncoder(retrieval_config.reranker_model)
                    rerank_time = time.time() - rerank_start
                    logger.info(f"Reranker model loaded in {rerank_time:.2f}s")
                except Exception as exc:
                    logger.warning(f"Failed to load reranker model: {exc}")
                    rag_state.reranker = None
            
            # Ensure collection exists and bootstrap documents
            logger.info("Ensuring Qdrant collection exists...")
            await _ensure_collection(rag_state.embedder, rag_state.client)
            
            try:
                _bootstrap_documents(rag_state.client, rag_state.lexical_index, rag_state.documents)
                logger.info(f"Bootstrapped {len(rag_state.documents)} document chunks into lexical index")
            except Exception as exc:
                logger.warning(f"Failed to bootstrap lexical index: {exc}")
            
            logger.info("RAG state preloaded successfully")
            return rag_state
            
        except Exception as e:
            logger.error(f"Failed to preload RAG state: {e}")
            raise
    
    @property
    def is_preloaded(self) -> bool:
        """Check if RAG is preloaded and ready"""
        return self._is_preloaded
    
    @property
    def rag_state(self) -> Optional[RagState]:
        """Get the preloaded RAG state"""
        return self._rag_state
    
    @property
    def preload_time(self) -> Optional[float]:
        """Get the preloading time in seconds"""
        return self._preload_time
    
    @property
    def preload_start_time(self) -> Optional[float]:
        """Get the preloading start time"""
        return self._preload_start_time
    
    @property
    def preload_error(self) -> Optional[str]:
        """Get the preloading error message if any"""
        return self._preload_error
    
    def get_status(self) -> dict:
        """Get preloading status information"""
        return {
            "is_preloaded": self._is_preloaded,
            "preload_time": self._preload_time,
            "preload_start_time": self._preload_start_time,
            "preload_error": self._preload_error,
            "rag_state_available": self._rag_state is not None
        }


# Global preloader instance
rag_preloader = RAGPreloader()