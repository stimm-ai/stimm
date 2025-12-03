#!/usr/bin/env python3
"""
Integration tests for RAG configuration routes.
"""
import sys
import uuid
import logging
sys.path.insert(0, 'src')

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from database.session import SessionLocal
from services.rag.rag_config_routes import router
from services.rag.config_models import RagConfigCreate, ProviderConfig
from services.rag.rag_config_service import RagConfigService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a test client using the router directly (need to mount it in an app)
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_list_rag_configs():
    """Test GET /rag-configs/"""
    response = client.get("/rag-configs/")
    assert response.status_code == 200
    configs = response.json()
    assert isinstance(configs, list)
    logger.info(f"Listed {len(configs)} RAG configs")


def test_create_and_delete_rag_config():
    """Test POST /rag-configs/ and DELETE /rag-configs/{id}"""
    # Create a unique name
    test_name = f"Test RAG Config {uuid.uuid4().hex[:8]}"
    provider_config = {
        "provider": "qdrant.internal",
        "config": {
            "collection_name": "test_collection",
            "embedding_model": "all-MiniLM-L6-v2",
            "top_k": 5,
            "enable_reranker": False,
            "ultra_low_latency": True,
        }
    }
    payload = {
        "name": test_name,
        "description": "Test RAG configuration",
        "provider_config": provider_config,
        "is_default": False,
    }
    # Create
    response = client.post("/rag-configs/", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == test_name
    assert created["provider"] == "qdrant.internal"
    config_id = created["id"]
    logger.info(f"Created RAG config ID: {config_id}")

    # Retrieve via GET
    response = client.get(f"/rag-configs/{config_id}")
    assert response.status_code == 200
    retrieved = response.json()
    assert retrieved["id"] == config_id

    # Delete
    response = client.delete(f"/rag-configs/{config_id}")
    assert response.status_code == 204

    # Verify deletion
    response = client.get(f"/rag-configs/{config_id}")
    assert response.status_code == 404
    logger.info("Create/delete test passed")


def test_update_rag_config():
    """Test PUT /rag-configs/{id}"""
    # First create a config
    test_name = f"Update Test {uuid.uuid4().hex[:8]}"
    provider_config = {
        "provider": "qdrant.internal",
        "config": {
            "collection_name": "test_collection",
            "embedding_model": "all-MiniLM-L6-v2",
            "top_k": 5,
            "enable_reranker": False,
            "ultra_low_latency": True,
        }
    }
    payload = {
        "name": test_name,
        "description": "Original",
        "provider_config": provider_config,
        "is_default": False,
    }
    response = client.post("/rag-configs/", json=payload)
    assert response.status_code == 201
    config_id = response.json()["id"]

    # Update
    update_payload = {
        "name": f"{test_name} Updated",
        "description": "Updated description",
        "is_default": True,
    }
    response = client.put(f"/rag-configs/{config_id}", json=update_payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == f"{test_name} Updated"
    assert updated["description"] == "Updated description"
    assert updated["is_default"] is True

    # Unset default before deletion (set is_default=False)
    unset_payload = {
        "is_default": False,
    }
    response = client.put(f"/rag-configs/{config_id}", json=unset_payload)
    assert response.status_code == 200
    unset = response.json()
    assert unset["is_default"] is False

    # Clean up
    response = client.delete(f"/rag-configs/{config_id}")
    assert response.status_code == 204
    logger.info("Update test passed")


def test_default_rag_config():
    """Test default RAG config endpoints"""
    # Create two configs
    provider_config = {
        "provider": "qdrant.internal",
        "config": {
            "collection_name": "test_collection",
            "embedding_model": "all-MiniLM-L6-v2",
            "top_k": 5,
            "enable_reranker": False,
            "ultra_low_latency": True,
        }
    }
    # First config (non-default)
    payload1 = {
        "name": f"First {uuid.uuid4().hex[:8]}",
        "description": "First",
        "provider_config": provider_config,
        "is_default": False,
    }
    response = client.post("/rag-configs/", json=payload1)
    assert response.status_code == 201
    first_id = response.json()["id"]

    # Second config (non-default)
    payload2 = {
        "name": f"Second {uuid.uuid4().hex[:8]}",
        "description": "Second",
        "provider_config": provider_config,
        "is_default": False,
    }
    response = client.post("/rag-configs/", json=payload2)
    assert response.status_code == 201
    second_id = response.json()["id"]

    # Set second as default via PUT /rag-configs/{id}/set-default
    response = client.put(f"/rag-configs/{second_id}/set-default")
    assert response.status_code == 200
    default_resp = response.json()
    assert default_resp["id"] == second_id
    assert default_resp["is_default"] is True

    # Get default via GET /rag-configs/default/current
    response = client.get("/rag-configs/default/current")
    assert response.status_code == 200
    current_default = response.json()
    assert current_default["id"] == second_id

    # Verify first is not default
    response = client.get(f"/rag-configs/{first_id}")
    assert response.status_code == 200
    first = response.json()
    assert first["is_default"] is False

    # Clean up (need to unset default before deletion)
    # Update second to not be default (by setting first as default)
    response = client.put(f"/rag-configs/{first_id}/set-default")
    assert response.status_code == 200
    # Now delete second (non-default)
    response = client.delete(f"/rag-configs/{second_id}")
    assert response.status_code == 204
    # Unset default on first before deletion
    response = client.put(f"/rag-configs/{first_id}", json={"is_default": False})
    assert response.status_code == 200
    # Delete first
    response = client.delete(f"/rag-configs/{first_id}")
    assert response.status_code == 204
    logger.info("Default config tests passed")


def test_provider_endpoints():
    """Test provider metadata endpoints"""
    # GET /rag-configs/providers/available
    response = client.get("/rag-configs/providers/available")
    assert response.status_code == 200
    providers = response.json()
    assert "providers" in providers
    assert "field_definitions" in providers
    logger.info(f"Available providers: {providers['providers']}")

    # GET /rag-configs/providers/qdrant.internal/fields
    response = client.get("/rag-configs/providers/qdrant.internal/fields")
    assert response.status_code == 200
    fields = response.json()
    assert "collection_name" in fields
    logger.info(f"Fields for qdrant.internal: {list(fields.keys())}")

    # GET for unknown provider (should return empty dict)
    response = client.get("/rag-configs/providers/unknown.provider/fields")
    assert response.status_code == 200
    fields = response.json()
    assert fields == {}
    logger.info("Provider endpoints test passed")


def test_validation_errors():
    """Test validation error responses"""
    # Missing required property
    provider_config = {
        "provider": "qdrant.internal",
        "config": {
            "embedding_model": "all-MiniLM-L6-v2",
            # missing collection_name
        }
    }
    payload = {
        "name": f"Invalid {uuid.uuid4().hex[:8]}",
        "description": "Invalid",
        "provider_config": provider_config,
        "is_default": False,
    }
    response = client.post("/rag-configs/", json=payload)
    assert response.status_code == 400
    error = response.json()
    assert "detail" in error
    assert "errors" in error["detail"]
    logger.info(f"Validation error caught: {error}")

    # Duplicate name (create two configs with same name)
    name = f"Duplicate {uuid.uuid4().hex[:8]}"
    provider_config_full = {
        "provider": "qdrant.internal",
        "config": {
            "collection_name": "test",
            "embedding_model": "all-MiniLM-L6-v2",
            "top_k": 5,
            "enable_reranker": False,
            "ultra_low_latency": True,
        }
    }
    payload1 = {
        "name": name,
        "description": "First",
        "provider_config": provider_config_full,
        "is_default": False,
    }
    response = client.post("/rag-configs/", json=payload1)
    assert response.status_code == 201
    first_id = response.json()["id"]

    payload2 = {
        "name": name,
        "description": "Second",
        "provider_config": provider_config_full,
        "is_default": False,
    }
    response = client.post("/rag-configs/", json=payload2)
    assert response.status_code == 409  # Conflict
    error = response.json()
    assert "detail" in error
    assert "errors" in error["detail"]

    # Clean up
    response = client.delete(f"/rag-configs/{first_id}")
    assert response.status_code == 204
    logger.info("Validation error tests passed")


def main():
    """Run all route tests."""
    success = True
    try:
        test_list_rag_configs()
        test_create_and_delete_rag_config()
        test_update_rag_config()
        test_default_rag_config()
        test_provider_endpoints()
        test_validation_errors()
    except Exception as e:
        logger.error(f"Route test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        success = False

    if success:
        logger.info("✅ All RAG config route tests passed")
        sys.exit(0)
    else:
        logger.error("❌ Some route tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()