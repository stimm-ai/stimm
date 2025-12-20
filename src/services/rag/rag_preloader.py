"""
RAG Preloader Service

This module provides preloading of RAG models and state at server startup
to eliminate the 25+ second delay on first user request.
"""

import logging
import time
from typing import Optional

from services.retrieval import _bootstrap_documents, _ensure_collection
from services.retrieval.config import retrieval_config

from .rag_state import RagState

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
        # Cache for agent-specific RAG states
        self._agent_rag_states: dict = {}  # agent_id -> RagState

    async def preload_all(self, agent_id: str = None) -> bool:
        """
        Preload all RAG components at server startup.

        Args:
            agent_id: Optional agent ID to use for agent-specific RAG configuration
                     If provided, will load embedding model from agent's RAG config.
                     If None, will use global .env configuration.

        Returns:
            bool: True if preloading successful, False otherwise
        """
        if self._is_preloaded:
            logger.info("RAG already preloaded, skipping")
            return True

        self._preload_start_time = time.time()
        if agent_id:
            logger.info(f"Starting RAG preloading for agent {agent_id}...")
        else:
            logger.info("Starting RAG preloading with global config...")

        try:
            # Preload RAG state (models, Qdrant connection, etc.)
            # Pass agent_id to use agent-specific config when available
            self._rag_state = await self._preload_rag_state(agent_id=agent_id)

            # Preload chatbot models
            from .chatbot_service import chatbot_service

            await chatbot_service.prewarm_models(agent_id=agent_id)

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

    async def _preload_rag_state(self, agent_id: str = None) -> RagState:
        """
        Preload RAG state including models and connections.

        Args:
            agent_id: Optional agent ID to load agent-specific RAG configuration.
                     If provided and agent has RAG config, uses that embedding model.
                     Otherwise, falls back to global retrieval_config.
        """
        logger.info("Preloading RAG state...")

        try:
            # Import required modules
            from qdrant_client import QdrantClient

            from services.embeddings import CrossEncoder, SentenceTransformer

            # Initialize RAG state
            rag_state = RagState()

            # Determine which embedding model to use
            embed_model_name = retrieval_config.embed_model_name  # Default fallback

            # Try to get agent-specific config if agent_id provided
            if agent_id:
                try:
                    import uuid

                    from services.agents_admin.agent_manager import get_agent_manager
                    from services.rag.rag_config_service import RagConfigService

                    # Convert agent_id to UUID if it's a string
                    if isinstance(agent_id, str):
                        agent_uuid = uuid.UUID(agent_id)
                    else:
                        agent_uuid = agent_id  # Already a UUID object

                    agent_manager = get_agent_manager()
                    agent_config = agent_manager.get_agent_config(agent_uuid)

                    if agent_config.rag_config_id:
                        rag_config_service = RagConfigService()
                        rag_config_resp = rag_config_service.get_rag_config(agent_config.rag_config_id)
                        rag_config_dict = rag_config_resp.model_dump()

                        # Extract embedding model from agent's RAG config
                        provider_config = rag_config_dict.get("provider_config", {})
                        agent_embed_model = provider_config.get("embedding_model")

                        if agent_embed_model:
                            embed_model_name = agent_embed_model
                            logger.info(f"📋 Using agent-specific embedding model: {embed_model_name}")
                        else:
                            logger.info(f"⚠️ Agent RAG config has no embedding_model, using global: {embed_model_name}")
                    else:
                        logger.info(f"ℹ️ Agent has no RAG config, using global embedding model: {embed_model_name}")

                except Exception as e:
                    logger.warning(f"⚠️ Could not load agent RAG config, using global: {e}")
            else:
                logger.info(f"ℹ️ No agent specified, using global embedding model: {embed_model_name}")

            # Load embedding model (either agent-specific or global)
            logger.info(f"Loading embedding model: {embed_model_name}")
            embed_start = time.time()
            rag_state.embedder = SentenceTransformer(embed_model_name)
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

            # Create retrieval engine for agent if it has a RAG config
            # This must be done AFTER embedder and client are initialized
            if agent_id:
                try:
                    import uuid

                    from services.agents_admin.agent_manager import get_agent_manager
                    from services.rag.rag_config_service import RagConfigService

                    # Convert agent_id to UUID if it's a string
                    if isinstance(agent_id, str):
                        agent_uuid = uuid.UUID(agent_id)
                    else:
                        agent_uuid = agent_id

                    agent_manager = get_agent_manager()
                    agent_config = agent_manager.get_agent_config(agent_uuid)

                    if agent_config.rag_config_id:
                        # Agent has RAG config - create retrieval engine
                        rag_config_service = RagConfigService()
                        retrieval_engine = rag_config_service.get_retrieval_engine(agent_config.rag_config_id)
                        rag_state.retrieval_engine = retrieval_engine
                        rag_state.skip_retrieval = False
                        logger.info(f"✅ Created retrieval engine for RAG config {agent_config.rag_config_id} (collection: {retrieval_engine.collection_name})")
                    else:
                        # Agent has NO RAG config - skip retrieval entirely
                        rag_state.retrieval_engine = None
                        rag_state.skip_retrieval = True
                        logger.info("ℹ️ Agent has no RAG config - RAG retrieval will be skipped")

                except Exception as e:
                    logger.warning(f"⚠️ Could not create retrieval engine: {e}")
                    # On error, skip retrieval to be safe
                    rag_state.skip_retrieval = True
            else:
                # No agent specified - use global behavior (don't skip retrieval)
                rag_state.skip_retrieval = False
                logger.info("ℹ️ No agent specified - using global RAG behavior")

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

    async def get_rag_state_for_agent(self, agent_id: str = None) -> RagState:
        """
        Get or create RAG state for a specific agent.

        This is the unified entry point for all RAG initialization,
        used by both CLI and event_loop paths.

        Args:
            agent_id: Optional agent ID. If provided, returns agent-specific state.
                     If None, returns global preloaded state.

        Returns:
            RagState configured for the agent
        """
        # Convert agent_id to string for cache key
        cache_key = str(agent_id) if agent_id else "global"

        # Check cache first
        if cache_key in self._agent_rag_states:
            logger.debug(f"Returning cached RAG state for agent {cache_key}")
            return self._agent_rag_states[cache_key]

        # For global (no agent), return preloaded state if available
        if agent_id is None and self._is_preloaded and self._rag_state:
            logger.debug("Returning global preloaded RAG state")
            self._agent_rag_states[cache_key] = self._rag_state
            return self._rag_state

        # Create new RAG state for this agent
        logger.info(f"Creating new RAG state for agent {cache_key}")
        rag_state = await self._preload_rag_state(agent_id=agent_id)

        # Cache it
        self._agent_rag_states[cache_key] = rag_state

        return rag_state

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
            "rag_state_available": self._rag_state is not None,
        }


# Global preloader instance
rag_preloader = RAGPreloader()
