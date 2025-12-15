# Main entry point for the stimm application.


import asyncio
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.agents.routes import router as stimm_router
from services.agents_admin.routes import router as agent_router
from services.livekit.routes import router as livekit_router

# Import route modules
from services.llm.llm_routes import router as llm_router
from services.provider_constants import get_provider_constants
from services.rag.chatbot_routes import router as chatbot_router
from services.rag.rag_config_routes import router as rag_config_router
from services.stt.routes import router as stt_router
from services.tts.routes import router as tts_router
from services.webrtc.signaling import router as signaling_router
from utils.logging_config import configure_logging

# Configure logging early
configure_logging()

logger = logging.getLogger(__name__)

# Configure logging early
configure_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Stimm API", version="1.0.0")

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
            logger.info(f"Environment detected as: {os.getenv('ENVIRONMENT', 'local')}")
            logger.info(f"Database URL: {env_config.database_url}")

            # Now initialize agent system
            from database.session import get_db
            from services.agents_admin.dev_agent_creator import initialize_default_agent

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

        # Initialize SIP Bridge Integration if enabled
        try:
            from services.sip_bridge_integration import start_sip_bridge

            # Start SIP Bridge in background (singleton ensures no duplicates)
            start_sip_bridge()
            logger.info("✅ SIP Bridge Integration initialized (robust singleton)")

        except ImportError as e:
            logger.warning(f"SIP Bridge Integration not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize SIP Bridge Integration: {e}")

        # Note: Stimm services are now initialized per-session in LiveKit service
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

# Mount shared static files
shared_static_dir = BASE_DIR / "static"
# Only mount if directory exists (for legacy support if needed)
if shared_static_dir.exists():
    app.mount("/shared-static", StaticFiles(directory=str(shared_static_dir)), name="shared_static")
    app.mount("/app-static", StaticFiles(directory=str(shared_static_dir)), name="app_static")

# Include routers
app.include_router(llm_router, prefix="/api", tags=["llm"])
app.include_router(chatbot_router, prefix="/rag", tags=["chatbot"])
app.include_router(stt_router, prefix="/api", tags=["stt"])
app.include_router(tts_router, prefix="/api", tags=["tts"])
app.include_router(stimm_router, prefix="/api", tags=["stimm"])
app.include_router(agent_router, prefix="/api", tags=["agents"])
app.include_router(rag_config_router, prefix="/api", tags=["rag-configs"])
app.include_router(signaling_router, prefix="/api", tags=["webrtc"])
app.include_router(livekit_router, prefix="/api", tags=["livekit"])


@app.get("/")
def read_root():
    return {"message": "Welcome to the Stimm API"}


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

        rag_preloader.get_status()  # status info not used but call kept for side effects

        if rag_preloader.is_preloaded:
            return {
                "status": "healthy",
                "rag_preloading": "completed",
                "preload_time": rag_preloader.preload_time,
                "preload_start_time": rag_preloader.preload_start_time,
                "rag_state_available": rag_preloader.rag_state is not None,
            }
        elif rag_preloader.preload_error:
            return {
                "status": "degraded",
                "rag_preloading": "failed",
                "preload_error": rag_preloader.preload_error,
                "preload_time": rag_preloader.preload_time,
                "rag_state_available": rag_preloader.rag_state is not None,
            }
        else:
            return {
                "status": "loading",
                "rag_preloading": "in_progress",
                "preload_start_time": rag_preloader.preload_start_time,
                "rag_state_available": rag_preloader.rag_state is not None,
            }

    except ImportError:
        return {
            "status": "degraded",
            "rag_preloading": "not_available",
            "message": "RAG preloader module not available, using lazy loading",
        }
    except Exception as e:
        return {"status": "error", "rag_preloading": "unknown", "error": str(e)}


@app.get("/health/sip-bridge")
async def sip_bridge_health():
    """Health check for SIP Bridge status"""
    try:
        from services.sip_bridge_integration import sip_bridge_integration

        if not sip_bridge_integration.is_enabled():
            return {
                "status": "disabled",
                "sip_bridge": "not_enabled",
                "message": "SIP Bridge is disabled (ENABLE_SIP_BRIDGE=false)",
            }

        if sip_bridge_integration.is_running():
            return {"status": "healthy", "sip_bridge": "running", "message": "SIP Bridge is running normally"}
        else:
            return {
                "status": "degraded",
                "sip_bridge": "not_running",
                "message": "SIP Bridge is enabled but not running",
            }

    except ImportError:
        return {
            "status": "error",
            "sip_bridge": "not_available",
            "message": "SIP Bridge Integration module not available",
        }
    except Exception as e:
        return {"status": "error", "sip_bridge": "error", "error": str(e)}


@app.get("/health/sip-bridge-status")
async def sip_bridge_status():
    """Detailed status of SIP Bridge"""
    try:
        from services.sip_bridge_integration import get_sip_bridge_status

        return get_sip_bridge_status()
    except ImportError:
        return {"error": "SIP Bridge Integration module not available"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Note: When running with uvicorn, uvicorn's own logging config might interact with ours.
    # But since we set force=True in configure_logging, ours should prevail if called before.
    # However, uvicorn.run re-configures logging unless log_config=None is passed.
    # For simplicity, we let uvicorn handle the basics via log_level arg,
    # but our configure_logging() above ensures app loggers are set correctly at module level.
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    host = os.getenv("HOST", "127.0.0.1")  # Default to localhost for security, allow override
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host=host, port=port, log_level=log_level)
