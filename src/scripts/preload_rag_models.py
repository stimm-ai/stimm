"""
RAG Model Preloading Script for Docker Build

This script preloads RAG models during Docker build to cache them
and speed up server startup. Models are downloaded and cached in
the Docker layer, making subsequent builds and server starts faster.
"""

import logging
import sys
import time
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("rag_preloader")


def preload_models():
    """Preload RAG models during Docker build"""
    logger.info("Starting RAG model preloading for Docker build...")
    start_time = time.time()

    try:
        # Import required modules
        from services.embeddings import CrossEncoder, SentenceTransformer
        from services.retrieval.config import retrieval_config

        logger.info(f"Preloading embedding model: {retrieval_config.embed_model_name}")

        # Preload embedding model
        embed_start = time.time()
        embed_model = SentenceTransformer(retrieval_config.embed_model_name)
        embed_time = time.time() - embed_start
        logger.info(f"Embedding model preloaded in {embed_time:.2f}s")

        # Preload reranker model if enabled
        if retrieval_config.enable_reranker:
            logger.info(f"Preloading reranker model: {retrieval_config.reranker_model}")
            rerank_start = time.time()
            _ = CrossEncoder(retrieval_config.reranker_model)  # preload only
            rerank_time = time.time() - rerank_start
            logger.info(f"Reranker model preloaded in {rerank_time:.2f}s")
        else:
            logger.info("Reranker preloading disabled")

        total_time = time.time() - start_time
        logger.info(f"RAG model preloading completed in {total_time:.2f}s")

        # Print model information for verification
        logger.info(f"Embedding model dimensions: {embed_model.get_sentence_embedding_dimension()}")
        if retrieval_config.enable_reranker:
            logger.info(f"Reranker model ready: {retrieval_config.reranker_model}")

        return True

    except Exception as e:
        logger.error(f"Failed to preload RAG models: {e}")
        return False


def verify_model_cache():
    """Verify that models are properly cached"""
    try:
        from huggingface_hub import snapshot_download

        # Check if models are cached
        from services.retrieval.config import retrieval_config

        logger.info("Verifying model cache...")

        # Check embedding model cache
        try:
            embed_cache_path = snapshot_download(repo_id=retrieval_config.embed_model_name, local_files_only=True)
            logger.info(f"Embedding model cached at: {embed_cache_path}")
        except Exception as e:
            logger.warning(f"Embedding model not fully cached: {e}")

        # Check reranker model cache if enabled
        if retrieval_config.enable_reranker:
            try:
                rerank_cache_path = snapshot_download(repo_id=retrieval_config.reranker_model, local_files_only=True)
                logger.info(f"Reranker model cached at: {rerank_cache_path}")
            except Exception as e:
                logger.warning(f"Reranker model not fully cached: {e}")

        logger.info("Model cache verification completed")
        return True

    except Exception as e:
        logger.error(f"Model cache verification failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("=== RAG Model Preloading Script ===")

    # Preload models
    success = preload_models()

    # Verify cache
    if success:
        verify_model_cache()

    if success:
        logger.info("✅ RAG model preloading completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ RAG model preloading failed")
        sys.exit(1)
