"""
Database package for stimm application.
"""

from .models import Agent, AgentSession, Base, RagConfig, User
from .session import get_db, get_engine

# For backward compatibility, provide engine as a property
engine = get_engine()

__all__ = ["get_db", "engine", "Base", "User", "Agent", "AgentSession", "RagConfig"]
