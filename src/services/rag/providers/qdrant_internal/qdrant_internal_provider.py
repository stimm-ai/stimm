"""
Qdrant Internal Provider for RAG
"""

from typing import Dict, Any, List


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
            # Optional fields are not required for validation
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
                "default": "stimm_knowledge"
            },
            "embedding_model": {
                "type": "select",
                "label": "Embedding Model",
                "required": True,
                "description": "Model used to generate embeddings",
                "options": [
                    {"value": "BAAI/bge-base-en-v1.5", "label": "BGE Base En v1.5"},
                    {"value": "sentence-transformers/all-MiniLM-L6-v2", "label": "MiniLM L6 v2"},
                    {"value": "sentence-transformers/all-mpnet-base-v2", "label": "MPNet Base v2"},
                    {"value": "intfloat/e5-base-v2", "label": "E5 Base v2"}
                ],
                "default": "BAAI/bge-base-en-v1.5"
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
            "enable_reranker": {
                "type": "boolean",
                "label": "Enable Reranker",
                "required": False,
                "description": "Whether to use cross-encoder reranking",
                "default": False
            },
            "ultra_low_latency": {
                "type": "boolean",
                "label": "Ultra Low Latency Mode",
                "required": False,
                "description": "Optimize for stimm latency (reduces retrieval quality)",
                "default": True
            },
            "qdrant_use_tls": {
                "type": "boolean",
                "label": "Use TLS",
                "required": False,
                "description": "Whether to use HTTPS for Qdrant connection",
                "default": False
            },
            "dense_candidate_count": {
                "type": "number",
                "label": "Dense Candidate Count",
                "required": False,
                "description": "Number of dense candidates to retrieve before reranking",
                "min": 1,
                "max": 100,
                "default": 24
            },
            "lexical_candidate_count": {
                "type": "number",
                "label": "Lexical Candidate Count",
                "required": False,
                "description": "Number of lexical candidates to retrieve before reranking",
                "min": 1,
                "max": 100,
                "default": 24
            },
            "max_top_k": {
                "type": "number",
                "label": "Max Top K",
                "required": False,
                "description": "Maximum allowed top_k value (safety limit)",
                "min": 1,
                "max": 20,
                "default": 8
            }
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