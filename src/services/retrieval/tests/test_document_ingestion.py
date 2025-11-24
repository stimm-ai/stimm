"""
Test for document ingestion functionality of the retrieval service.
"""
import pytest
from fastapi.testclient import TestClient
from services.rag.rag_routes import app

client = TestClient(app)

def test_document_ingestion():
    """Test document ingestion endpoint."""
    # Manually initialize the RAG service
    from services.rag.rag_routes import app
    from services.rag.rag_state import RagState
    from sentence_transformers import SentenceTransformer
    from qdrant_client import QdrantClient
    import uuid

    # Initialize the RAG service
    embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
    qdrant_client = QdrantClient(host="qdrant", port=6333)
    rag_state = RagState()
    rag_state.embedder = embedder
    rag_state.client = qdrant_client
    app.state.rag = rag_state

    # Test with empty documents
    response = client.post("/knowledge/documents", json={"documents": []})
    assert response.status_code == 400
    assert "No documents provided" in response.json()["detail"]

    # Test with valid document
    document = {
        "documents": [
            {
                "text": "This is a test document",
                "id": str(uuid.uuid4()),
                "namespace": "test",
                "metadata": {"source": "test"}
            }
        ]
    }
    response = client.post("/knowledge/documents", json=document)
    assert response.status_code == 200
    assert response.json()["inserted"] == 1