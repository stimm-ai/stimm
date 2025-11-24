"""
Retrieval Service Configuration Module
"""

import os
import re
from dotenv import load_dotenv

load_dotenv()


class RetrievalConfig:
    """Configuration for Retrieval Service"""

    def __init__(self):
        # Qdrant configuration
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", "voicebot_knowledge")
        self.qdrant_use_tls = os.getenv("QDRANT_USE_TLS", "false").lower() in {"1", "true", "yes"}
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        # Embedding configuration
        self.embed_model_name = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-base-en-v1.5")
        self.embed_batch_size = int(os.getenv("EMBED_BATCH_SIZE", "16"))
        self.embed_normalize = os.getenv("EMBED_NORMALIZE", "true").lower() in {"1", "true", "yes"}

        # Retrieval configuration - optimized for voicebot
        self.default_top_k = int(os.getenv("RAG_DEFAULT_TOP_K", "2"))  # Reduced for voice
        self.max_top_k = int(os.getenv("RAG_MAX_TOP_K", "4"))  # Reduced for voice
        self.max_text_length = int(os.getenv("RAG_MAX_TEXT_LENGTH", "2048"))  # Reduced for voice

        # Candidate counts - optimized for voicebot
        self.dense_candidate_count = int(os.getenv("RAG_DENSE_CANDIDATE_COUNT", "8"))  # Reduced
        self.lexical_candidate_count = int(os.getenv("RAG_LEXICAL_CANDIDATE_COUNT", "8"))  # Reduced

        # Reranker configuration
        self.reranker_model = os.getenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-base").strip()
        self.enable_reranker = self.reranker_model.lower() not in {"", "none", "false", "0"}
        self.rerank_max_candidates = int(os.getenv("RAG_RERANK_MAX_CANDIDATES", "48"))
        self.rerank_max_chars = int(os.getenv("RAG_RERANK_MAX_CHARS", "1200"))

        # Ultra-low latency configuration for voicebot
        self.ultra_low_latency_mode = os.getenv("VOICEBOT_ULTRA_LOW_LATENCY", "true").lower() in {"1", "true", "yes"}
        self.fast_embed_model = os.getenv("VOICEBOT_FAST_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.ultra_top_k = int(os.getenv("VOICEBOT_ULTRA_TOP_K", "1"))
        self.ultra_dense_candidates = int(os.getenv("VOICEBOT_ULTRA_DENSE_CANDIDATES", "2"))
        self.ultra_lexical_candidates = int(os.getenv("VOICEBOT_ULTRA_LEXICAL_CANDIDATES", "2"))

        # Token pattern for lexical indexing
        self._token_pattern = re.compile(r"[A-Za-z0-9']+")

    def get_qdrant_url(self):
        """Get the Qdrant service URL"""
        protocol = "https" if self.qdrant_use_tls else "http"
        return f"{protocol}://{self.qdrant_host}:{self.qdrant_port}"


# Initialize the configuration
retrieval_config = RetrievalConfig()