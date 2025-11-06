"""
Agent Configuration Helper

Helper service to combine agent-specific configurations with global provider configurations.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from .global_config_service import GlobalConfigService, get_global_config_service
from .models import AgentResponse

logger = logging.getLogger(__name__)


class AgentConfigHelper:
    """Helper for managing agent configurations with global provider settings"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.global_config_service = get_global_config_service(db_session)
    
    def get_combined_agent_config(self, agent: AgentResponse) -> Dict[str, Any]:
        """
        Get combined configuration for an agent (agent-specific + global provider settings)
        
        Args:
            agent: Agent data
            
        Returns:
            Dict with combined configuration for LLM, TTS, and STT providers
        """
        try:
            combined_config = {
                "llm": {},
                "tts": {},
                "stt": {}
            }
            
            # Process LLM configuration
            if agent.llm_provider and agent.llm_config:
                llm_agent_config = {
                    "provider_type": "llm",
                    "provider_name": agent.llm_provider,
                    "provider_settings": agent.llm_config
                }
                combined_config["llm"] = self.global_config_service.get_provider_settings_for_agent(llm_agent_config)
            
            # Process TTS configuration
            if agent.tts_provider and agent.tts_config:
                tts_agent_config = {
                    "provider_type": "tts",
                    "provider_name": agent.tts_provider,
                    "provider_settings": agent.tts_config
                }
                combined_config["tts"] = self.global_config_service.get_provider_settings_for_agent(tts_agent_config)
            
            # Process STT configuration
            if agent.stt_provider and agent.stt_config:
                stt_agent_config = {
                    "provider_type": "stt",
                    "provider_name": agent.stt_provider,
                    "provider_settings": agent.stt_config
                }
                combined_config["stt"] = self.global_config_service.get_provider_settings_for_agent(stt_agent_config)
            
            return combined_config
            
        except Exception as e:
            logger.error(f"Failed to get combined agent config for agent {agent.id}: {e}")
            # Fallback to agent-specific config only
            return {
                "llm": agent.llm_config or {},
                "tts": agent.tts_config or {},
                "stt": agent.stt_config or {}
            }
    
    def get_provider_config_for_agent(self, agent: AgentResponse, provider_type: str) -> Dict[str, Any]:
        """
        Get combined configuration for a specific provider type for an agent
        
        Args:
            agent: Agent data
            provider_type: 'llm', 'tts', or 'stt'
            
        Returns:
            Dict with combined provider configuration
        """
        try:
            if provider_type == "llm" and agent.llm_provider and agent.llm_config:
                agent_config = {
                    "provider_type": "llm",
                    "provider_name": agent.llm_provider,
                    "provider_settings": agent.llm_config
                }
                return self.global_config_service.get_provider_settings_for_agent(agent_config)
            
            elif provider_type == "tts" and agent.tts_provider and agent.tts_config:
                agent_config = {
                    "provider_type": "tts",
                    "provider_name": agent.tts_provider,
                    "provider_settings": agent.tts_config
                }
                return self.global_config_service.get_provider_settings_for_agent(agent_config)
            
            elif provider_type == "stt" and agent.stt_provider and agent.stt_config:
                agent_config = {
                    "provider_type": "stt",
                    "provider_name": agent.stt_provider,
                    "provider_settings": agent.stt_config
                }
                return self.global_config_service.get_provider_settings_for_agent(agent_config)
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get {provider_type} config for agent {agent.id}: {e}")
            return {}
    
    def validate_agent_configuration(self, agent: AgentResponse) -> Dict[str, Any]:
        """
        Validate that an agent has all required configuration settings
        
        Args:
            agent: Agent data
            
        Returns:
            Dict with validation results
        """
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Get provider templates to check required settings
            templates = self.global_config_service.get_provider_templates()
            
            # Check LLM configuration
            if agent.llm_provider:
                llm_templates = [t for t in templates if t["provider_type"] == "llm" and t["provider_name"] == agent.llm_provider]
                combined_llm_config = self.get_provider_config_for_agent(agent, "llm")
                
                for template in llm_templates:
                    if template["is_required"] and template["setting_name"] not in combined_llm_config:
                        validation_results["is_valid"] = False
                        validation_results["errors"].append(
                            f"LLM: Missing required setting '{template['setting_name']}' for provider '{agent.llm_provider}'"
                        )
            
            # Check TTS configuration
            if agent.tts_provider:
                tts_templates = [t for t in templates if t["provider_type"] == "tts" and t["provider_name"] == agent.tts_provider]
                combined_tts_config = self.get_provider_config_for_agent(agent, "tts")
                
                for template in tts_templates:
                    if template["is_required"] and template["setting_name"] not in combined_tts_config:
                        validation_results["is_valid"] = False
                        validation_results["errors"].append(
                            f"TTS: Missing required setting '{template['setting_name']}' for provider '{agent.tts_provider}'"
                        )
            
            # Check STT configuration
            if agent.stt_provider:
                stt_templates = [t for t in templates if t["provider_type"] == "stt" and t["provider_name"] == agent.stt_provider]
                combined_stt_config = self.get_provider_config_for_agent(agent, "stt")
                
                for template in stt_templates:
                    if template["is_required"] and template["setting_name"] not in combined_stt_config:
                        validation_results["is_valid"] = False
                        validation_results["errors"].append(
                            f"STT: Missing required setting '{template['setting_name']}' for provider '{agent.stt_provider}'"
                        )
            
            # Add warnings for missing global configurations
            if agent.llm_provider:
                global_llm_config = self.global_config_service.get_provider_config("llm", agent.llm_provider)
                if not global_llm_config:
                    validation_results["warnings"].append(
                        f"LLM: No global configuration found for provider '{agent.llm_provider}'"
                    )
            
            if agent.tts_provider:
                global_tts_config = self.global_config_service.get_provider_config("tts", agent.tts_provider)
                if not global_tts_config:
                    validation_results["warnings"].append(
                        f"TTS: No global configuration found for provider '{agent.tts_provider}'"
                    )
            
            if agent.stt_provider:
                global_stt_config = self.global_config_service.get_provider_config("stt", agent.stt_provider)
                if not global_stt_config:
                    validation_results["warnings"].append(
                        f"STT: No global configuration found for provider '{agent.stt_provider}'"
                    )
            
        except Exception as e:
            logger.error(f"Failed to validate agent configuration for agent {agent.id}: {e}")
            validation_results["is_valid"] = False
            validation_results["errors"].append(f"Validation error: {str(e)}")
        
        return validation_results


# Global helper instance
_agent_config_helper = None

def get_agent_config_helper(db_session: Session) -> AgentConfigHelper:
    """Get or create agent config helper instance"""
    global _agent_config_helper
    if _agent_config_helper is None:
        _agent_config_helper = AgentConfigHelper(db_session)
    return _agent_config_helper