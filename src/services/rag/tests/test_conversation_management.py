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
    qdrant_client = QdrantClient(host="qdrant", port=6333)
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