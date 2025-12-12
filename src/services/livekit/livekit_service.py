import asyncio
import logging
import uuid
from typing import Any, Dict

from livekit import api

from environment_config import config
from services.agents_admin.agent_service import AgentService

logger = logging.getLogger(__name__)


class LiveKitService:
    """
    Service pour gérer les connexions LiveKit et générer des tokens d'accès.
    """

    def __init__(self, livekit_url: str = None, api_key: str = None, api_secret: str = None):
        self.livekit_url = livekit_url or config.livekit_url.replace("ws://", "http://")
        self.api_key = api_key or config.livekit_api_key
        self.api_secret = api_secret or config.livekit_api_secret

        # Initialiser les services existants
        self.stimm_service = None  # Sera initialisé plus tard si nécessaire
        self.agent_service = AgentService()

        # Suivi des sessions actives
        self.active_sessions = {}

        # SIP room monitoring - DISABLED (now handled by SIPBridgeIntegration)
        self.sip_monitoring_enabled = False
        self.sip_room_prefix = "sip-inbound"
        self.sip_agent_name = "Development Agent"
        self.monitored_sip_rooms = set()
        self.sip_monitor_task = None
        self.lkapi = None  # Will be initialized in methods

    async def start_sip_monitoring(self):
        """Start monitoring for SIP rooms (DEPRECATED - use SIPBridgeIntegration)"""
        logger.warning("⚠️ LiveKitService.start_sip_monitoring() is deprecated. SIP monitoring is now handled by SIPBridgeIntegration.")
        return

    async def stop_sip_monitoring(self):
        """Stop monitoring for SIP rooms (DEPRECATED)"""
        logger.warning("⚠️ LiveKitService.stop_sip_monitoring() is deprecated.")
        return

    async def _monitor_sip_rooms(self):
        """Monitor for SIP rooms and spawn agents automatically (DEPRECATED)"""
        logger.warning("⚠️ LiveKitService._monitor_sip_rooms() is deprecated.")
        await asyncio.sleep(1)

    async def _spawn_agent_for_sip_room(self, room_name: str) -> bool:
        """Spawn our custom agent for a SIP room (DEPRECATED)"""
        logger.warning(f"⚠️ LiveKitService._spawn_agent_for_sip_room({room_name}) is deprecated. Use SIPBridgeIntegration instead.")
        return False

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
                room_name = f"stimm_{agent_id}_{uuid.uuid4().hex[:8]}"

            # Générer un token d'accès pour le frontend
            token = (
                api.AccessToken(self.api_key, self.api_secret)
                .with_identity(f"user_{uuid.uuid4().hex[:8]}")
                .with_name("User")
                .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
            )

            access_token = token.to_jwt()

            logger.info(f"✅ Generated LiveKit token for room {room_name} for agent {agent_id}")

            return {
                "room_name": room_name,
                "access_token": access_token,
                "livekit_url": self.livekit_url.replace("http", "ws"),
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
            agent_token = (
                api.AccessToken(self.api_key, self.api_secret)
                .with_identity(f"agent_{agent_id}_{uuid.uuid4().hex[:8]}")
                .with_name(f"Agent-{agent_id}")
                .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
            )

            agent_access_token = agent_token.to_jwt()

            # Use shared factory to create session
            from services.agents.agent_factory import create_agent_session

            session_data = await create_agent_session(agent_id=agent_id, room_name=room_name, token=agent_access_token, livekit_url=self.livekit_url)

            agent_bridge = session_data["agent_bridge"]
            session_id = session_data["session_id"]

            # Store the session
            self.active_sessions[session_id] = {
                "agent_id": agent_id,
                "room_name": room_name,
                "stimm_service": session_data["stimm_service"],
                "agent_bridge": agent_bridge,
                "created_at": asyncio.get_event_loop().time(),
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
