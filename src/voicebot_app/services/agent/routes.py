"""
Agent Management API Routes

This module provides FastAPI routes for managing agents, including:
- CRUD operations for agents
- Default agent management
- Provider configuration management
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .agent_service import AgentService
from .models import Agent, AgentCreate, AgentUpdate, ProviderConfig
from .exceptions import AgentNotFoundError, AgentValidationError
from ...database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=List[Agent])
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all agents with pagination"""
    agent_service = AgentService(db)
    agents = agent_service.get_all_agents(skip=skip, limit=limit)
    return agents


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific agent by ID"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.get_agent(agent_id)
        return agent
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found"
        )


@router.post("/", response_model=Agent, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_db)
):
    """Create a new agent"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.create_agent(agent_data)
        return agent
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent"
        )


@router.put("/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing agent"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.update_agent(agent_id, agent_data)
        return agent
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found"
        )
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent"
        )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Delete an agent"""
    agent_service = AgentService(db)
    try:
        agent_service.delete_agent(agent_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent"
        )


@router.get("/default/current", response_model=Agent)
async def get_default_agent(
    db: Session = Depends(get_db)
):
    """Get the current default agent"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.get_default_agent()
        return agent
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default agent found"
        )


@router.put("/{agent_id}/set-default", response_model=Agent)
async def set_default_agent(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Set an agent as the default agent"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.set_default_agent(agent_id)
        return agent
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to set default agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default agent"
        )


@router.get("/{agent_id}/providers", response_model=dict)
async def get_agent_providers(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Get provider configurations for an agent"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.get_agent(agent_id)
        return agent.provider_configs
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found"
        )


@router.put("/{agent_id}/providers", response_model=Agent)
async def update_agent_providers(
    agent_id: str,
    provider_configs: dict,
    db: Session = Depends(get_db)
):
    """Update provider configurations for an agent"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.update_agent_providers(agent_id, provider_configs)
        return agent
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found"
        )
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update agent providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent providers"
        )