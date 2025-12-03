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
    
    # Use environment-aware Qdrant connection
    from environment_config import get_environment_config
    env_config = get_environment_config()
    qdrant_config = env_config.get_service_config("qdrant")
    
    # Parse Qdrant URL to extract host and port
    qdrant_url = qdrant_config.get("url", "http://localhost:6333")
    if "://" in qdrant_url:
        protocol_and_host = qdrant_url.split("://")[1]
        if ":" in protocol_and_host:
            host, port_part = protocol_and_host.split(":")
            port = int(port_part.split("/")[0])
        else:
            host = protocol_and_host.split("/")[0]
            port = 6333
    else:
        host = "localhost"
        port = 6333
    
    qdrant_client = QdrantClient(host=host, port=port)
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