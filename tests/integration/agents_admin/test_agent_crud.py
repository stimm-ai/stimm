#!/usr/bin/env python3
"""
Integration tests for Agent CRUD operations.

Tests the AgentService's create, read, update, delete, and list operations
for agent management.
"""

import uuid

import pytest

from services.agents_admin.agent_service import AgentService
from services.agents_admin.exceptions import (
    AgentNotFoundError,
    AgentValidationError,
)
from services.agents_admin.models import AgentCreate, AgentUpdate, ProviderConfig


@pytest.fixture
def agent_service():
    """Create an AgentService instance for testing."""
    return AgentService()


@pytest.fixture
def sample_provider_configs(agent_service):
    """Get sample provider configs from default agent."""
    default_agent = agent_service.get_default_agent()
    return {
        "llm": ProviderConfig(provider=default_agent.llm_provider, config=default_agent.llm_config),
        "tts": ProviderConfig(provider=default_agent.tts_provider, config=default_agent.tts_config),
        "stt": ProviderConfig(provider=default_agent.stt_provider, config=default_agent.stt_config),
    }


def test_create_agent(agent_service, sample_provider_configs):
    """Test creating a new agent with valid configuration."""
    test_name = f"Test Agent {uuid.uuid4().hex[:8]}"

    agent_data = AgentCreate(
        name=test_name,
        description="Integration test agent",
        system_prompt="You are a test assistant.",
        llm_config=sample_provider_configs["llm"],
        tts_config=sample_provider_configs["tts"],
        stt_config=sample_provider_configs["stt"],
        is_default=False,
    )

    # Create agent
    created = agent_service.create_agent(agent_data)

    assert created.name == test_name
    assert created.description == "Integration test agent"
    assert created.system_prompt == "You are a test assistant."
    assert created.is_default is False
    assert created.is_active is True

    # Cleanup
    agent_service.delete_agent(created.id)
    print(f"✅ Created and deleted test agent: {test_name}")


def test_get_agent(agent_service, sample_provider_configs):
    """Test retrieving an agent by ID."""
    # Create a test agent
    test_name = f"Get Test Agent {uuid.uuid4().hex[:8]}"
    agent_data = AgentCreate(
        name=test_name,
        description="Test get operation",
        llm_config=sample_provider_configs["llm"],
        tts_config=sample_provider_configs["tts"],
        stt_config=sample_provider_configs["stt"],
        is_default=False,
    )
    created = agent_service.create_agent(agent_data)

    # Retrieve the agent
    retrieved = agent_service.get_agent(created.id)

    assert retrieved.id == created.id
    assert retrieved.name == test_name
    assert retrieved.description == "Test get operation"

    # Cleanup
    agent_service.delete_agent(created.id)
    print(f"✅ Retrieved agent by ID: {created.id}")


def test_get_nonexistent_agent(agent_service):
    """Test retrieving a non-existent agent raises error."""
    fake_id = uuid.uuid4()

    with pytest.raises(AgentNotFoundError):
        agent_service.get_agent(fake_id)

    print("✅ Correctly raised AgentNotFoundError for non-existent agent")


def test_update_agent(agent_service, sample_provider_configs):
    """Test updating an agent's configuration."""
    # Create a test agent
    test_name = f"Update Test Agent {uuid.uuid4().hex[:8]}"
    agent_data = AgentCreate(
        name=test_name,
        description="Original description",
        llm_config=sample_provider_configs["llm"],
        tts_config=sample_provider_configs["tts"],
        stt_config=sample_provider_configs["stt"],
        is_default=False,
    )
    created = agent_service.create_agent(agent_data)

    # Update the agent
    update_data = AgentUpdate(name=f"{test_name} Updated", description="Updated description", system_prompt="Updated system prompt")
    updated = agent_service.update_agent(created.id, update_data)

    assert updated.name == f"{test_name} Updated"
    assert updated.description == "Updated description"
    assert updated.system_prompt == "Updated system prompt"

    # Cleanup
    agent_service.delete_agent(created.id)
    print(f"✅ Updated agent: {created.id}")


def test_delete_agent(agent_service, sample_provider_configs):
    """Test deleting a non-default agent."""
    # Create a test agent
    test_name = f"Delete Test Agent {uuid.uuid4().hex[:8]}"
    agent_data = AgentCreate(
        name=test_name, description="To be deleted", llm_config=sample_provider_configs["llm"], tts_config=sample_provider_configs["tts"], stt_config=sample_provider_configs["stt"], is_default=False
    )
    created = agent_service.create_agent(agent_data)
    agent_id = created.id

    # Delete the agent
    result = agent_service.delete_agent(agent_id)
    assert result is True

    # Verify it's gone
    with pytest.raises(AgentNotFoundError):
        agent_service.get_agent(agent_id)

    print(f"✅ Deleted agent: {agent_id}")


def test_delete_default_agent_fails(agent_service):
    """Test that deleting the default agent raises an error."""
    default_agent = agent_service.get_default_agent()

    # Should not be able to delete default agent
    with pytest.raises(AgentValidationError) as exc_info:
        agent_service.delete_agent(default_agent.id)

    assert "Cannot delete default agent" in str(exc_info.value)
    print("✅ Correctly prevented deletion of default agent")


def test_list_agents(agent_service, sample_provider_configs):
    """Test listing all agents with filtering."""
    # Create a few test agents
    test_agents = []
    for i in range(3):
        test_name = f"List Test Agent {i} {uuid.uuid4().hex[:4]}"
        agent_data = AgentCreate(
            name=test_name,
            description=f"Test agent {i}",
            llm_config=sample_provider_configs["llm"],
            tts_config=sample_provider_configs["tts"],
            stt_config=sample_provider_configs["stt"],
            is_default=False,
        )
        created = agent_service.create_agent(agent_data)
        test_agents.append(created)

    # List all active agents
    result = agent_service.list_agents(active_only=True)

    assert len(result.agents) >= 3  # At least our 3 test agents

    # Verify our test agents are in the list
    agent_ids = [agent.id for agent in result.agents]
    for test_agent in test_agents:
        assert test_agent.id in agent_ids

    # Cleanup
    for test_agent in test_agents:
        agent_service.delete_agent(test_agent.id)

    print(f"✅ Listed agents and found {len(result.agents)} active agents")


def test_get_default_agent(agent_service):
    """Test getting the default agent."""
    default_agent = agent_service.get_default_agent()

    assert default_agent is not None
    assert default_agent.is_default is True
    assert default_agent.is_active is True

    print(f"✅ Retrieved default agent: {default_agent.name}")


if __name__ == "__main__":
    print("Running agent CRUD integration tests...")
    pytest.main([__file__, "-v"])
