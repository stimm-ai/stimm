"""
Global Provider Configuration Service

This service manages global provider configurations that apply to all agents
of a given provider type, replacing environment variable-based configuration.
"""

import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .global_config_models import (
    GlobalProviderConfig, 
    ProviderSettingTemplate, 
    DEFAULT_PROVIDER_TEMPLATES,
    Base
)

logger = logging.getLogger(__name__)


class GlobalConfigService:
    """Service for managing global provider configurations"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def initialize_templates(self) -> None:
        """Initialize provider setting templates in the database"""
        try:
            # First, delete all existing templates to ensure clean state
            self.db.query(ProviderSettingTemplate).delete()
            
            # Then add all templates from DEFAULT_PROVIDER_TEMPLATES
            for template_data in DEFAULT_PROVIDER_TEMPLATES:
                template = ProviderSettingTemplate(**template_data)
                self.db.add(template)
            
            self.db.commit()
            logger.info("Provider setting templates initialized successfully")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to initialize provider templates: {e}")
            raise
    
    def get_provider_config(self, provider_type: str, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get global configuration for a specific provider"""
        try:
            config = self.db.query(GlobalProviderConfig).filter(
                and_(
                    GlobalProviderConfig.provider_type == provider_type,
                    GlobalProviderConfig.provider_name == provider_name,
                    GlobalProviderConfig.is_active == True
                )
            ).first()
            
            if config:
                return config.settings
            return None
        except Exception as e:
            logger.error(f"Failed to get provider config for {provider_type}/{provider_name}: {e}")
            return None
    
    def set_provider_config(self, provider_type: str, provider_name: str, settings: Dict[str, Any]) -> bool:
        """Set global configuration for a specific provider"""
        try:
            # Check if config already exists
            existing = self.db.query(GlobalProviderConfig).filter(
                and_(
                    GlobalProviderConfig.provider_type == provider_type,
                    GlobalProviderConfig.provider_name == provider_name
                )
            ).first()
            
            if existing:
                # Update existing config
                existing.settings = settings
                existing.is_active = True
            else:
                # Create new config
                config = GlobalProviderConfig(
                    provider_type=provider_type,
                    provider_name=provider_name,
                    settings=settings,
                    is_active=True
                )
                self.db.add(config)
            
            self.db.commit()
            logger.info(f"Updated global config for {provider_type}/{provider_name}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to set provider config for {provider_type}/{provider_name}: {e}")
            return False
    
    def delete_provider_config(self, provider_type: str, provider_name: str) -> bool:
        """Delete global configuration for a specific provider"""
        try:
            config = self.db.query(GlobalProviderConfig).filter(
                and_(
                    GlobalProviderConfig.provider_type == provider_type,
                    GlobalProviderConfig.provider_name == provider_name
                )
            ).first()
            
            if config:
                self.db.delete(config)
                self.db.commit()
                logger.info(f"Deleted global config for {provider_type}/{provider_name}")
                return True
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete provider config for {provider_type}/{provider_name}: {e}")
            return False
    
    def get_all_provider_configs(self, provider_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all global provider configurations, optionally filtered by type"""
        try:
            query = self.db.query(GlobalProviderConfig).filter(
                GlobalProviderConfig.is_active == True
            )
            
            if provider_type:
                query = query.filter(GlobalProviderConfig.provider_type == provider_type)
            
            configs = query.all()
            return [config.to_dict() for config in configs]
        except Exception as e:
            logger.error(f"Failed to get all provider configs: {e}")
            return []
    
    def get_provider_templates(self, provider_type: Optional[str] = None, 
                             provider_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get provider setting templates"""
        try:
            query = self.db.query(ProviderSettingTemplate)
            
            if provider_type:
                query = query.filter(ProviderSettingTemplate.provider_type == provider_type)
            if provider_name:
                query = query.filter(ProviderSettingTemplate.provider_name == provider_name)
            
            templates = query.all()
            return [template.to_dict() for template in templates]
        except Exception as e:
            logger.error(f"Failed to get provider templates: {e}")
            return []
    
    def migrate_env_variables(self, env_vars: Dict[str, str]) -> Dict[str, bool]:
        """Migrate environment variables to global configurations"""
        results = {}
        
        # TTS Providers - Only global settings (exclude api_key, voice_id, model_id, model, language)
        tts_mappings = {
            "deepgram": {
                "sample_rate": "DEEPGRAM_TTS_SAMPLE_RATE",
                "encoding": "DEEPGRAM_TTS_ENCODING"
            },
            "elevenlabs": {
                "sample_rate": "ELEVENLABS_TTS_SAMPLE_RATE",
                "encoding": "ELEVENLABS_TTS_ENCODING",
                "output_format": "ELEVENLABS_TTS_OUTPUT_FORMAT"
            },
            "async.ai": {
                "url": "ASYNC_AI_TTS_URL",
                "sample_rate": "ASYNC_AI_TTS_SAMPLE_RATE",
                "encoding": "ASYNC_AI_TTS_ENCODING",
                "container": "ASYNC_AI_TTS_CONTAINER"
            },
            "kokoro.local": {
                "url": "KOKORO_LOCAL_TTS_URL",
                "sample_rate": "KOKORO_TTS_SAMPLE_RATE",
                "encoding": "KOKORO_TTS_ENCODING",
                "container": "KOKORO_TTS_CONTAINER",
                "speed": "KOKORO_TTS_DEFAULT_SPEED"
            }
        }
        
        # STT Providers - Only global settings (exclude api_key, model, language)
        stt_mappings = {
            "deepgram": {
                "sample_rate": "DEEPGRAM_STT_SAMPLE_RATE"
            },
            "whisper.local": {
                "url": "WHISPER_LOCAL_STT_URL",
                "path": "WHISPER_STT_WS_PATH"
            }
        }
        
        # LLM Providers - Only global settings (exclude api_key, model)
        llm_mappings = {
            "groq.com": {
                "api_url": "GROQ_LLM_API_URL",
                "completions_path": "GROQ_LLM_COMPLETIONS_PATH"
            },
            "mistral.ai": {
                "api_url": "MISTRAL_LLM_API_URL",
                "completions_path": "MISTRAL_LLM_COMPLETIONS_PATH"
            },
            "openrouter.ai": {
                "api_url": "OPENROUTER_LLM_API_URL",
                "completions_path": "OPENROUTER_LLM_COMPLETIONS_PATH"
            },
            "llama-cpp.local": {
                "api_url": "LLAMA_CPP_LLM_API_URL",
                "completions_path": "LLAMA_CPP_LLM_COMPLETIONS_PATH"
            }
        }
        
        # Migrate TTS providers
        for provider_name, mappings in tts_mappings.items():
            settings = {}
            for setting_key, env_var in mappings.items():
                if env_var in env_vars and env_vars[env_var]:
                    settings[setting_key] = env_vars[env_var]
            
            if settings:
                success = self.set_provider_config("tts", provider_name, settings)
                results[f"tts.{provider_name}"] = success
        
        # Migrate STT providers
        for provider_name, mappings in stt_mappings.items():
            settings = {}
            for setting_key, env_var in mappings.items():
                if env_var in env_vars and env_vars[env_var]:
                    settings[setting_key] = env_vars[env_var]
            
            if settings:
                success = self.set_provider_config("stt", provider_name, settings)
                results[f"stt.{provider_name}"] = success
        
        # Migrate LLM providers
        for provider_name, mappings in llm_mappings.items():
            settings = {}
            for setting_key, env_var in mappings.items():
                if env_var in env_vars and env_vars[env_var]:
                    settings[setting_key] = env_vars[env_var]
            
            if settings:
                success = self.set_provider_config("llm", provider_name, settings)
                results[f"llm.{provider_name}"] = success
        
        return results
    
    def get_provider_settings_for_agent(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get combined settings for an agent (agent-specific + global provider settings)"""
        try:
            provider_type = agent_config.get("provider_type")  # 'tts', 'stt', 'llm'
            provider_name = agent_config.get("provider_name")  # 'deepgram', 'whisper.local', etc.
            
            if not provider_type or not provider_name:
                return agent_config.get("provider_settings", {})
            
            # Get global provider settings
            global_settings = self.get_provider_config(provider_type, provider_name) or {}
            
            # Get agent-specific settings
            agent_settings = agent_config.get("provider_settings", {})
            
            # Merge settings (agent-specific settings override global settings)
            combined_settings = {**global_settings, **agent_settings}
            
            return combined_settings
        except Exception as e:
            logger.error(f"Failed to get provider settings for agent: {e}")
            return agent_config.get("provider_settings", {})


# Global service instance
_global_config_service = None

def get_global_config_service(db_session: Session) -> GlobalConfigService:
    """Get or create global config service instance"""
    global _global_config_service
    if _global_config_service is None:
        _global_config_service = GlobalConfigService(db_session)
    return _global_config_service