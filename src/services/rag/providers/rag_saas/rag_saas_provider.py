"""
RAG SaaS Provider for RAG
"""

from typing import Dict, Any, List


class RagSaaSProvider:
    """
    Provider for third‑party SaaS RAG services.

    This provider connects to an external RAG API (e.g., OpenAI Retrieval, Cohere, etc.).
    Non‑configurable parameters (base URL) are retrieved from provider constants.
    """

    @classmethod
    def get_expected_properties(cls) -> List[str]:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return [
            "api_key",
            "model",
            "top_k"
        ]

    @classmethod
    def get_field_definitions(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get the field definitions for this provider.

        Returns:
            Dictionary mapping field names to field metadata
        """
        return {
            "api_key": {
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "API key for the SaaS RAG service"
            },
            "model": {
                "type": "text",
                "label": "Model",
                "required": True,
                "description": "Model identifier (e.g., 'openai-embedding-3-large', 'cohere-embed-v3')",
                "default": "openai-embedding-3-small"
            },
            "top_k": {
                "type": "number",
                "label": "Top K",
                "required": True,
                "description": "Number of retrieved documents to return (higher values increase recall but may impact latency)",
                "min": 1,
                "max": 10,
                "default": 2
            },
            "embedding_model": {
                "type": "select",
                "label": "Embedding Model (optional)",
                "required": False,
                "description": "Model used to generate embeddings for queries (if using local embedding)",
                "options": [
                    {"value": "BAAI/bge-base-en-v1.5", "label": "BGE Base En v1.5"},
                    {"value": "sentence-transformers/all-MiniLM-L6-v2", "label": "MiniLM L6 v2"},
                    {"value": "sentence-transformers/all-mpnet-base-v2", "label": "MPNet Base v2"},
                    {"value": "intfloat/e5-base-v2", "label": "E5 Base v2"}
                ],
                "default": "BAAI/bge-base-en-v1.5"
            },
            "enable_reranker": {
                "type": "boolean",
                "label": "Enable Reranker",
                "required": False,
                "description": "Whether to use cross-encoder reranking (requires reranker model)",
                "default": False
            },
            "ultra_low_latency": {
                "type": "boolean",
                "label": "Ultra Low Latency Mode",
                "required": False,
                "description": "Optimize for stimm latency (reduces retrieval quality)",
                "default": True
            }
        }

    @classmethod
    def to_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert standardized frontend config to provider‑specific format.

        For SaaS RAG, no transformation needed.
        """
        return config.copy()

    @classmethod
    def from_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert provider‑specific config to standardized frontend format.

        For SaaS RAG, no transformation needed.
        """
        return config.copy()