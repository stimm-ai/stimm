"""
Unit tests for agent management custom exceptions.

These tests verify that custom exception classes work correctly,
including proper error messages and inheritance hierarchy.
"""

import pytest

from services.agents_admin.exceptions import (
    AgentAlreadyExistsError,
    AgentConfigurationError,
    AgentNotFoundError,
    AgentProviderError,
    AgentServiceError,
    AgentValidationError,
    DefaultAgentConflictError,
)


@pytest.mark.unit
class TestAgentExceptions:
    """Test suite for agent service custom exceptions."""

    def test_agent_service_error_inheritance(self):
        """Test that AgentServiceError is the base exception."""
        error = AgentServiceError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_agent_not_found_error_with_id(self):
        """Test AgentNotFoundError with agent_id parameter."""
        agent_id = "test-agent-123"
        error = AgentNotFoundError(agent_id=agent_id)

        assert isinstance(error, AgentServiceError)
        assert agent_id in str(error)
        assert "not found" in str(error)

    def test_agent_not_found_error_with_message(self):
        """Test AgentNotFoundError with custom message."""
        custom_message = "Custom not found message"
        error = AgentNotFoundError(message=custom_message)

        assert str(error) == custom_message

    def test_agent_not_found_error_default(self):
        """Test AgentNotFoundError with no parameters."""
        error = AgentNotFoundError()

        assert "Agent not found" in str(error)

    def test_agent_already_exists_error_with_name(self):
        """Test AgentAlreadyExistsError with name parameter."""
        agent_name = "TestAgent"
        error = AgentAlreadyExistsError(name=agent_name)

        assert isinstance(error, AgentServiceError)
        assert agent_name in str(error)
        assert "already exists" in str(error)

    def test_agent_already_exists_error_with_message(self):
        """Test AgentAlreadyExistsError with custom message."""
        custom_message = "Custom exists message"
        error = AgentAlreadyExistsError(message=custom_message)

        assert str(error) == custom_message

    def test_agent_already_exists_error_default(self):
        """Test AgentAlreadyExistsError with no parameters."""
        error = AgentAlreadyExistsError()

        assert "already exists" in str(error)

    def test_agent_validation_error(self):
        """Test AgentValidationError message formatting."""
        validation_msg = "Invalid field value"
        error = AgentValidationError(validation_msg)

        assert isinstance(error, AgentServiceError)
        assert "validation failed" in str(error)
        assert validation_msg in str(error)

    def test_agent_configuration_error(self):
        """Test AgentConfigurationError message formatting."""
        config_msg = "Missing required config"
        error = AgentConfigurationError(config_msg)

        assert isinstance(error, AgentServiceError)
        assert "configuration error" in str(error)
        assert config_msg in str(error)

    def test_default_agent_conflict_error(self):
        """Test DefaultAgentConflictError message formatting."""
        conflict_msg = "Cannot delete default agent"
        error = DefaultAgentConflictError(conflict_msg)

        assert isinstance(error, AgentServiceError)
        assert "Default agent conflict" in str(error)
        assert conflict_msg in str(error)

    def test_agent_provider_error(self):
        """Test AgentProviderError with provider type."""
        provider_type = "LLM"
        error_msg = "Invalid API key"
        error = AgentProviderError(provider_type, error_msg)

        assert isinstance(error, AgentServiceError)
        assert provider_type in str(error)
        assert error_msg in str(error)
        assert "provider error" in str(error)

    def test_exception_hierarchy(self):
        """Test that all exceptions inherit from AgentServiceError."""
        exceptions = [
            AgentNotFoundError(),
            AgentAlreadyExistsError(),
            AgentValidationError("test"),
            AgentConfigurationError("test"),
            DefaultAgentConflictError("test"),
            AgentProviderError("test", "test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, AgentServiceError)
            assert isinstance(exc, Exception)
