"""
Test for conversation management functionality of the RAG service.
"""
import pytest
from fastapi.testclient import TestClient
from services.rag.rag_routes import app

client = TestClient(app)

def test_conversation_management():
    """Test conversation management endpoints."""
    # Manually initialize the RAG service
    from services.rag.rag_routes import app
    from services.rag.rag_state import RagState
    from sentence_transformers import SentenceTransformer
    from qdrant_client import QdrantClient

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

    # Create a conversation
    conv_id = "test-conv-1"
    message = {
        "conversation_id": conv_id,
        "message": {
            "role": "user",
            "content": "Hello, what services do you offer?",
            "metadata": {}
        }
    }
    response = client.post("/conversation/message", json=message)
    assert response.status_code == 200
    assert response.json()["conversation_id"] == conv_id
    assert len(response.json()["messages"]) == 1

    # Get conversation
    response = client.get(f"/conversation/{conv_id}")
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 1

    # Reset conversation
    response = client.delete(f"/conversation/{conv_id}")
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 0