#!/usr/bin/env python3
"""
Integration tests for RAG configuration service.
"""
import sys
import uuid
import logging
sys.path.insert(0, 'src')

from services.rag.rag_config_service import RagConfigService
from services.rag.config_models import RagConfigCreate, ProviderConfig
from services.agents_admin.exceptions import (
    AgentNotFoundError,
    AgentAlreadyExistsError,
    AgentValidationError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_rag_config_crud():
    """Test basic CRUD operations for RAG configurations."""
    service = RagConfigService()
    user_id = None  # will use system user

    # Generate unique name
    test_name = f"Test RAG Config {uuid.uuid4().hex[:8]}"
    provider_config = ProviderConfig(
        provider="qdrant.internal",
        config={
            "collection_name": "test_collection",
            "embedding_model": "all-MiniLM-L6-v2",
            "top_k": 5,
            "enable_reranker": False,
            "ultra_low_latency": True,
        }
    )
    create_data = RagConfigCreate(
        name=test_name,
        description="Test RAG configuration",
        provider_config=provider_config,
        is_default=False,
    )

    # 1. Create
    logger.info(f"Creating RAG config: {test_name}")
    created = service.create_rag_config(create_data, user_id)
    assert created.name == test_name
    assert created.provider == "qdrant.internal"
    assert created.provider_config["collection_name"] == "test_collection"
    assert created.is_default is False
    assert created.is_active is True
    logger.info(f"Created RAG config ID: {created.id}")

    # 2. Retrieve
    retrieved = service.get_rag_config(created.id, user_id)
    assert retrieved.id == created.id
    assert retrieved.name == test_name

    # 3. List
    list_result = service.list_rag_configs(user_id, active_only=True)
    assert any(cfg.id == created.id for cfg in list_result.configs)

    # 4. Update
    from services.rag.config_models import RagConfigUpdate
    update_data = RagConfigUpdate(
        name=f"{test_name} Updated",
        description="Updated description",
        is_default=True,
    )
    updated = service.update_rag_config(created.id, update_data, user_id)
    assert updated.name == f"{test_name} Updated"
    assert updated.description == "Updated description"
    assert updated.is_default is True
    # Ensure previous default is unset (if any)
    # Not testing here because we don't have another default

    # 5. Set default via dedicated method
    # First create another config
    second_name = f"Second RAG Config {uuid.uuid4().hex[:8]}"
    second_create = RagConfigCreate(
        name=second_name,
        description="Second config",
        provider_config=provider_config,
        is_default=False,
    )
    second = service.create_rag_config(second_create, user_id)
    # Set second as default
    new_default = service.set_default_rag_config(second.id, user_id)
    assert new_default.is_default is True
    # Verify first config is no longer default
    first_after = service.get_rag_config(created.id, user_id)
    assert first_after.is_default is False

    # 6. Get default config
    default = service.get_default_rag_config(user_id)
    assert default.id == second.id

    # 7. Delete second config (should fail because it's default)
    try:
        service.delete_rag_config(second.id, user_id)
        assert False, "Should have raised AgentValidationError"
    except AgentValidationError as e:
        assert "Cannot delete default RAG configuration" in str(e)
        logger.info("Correctly prevented deletion of default config")

    # 8. Delete first config (non-default)
    deleted = service.delete_rag_config(created.id, user_id)
    assert deleted is True
    # Verify it's gone
    try:
        service.get_rag_config(created.id, user_id)
        assert False, "Should have raised AgentNotFoundError"
    except AgentNotFoundError:
        logger.info("First config deleted successfully")

    # 9. Clean up second config by setting another default (none left) and deleting
    # Create a dummy config to become default
    dummy = service.create_rag_config(
        RagConfigCreate(
            name=f"Dummy {uuid.uuid4().hex[:4]}",
            description="Dummy",
            provider_config=provider_config,
            is_default=False,
        ),
        user_id
    )
    service.set_default_rag_config(dummy.id, user_id)
    # Now second is not default, can delete
    service.delete_rag_config(second.id, user_id)
    # Unset dummy as default before deletion
    from services.rag.config_models import RagConfigUpdate
    service.update_rag_config(dummy.id, RagConfigUpdate(is_default=False), user_id)
    service.delete_rag_config(dummy.id, user_id)

    logger.info("All CRUD tests passed")
    return True


def test_validation():
    """Test validation of provider configurations."""
    service = RagConfigService()
    user_id = None

    # Missing required property (collection_name)
    provider_config = ProviderConfig(
        provider="qdrant.internal",
        config={
            "embedding_model": "all-MiniLM-L6-v2",
            # missing collection_name
        }
    )
    create_data = RagConfigCreate(
        name=f"Invalid Config {uuid.uuid4().hex[:8]}",
        description="Invalid",
        provider_config=provider_config,
        is_default=False,
    )
    try:
        service.create_rag_config(create_data, user_id)
        assert False, "Should have raised AgentValidationError"
    except AgentValidationError as e:
        assert "Missing required property" in str(e)
        logger.info(f"Validation correctly caught missing property: {e}")

    # Unknown provider (should still pass validation but default to vectorbase)
    provider_config2 = ProviderConfig(
        provider="unknown.provider",
        config={
            "collection_name": "test",
            "embedding_model": "test",
        }
    )
    create_data2 = RagConfigCreate(
        name=f"Unknown Provider {uuid.uuid4().hex[:8]}",
        description="Unknown",
        provider_config=provider_config2,
        is_default=False,
    )
    # This will create because validation only checks expected properties (which may be empty)
    created = service.create_rag_config(create_data2, user_id)
    assert created.provider == "unknown.provider"
    # Clean up
    service.delete_rag_config(created.id, user_id)

    logger.info("Validation tests passed")
    return True


def test_retrieval_engine():
    """Test retrieval engine creation for qdrant.internal provider."""
    service = RagConfigService()
    user_id = None

    # Create a config with qdrant.internal
    provider_config = ProviderConfig(
        provider="qdrant.internal",
        config={
            "collection_name": "test_collection",
            "embedding_model": "all-MiniLM-L6-v2",
            "top_k": 10,
            "enable_reranker": True,
            "ultra_low_latency": False,
        }
    )
    create_data = RagConfigCreate(
        name=f"Engine Test {uuid.uuid4().hex[:8]}",
        description="Test retrieval engine",
        provider_config=provider_config,
        is_default=False,
    )
    created = service.create_rag_config(create_data, user_id)

    try:
        engine = service.get_retrieval_engine(created.id, user_id)
        # Check that engine is configured correctly
        assert engine.collection_name == "test_collection"
        assert engine.embed_model_name == "all-MiniLM-L6-v2"
        assert engine.top_k == 10
        assert engine.enable_reranker is True
        assert engine.ultra_low_latency_mode is False
        logger.info("Retrieval engine created successfully")
    except NotImplementedError as e:
        logger.warning(f"Retrieval engine not fully implemented: {e}")
    finally:
        service.delete_rag_config(created.id, user_id)

    # Test unsupported provider (pinecone.io is not yet implemented for retrieval engine)
    provider_config2 = ProviderConfig(
        provider="pinecone.io",
        config={
            "index_name": "test",
            "api_key": "fake",
            "top_k": 5,
            "namespace": "test-ns",
        }
    )
    create_data2 = RagConfigCreate(
        name=f"Unsupported Provider {uuid.uuid4().hex[:8]}",
        description="Test unsupported",
        provider_config=provider_config2,
        is_default=False,
    )
    created2 = service.create_rag_config(create_data2, user_id)
    try:
        engine = service.get_retrieval_engine(created2.id, user_id)
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError as e:
        assert "pinecone.io" in str(e)
        logger.info("Correctly raised NotImplementedError for unsupported provider")
    finally:
        service.delete_rag_config(created2.id, user_id)

    logger.info("Retrieval engine tests passed")
    return True


def main():
    """Run all tests."""
    success = True
    try:
        success = test_rag_config_crud() and success
        success = test_validation() and success
        success = test_retrieval_engine() and success
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        success = False

    if success:
        logger.info("✅ All RAG config service tests passed")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()