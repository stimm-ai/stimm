"""
Utility to create default development agent from .env configuration.
"""
import os
import logging
from typing import Dict, Any

from sqlalchemy.orm import Session

from .agent_service import AgentService
from .models import AgentCreate, ProviderConfig
from .exceptions import AgentAlreadyExistsError

logger = logging.getLogger(__name__)


class DevAgentCreator:
    """Creates default development agent from environment variables."""
    
    def __init__(self, db_session: Session):
        """
        Initialize DevAgentCreator.
        
        Args:
            db_session: SQLAlchemy session
        """
        self.db_session = db_session
        self.agent_service = AgentService(db_session)
    
    def create_default_dev_agent(self) -> bool:
        """
        Create default development agent from .env configuration.
        
        Returns:
            bool: True if agent was created or already exists
        """
        try:
            # Check if default agent already exists
            try:
                default_agent = self.agent_service.get_default_agent()
                logger.info(f"Default agent already exists: {default_agent.name} (ID: {default_agent.id})")
                
                # Delete the existing default agent to recreate it with updated configuration
                logger.info("Deleting existing default agent to recreate with updated configuration")
                self.agent_service.delete_agent(default_agent.id)
                
            except Exception:
                # Default agent doesn't exist, create it
                pass
            
            # Create agent configuration from environment variables
            agent_data = self._build_agent_from_env()
            
            # Create the agent
            agent = self.agent_service.create_agent(agent_data)
            
            logger.info(f"Created default development agent: {agent.name} (ID: {agent.id})")
            logger.info(f"  LLM Provider: {agent.llm_provider}")
            logger.info(f"  TTS Provider: {agent.tts_provider}")
            logger.info(f"  STT Provider: {agent.stt_provider}")
            logger.info(f"  LLM Model: {agent.llm_config.get('model', 'default')}")
            logger.info(f"  TTS Voice: {agent.tts_config.get('voice', agent.tts_config.get('voice_id', 'default'))}")
            logger.info(f"  STT Model: {agent.stt_config.get('model', 'default')}")
            
            return True
            
        except AgentAlreadyExistsError:
            logger.info("Default development agent already exists")
            return True
        except Exception as e:
            logger.error(f"Failed to create default development agent: {e}")
            return False
    
    def _build_agent_from_env(self) -> AgentCreate:
        """
        Build agent configuration from environment variables.
        
        Returns:
            AgentCreate: Agent creation data
        """
        # Get provider selections from environment
        llm_provider = os.getenv("LLM_PROVIDER", "groq.com")
        tts_provider = os.getenv("TTS_PROVIDER", "async.ai")
        stt_provider = os.getenv("STT_PROVIDER", "whisper.local")
        
        # Build provider configurations
        llm_config = self._build_llm_config(llm_provider)
        tts_config = self._build_tts_config(tts_provider)
        stt_config = self._build_stt_config(stt_provider)
        
        return AgentCreate(
            name="Development Agent",
            description="Default development agent created from .env configuration",
            llm_provider=llm_provider,
            llm_model_name=llm_config.get("model", "default"),
            llm_api_key=llm_config.get("api_key", ""),
            tts_provider=tts_provider,
            tts_voice_name=self._get_tts_voice_name(tts_provider, tts_config),
            tts_api_key=tts_config.get("api_key", ""),
            stt_provider=stt_provider,
            stt_model_name=stt_config.get("model", "default"),
            stt_api_key=stt_config.get("api_key", ""),
            is_default=True
        )
    
    def _build_llm_config(self, provider: str) -> Dict[str, Any]:
        """Build LLM provider configuration from environment."""
        config = {}
        
        if provider == "groq.com":
            config.update({
                "api_key": os.getenv("GROQ_LLM_API_KEY"),
                "model": os.getenv("GROQ_LLM_MODEL", "llama-3.1-8b-instant"),
                "api_url": os.getenv("GROQ_LLM_API_URL", "https://api.groq.com"),
                "completions_path": os.getenv("GROQ_LLM_COMPLETIONS_PATH", "/openai/v1/chat/completions")
            })
        elif provider == "mistral.ai":
            config.update({
                "api_key": os.getenv("MISTRAL_LLM_API_KEY"),
                "model": os.getenv("MISTRAL_LLM_MODEL", "mistral-large-latest"),
                "api_url": os.getenv("MISTRAL_LLM_API_URL", "https://api.mistral.ai/v1"),
                "completions_path": os.getenv("MISTRAL_LLM_COMPLETIONS_PATH", "/chat/completions")
            })
        elif provider == "openrouter.ai":
            config.update({
                "api_key": os.getenv("OPENROUTER_LLM_API_KEY"),
                "model": os.getenv("OPENROUTER_LLM_MODEL", "anthropic/claude-3.5-sonnet"),
                "api_url": os.getenv("OPENROUTER_LLM_API_URL", "https://openrouter.ai/api/v1"),
                "completions_path": os.getenv("OPENROUTER_LLM_COMPLETIONS_PATH", "/chat/completions"),
                "app_name": os.getenv("OPENROUTER_LLM_APP_NAME", "VoiceBot"),
                "app_url": os.getenv("OPENROUTER_LLM_APP_URL", "https://github.com/etienne/voicebot")
            })
        elif provider == "llama-cpp.local":
            config.update({
                "api_url": os.getenv("LLAMA_CPP_LLM_API_URL", "http://llama-cpp-server:8002"),
                "api_key": os.getenv("LLAMA_CPP_LLM_API_KEY", ""),
                "model": os.getenv("LLAMA_CPP_LLM_MODEL", "default"),
                "completions_path": os.getenv("LLAMA_CPP_LLM_COMPLETIONS_PATH", "/v1/chat/completions")
            })
        
        # Remove None values
        return {k: v for k, v in config.items() if v is not None}
    
    def _build_tts_config(self, provider: str) -> Dict[str, Any]:
        """Build TTS provider configuration from environment."""
        config = {}
        
        if provider == "async.ai":
            config.update({
                "api_key": os.getenv("ASYNC_API_KEY"),
                "voice_id": os.getenv("ASYNC_AI_TTS_VOICE_ID", "e7b694f8-d277-47ff-82bf-cb48e7662647"),
                "model_id": os.getenv("ASYNC_AI_TTS_MODEL_ID", "asyncflow_v2.0"),
                "sample_rate": int(os.getenv("ASYNC_AI_TTS_SAMPLE_RATE", "44100")),
                "encoding": os.getenv("ASYNC_AI_TTS_ENCODING", "pcm_s16le"),
                "container": os.getenv("ASYNC_AI_TTS_CONTAINER", "raw"),
                "url": os.getenv("ASYNC_AI_TTS_URL", "wss://api.async.ai/text_to_speech/websocket/ws")
            })
        elif provider == "kokoro.local":
            config.update({
                "url": os.getenv("KOKORO_LOCAL_TTS_URL", "ws://kokoro-tts:5000/ws/tts/stream"),
                "voice": os.getenv("KOKORO_TTS_DEFAULT_VOICE", "af_sarah"),
                "voice_id": os.getenv("KOKORO_TTS_DEFAULT_VOICE", "af_sarah"),
                "sample_rate": int(os.getenv("KOKORO_TTS_SAMPLE_RATE", "22050")),
                "encoding": os.getenv("KOKORO_TTS_ENCODING", "pcm_s16le"),
                "container": os.getenv("KOKORO_TTS_CONTAINER", "raw"),
                "language": os.getenv("KOKORO_TTS_DEFAULT_LANGUAGE", "fr-fr"),
                "speed": float(os.getenv("KOKORO_TTS_DEFAULT_SPEED", "0.8"))
            })
        elif provider == "deepgram.com":
            config.update({
                "api_key": os.getenv("DEEPGRAM_TTS_API_KEY"),
                "model": os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en"),
                "sample_rate": int(os.getenv("DEEPGRAM_TTS_SAMPLE_RATE", "16000")),
                "encoding": os.getenv("DEEPGRAM_TTS_ENCODING", "linear16")
            })
        elif provider == "elevenlabs.io":
            config.update({
                "api_key": os.getenv("ELEVENLABS_TTS_API_KEY"),
                "voice_id": os.getenv("ELEVENLABS_TTS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
                "model_id": os.getenv("ELEVENLABS_TTS_MODEL_ID", "eleven_multilingual_v2"),
                "sample_rate": int(os.getenv("ELEVENLABS_TTS_SAMPLE_RATE", "22050")),
                "encoding": os.getenv("ELEVENLABS_TTS_ENCODING", "pcm_s16le"),
                "output_format": os.getenv("ELEVENLABS_TTS_OUTPUT_FORMAT", "pcm_22050")
            })
        
        # Remove None values
        return {k: v for k, v in config.items() if v is not None}
    
    def _get_tts_voice_name(self, provider: str, tts_config: Dict[str, Any]) -> str:
        """Get the appropriate voice name/ID based on provider requirements."""
        if provider == "kokoro.local":
            # Kokoro uses voice names (e.g., "ff_siwis")
            return tts_config.get("voice", "default")
        elif provider == "async.ai":
            # Async AI uses voice IDs (UUID format)
            return tts_config.get("voice_id", "default")
        elif provider == "elevenlabs.io":
            # ElevenLabs uses voice IDs
            return tts_config.get("voice_id", "default")
        elif provider == "deepgram.com":
            # Deepgram uses model names for voices
            return tts_config.get("model", "default")
        else:
            return "default"
    
    def _build_stt_config(self, provider: str) -> Dict[str, Any]:
        """Build STT provider configuration from environment."""
        config = {}
        
        if provider == "whisper.local":
            config.update({
                "url": os.getenv("WHISPER_LOCAL_STT_URL", "ws://whisper-stt:8003"),
                "path": os.getenv("WHISPER_STT_WS_PATH", "/api/stt/stream")
            })
        elif provider == "deepgram.com":
            config.update({
                "api_key": os.getenv("DEEPGRAM_STT_API_KEY"),
                "model": os.getenv("DEEPGRAM_MODEL", "nova-2"),
                "language": os.getenv("DEEPGRAM_LANGUAGE", "fr")
            })
        
        # Remove None values
        return {k: v for k, v in config.items() if v is not None}


def initialize_default_agent(db_session: Session) -> bool:
    """
    Initialize default development agent.
    
    Args:
        db_session: SQLAlchemy session
        
    Returns:
        bool: True if successful
    """
    creator = DevAgentCreator(db_session)
    return creator.create_default_dev_agent()