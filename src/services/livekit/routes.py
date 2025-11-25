import logging
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .livekit_service import livekit_service

logger = logging.getLogger(__name__)

router = APIRouter()

class CreateRoomRequest(BaseModel):
    agent_id: str
    room_name: str = None

class CreateRoomResponse(BaseModel):
    room_name: str
    access_token: str
    livekit_url: str
    session_id: str

class JobNotificationRequest(BaseModel):
    agent_id: str
    room_name: str
    user_id: str = None

@router.post("/livekit/create-room", response_model=CreateRoomResponse)
async def create_livekit_room(request: CreateRoomRequest):
    """
    Créer une salle LiveKit pour un agent spécifique.
    
    Le frontend appelle cet endpoint pour obtenir les informations de connexion.
    """
    try:
        logger.info(f"🎯 Creating LiveKit room for agent {request.agent_id}")
        
        # Créer la salle LiveKit
        room_info = await livekit_service.create_room_for_agent(
            request.agent_id,
            request.room_name
        )
        
        # Générer un ID de session
        session_id = str(uuid.uuid4())
        
        # Notifier l'agent de rejoindre la salle
        await livekit_service.notify_agent_to_join(request.agent_id, room_info["room_name"])
        
        response = CreateRoomResponse(
            room_name=room_info["room_name"],
            access_token=room_info["access_token"],
            livekit_url=room_info["livekit_url"],
            session_id=session_id
        )
        
        logger.info(f"✅ LiveKit room created: {room_info['room_name']} for agent {request.agent_id}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Failed to create LiveKit room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create LiveKit room: {str(e)}")

@router.post("/livekit/job-notification")
async def job_notification(request: JobNotificationRequest):
    """
    Endpoint pour notifier un agent de rejoindre une salle.
    
    Peut être appelé par le frontend ou d'autres services.
    """
    try:
        logger.info(f"📨 Job notification for agent {request.agent_id} to join room {request.room_name}")
        
        # Notifier l'agent via le service LiveKit
        await livekit_service.notify_agent_to_join(request.agent_id, request.room_name)
        
        return {
            "status": "success",
            "message": f"Agent {request.agent_id} notified to join room {request.room_name}"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send job notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send job notification: {str(e)}")

@router.get("/livekit/health")
async def livekit_health():
    """
    Vérifier la santé du service LiveKit.
    """
    try:
        # Vérifier que le service est opérationnel
        # Pour l'instant, nous retournons simplement un statut basique
        # sans dépendre de active_sessions qui n'est pas encore implémenté
        return {
            "status": "healthy",
            "active_sessions": len(livekit_service.active_sessions),
            "livekit_url": livekit_service.livekit_url
        }
    except Exception as e:
        logger.error(f"❌ LiveKit health check failed: {e}")
        raise HTTPException(status_code=503, detail="LiveKit service unavailable")

@router.delete("/livekit/session/{session_id}")
async def cleanup_session(session_id: str):
    """
    Nettoyer une session LiveKit terminée.
    """
    try:
        await livekit_service.cleanup_session(session_id)
        return {
            "status": "success",
            "message": f"Session {session_id} cleaned up"
        }
    except Exception as e:
        logger.error(f"❌ Failed to cleanup session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup session: {str(e)}")