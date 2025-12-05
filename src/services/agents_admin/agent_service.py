"""
Agent Service for CRUD operations and agent management.
"""
import logging
import uuid
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database import get_db, User, Agent, AgentSession, RagConfig
from .models import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentSessionCreate
)
from .exceptions import (
    AgentNotFoundError,
    AgentAlreadyExistsError,
    AgentValidationError,
    DefaultAgentConflictError
)
from .provider_registry import get_provider_registry

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing agents and their configurations."""
    
    def __init__(self, db_session: Session = None):
        """
        Initialize AgentService.
        
        Args:
            db_session: SQLAlchemy session (if None, will use dependency injection)
        """
        self.db_session = db_session
    
    def _get_session(self) -> Session:
        """Get database session."""
        if self.db_session:
            return self.db_session
        # Create a new session if none provided
        from database.session import SessionLocal
        return SessionLocal()
    
    def _get_system_user_id(self) -> UUID:
        """Get the system user ID."""
        session = self._get_session()
        try:
            system_user = session.query(User).filter(
                User.username == 'system'
            ).first()
            
            if not system_user:
                # Create system user if it doesn't exist
                system_user = User(
                    id=uuid.UUID('00000000-0000-0000-0000-000000000000'),
                    username='system',
                    email='system@stimm.local'
                )
                session.add(system_user)
                session.commit()
                session.refresh(system_user)
            
            return system_user.id
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()
    
    def _validate_provider_config(self, provider_type: str, provider_name: str, config: Dict[str, Any]) -> None:
        """
        Validate provider configuration against expected properties.
        
        Args:
            provider_type: Type of provider ('llm', 'tts', 'stt')
            provider_name: Name of provider (e.g., 'groq.com', 'kokoro.local')
            config: Provider configuration to validate
            
        Raises:
            AgentValidationError: If validation fails
        """
        registry = get_provider_registry()
        
        # Get expected properties for this provider
        expected_properties = registry.get_expected_properties(provider_type, provider_name)
        
        if not expected_properties:
            logger.warning(f"No expected properties defined for {provider_type}.{provider_name}")
            return
        
        # Check for required properties
        for prop in expected_properties:
            if prop not in config:
                raise AgentValidationError(
                    f"Missing required property '{prop}' for {provider_type} provider '{provider_name}'"
                )
        
        # Check for unknown properties
        for prop in config.keys():
            if prop not in expected_properties:
                logger.warning(f"Unknown property '{prop}' for {provider_type} provider '{provider_name}'")
    
    def _validate_agent_configurations(self, agent_data: AgentCreate) -> None:
        """
        Validate all provider configurations for an agent.
        
        Args:
            agent_data: Agent creation data
            
        Raises:
            AgentValidationError: If any validation fails
        """
        # Validate LLM configuration
        if agent_data.llm_config:
            self._validate_provider_config(
                'llm',
                agent_data.llm_config.provider,
                agent_data.llm_config.config
            )
        
        # Validate TTS configuration
        if agent_data.tts_config:
            self._validate_provider_config(
                'tts',
                agent_data.tts_config.provider,
                agent_data.tts_config.config
            )
        
        # Validate STT configuration
        if agent_data.stt_config:
            self._validate_provider_config(
                'stt',
                agent_data.stt_config.provider,
                agent_data.stt_config.config
            )
    
    def _validate_agent_update_configurations(self, agent_data: AgentUpdate) -> None:
        """
        Validate provider configurations for an agent update.
        
        Args:
            agent_data: Agent update data
            
        Raises:
            AgentValidationError: If any validation fails
        """
        # Validate LLM configuration if provided
        if agent_data.llm_config:
            self._validate_provider_config(
                'llm',
                agent_data.llm_config.provider,
                agent_data.llm_config.config
            )
        
        # Validate TTS configuration if provided
        if agent_data.tts_config:
            self._validate_provider_config(
                'tts',
                agent_data.tts_config.provider,
                agent_data.tts_config.config
            )
        
        # Validate STT configuration if provided
        if agent_data.stt_config:
            self._validate_provider_config(
                'stt',
                agent_data.stt_config.provider,
                agent_data.stt_config.config
            )
    
    def _validate_rag_config_id(self, rag_config_id: Optional[UUID], user_id: UUID, session: Session) -> None:
        """
        Validate that a RAG configuration ID exists and belongs to the user (or system).
        
        Args:
            rag_config_id: RAG configuration ID to validate (can be None)
            user_id: User ID to check ownership
            session: Database session
            
        Raises:
            AgentValidationError: If RAG config not found or doesn't belong to user
        """
        if rag_config_id is None:
            return
        
        rag_config = session.query(RagConfig).filter(
            and_(
                RagConfig.id == rag_config_id,
                RagConfig.user_id == user_id
            )
        ).first()
        
        if not rag_config:
            raise AgentValidationError(
                f"RAG configuration with ID {rag_config_id} not found or does not belong to user"
            )
      
    def create_agent(self, agent_data: AgentCreate, user_id: Optional[UUID] = None) -> AgentResponse:
        """
        Create a new agent.
        
        Args:
            agent_data: Agent creation data
            user_id: User ID (if None, uses system user)
        
        Returns:
            AgentResponse: Created agent data
        
        Raises:
            AgentAlreadyExistsError: If agent with same name exists
            AgentValidationError: If validation fails
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()
            
            # Check if agent with same name exists for this user
            existing_agent = session.query(Agent).filter(
                and_(
                    Agent.user_id == user_id,
                    Agent.name == agent_data.name
                )
            ).first()
            
            if existing_agent:
                raise AgentAlreadyExistsError(name=agent_data.name)
            
            # Validate provider configurations
            self._validate_agent_configurations(agent_data)
            
            # Handle default agent logic
            if agent_data.is_default:
                # Unset any existing default agent for this user
                session.query(Agent).filter(
                    and_(
                        Agent.user_id == user_id,
                        Agent.is_default == True
                    )
                ).update({'is_default': False})
            
            # Validate RAG configuration ID if provided
            self._validate_rag_config_id(agent_data.rag_config_id, user_id, session)
            
            # Create new agent with standardized field names
            agent = Agent(
                user_id=user_id,
                name=agent_data.name,
                description=agent_data.description,
                system_prompt=agent_data.system_prompt,
                llm_provider=agent_data.llm_config.provider,
                tts_provider=agent_data.tts_config.provider,
                stt_provider=agent_data.stt_config.provider,
                llm_config=agent_data.llm_config.config,
                tts_config=agent_data.tts_config.config,
                stt_config=agent_data.stt_config.config,
                is_default=agent_data.is_default,
                rag_config_id=agent_data.rag_config_id,
                is_active=True
            )
            
            session.add(agent)
            session.commit()
            session.refresh(agent)
            
            # Invalidate agent manager cache for the new agent
            try:
                from .agent_manager import get_agent_manager
                agent_manager = get_agent_manager()
                agent_manager.invalidate_cache(agent.id)
                logger.debug(f"Invalidated cache for new agent {agent.id}")
            except Exception as e:
                logger.warning(f"Failed to invalidate agent cache: {e}")
            
            logger.info(f"Created agent: {agent.name} (ID: {agent.id})")
            return AgentResponse.model_validate(agent)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()
    
    def get_agent(self, agent_id: UUID, user_id: Optional[UUID] = None) -> AgentResponse:
        """
        Get agent by ID.
        
        Args:
            agent_id: Agent ID
            user_id: User ID (if None, uses system user)
            
        Returns:
            AgentResponse: Agent data
            
        Raises:
            AgentNotFoundError: If agent not found
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()
            
            agent = session.query(Agent).filter(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == user_id
                )
            ).first()
            
            if not agent:
                raise AgentNotFoundError(agent_id=str(agent_id))
            
            return AgentResponse.model_validate(agent)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()
    
    def list_agents(
        self,
        user_id: Optional[UUID] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> AgentListResponse:
        """
        List agents for a user.
        
        Args:
            user_id: User ID (if None, uses system user)
            active_only: Only return active agents
            skip: Number of agents to skip
            limit: Maximum number of agents to return
        
        Returns:
            AgentListResponse: List of agents and total count
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()
            
            query = session.query(Agent).filter(Agent.user_id == user_id)
            
            if active_only:
                query = query.filter(Agent.is_active == True)
            
            total = query.count()
            agents = query.offset(skip).limit(limit).all()
            
            agent_responses = [AgentResponse.model_validate(agent) for agent in agents]
            
            return AgentListResponse(
                agents=agent_responses,
                total=total
            )
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()
    
    def update_agent(
        self,
        agent_id: UUID,
        agent_data: AgentUpdate,
        user_id: Optional[UUID] = None
    ) -> AgentResponse:
        """
        Update an existing agent.
        
        Args:
            agent_id: Agent ID
            agent_data: Agent update data
            user_id: User ID (if None, uses system user)
        
        Returns:
            AgentResponse: Updated agent data
        
        Raises:
            AgentNotFoundError: If agent not found
            AgentAlreadyExistsError: If name conflict
            DefaultAgentConflictError: If default agent conflict
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()
            
            agent = session.query(Agent).filter(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == user_id
                )
            ).first()
            
            if not agent:
                raise AgentNotFoundError(agent_id=str(agent_id))
            
            # Check for name conflict
            if agent_data.name and agent_data.name != agent.name:
                existing_agent = session.query(Agent).filter(
                    and_(
                        Agent.user_id == user_id,
                        Agent.name == agent_data.name,
                        Agent.id != agent_id
                    )
                ).first()
                
                if existing_agent:
                    raise AgentAlreadyExistsError(name=agent_data.name)
                
                # Validate provider configurations if provided
                self._validate_agent_update_configurations(agent_data)
                
                # Handle default agent logic
            if agent_data.is_default is True and not agent.is_default:
                # Unset any existing default agent for this user
                session.query(Agent).filter(
                    and_(
                        Agent.user_id == user_id,
                        Agent.is_default == True,
                        Agent.id != agent_id
                    )
                ).update({'is_default': False})
            
            # Validate RAG configuration ID if provided
            if agent_data.rag_config_id is not None:
                self._validate_rag_config_id(agent_data.rag_config_id, user_id, session)
            
            # Update fields
            update_fields = {}
            
            if agent_data.name is not None:
                update_fields['name'] = agent_data.name
            if agent_data.description is not None:
                update_fields['description'] = agent_data.description
            if agent_data.system_prompt is not None:
                update_fields['system_prompt'] = agent_data.system_prompt
            if agent_data.is_default is not None:
                update_fields['is_default'] = agent_data.is_default
            if agent_data.is_active is not None:
                update_fields['is_active'] = agent_data.is_active
            if agent_data.rag_config_id is not None:
                update_fields['rag_config_id'] = agent_data.rag_config_id
            
            # Update provider configurations - merge with existing configs to preserve API keys
            # Mapping is now handled within each provider implementation
            if agent_data.llm_config is not None:
                update_fields['llm_provider'] = agent_data.llm_config.provider
                # Merge new config with existing config to preserve API keys if not provided
                merged_llm_config = agent.llm_config.copy()
                merged_llm_config.update(agent_data.llm_config.config)
                update_fields['llm_config'] = merged_llm_config
            
            if agent_data.tts_config is not None:
                update_fields['tts_provider'] = agent_data.tts_config.provider
                # Merge new config with existing config to preserve API keys if not provided
                merged_tts_config = agent.tts_config.copy()
                merged_tts_config.update(agent_data.tts_config.config)
                update_fields['tts_config'] = merged_tts_config
            
            if agent_data.stt_config is not None:
                update_fields['stt_provider'] = agent_data.stt_config.provider
                # Merge new config with existing config to preserve API keys if not provided
                merged_stt_config = agent.stt_config.copy()
                merged_stt_config.update(agent_data.stt_config.config)
                update_fields['stt_config'] = merged_stt_config
            
            # Apply updates
            for field, value in update_fields.items():
                setattr(agent, field, value)
            
            session.commit()
            session.refresh(agent)
            
            # Invalidate agent manager cache to ensure real-time updates
            try:
                from .agent_manager import get_agent_manager
                agent_manager = get_agent_manager()
                agent_manager.invalidate_cache(agent_id)
                logger.debug(f"Invalidated cache for agent {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to invalidate agent cache: {e}")
            
            logger.info(f"Updated agent: {agent.name} (ID: {agent.id})")
            return AgentResponse.model_validate(agent)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()
    
    def delete_agent(self, agent_id: UUID, user_id: Optional[UUID] = None) -> bool:
        """
        Delete an agent.
        
        Args:
            agent_id: Agent ID
            user_id: User ID (if None, uses system user)
        
        Returns:
            bool: True if deleted successfully
        
        Raises:
            AgentNotFoundError: If agent not found
            AgentValidationError: If trying to delete default agent
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()
            
            agent = session.query(Agent).filter(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == user_id
                )
            ).first()
            
            if not agent:
                raise AgentNotFoundError(agent_id=str(agent_id))
            
            # Prevent deletion of default agent
            if agent.is_default:
                raise AgentValidationError("Cannot delete default agent")
            
            session.delete(agent)
            session.commit()
            
            logger.info(f"Deleted agent: {agent.name} (ID: {agent.id})")
            return True
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()
    
    def get_default_agent(self, user_id: Optional[UUID] = None) -> AgentResponse:
        """
        Get the default agent for a user.
        
        Args:
            user_id: User ID (if None, uses system user)
            
        Returns:
            AgentResponse: Default agent data
            
        Raises:
            AgentNotFoundError: If no default agent found
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()
            
            agent = session.query(Agent).filter(
                and_(
                    Agent.user_id == user_id,
                    Agent.is_default == True,
                    Agent.is_active == True
                )
            ).first()
            
            if not agent:
                raise AgentNotFoundError("No default agent found")
            
            return AgentResponse.model_validate(agent)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()
    
    def set_default_agent(self, agent_id: UUID, user_id: Optional[UUID] = None) -> AgentResponse:
        """
        Set an agent as the default for a user.
        
        Args:
            agent_id: Agent ID to set as default
            user_id: User ID (if None, uses system user)
        
        Returns:
            AgentResponse: Updated agent data
        
        Raises:
            AgentNotFoundError: If agent not found
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()
            
            # Verify agent exists and belongs to user
            agent = session.query(Agent).filter(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == user_id
                )
            ).first()
            
            if not agent:
                raise AgentNotFoundError(agent_id=str(agent_id))
            
            # Unset any existing default agent
            session.query(Agent).filter(
                and_(
                    Agent.user_id == user_id,
                    Agent.is_default == True
                )
            ).update({'is_default': False})
            
            # Set new default agent
            agent.is_default = True
            session.commit()
            session.refresh(agent)
            
            # Invalidate agent manager cache for the new default agent
            try:
                from .agent_manager import get_agent_manager
                agent_manager = get_agent_manager()
                agent_manager.invalidate_cache(agent_id)
                logger.debug(f"Invalidated cache for new default agent {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to invalidate agent cache: {e}")
            
            logger.info(f"Set default agent: {agent.name} (ID: {agent.id})")
            return AgentResponse.model_validate(agent)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()