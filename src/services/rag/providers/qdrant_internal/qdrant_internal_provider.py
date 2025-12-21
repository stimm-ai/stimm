"""
Qdrant Internal Provider for RAG
"""

from typing import Any, Dict, List


class QdrantInternalProvider:
    """
    Provider for internal Qdrant vector database.

    This provider connects to a Qdrant instance managed within stimm.
    Non-configurable parameters (host, port, TLS, API key) are retrieved from
    provider constants.
    """

    @classmethod
    def get_expected_properties(cls) -> List[str]:
        """
        Get the list of expected properties for this provider.

        Returns:
            List of property names that this provider expects
        """
        return [
            "collection_name",
            "embedding_model",
            "top_k",
        ]

    @classmethod
    def get_field_definitions(cls) -> Dict[str, Dict[str, Any]]:
        """
        Get the field definitions for this provider.

        Returns:
            Dictionary mapping field names to field metadata
        """
        return {
            "collection_name": {
                "type": "text",
                "label": "Collection Name",
                "required": True,
                "description": "Name of the Qdrant collection to query",
                "default": "stimm_knowledge",
            },
            "embedding_model": {
                "type": "select",
                "label": "Embedding Model",
                "required": True,
                "description": "Model used to generate embeddings (ONNX-compatible only)",
                "options": [
                    {"value": "sentence-transformers/all-MiniLM-L6-v2", "label": "MiniLM L6 v2 (384 dims, fast)"},
                ],
                "default": "sentence-transformers/all-MiniLM-L6-v2",
            },
            "top_k": {
                "type": "number",
                "label": "Results Count (Top K)",
                "required": True,
                "description": "Number of context chunks to send to the LLM. Recommended: 4-8.",
                "min": 1,
                "max": 20,
                "default": 6,
            },
            "dense_candidate_count": {
                "type": "number",
                "label": "Search Depth (Candidates)",
                "required": False,
                "description": "Number of points to explore in vector space. Recommended: 20-40 for high precision without latency impact.",
                "min": 1,
                "max": 100,
                "default": 40,
            },
        }

    @classmethod
    def to_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert standardized frontend config to provider-specific format.

        For Qdrant internal, no transformation needed.
        """
        return config.copy()

    @classmethod
    def from_provider_format(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert provider-specific config to standardized frontend format.

        For Qdrant internal, no transformation needed.
        """
        return config.copy()
