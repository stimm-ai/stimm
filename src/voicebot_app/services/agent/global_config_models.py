"""
Global Provider Configuration Models

This module defines the database models for global provider configurations
that apply to all agents of a given provider type.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class GlobalProviderConfig(Base):
    """Global configuration for provider settings that apply to all agents"""
    
    __tablename__ = "global_provider_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_type = Column(String(50), nullable=False, index=True)  # 'tts', 'stt', 'llm'
    provider_name = Column(String(100), nullable=False, index=True)  # 'deepgram', 'whisper.local', 'groq.com', etc.
    settings = Column(JSON, nullable=False, default=dict)  # Provider-specific settings as JSON
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Optional: user_id for future IAM integration
    user_id = Column(String(100), nullable=True, index=True)
    
    def __repr__(self):
        return f"<GlobalProviderConfig(provider_type='{self.provider_type}', provider_name='{self.provider_name}', is_active={self.is_active})>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "provider_type": self.provider_type,
            "provider_name": self.provider_name,
            "settings": self.settings,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "user_id": self.user_id
        }


class ProviderSettingTemplate(Base):
    """Template for provider settings with validation rules"""
    
    __tablename__ = "provider_setting_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_type = Column(String(50), nullable=False, index=True)
    provider_name = Column(String(100), nullable=False, index=True)
    setting_name = Column(String(100), nullable=False)
    setting_type = Column(String(50), nullable=False)  # 'string', 'integer', 'float', 'boolean', 'url'
    default_value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    is_required = Column(Boolean, default=False, nullable=False)
    validation_rules = Column(JSON, nullable=True)  # e.g., {"min": 0, "max": 100}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ProviderSettingTemplate(provider='{self.provider_name}', setting='{self.setting_name}', type='{self.setting_type}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "provider_type": self.provider_type,
            "provider_name": self.provider_name,
            "setting_name": self.setting_name,
            "setting_type": self.setting_type,
            "default_value": self.default_value,
            "description": self.description,
            "is_required": self.is_required,
            "validation_rules": self.validation_rules,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# Default provider templates for known providers
# Only include truly global settings (URLs, paths, formats, etc.)
# Exclude agent-specific settings (api_key, voice_id, model_id, model, language)
DEFAULT_PROVIDER_TEMPLATES = [
    # TTS Providers - Only global settings
    {
        "provider_type": "tts",
        "provider_name": "deepgram",
        "setting_name": "base_url",
        "setting_type": "url",
        "default_value": "https://api.deepgram.com",
        "description": "Base URL for Deepgram API",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "deepgram",
        "setting_name": "sample_rate",
        "setting_type": "integer",
        "default_value": "16000",
        "description": "Sample rate in Hz",
        "is_required": False,
        "validation_rules": {"min": 8000, "max": 48000}
    },
    {
        "provider_type": "tts",
        "provider_name": "deepgram",
        "setting_name": "encoding",
        "setting_type": "string",
        "default_value": "linear16",
        "description": "Audio encoding format",
        "is_required": False
    },
    
    # ElevenLabs TTS - Only global settings
    {
        "provider_type": "tts",
        "provider_name": "elevenlabs",
        "setting_name": "sample_rate",
        "setting_type": "integer",
        "default_value": "22050",
        "description": "Sample rate in Hz",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "elevenlabs",
        "setting_name": "encoding",
        "setting_type": "string",
        "default_value": "pcm_s16le",
        "description": "Audio encoding format",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "elevenlabs",
        "setting_name": "output_format",
        "setting_type": "string",
        "default_value": "pcm_22050",
        "description": "Output format",
        "is_required": False
    },
    
    # Async.AI TTS - Only global settings
    {
        "provider_type": "tts",
        "provider_name": "async.ai",
        "setting_name": "url",
        "setting_type": "url",
        "default_value": "wss://api.async.ai/text_to_speech/websocket/ws",
        "description": "WebSocket URL",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "async.ai",
        "setting_name": "sample_rate",
        "setting_type": "integer",
        "default_value": "44100",
        "description": "Sample rate in Hz",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "async.ai",
        "setting_name": "encoding",
        "setting_type": "string",
        "default_value": "pcm_s16le",
        "description": "Audio encoding format",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "async.ai",
        "setting_name": "container",
        "setting_type": "string",
        "default_value": "raw",
        "description": "Audio container format",
        "is_required": False
    },
    
    # Kokoro Local TTS - Only global settings
    {
        "provider_type": "tts",
        "provider_name": "kokoro.local",
        "setting_name": "url",
        "setting_type": "url",
        "default_value": "ws://kokoro-tts:5000/ws/tts/stream",
        "description": "WebSocket URL",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "kokoro.local",
        "setting_name": "sample_rate",
        "setting_type": "integer",
        "default_value": "33000",
        "description": "Sample rate in Hz",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "kokoro.local",
        "setting_name": "encoding",
        "setting_type": "string",
        "default_value": "pcm_s16le",
        "description": "Audio encoding format",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "kokoro.local",
        "setting_name": "container",
        "setting_type": "string",
        "default_value": "raw",
        "description": "Audio container format",
        "is_required": False
    },
    {
        "provider_type": "tts",
        "provider_name": "kokoro.local",
        "setting_name": "speed",
        "setting_type": "float",
        "default_value": "0.8",
        "description": "Speech speed",
        "is_required": False,
        "validation_rules": {"min": 0.1, "max": 2.0}
    },
    
    # STT Providers - Only global settings
    {
        "provider_type": "stt",
        "provider_name": "deepgram",
        "setting_name": "base_url",
        "setting_type": "url",
        "default_value": "https://api.deepgram.com",
        "description": "Base URL for Deepgram API",
        "is_required": False
    },
    {
        "provider_type": "stt",
        "provider_name": "deepgram",
        "setting_name": "sample_rate",
        "setting_type": "integer",
        "default_value": "16000",
        "description": "Sample rate in Hz",
        "is_required": False
    },
    
    # Whisper Local STT - Only global settings
    {
        "provider_type": "stt",
        "provider_name": "whisper.local",
        "setting_name": "url",
        "setting_type": "url",
        "default_value": "ws://whisper-stt:8003",
        "description": "WebSocket URL",
        "is_required": False
    },
    {
        "provider_type": "stt",
        "provider_name": "whisper.local",
        "setting_name": "path",
        "setting_type": "string",
        "default_value": "/api/stt/stream",
        "description": "WebSocket path",
        "is_required": False
    },
    
    # LLM Providers - Only global settings
    {
        "provider_type": "llm",
        "provider_name": "groq.com",
        "setting_name": "api_url",
        "setting_type": "url",
        "default_value": "https://api.groq.com",
        "description": "API Base URL",
        "is_required": False
    },
    {
        "provider_type": "llm",
        "provider_name": "groq.com",
        "setting_name": "completions_path",
        "setting_type": "string",
        "default_value": "/openai/v1/chat/completions",
        "description": "Completions endpoint path",
        "is_required": False
    },
    
    # Mistral.ai LLM - Only global settings
    {
        "provider_type": "llm",
        "provider_name": "mistral.ai",
        "setting_name": "api_url",
        "setting_type": "url",
        "default_value": "https://api.mistral.ai/v1",
        "description": "API Base URL",
        "is_required": False
    },
    {
        "provider_type": "llm",
        "provider_name": "mistral.ai",
        "setting_name": "completions_path",
        "setting_type": "string",
        "default_value": "/chat/completions",
        "description": "Completions endpoint path",
        "is_required": False
    },
    
    # OpenRouter.ai LLM - Only global settings
    {
        "provider_type": "llm",
        "provider_name": "openrouter.ai",
        "setting_name": "api_url",
        "setting_type": "url",
        "default_value": "https://openrouter.ai/api/v1",
        "description": "API Base URL",
        "is_required": False
    },
    {
        "provider_type": "llm",
        "provider_name": "openrouter.ai",
        "setting_name": "completions_path",
        "setting_type": "string",
        "default_value": "/chat/completions",
        "description": "Completions endpoint path",
        "is_required": False
    },
    
    # Llama.cpp LLM - Only global settings
    {
        "provider_type": "llm",
        "provider_name": "llama-cpp.local",
        "setting_name": "api_url",
        "setting_type": "url",
        "default_value": "http://llama-cpp-server:8002",
        "description": "API Base URL",
        "is_required": False
    },
    {
        "provider_type": "llm",
        "provider_name": "llama-cpp.local",
        "setting_name": "completions_path",
        "setting_type": "string",
        "default_value": "/v1/chat/completions",
        "description": "Completions endpoint path",
        "is_required": False
    }
]