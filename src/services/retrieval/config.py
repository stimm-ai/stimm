"""
Retrieval Service Configuration Module
"""

import os
import re

from dotenv import load_dotenv

from environment_config import config

load_dotenv()


class RetrievalConfig:
    """Configuration for Retrieval Service"""

    def __init__(self):
        qdrant_url = config.qdrant_url
        if "://" in qdrant_url:
            protocol_and_host = qdrant_url.split("://")[1]
            if ":" in protocol_and_host:
                self.qdrant_host, port_part = protocol_and_host.split(":")
                self.qdrant_port = int(port_part.split("/")[0])
            else:
                self.qdrant_host = protocol_and_host.split("/")[0]
                self.qdrant_port = 6333
        else:
            # Fallback to environment variables (deprecated, use QDRANT_URL)
            self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

        # Other Qdrant configuration
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION_NAME", os.getenv("QDRANT_COLLECTION", "stimm_knowledge"))
        self.qdrant_use_tls = os.getenv("QDRANT_USE_TLS", "false").lower() in {"1", "true", "yes"}
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        # Embedding configuration
        self.embed_model_name = os.getenv("QDRANT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.embed_batch_size = int(os.getenv("EMBED_BATCH_SIZE", "16"))
        self.embed_normalize = os.getenv("EMBED_NORMALIZE", "true").lower() in {"1", "true", "yes"}

        # Retrieval configuration - optimized for stimm
        self.default_top_k = int(os.getenv("QDRANT_DEFAULT_TOP_K", "2"))  # Reduced for voice
        self.max_top_k = int(os.getenv("QDRANT_MAX_TOP_K", "4"))  # Reduced for voice
        self.max_text_length = int(os.getenv("RAG_MAX_TEXT_LENGTH", "2048"))  # Reduced for voice

        # Candidate counts - optimized for stimm
        self.dense_candidate_count = int(os.getenv("QDRANT_DENSE_CANDIDATE_COUNT", "24"))  # Higher for better reranking coverage
        self.lexical_candidate_count = int(os.getenv("QDRANT_LEXICAL_CANDIDATE_COUNT", "24"))  # Higher for better reranking coverage

        # Reranker configuration (Legacy - reranking is too slow for voice)
        self.reranker_model = os.getenv("RAG_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2").strip()
        self.enable_reranker = False  # Globally disabled for latency
        self.rerank_max_candidates = int(os.getenv("RAG_RERANK_MAX_CANDIDATES", "24"))
        self.rerank_max_chars = int(os.getenv("RAG_RERANK_MAX_CHARS", "1200"))

        # Ultra-low latency configuration for stimm (Production path)
        self.ultra_low_latency_mode = True  # Always on
        self.fast_embed_model = os.getenv("STIMM_FAST_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.ultra_top_k = int(os.getenv("STIMM_ULTRA_TOP_K", "6"))
        self.ultra_dense_candidates = int(os.getenv("STIMM_ULTRA_DENSE_CANDIDATES", "40"))
        self.ultra_lexical_candidates = int(os.getenv("STIMM_ULTRA_LEXICAL_CANDIDATES", "40"))

        # Token pattern for lexical indexing
        self._token_pattern = re.compile(r"[A-Za-z0-9']+")

    def get_qdrant_url(self):
        """Get the Qdrant service URL"""
        protocol = "https" if self.qdrant_use_tls else "http"
        return f"{protocol}://{self.qdrant_host}:{self.qdrant_port}"


# Initialize the configuration
retrieval_config = RetrievalConfig()
