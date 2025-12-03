"""
Test for service initialization of the RAG service.
"""
import pytest
from fastapi.testclient import TestClient
from services.rag.rag_routes import app

client = TestClient(app)

def test_rag_service_initialization():
    """Test that the RAG service initializes correctly."""
    response = client.get("/")
    assert response.status_code == 404  # Default FastAPI response for root