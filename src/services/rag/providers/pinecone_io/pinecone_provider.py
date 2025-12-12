"""
Pinecone.io Provider for RAG
"""

from typing import Any, Dict, List


class PineconeProvider:
    """
    Provider for Pinecone vector database.

    This provider connects to a Pinecone cloud instance.
    Non-configurable parameters (API URL, environment) are retrieved from
    provider constants.
    """

    @classmethod
    def get_expected_properties(cls) -> List[str]:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return ["index_name", "api_key", "top_k", "namespace"]

    @classmethod
    def get_field_definitions(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get the field definitions for this provider.

        Returns:
            Dictionary mapping field names to field metadata
        """
        return {
            "index_name": {
                "type": "text",
                "label": "Index Name",
                "required": True,
                "description": "Name of the Pinecone index to query",
                "default": "stimm",
            },
            "api_key": {
                "type": "password",
                "label": "API Key",
                "required": True,
                "description": "Pinecone API key for authentication",
            },
            "top_k": {
                "type": "number",
                "label": "Top K",
                "required": True,
                "description": "Number of retrieved documents to return (higher values increase recall but may impact latency)",
                "min": 1,
                "max": 10,
                "default": 2,
            },
            "namespace": {
                "type": "text",
                "label": "Namespace",
                "required": False,
                "description": "Optional namespace within the index",
            },
            "embedding_model": {
                "type": "select",
                "label": "Embedding Model",
                "required": False,
                "description": "Model used to generate embeddings for queries (only needed if using local embedding)",
                "options": [
                    {"value": "BAAI/bge-base-en-v1.5", "label": "BGE Base En v1.5"},
                    {"value": "sentence-transformers/all-MiniLM-L6-v2", "label": "MiniLM L6 v2"},
                    {"value": "sentence-transformers/all-mpnet-base-v2", "label": "MPNet Base v2"},
                    {"value": "intfloat/e5-base-v2", "label": "E5 Base v2"},
                ],
                "default": "BAAI/bge-base-en-v1.5",
            },
            "enable_reranker": {
                "type": "boolean",
                "label": "Enable Reranker",
                "required": False,
                "description": "Whether to use cross-encoder reranking (requires reranker model)",
                "default": False,
            },
            "ultra_low_latency": {
                "type": "boolean",
                "label": "Ultra Low Latency Mode",
                "required": False,
                "description": "Optimize for stimm latency (reduces retrieval quality)",
                "default": True,
            },
        }

    @classmethod
    def to_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert standardized frontend config to provider-specific format.

        For Pinecone, no transformation needed.
        """
        return config.copy()

    @classmethod
    def from_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert provider-specific config to standardized frontend format.

        For Pinecone, no transformation needed.
        """
        return config.copy()
