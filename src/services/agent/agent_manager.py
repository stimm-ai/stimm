"""
Agent Manager for runtime agent resolution, caching, and session management.
"""
import logging
import time
import uuid
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from database import get_db, Agent, AgentSession
from .models import AgentConfig, AgentResponse, AgentSessionCreate
from .agent_service import AgentService
from .exceptions import AgentNotFoundError, AgentServiceError

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manages runtime agent resolution, caching, and session management.
    
    This class provides:
    - Agent configuration caching for performance
    - Runtime agent switching
    - Session management for different interfaces
    - Fallback to default agent when needed
    """
    
    def __init__(self, db_session: Session = None):
        """
        Initialize AgentManager.
        
        Args:
            db_session: SQLAlchemy session
        """
        self.db_session = db_session
        self.agent_service = AgentService(db_session)
        
        # Cache for agent configurations (agent_id -> AgentConfig)
        self._agent_cache: Dict[UUID, AgentConfig] = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._cache_timestamps: Dict[UUID, float] = {}
        
        # Active sessions (session_id -> agent_id)
        self._active_sessions: Dict[str, UUID] = {}
    
    def _get_session(self) -> Session:
        """Get database session."""
        if self.db_session:
            return self.db_session
        # Create a new session if none provided
        from database.session import SessionLocal
        return SessionLocal()
    
    def _clean_cache(self):
        """Clean expired cache entries."""
        current_time = time.time()
        expired_keys = [
            agent_id for agent_id, timestamp in self._cache_timestamps.items()
            if current_time - timestamp > self._cache_ttl
        ]
        
        for agent_id in expired_keys:
            self._agent_cache.pop(agent_id, None)
            self._cache_timestamps.pop(agent_id, None)
        
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
    
    def get_agent_config(self, agent_id: Optional[UUID] = None) -> AgentConfig:
        """
        Get agent configuration, with caching.
        
        Args:
            agent_id: Agent ID (if None, returns default agent)
            
        Returns:
            AgentConfig: Agent configuration
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        # Clean expired cache entries
        self._clean_cache()
        
        # If no agent_id provided, use default agent
        if agent_id is None:
            default_agent = self.agent_service.get_default_agent()
            agent_id = default_agent.id
        
        # Check cache first
        if agent_id in self._agent_cache:
            logger.debug(f"Cache hit for agent {agent_id}")
            return self._agent_cache[agent_id]
        
        # Get from database
        logger.debug(f"Cache miss for agent {agent_id}, fetching from database")
        agent = self.agent_service.get_agent(agent_id)
        agent_config = AgentConfig.from_agent_response(agent)
        
        # Cache the configuration
        self._agent_cache[agent_id] = agent_config
        self._cache_timestamps[agent_id] = time.time()
        
        return agent_config
    
    def get_agent_config_by_name(self, agent_name: str) -> AgentConfig:
        """
        Get agent configuration by name.
        
        Args:
            agent_name: Agent name
            
        Returns:
            AgentConfig: Agent configuration
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        session = self._get_session()
        
        # Find agent by name for system user
        system_user_id = self.agent_service._get_system_user_id()
        agent = session.query(Agent).filter(
            Agent.user_id == system_user_id,
            Agent.name == agent_name,
            Agent.is_active == True
        ).first()
        
        if not agent:
            raise AgentNotFoundError(f"Agent with name '{agent_name}' not found")
        
        return self.get_agent_config(agent.id)
    
    def create_session(self, session_data: AgentSessionCreate) -> str:
        """
        Create a new agent session.
        
        Args:
            session_data: Session creation data
            
        Returns:
            str: Session ID
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        session = self._get_session()
        
        # Verify agent exists
        try:
            self.agent_service.get_agent(session_data.agent_id)
        except AgentNotFoundError:
            raise AgentNotFoundError(f"Agent {session_data.agent_id} not found")
        
        # Create session
        agent_session = AgentSession(
            user_id=self.agent_service._get_system_user_id(),
            agent_id=session_data.agent_id,
            session_type=session_data.session_type,
            ip_address=session_data.ip_address,
            user_agent=session_data.user_agent,
            expires_at=datetime.utcnow() + timedelta(hours=24)  # 24-hour session
        )
        
        session.add(agent_session)
        session.commit()
        session.refresh(agent_session)
        
        session_id = str(agent_session.id)
        self._active_sessions[session_id] = session_data.agent_id
        
        logger.info(f"Created agent session: {session_id} for agent {session_data.agent_id}")
        return session_id
    
    def get_session_agent(self, session_id: str) -> AgentConfig:
        """
        Get agent configuration for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            AgentConfig: Agent configuration for the session
            
        Raises:
            AgentNotFoundError: If session or agent not found
        """
        session = self._get_session()
        
        # Check active sessions first
        if session_id in self._active_sessions:
            agent_id = self._active_sessions[session_id]
            return self.get_agent_config(agent_id)
        
        # Check database for session
        agent_session = session.query(AgentSession).filter(
            AgentSession.id == UUID(session_id),
            AgentSession.expires_at > datetime.utcnow()
        ).first()
        
        if not agent_session:
            raise AgentNotFoundError(f"Session {session_id} not found or expired")
        
        # Cache the session
        self._active_sessions[session_id] = agent_session.agent_id
        
        return self.get_agent_config(agent_session.agent_id)
    
    def end_session(self, session_id: str) -> bool:
        """
        End an agent session.
        
        Args:
            session_id: Session ID
            
        Returns:
            bool: True if session ended successfully
        """
        session = self._get_session()
        
        # Remove from active sessions
        self._active_sessions.pop(session_id, None)
        
        # Mark as expired in database
        agent_session = session.query(AgentSession).filter(
            AgentSession.id == UUID(session_id)
        ).first()
        
        if agent_session:
            agent_session.expires_at = datetime.utcnow()
            session.commit()
            logger.info(f"Ended agent session: {session_id}")
            return True
        
        return False
    
    def switch_agent_in_session(self, session_id: str, new_agent_id: UUID) -> AgentConfig:
        """
        Switch agent in an existing session.
        
        Args:
            session_id: Session ID
            new_agent_id: New agent ID
            
        Returns:
            AgentConfig: New agent configuration
            
        Raises:
            AgentNotFoundError: If session or agent not found
        """
        session = self._get_session()
        
        # Verify new agent exists
        try:
            self.agent_service.get_agent(new_agent_id)
        except AgentNotFoundError:
            raise AgentNotFoundError(f"Agent {new_agent_id} not found")
        
        # Update session in database
        agent_session = session.query(AgentSession).filter(
            AgentSession.id == UUID(session_id),
            AgentSession.expires_at > datetime.utcnow()
        ).first()
        
        if not agent_session:
            raise AgentNotFoundError(f"Session {session_id} not found or expired")
        
        # Update session
        agent_session.agent_id = new_agent_id
        session.commit()
        
        # Update active sessions cache
        self._active_sessions[session_id] = new_agent_id
        
        # Clear cache for old agent if no longer used
        old_agent_id = agent_session.agent_id
        if old_agent_id not in self._active_sessions.values():
            self._agent_cache.pop(old_agent_id, None)
            self._cache_timestamps.pop(old_agent_id, None)
        
        logger.info(f"Switched session {session_id} to agent {new_agent_id}")
        return self.get_agent_config(new_agent_id)
    
    def get_active_sessions_count(self) -> int:
        """
        Get count of active sessions.
        
        Returns:
            int: Number of active sessions
        """
        session = self._get_session()
        
        count = session.query(AgentSession).filter(
            AgentSession.expires_at > datetime.utcnow()
        ).count()
        
        return count
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions from database.
        
        Returns:
            int: Number of sessions cleaned up
        """
        session = self._get_session()
        
        # Delete expired sessions
        result = session.query(AgentSession).filter(
            AgentSession.expires_at <= datetime.utcnow()
        ).delete()
        
        session.commit()
        
        # Clean active sessions cache
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, timestamp in self._cache_timestamps.items()
            if current_time - timestamp > self._cache_ttl
        ]
        
        for session_id in expired_sessions:
            self._active_sessions.pop(session_id, None)
        
        logger.info(f"Cleaned up {result} expired sessions")
        return result
    
    def invalidate_cache(self, agent_id: Optional[UUID] = None):
        """
        Invalidate agent cache.
        
        Args:
            agent_id: Specific agent ID to invalidate (if None, invalidate all)
        """
        if agent_id:
            self._agent_cache.pop(agent_id, None)
            self._cache_timestamps.pop(agent_id, None)
            logger.debug(f"Invalidated cache for agent {agent_id}")
        else:
            self._agent_cache.clear()
            self._cache_timestamps.clear()
            logger.debug("Invalidated all agent cache")


# Global agent manager instance
_agent_manager: Optional[AgentManager] = None

def get_agent_manager() -> AgentManager:
    """Get global agent manager instance."""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager