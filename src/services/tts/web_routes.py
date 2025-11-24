"""
TTS Web Interface Routes

This module provides a web interface for testing the TTS service
with token streaming simulation and real-time audio playback.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database.session import get_db
from ..agent.agent_service import AgentService
from database.models import Agent

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create router
router = APIRouter()

# Initialize templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


async def get_available_agents(db: Session = Depends(get_db)) -> List[Agent]:
    """Get list of available agents for selection"""
    try:
        agent_service = AgentService(db)
        agents_response = agent_service.list_agents()
        return agents_response.agents
    except Exception as e:
        logger.error(f"Failed to fetch agents: {e}")
        return []

@router.get("/interface", response_class=HTMLResponse)
async def tts_interface(request: Request, db: Session = Depends(get_db)):
    """Serve the TTS web interface"""
    try:
        # Get the TTS interface text from environment variable
        tts_interface_text = os.getenv("TTS_INTERFACE_TEXT", "Cette démonstration met en avant la diffusion en temps réel des jetons d’un modèle de langage. Merci d'avoir écouté ce texte. Ce test permer, grâce à des sliders de visualisation, de vérifier si la réception de chunks auidio se fait bien en parrallèlle avec l'envoie des tokens issue du LLM. J'éspère que cela vous aidera. A bientôt pour de nouvelles aventures. Et surtout prenez soin de vous. Au revoir.")

        # Get available agents
        agents = await get_available_agents(db)

        # Don't provide any global provider configuration
        # The JavaScript agent selector will handle displaying the selected agent's configuration
        return templates.TemplateResponse("tts_interface.html", {
            "request": request,
            "tts_interface_text": tts_interface_text,
            "agents": agents
        })
    except Exception as e:
        logger.error(f"Failed to load TTS interface template: {e}")
        raise HTTPException(status_code=500, detail="Failed to load TTS interface")

@router.get("/health")
async def tts_web_health():
    """Health check for TTS web interface"""
    return {
        "status": "healthy",
        "service": "tts_web_interface",
        "description": "Web interface for testing TTS service with token streaming and real-time audio playback"
    }

@router.get("/")
async def tts_web_root():
    """Root endpoint for TTS web interface"""
    return {
        "service": "TTS Web Interface",
        "endpoints": {
            "interface": "/tts/interface",
            "health": "/tts/health"
        },
        "description": "Web interface for testing TTS service with simulated LLM token streaming and real-time audio playback"
    }