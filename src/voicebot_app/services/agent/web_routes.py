from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional

from database.session import get_db
from .agent_service import AgentService
from .models import AgentResponse, AgentCreate, AgentUpdate

router = APIRouter(prefix="/agent", tags=["agent_web"])
templates = Jinja2Templates(directory="services/agent/templates")


@router.get("/admin", response_class=HTMLResponse)
async def agent_admin_interface(request: Request, db: Session = Depends(get_db)):
    """Agent administration interface"""
    agent_service = AgentService(db)
    
    try:
        agents_result = agent_service.list_agents()
        agents = agents_result.agents
        default_agent = agent_service.get_default_agent()
        
        return templates.TemplateResponse(
            "agent_admin.html",
            {
                "request": request,
                "agents": agents,
                "default_agent": default_agent,
                "error": None
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "agent_admin.html",
            {
                "request": request,
                "agents": [],
                "default_agent": None,
                "error": f"Error loading agents: {str(e)}"
            }
        )


@router.get("/create", response_class=HTMLResponse)
async def create_agent_form(request: Request):
    """Form for creating a new agent"""
    return templates.TemplateResponse(
        "agent_form.html",
        {
            "request": request,
            "agent": None,
            "action": "create",
            "error": None
        }
    )


@router.get("/edit/{agent_id}", response_class=HTMLResponse)
async def edit_agent_form(request: Request, agent_id: int, db: Session = Depends(get_db)):
    """Form for editing an existing agent"""
    agent_service = AgentService(db)
    
    try:
        agent = agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        return templates.TemplateResponse(
            "agent_form.html",
            {
                "request": request,
                "agent": agent,
                "action": "edit",
                "error": None
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "agent_form.html",
            {
                "request": request,
                "agent": None,
                "action": "edit",
                "error": f"Error loading agent: {str(e)}"
            }
        )