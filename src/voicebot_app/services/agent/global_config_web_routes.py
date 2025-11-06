"""
Global Provider Configuration Web Routes

Web routes for the global configuration administration interface.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter(prefix="/agent", tags=["agent-web"])

# Get the templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.get("/global-config", response_class=HTMLResponse)
async def global_config_admin(request: Request):
    """Global configuration administration interface"""
    return templates.TemplateResponse(
        "global_config_admin.html",
        {"request": request}
    )