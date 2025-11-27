#Main entry point for the voicebot application.


import asyncio
import logging
import os
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

# Import route modules
from services.llm.llm_routes import router as llm_router
from services.rag.chatbot_routes import router as chatbot_router
from services.stt.routes import router as stt_router
from services.stt.web_routes import router as stt_web_router
from services.tts.routes import router as tts_router
from services.tts.web_routes import router as tts_web_router
from services.agents.routes import router as voicebot_router
from services.agents_admin.routes import router as agent_router
from services.provider_constants import get_provider_constants
from services.webrtc.signaling import router as signaling_router
from services.livekit.routes import router as livekit_router
from utils.logging_config import configure_logging

# Configure logging early
configure_logging()

logger = logging.getLogger(__name__)

# Configure logging early
configure_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Voicebot API", version="1.0.0")

# Detect if we're running from src/ directory or root
current_dir = Path.cwd()
if current_dir.name == "src":
    # Running from src/ directory
    BASE_DIR = current_dir
else:
    # Running from root directory
    BASE_DIR = current_dir / "src"


@app.on_event("startup")
async def startup_event():
    """Preload RAG models and initialize agent system at server startup"""
    try:
        logger.info("Starting RAG preloading and agent initialization at server startup...")
        
        # Import here to avoid circular imports
        try:
            from services.rag.rag_preloader import rag_preloader
            
            # Start preloading in background to not block server startup
            async def preload_rag():
                success = await rag_preloader.preload_all()
                if success:
                    logger.info("✅ RAG preloading completed successfully")
                else:
                    logger.error(f"❌ RAG preloading failed: {rag_preloader.preload_error}")
            
            # Start preloading as background task
            asyncio.create_task(preload_rag())
            
        except ImportError as e:
            logger.warning(f"RAG preloader not available, using lazy loading: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize RAG preloader: {e}")
        
        # Initialize agent system (default agent only; no global provider config)
        try:
            # Force environment config loading first to ensure correct database URL
            from environment_config import get_environment_config
            env_config = get_environment_config()
            logger.info(f"Environment detected as: {env_config.environment_type}")
            logger.info(f"Database URL: {env_config.database_url}")
            
            # Now initialize agent system
            from services.agents_admin.dev_agent_creator import initialize_default_agent
            from database.session import get_db

            db_gen = get_db()
            db = next(db_gen)
            try:
                success = initialize_default_agent(db)
                if success:
                    logger.info("✅ Default development agent initialized successfully")
                else:
                    logger.error("❌ Failed to initialize default development agent")
            finally:
                db_gen.close()

        except ImportError as e:
            logger.warning(f"Agent system not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize agent system: {e}")
        
        # Note: Voicebot services are now initialized per-session in LiveKit service
        # to avoid concurrency issues with providers like Deepgram
        
    except Exception as e:
        logger.error(f"Failed to start startup procedures: {e}")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for voicebot wrapper
static_dir = BASE_DIR / "services" / "agents" / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="voicebot_static")

# Mount shared static files
shared_static_dir = BASE_DIR / "static"
app.mount("/shared-static", StaticFiles(directory=str(shared_static_dir)), name="shared_static")

# Mount app static files
app.mount("/app-static", StaticFiles(directory=str(shared_static_dir)), name="app_static")

# Include routers
app.include_router(llm_router, prefix="/api", tags=["llm"])
app.include_router(chatbot_router, prefix="/rag", tags=["chatbot"])
app.include_router(stt_router, prefix="/api", tags=["stt"])
app.include_router(stt_web_router, prefix="/stt", tags=["stt-web"])
app.include_router(tts_router, prefix="/api", tags=["tts"])
app.include_router(tts_web_router, prefix="/tts", tags=["tts-web"])
app.include_router(voicebot_router, prefix="/api", tags=["voicebot"])
app.include_router(agent_router, prefix="/api", tags=["agents"])
app.include_router(signaling_router, prefix="/api", tags=["webrtc"])
app.include_router(livekit_router, prefix="/api", tags=["livekit"])
# Templates for voicebot interface
templates_dir = BASE_DIR / "services" / "agents" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/")
def read_root():
    return {"message": "Welcome to the Voicebot API"}

@app.get("/health")
def health_check():
    """Basic health check"""
    return {"status": "healthy"}


@app.get("/api/provider-constants")
async def get_provider_constants_endpoint():
    """Serve provider constants to JavaScript frontend"""
    try:
        constants = get_provider_constants()
        return constants
    except Exception as e:
        logger.error(f"Failed to load provider constants: {e}")
        return {"error": "Failed to load provider constants"}


@app.get("/health/rag-preloading")
async def rag_preloading_health():
    """Health check for RAG preloading status"""
    try:
        from services.rag.rag_preloader import rag_preloader
        
        status_info = rag_preloader.get_status()
        
        if rag_preloader.is_preloaded:
            return {
                "status": "healthy",
                "rag_preloading": "completed",
                "preload_time": rag_preloader.preload_time,
                "preload_start_time": rag_preloader.preload_start_time,
                "rag_state_available": rag_preloader.rag_state is not None
            }
        elif rag_preloader.preload_error:
            return {
                "status": "degraded",
                "rag_preloading": "failed",
                "preload_error": rag_preloader.preload_error,
                "preload_time": rag_preloader.preload_time,
                "rag_state_available": rag_preloader.rag_state is not None
            }
        else:
            return {
                "status": "loading",
                "rag_preloading": "in_progress",
                "preload_start_time": rag_preloader.preload_start_time,
                "rag_state_available": rag_preloader.rag_state is not None
            }
            
    except ImportError:
        return {
            "status": "degraded",
            "rag_preloading": "not_available",
            "message": "RAG preloader module not available, using lazy loading"
        }
    except Exception as e:
        return {
            "status": "error",
            "rag_preloading": "unknown",
            "error": str(e)
        }

@app.get("/voicebot/interface")
async def voicebot_interface(request: Request):
    """Serve the voicebot interface."""
    return templates.TemplateResponse("voicebot.html", {"request": request})

if __name__ == "__main__":
    # Note: When running with uvicorn, uvicorn's own logging config might interact with ours.
    # But since we set force=True in configure_logging, ours should prevail if called before.
    # However, uvicorn.run re-configures logging unless log_config=None is passed.
    # For simplicity, we let uvicorn handle the basics via log_level arg,
    # but our configure_logging() above ensures app loggers are set correctly at module level.
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level=log_level)