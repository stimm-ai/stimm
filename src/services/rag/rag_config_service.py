"""
RAG Configuration Service for CRUD operations.
"""

import logging
import uuid
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from database import RagConfig, User
from services.agents_admin.exceptions import (
    AgentAlreadyExistsError,
    AgentNotFoundError,
    AgentValidationError,
)
from services.agents_admin.provider_registry import get_provider_registry

from .config_models import (
    RagConfigCreate,
    RagConfigListResponse,
    RagConfigResponse,
    RagConfigUpdate,
)

logger = logging.getLogger(__name__)


class RagConfigService:
    """Service for managing RAG configurations."""

    def __init__(self, db_session: Session = None):
        """
        Initialize RagConfigService.

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
            system_user = session.query(User).filter(User.username == "system").first()

            if not system_user:
                # Create system user if it doesn't exist
                system_user = User(id=uuid.UUID("00000000-0000-0000-0000-000000000000"), username="system", email="system@stimm.local")
                session.add(system_user)
                session.commit()
                session.refresh(system_user)

            return system_user.id
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def _determine_provider_type(self, provider_name: str) -> str:
        """
        Determine provider type based on provider name.

        Args:
            provider_name: Provider name (e.g., 'qdrant.internal', 'pinecone.io', 'rag.saas')

        Returns:
            'vectorbase' for managed vector databases, 'saas_rag' for SaaS RAG services.
        """
        if provider_name.endswith(".internal") or provider_name.endswith(".io"):
            return "vectorbase"
        elif provider_name.startswith("rag."):
            return "saas_rag"
        else:
            # Default to vectorbase for unknown providers
            logger.warning(f"Unknown provider '{provider_name}', defaulting to 'vectorbase'")
            return "vectorbase"

    def _validate_provider_config(self, provider_name: str, config: Dict[str, Any]) -> None:
        """
        Validate provider configuration against expected properties.

        Args:
            provider_name: Name of provider (e.g., 'qdrant.internal', 'pinecone.io')
            config: Provider configuration to validate

        Raises:
            AgentValidationError: If validation fails
        """
        registry = get_provider_registry()

        # Get expected properties for this provider (type 'rag')
        expected_properties = registry.get_expected_properties("rag", provider_name)

        if not expected_properties:
            logger.warning(f"No expected properties defined for rag provider '{provider_name}'")
            return

        # Check for required properties
        for prop in expected_properties:
            if prop not in config:
                raise AgentValidationError(f"Missing required property '{prop}' for RAG provider '{provider_name}'")

        # Check for unknown properties
        for prop in config.keys():
            if prop not in expected_properties:
                logger.warning(f"Unknown property '{prop}' for RAG provider '{provider_name}'")

    def _validate_rag_config_create(self, rag_config_data: RagConfigCreate) -> None:
        """
        Validate RAG configuration creation data.

        Args:
            rag_config_data: RAG configuration creation data

        Raises:
            AgentValidationError: If validation fails
        """
        # Validate provider configuration
        self._validate_provider_config(rag_config_data.provider_config.provider, rag_config_data.provider_config.config)

    def _validate_rag_config_update(self, rag_config_data: RagConfigUpdate) -> None:
        """
        Validate RAG configuration update data.

        Args:
            rag_config_data: RAG configuration update data

        Raises:
            AgentValidationError: If validation fails
        """
        if rag_config_data.provider_config:
            self._validate_provider_config(rag_config_data.provider_config.provider, rag_config_data.provider_config.config)

    def create_rag_config(self, rag_config_data: RagConfigCreate, user_id: Optional[UUID] = None) -> RagConfigResponse:
        """
        Create a new RAG configuration.

        Args:
            rag_config_data: RAG configuration creation data
            user_id: User ID (if None, uses system user)

        Returns:
            RagConfigResponse: Created RAG configuration data

        Raises:
            AgentAlreadyExistsError: If RAG config with same name exists
            AgentValidationError: If validation fails
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()

            # Check if RAG config with same name exists for this user
            existing_config = session.query(RagConfig).filter(and_(RagConfig.user_id == user_id, RagConfig.name == rag_config_data.name)).first()

            if existing_config:
                raise AgentAlreadyExistsError(name=rag_config_data.name)

            # Validate provider configurations
            self._validate_rag_config_create(rag_config_data)

            # Determine provider type
            provider_type = self._determine_provider_type(rag_config_data.provider_config.provider)

            # Handle default RAG config logic
            if rag_config_data.is_default:
                # Unset any existing default RAG config for this user
                session.query(RagConfig).filter(and_(RagConfig.user_id == user_id, RagConfig.is_default)).update({"is_default": False})

            # Create new RAG config
            rag_config = RagConfig(
                user_id=user_id,
                name=rag_config_data.name,
                description=rag_config_data.description,
                provider_type=provider_type,
                provider=rag_config_data.provider_config.provider,
                provider_config=rag_config_data.provider_config.config,
                is_default=rag_config_data.is_default,
                is_active=True,
            )

            session.add(rag_config)
            session.commit()
            session.refresh(rag_config)

            logger.info(f"Created RAG config: {rag_config.name} (ID: {rag_config.id})")
            return RagConfigResponse.model_validate(rag_config)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def get_rag_config(self, rag_config_id: UUID, user_id: Optional[UUID] = None) -> RagConfigResponse:
        """
        Get RAG configuration by ID.

        Args:
            rag_config_id: RAG configuration ID
            user_id: User ID (if None, uses system user)

        Returns:
            RagConfigResponse: RAG configuration data

        Raises:
            AgentNotFoundError: If RAG config not found
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()

            rag_config = session.query(RagConfig).filter(and_(RagConfig.id == rag_config_id, RagConfig.user_id == user_id)).first()

            if not rag_config:
                raise AgentNotFoundError(agent_id=str(rag_config_id))

            return RagConfigResponse.model_validate(rag_config)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def list_rag_configs(self, user_id: Optional[UUID] = None, active_only: bool = True, skip: int = 0, limit: int = 100) -> RagConfigListResponse:
        """
        List RAG configurations for a user.

        Args:
            user_id: User ID (if None, uses system user)
            active_only: Only return active configurations
            skip: Number of configurations to skip
            limit: Maximum number of configurations to return

        Returns:
            RagConfigListResponse: List of RAG configurations and total count
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()

            query = session.query(RagConfig).filter(RagConfig.user_id == user_id)

            if active_only:
                query = query.filter(RagConfig.is_active)

            total = query.count()
            configs = query.offset(skip).limit(limit).all()

            config_responses = [RagConfigResponse.model_validate(config) for config in configs]

            return RagConfigListResponse(configs=config_responses, total=total)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def update_rag_config(self, rag_config_id: UUID, rag_config_data: RagConfigUpdate, user_id: Optional[UUID] = None) -> RagConfigResponse:
        """
        Update an existing RAG configuration.

        Args:
            rag_config_id: RAG configuration ID
            rag_config_data: RAG configuration update data
            user_id: User ID (if None, uses system user)

        Returns:
            RagConfigResponse: Updated RAG configuration data

        Raises:
            AgentNotFoundError: If RAG config not found
            AgentAlreadyExistsError: If name conflict
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()

            rag_config = session.query(RagConfig).filter(and_(RagConfig.id == rag_config_id, RagConfig.user_id == user_id)).first()

            if not rag_config:
                raise AgentNotFoundError(agent_id=str(rag_config_id))

            # Check for name conflict
            if rag_config_data.name and rag_config_data.name != rag_config.name:
                existing_config = (
                    session.query(RagConfig)
                    .filter(
                        and_(
                            RagConfig.user_id == user_id,
                            RagConfig.name == rag_config_data.name,
                            RagConfig.id != rag_config_id,
                        )
                    )
                    .first()
                )

                if existing_config:
                    raise AgentAlreadyExistsError(name=rag_config_data.name)

            # Validate provider configurations if provided
            if rag_config_data.provider_config:
                self._validate_rag_config_update(rag_config_data)

            # Handle default RAG config logic
            if rag_config_data.is_default is True and not rag_config.is_default:
                # Unset any existing default RAG config for this user
                session.query(RagConfig).filter(and_(RagConfig.user_id == user_id, RagConfig.is_default, RagConfig.id != rag_config_id)).update({"is_default": False})

            # Update fields
            update_fields = {}

            if rag_config_data.name is not None:
                update_fields["name"] = rag_config_data.name
            if rag_config_data.description is not None:
                update_fields["description"] = rag_config_data.description
            if rag_config_data.is_default is not None:
                update_fields["is_default"] = rag_config_data.is_default
            if rag_config_data.is_active is not None:
                update_fields["is_active"] = rag_config_data.is_active

            # Update provider configuration - merge with existing config to preserve API keys
            if rag_config_data.provider_config is not None:
                # Determine provider type if provider changed
                if rag_config_data.provider_config.provider != rag_config.provider:
                    update_fields["provider"] = rag_config_data.provider_config.provider
                    update_fields["provider_type"] = self._determine_provider_type(rag_config_data.provider_config.provider)
                # Merge new config with existing config to preserve API keys if not provided
                merged_config = rag_config.provider_config.copy()
                merged_config.update(rag_config_data.provider_config.config)
                update_fields["provider_config"] = merged_config

            # Apply updates
            for field, value in update_fields.items():
                setattr(rag_config, field, value)

            session.commit()
            session.refresh(rag_config)

            logger.info(f"Updated RAG config: {rag_config.name} (ID: {rag_config.id})")
            return RagConfigResponse.model_validate(rag_config)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def delete_rag_config(self, rag_config_id: UUID, user_id: Optional[UUID] = None) -> bool:
        """
        Delete a RAG configuration.

        Args:
            rag_config_id: RAG configuration ID
            user_id: User ID (if None, uses system user)

        Returns:
            bool: True if deleted successfully

        Raises:
            AgentNotFoundError: If RAG config not found
            AgentValidationError: If trying to delete default RAG config
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()

            rag_config = session.query(RagConfig).filter(and_(RagConfig.id == rag_config_id, RagConfig.user_id == user_id)).first()

            if not rag_config:
                raise AgentNotFoundError(agent_id=str(rag_config_id))

            # Prevent deletion of default RAG config
            if rag_config.is_default:
                raise AgentValidationError("Cannot delete default RAG configuration")

            session.delete(rag_config)
            session.commit()

            logger.info(f"Deleted RAG config: {rag_config.name} (ID: {rag_config.id})")
            return True
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def get_default_rag_config(self, user_id: Optional[UUID] = None) -> RagConfigResponse:
        """
        Get the default RAG configuration for a user.

        Args:
            user_id: User ID (if None, uses system user)

        Returns:
            RagConfigResponse: Default RAG configuration data

        Raises:
            AgentNotFoundError: If no default RAG config found
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()

            rag_config = session.query(RagConfig).filter(and_(RagConfig.user_id == user_id, RagConfig.is_default, RagConfig.is_active)).first()

            if not rag_config:
                raise AgentNotFoundError("No default RAG configuration found")

            return RagConfigResponse.model_validate(rag_config)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def set_default_rag_config(self, rag_config_id: UUID, user_id: Optional[UUID] = None) -> RagConfigResponse:
        """
        Set a RAG configuration as the default for a user.

        Args:
            rag_config_id: RAG configuration ID to set as default
            user_id: User ID (if None, uses system user)

        Returns:
            RagConfigResponse: Updated RAG configuration data

        Raises:
            AgentNotFoundError: If RAG config not found
        """
        session = self._get_session()
        try:
            user_id = user_id or self._get_system_user_id()

            # Verify RAG config exists and belongs to user
            rag_config = session.query(RagConfig).filter(and_(RagConfig.id == rag_config_id, RagConfig.user_id == user_id)).first()

            if not rag_config:
                raise AgentNotFoundError(agent_id=str(rag_config_id))

            # Unset any existing default RAG config
            session.query(RagConfig).filter(and_(RagConfig.user_id == user_id, RagConfig.is_default)).update({"is_default": False})

            # Set new default RAG config
            rag_config.is_default = True
            session.commit()
            session.refresh(rag_config)

            logger.info(f"Set default RAG config: {rag_config.name} (ID: {rag_config.id})")
            return RagConfigResponse.model_validate(rag_config)
        finally:
            # Close the session only if it's locally created (not provided via db_session)
            if self.db_session is None:
                session.close()

    def get_retrieval_engine(self, rag_config_id: UUID, user_id: Optional[UUID] = None):
        """
        Create a RetrievalEngine instance for the given RAG configuration.

        Args:
            rag_config_id: RAG configuration ID
            user_id: User ID (if None, uses system user)

        Returns:
            RetrievalEngine: Configured retrieval engine

        Raises:
            AgentNotFoundError: If RAG config not found
            NotImplementedError: If provider is not yet supported
        """
        from .retrieval_engine import RetrievalEngine

        rag_config_resp = self.get_rag_config(rag_config_id, user_id)
        rag_config = rag_config_resp.model_dump()
        provider = rag_config["provider"]
        config = rag_config["provider_config"]

        if provider == "qdrant.internal":
            # Map provider config to RetrievalEngine parameters
            collection_name = config.get("collection_name")
            embed_model_name = config.get("embedding_model")
            top_k = config.get("top_k")
            enable_reranker = config.get("enable_reranker")
            ultra_low_latency = config.get("ultra_low_latency", True)
            dense_candidate_count = config.get("dense_candidate_count")
            lexical_candidate_count = config.get("lexical_candidate_count")
            # max_top_k = config.get("max_top_k")  # unused

            # Qdrant connection parameters (could be overridden via config, but default to global)
            qdrant_host = config.get("qdrant_host")
            qdrant_port = config.get("qdrant_port")
            qdrant_use_tls = config.get("qdrant_use_tls")
            qdrant_api_key = config.get("qdrant_api_key")

            engine = RetrievalEngine(
                collection_name=collection_name,
                embed_model_name=embed_model_name,
                top_k=top_k,
                enable_reranker=enable_reranker,
                ultra_low_latency_mode=ultra_low_latency,
                dense_candidate_count=dense_candidate_count,
                lexical_candidate_count=lexical_candidate_count,
                qdrant_host=qdrant_host,
                qdrant_port=qdrant_port,
                qdrant_use_tls=qdrant_use_tls,
                qdrant_api_key=qdrant_api_key,
            )
            return engine
        elif provider == "pinecone.io":
            # TODO: Implement Pinecone provider
            raise NotImplementedError(f"Provider {provider} not yet supported")
        elif provider == "rag.saas":
            # TODO: Implement SaaS RAG provider
            raise NotImplementedError(f"Provider {provider} not yet supported")
        else:
            raise ValueError(f"Unknown provider: {provider}")
