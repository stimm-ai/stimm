"""
Custom exceptions for agent management service.
"""

class AgentServiceError(Exception):
    """Base exception for agent service errors."""
    pass


class AgentNotFoundError(AgentServiceError):
    """Raised when an agent is not found."""
    
    def __init__(self, agent_id: str = None, message: str = None):
        if message:
            super().__init__(message)
        elif agent_id:
            super().__init__(f"Agent with ID '{agent_id}' not found")
        else:
            super().__init__("Agent not found")


class AgentAlreadyExistsError(AgentServiceError):
    """Raised when trying to create an agent that already exists."""
    
    def __init__(self, name: str = None, message: str = None):
        if message:
            super().__init__(message)
        elif name:
            super().__init__(f"Agent with name '{name}' already exists")
        else:
            super().__init__("Agent already exists")


class AgentValidationError(AgentServiceError):
    """Raised when agent validation fails."""
    
    def __init__(self, message: str):
        super().__init__(f"Agent validation failed: {message}")


class AgentConfigurationError(AgentServiceError):
    """Raised when agent configuration is invalid."""
    
    def __init__(self, message: str):
        super().__init__(f"Agent configuration error: {message}")


class DefaultAgentConflictError(AgentServiceError):
    """Raised when there's a conflict with default agent operations."""
    
    def __init__(self, message: str):
        super().__init__(f"Default agent conflict: {message}")


class AgentProviderError(AgentServiceError):
    """Raised when there's an error with agent provider configuration."""
    
    def __init__(self, provider_type: str, message: str):
        super().__init__(f"{provider_type} provider error: {message}")