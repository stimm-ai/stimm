"""
STT Web Interface Routes

This module provides a web interface for testing the STT service
with audio playback and real-time transcription display.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from database.session import get_db
from services.agent.agent_service import AgentService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Test audio file path (relative to the src directory)
TEST_AUDIO_PATH = Path(__file__).parent.parent.parent / "services" / "stt" / "tests" / "Enregistrement.wav"


@router.get("/interface", response_class=HTMLResponse)
async def stt_interface(request: Request, db=Depends(get_db)):
    """Serve the STT web interface with agent selection"""
    try:
        # Get available agents
        agent_service = AgentService(db)
        agents_response = agent_service.list_agents()
        
        # Prepare agent data for template
        agent_list = [
            {
                "id": str(agent.id),
                "name": agent.name,
                "description": agent.description,
                "stt_provider": agent.stt_provider
            }
            for agent in agents_response.agents
        ]
        
        return templates.TemplateResponse(
            "stt_interface.html",
            {
                "request": request,
                "agents": agent_list
            }
        )
    except Exception as e:
        logger.error(f"Failed to load STT interface template: {e}")
        raise HTTPException(status_code=500, detail="Failed to load STT interface")


@router.get("/test-audio")
async def get_test_audio():
    """Serve the test audio file for the STT interface"""
    try:
        # Check if test audio file exists
        if not TEST_AUDIO_PATH.exists():
            logger.error(f"Test audio file not found at: {TEST_AUDIO_PATH}")
            raise HTTPException(status_code=404, detail="Test audio file not found")
        
        # Return the audio file
        return FileResponse(
            path=TEST_AUDIO_PATH,
            media_type="audio/wav",
            filename="Enregistrement.wav"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve test audio file: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve audio file")


@router.get("/health")
async def stt_web_health():
    """Health check for STT web interface"""
    return {
        "status": "healthy",
        "service": "stt_web_interface",
        "test_audio_available": TEST_AUDIO_PATH.exists()
    }


@router.get("/")
async def stt_web_root():
    """Root endpoint for STT web interface"""
    return {
        "service": "STT Web Interface",
        "endpoints": {
            "interface": "/stt/interface",
            "test_audio": "/stt/test-audio",
            "health": "/stt/health"
        },
        "description": "Web interface for testing STT service with audio playback and real-time transcription"
    }