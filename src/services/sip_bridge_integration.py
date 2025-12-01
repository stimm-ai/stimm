"""
SIP Bridge Integration Service
Intégration du sip-agent-bridge dans le conteneur voicebot-app
"""

import asyncio
import os
import logging
from typing import Optional
import threading
import time

logger = logging.getLogger(__name__)

class SIPBridgeIntegration:
    """Service d'intégration pour le SIP Agent Bridge"""
    
    def __init__(self):
        self.monitoring_thread: Optional[threading.Thread] = None
        self.running = False
        self._monitoring_task = None
        
    def start(self):
        """Démarre le service SIP Bridge si activé"""
        if not self.is_enabled():
            logger.info("SIP Bridge désactivé (ENABLE_SIP_BRIDGE=false)")
            return
            
        logger.info("Démarrage du SIP Bridge Integration...")
        
        try:
            # Créer et démarrer le monitoring dans un thread séparé
            self.monitoring_thread = threading.Thread(
                target=self._run_monitoring,
                name="SIPBridgeMonitoring",
                daemon=True
            )
            self.monitoring_thread.start()
            self.running = True
            logger.info("SIP Bridge monitoring démarré avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du SIP Bridge: {e}")
            self.running = False
            
    def stop(self):
        """Arrête le service SIP Bridge"""
        if not self.running:
            return
            
        logger.info("Arrêt du SIP Bridge Integration...")
        self.running = False
        
        try:
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5)
                
            logger.info("SIP Bridge monitoring arrêté avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt du SIP Bridge: {e}")
            
    def _run_monitoring(self):
        """Exécute le monitoring dans le thread"""
        try:
            # Importer ici pour éviter les imports circulaires
            from services.livekit.livekit_service import livekit_service
            
            logger.info("Démarrage du monitoring des rooms SIP...")
            
            # Démarrer le monitoring SIP du service LiveKit
            asyncio.run(livekit_service.start_sip_monitoring())
            logger.info("✅ SIP monitoring démarré via LiveKit service")
            
            # Garder le thread en vie tant que le monitoring est actif
            while self.running:
                time.sleep(1)
                
            # Arrêter le monitoring à la fin
            asyncio.run(livekit_service.stop_sip_monitoring())
            logger.info("✅ SIP monitoring arrêté")
            
        except Exception as e:
            logger.error(f"Erreur fatale dans le SIP Bridge monitoring: {e}")
            self.running = False
            
    def is_enabled(self) -> bool:
        """Vérifie si le SIP Bridge est activé"""
        return os.getenv("ENABLE_SIP_BRIDGE", "false").lower() == "true"
        
    def is_running(self) -> bool:
        """Vérifie si le service est en cours d'exécution"""
        return self.running and self.monitoring_thread and self.monitoring_thread.is_alive()

# Instance globale
sip_bridge_integration = SIPBridgeIntegration()

def start_sip_bridge():
    """Fonction helper pour démarrer le bridge"""
    sip_bridge_integration.start()

def stop_sip_bridge():
    """Fonction helper pour arrêter le bridge"""
    sip_bridge_integration.stop()