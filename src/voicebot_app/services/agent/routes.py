"""
Agent Management API Routes

This module provides FastAPI routes for managing agents, including:
- CRUD operations for agents
- Default agent management
- Provider configuration management
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .agent_service import AgentService
from .models import AgentResponse, AgentCreate, AgentUpdate, ProviderConfig
from .exceptions import AgentNotFoundError, AgentValidationError
from .property_mapper import PropertyMapper
from database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all agents with pagination"""
    agent_service = AgentService(db)
    agents_result = agent_service.list_agents(skip=skip, limit=limit)
    
    # Convert provider-specific configs back to standardized format for frontend
    standardized_agents = []
    for agent in agents_result.agents:
        agent_dict = agent.model_dump()
        
        # Convert LLM config
        if agent_dict.get('llm_config') and agent_dict.get('llm_provider'):
            agent_dict['llm_config'] = PropertyMapper.from_provider_format(
                "llm", agent_dict['llm_provider'], agent_dict['llm_config']
            )
        
        # Convert TTS config
        if agent_dict.get('tts_config') and agent_dict.get('tts_provider'):
            agent_dict['tts_config'] = PropertyMapper.from_provider_format(
                "tts", agent_dict['tts_provider'], agent_dict['tts_config']
            )
        
        # Convert STT config
        if agent_dict.get('stt_config') and agent_dict.get('stt_provider'):
            agent_dict['stt_config'] = PropertyMapper.from_provider_format(
                "stt", agent_dict['stt_provider'], agent_dict['stt_config']
            )
        
        standardized_agents.append(AgentResponse(**agent_dict))
    
    return standardized_agents


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific agent by ID"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.get_agent(agent_id)
        
        # Convert provider-specific configs back to standardized format for frontend
        agent_dict = agent.model_dump()
        
        # Convert LLM config
        if agent_dict.get('llm_config') and agent_dict.get('llm_provider'):
            agent_dict['llm_config'] = PropertyMapper.from_provider_format(
                "llm", agent_dict['llm_provider'], agent_dict['llm_config']
            )
        
        # Convert TTS config
        if agent_dict.get('tts_config') and agent_dict.get('tts_provider'):
            agent_dict['tts_config'] = PropertyMapper.from_provider_format(
                "tts", agent_dict['tts_provider'], agent_dict['tts_config']
            )
        
        # Convert STT config
        if agent_dict.get('stt_config') and agent_dict.get('stt_provider'):
            agent_dict['stt_config'] = PropertyMapper.from_provider_format(
                "stt", agent_dict['stt_provider'], agent_dict['stt_config']
            )
        
        return AgentResponse(**agent_dict)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found"
        )


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
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
            detail={"message": str(e), "errors": [str(e)]}
        )
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create agent", "errors": [str(e)]}
        )


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing agent"""
    agent_service = AgentService(db)
    try:
        agent = agent_service.update_agent(agent_id, agent_data)
        
        # Convert provider-specific configs back to standardized format for frontend
        agent_dict = agent.model_dump()
        
        # Convert LLM config
        if agent_dict.get('llm_config') and agent_dict.get('llm_provider'):
            agent_dict['llm_config'] = PropertyMapper.from_provider_format(
                "llm", agent_dict['llm_provider'], agent_dict['llm_config']
            )
        
        # Convert TTS config
        if agent_dict.get('tts_config') and agent_dict.get('tts_provider'):
            agent_dict['tts_config'] = PropertyMapper.from_provider_format(
                "tts", agent_dict['tts_provider'], agent_dict['tts_config']
            )
        
        # Convert STT config
        if agent_dict.get('stt_config') and agent_dict.get('stt_provider'):
            agent_dict['stt_config'] = PropertyMapper.from_provider_format(
                "stt", agent_dict['stt_provider'], agent_dict['stt_config']
            )
        
        return AgentResponse(**agent_dict)
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


@router.get("/default/current", response_model=AgentResponse)
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


@router.put("/{agent_id}/set-default", response_model=AgentResponse)
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


@router.put("/{agent_id}/providers", response_model=AgentResponse)
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


@router.get("/providers/available", response_model=Dict[str, Any])
async def get_available_providers():
    """Get available providers from provider_constants.json"""
    try:
        # Load provider constants from JSON file
        provider_constants_path = Path(__file__).parent.parent / "provider_constants.json"
        with open(provider_constants_path, 'r') as f:
            provider_constants = json.load(f)
        
        # Transform the data to match the frontend format using property mapper
        providers = {
            "llm": {
                "providers": [
                    {"value": provider, "label": provider.replace('.com', '').replace('.ai', '').replace('.local', '').title()}
                    for provider in provider_constants.get("llm", {}).keys()
                ],
                "configurable_fields": PropertyMapper.get_standardized_fields("llm")
            },
            "tts": {
                "providers": [
                    {"value": provider, "label": provider.replace('.com', '').replace('.io', '').replace('.local', '').replace('.ai', '').title()}
                    for provider in provider_constants.get("tts", {}).keys()
                ],
                "configurable_fields": PropertyMapper.get_standardized_fields("tts")
            },
            "stt": {
                "providers": [
                    {"value": provider, "label": provider.replace('.com', '').replace('.local', '').title()}
                    for provider in provider_constants.get("stt", {}).keys()
                ],
                "configurable_fields": PropertyMapper.get_standardized_fields("stt")
            }
        }
        
        return providers
    except Exception as e:
        logger.error(f"Failed to load provider constants: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load available providers"
        )