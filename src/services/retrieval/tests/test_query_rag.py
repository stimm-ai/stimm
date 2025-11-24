"""
Test for query functionality of the retrieval service.
"""
import pytest
from fastapi.testclient import TestClient
from services.rag.rag_routes import app

client = TestClient(app)

def test_query_rag():
    """Test retrieval query endpoint."""
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

    # First ingest a document
    document = {
        "documents": [
            {
                "text": "Bayview Horizon Bank offers personal banking services",
                "id": str(uuid.uuid4()),
                "namespace": "banking",
                "metadata": {"source": "website"}
            }
        ]
    }
    client.post("/knowledge/documents", json=document)

    # Now query for it
    query = {
        "question": "What services does Bayview Horizon Bank offer?",
        "namespace": "banking"
    }
    response = client.post("/rag/query", json=query)
    assert response.status_code == 200
    assert "contexts" in response.json()
    assert len(response.json()["contexts"]) > 0

    # Now query for it
    query = {
        "question": "What services does Bayview Horizon Bank offer?",
        "namespace": "banking"
    }
    response = client.post("/rag/query", json=query)
    assert response.status_code == 200
    assert "contexts" in response.json()
    assert len(response.json()["contexts"]) > 0