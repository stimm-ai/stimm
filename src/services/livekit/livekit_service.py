import asyncio
import logging
import uuid
import os
from typing import Dict, Any
from livekit import api

# Import the new environment configuration
from environment_config import get_livekit_url

from services.agents.voicebot_service import get_voicebot_service, VoicebotService
from services.agents_admin.agent_service import AgentService
from .agent_bridge import create_agent_bridge

logger = logging.getLogger(__name__)

class LiveKitService:
    """
    Service pour gérer les connexions LiveKit et générer des tokens d'accès.
    """
    
    def __init__(self, livekit_url: str = None,
                 api_key: str = "devkey", api_secret: str = "secret"):
        # Use environment-aware LiveKit URL
        self.livekit_url = livekit_url or os.getenv("LIVEKIT_URL", get_livekit_url().replace("ws://", "http://"))
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Initialiser les services existants
        self.voicebot_service = None  # Sera initialisé plus tard si nécessaire
        self.agent_service = AgentService()
        
        # Suivi des sessions actives
        self.active_sessions = {}
    
    async def create_room_for_agent(self, agent_id: str, room_name: str = None) -> Dict[str, Any]:
        """
        Générer un token d'accès pour une salle LiveKit.
        
        Args:
            agent_id: ID de l'agent à connecter
            room_name: Nom spécifique de la salle (optionnel)
            
        Returns:
            Dict contenant room_name et token d'accès
        """
        try:
            # Utiliser le nom de salle fourni ou générer un nom unique
            if not room_name:
                room_name = f"voicebot_{agent_id}_{uuid.uuid4().hex[:8]}"
            
            # Générer un token d'accès pour le frontend
            token = api.AccessToken(self.api_key, self.api_secret) \
                .with_identity(f"user_{uuid.uuid4().hex[:8]}") \
                .with_name("User") \
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True
                ))
            
            access_token = token.to_jwt()
            
            logger.info(f"✅ Generated LiveKit token for room {room_name} for agent {agent_id}")
            
            return {
                "room_name": room_name,
                "access_token": access_token,
                "livekit_url": self.livekit_url.replace("http", "ws")
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate LiveKit token: {e}")
            raise
    
    async def notify_agent_to_join(self, agent_id: str, room_name: str):
        """
        Notifier un agent de rejoindre une salle LiveKit.
        
        Args:
            agent_id: ID de l'agent
            room_name: Nom de la salle à rejoindre
        """
        try:
            logger.info(f"📨 Notified agent {agent_id} to join room {room_name}")
            
            # Generate a token for the agent to connect to LiveKit
            agent_token = api.AccessToken(self.api_key, self.api_secret) \
                .with_identity(f"agent_{agent_id}_{uuid.uuid4().hex[:8]}") \
                .with_name(f"Agent-{agent_id}") \
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True
                ))
            
            agent_access_token = agent_token.to_jwt()
            
            # Create new service instances for this session to avoid concurrency issues
            from services.stt.stt import STTService
            from services.tts.tts import TTSService
            from services.vad.silero_service import SileroVADService
            from services.rag.chatbot_service import chatbot_service
            
            # Create new instances for this session
            stt_service = STTService(agent_id=agent_id)
            tts_service = TTSService(agent_id=agent_id)
            vad_service = SileroVADService()
            
            voicebot_service = VoicebotService(
                stt_service=stt_service,
                chatbot_service=chatbot_service,
                tts_service=tts_service,
                vad_service=vad_service,
                agent_id=agent_id
            )
            
            # Determine sample rate from TTS provider
            sample_rate = 24000  # Default
            if hasattr(tts_service, 'provider') and hasattr(tts_service.provider, 'sample_rate'):
                sample_rate = tts_service.provider.sample_rate
                logger.info(f"🎤 Using sample rate {sample_rate}Hz from TTS provider")
            
            # Create and connect the agent bridge to LiveKit
            agent_bridge = await create_agent_bridge(
                agent_id=agent_id,
                room_name=room_name,
                token=agent_access_token,
                livekit_url=self.livekit_url,
                sample_rate=sample_rate
            )
            
            # Connect the bridge to the voicebot service
            agent_bridge.set_voicebot_service(voicebot_service)
            
            # Store the session
            session_id = f"{agent_id}_{room_name}"
            self.active_sessions[session_id] = {
                "agent_id": agent_id,
                "room_name": room_name,
                "voicebot_service": voicebot_service,
                "agent_bridge": agent_bridge,
                "created_at": asyncio.get_event_loop().time()
            }
            
            # Start the agent session in the background
            asyncio.create_task(agent_bridge.start_session())
            
            logger.info(f"✅ Agent {agent_id} connected to LiveKit room {room_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to notify agent: {e}")
            raise

    async def cleanup_session(self, session_id: str):
        """
        Nettoyer une session LiveKit terminée.
        
        Args:
            session_id: ID de la session à nettoyer
        """
        try:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
                logger.info(f"✅ Cleaned up LiveKit session {session_id}")
            else:
                logger.warning(f"⚠️ Session {session_id} not found in active sessions")
                
        except Exception as e:
            logger.error(f"❌ Failed to cleanup session {session_id}: {e}")
            raise

# Instance globale du service
livekit_service = LiveKitService()