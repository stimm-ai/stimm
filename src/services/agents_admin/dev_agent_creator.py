"""
Utility to create default development agent from .env configuration.
"""

import logging
import os
from typing import Any, Dict

from sqlalchemy.orm import Session

from .agent_service import AgentService
from .exceptions import AgentAlreadyExistsError
from .models import AgentCreate, AgentUpdate, ProviderConfig

logger = logging.getLogger(__name__)


class DevAgentCreator:
    """Creates default development agent from environment variables."""

    # Mapping from (provider_type, provider_name) to list of config definitions
    _PROVIDER_ENV_MAPPING = {
        ("llm", "groq.com"): [
            ("api_key", "GROQ_LLM_API_KEY", None, str),
            ("model", "GROQ_LLM_MODEL", "llama-3.1-8b-instant", str),
            ("api_url", "GROQ_LLM_API_URL", "https://api.groq.com", str),
            ("completions_path", "GROQ_LLM_COMPLETIONS_PATH", "/openai/v1/chat/completions", str),
        ],
        ("llm", "mistral.ai"): [
            ("api_key", "MISTRAL_LLM_API_KEY", None, str),
            ("model", "MISTRAL_LLM_MODEL", "mistral-large-latest", str),
            ("api_url", "MISTRAL_LLM_API_URL", "https://api.mistral.ai/v1", str),
            ("completions_path", "MISTRAL_LLM_COMPLETIONS_PATH", "/chat/completions", str),
        ],
        ("llm", "openrouter.ai"): [
            ("api_key", "OPENROUTER_LLM_API_KEY", None, str),
            ("model", "OPENROUTER_LLM_MODEL", "anthropic/claude-3.5-sonnet", str),
            ("api_url", "OPENROUTER_LLM_API_URL", "https://openrouter.ai/api/v1", str),
            ("completions_path", "OPENROUTER_LLM_COMPLETIONS_PATH", "/chat/completions", str),
            ("app_name", "OPENROUTER_LLM_APP_NAME", "Stimm", str),
            ("app_url", "OPENROUTER_LLM_APP_URL", "https://github.com/etienne/stimm", str),
        ],
        ("llm", "llama-cpp.local"): [
            ("api_url", "LLAMA_CPP_LLM_API_URL", "http://llama-cpp-server:8002", str),
            ("api_key", "LLAMA_CPP_LLM_API_KEY", "local", str),
            ("model", "LLAMA_CPP_LLM_MODEL", "default", str),
            ("completions_path", "LLAMA_CPP_LLM_COMPLETIONS_PATH", "/v1/chat/completions", str),
        ],
        ("tts", "async.ai"): [
            ("api_key", "ASYNC_API_KEY", None, str),
            ("voice", "ASYNC_AI_TTS_VOICE_ID", "e7b694f8-d277-47ff-82bf-cb48e7662647", str),
            ("voice_id", "ASYNC_AI_TTS_VOICE_ID", "e7b694f8-d277-47ff-82bf-cb48e7662647", str),
            ("model", "ASYNC_AI_TTS_MODEL_ID", "asyncflow_v2.0", str),
            ("model_id", "ASYNC_AI_TTS_MODEL_ID", "asyncflow_v2.0", str),
            ("sample_rate", "ASYNC_AI_TTS_SAMPLE_RATE", 44100, int),
            ("encoding", "ASYNC_AI_TTS_ENCODING", "pcm_s16le", str),
            ("container", "ASYNC_AI_TTS_CONTAINER", "raw", str),
            ("url", "ASYNC_AI_TTS_URL", "wss://api.async.ai/text_to_speech/websocket/ws", str),
        ],
        ("tts", "kokoro.local"): [
            ("url", "KOKORO_LOCAL_TTS_URL", "ws://kokoro-tts:5000/ws/tts/stream", str),
            ("voice", "KOKORO_TTS_DEFAULT_VOICE", "af_sarah", str),
            ("voice_id", "KOKORO_TTS_DEFAULT_VOICE", "af_sarah", str),
            ("sample_rate", "KOKORO_TTS_SAMPLE_RATE", 22050, int),
            ("encoding", "KOKORO_TTS_ENCODING", "pcm_s16le", str),
            ("container", "KOKORO_TTS_CONTAINER", "raw", str),
            ("language", "KOKORO_TTS_DEFAULT_LANGUAGE", "fr-fr", str),
            ("speed", "KOKORO_TTS_DEFAULT_SPEED", 1.0, float),
        ],
        ("tts", "deepgram.com"): [
            ("api_key", "DEEPGRAM_TTS_API_KEY", None, str),
            ("model", "DEEPGRAM_TTS_MODEL", "aura-asteria-en", str),
            ("sample_rate", "DEEPGRAM_TTS_SAMPLE_RATE", 16000, int),
            ("encoding", "DEEPGRAM_TTS_ENCODING", "linear16", str),
        ],
        ("tts", "elevenlabs.io"): [
            ("api_key", "ELEVENLABS_TTS_API_KEY", None, str),
            ("voice", "ELEVENLABS_TTS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM", str),
            ("voice_id", "ELEVENLABS_TTS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM", str),
            ("model", "ELEVENLABS_TTS_MODEL_ID", "eleven_multilingual_v2", str),
            ("model_id", "ELEVENLABS_TTS_MODEL_ID", "eleven_multilingual_v2", str),
            ("sample_rate", "ELEVENLABS_TTS_SAMPLE_RATE", 22050, int),
            ("encoding", "ELEVENLABS_TTS_ENCODING", "pcm_s16le", str),
            ("output_format", "ELEVENLABS_TTS_OUTPUT_FORMAT", "pcm_22050", str),
        ],
        ("tts", "hume.ai"): [
            ("api_key", "HUME_TTS_API_KEY", None, str),
            ("voice", "HUME_TTS_VOICE_ID", "default", str),
            ("version", "HULME_TTS_MODEL_VERSION", "2", str),
        ],
        ("stt", "whisper.local"): [
            ("url", "CUSTOM_WHISPER_STT_URL", "ws://whisper-stt:8003/api/stt/stream", str),
        ],
        ("stt", "deepgram.com"): [
            ("api_key", "DEEPGRAM_STT_API_KEY", None, str),
            ("model", "DEEPGRAM_MODEL", "nova-2", str),
            ("language", "DEEPGRAM_LANGUAGE", "fr", str),
        ],
    }

    def __init__(self, db_session: Session):
        """
        Initialize DevAgentCreator.

        Args:
            db_session: SQLAlchemy session
        """
        self.db_session = db_session
        self.agent_service = AgentService(db_session)

    def _filter_config(self, provider_type: str, provider_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter config to only include expected properties for the provider.

        This ensures we don't pass extra properties that cause validation warnings.
        """
        from .provider_registry import get_provider_registry

        registry = get_provider_registry()
        expected = registry.get_expected_properties(provider_type, provider_name)
        if not expected:
            # If we can't determine expected properties, keep all config
            return config
        # Keep only keys that are in expected properties
        filtered = {k: v for k, v in config.items() if k in expected}
        # Log if we removed any keys (debug)
        removed = set(config.keys()) - set(filtered.keys())
        if removed:
            logger.debug(f"Removed extra config keys for {provider_type}.{provider_name}: {removed}")
        return filtered

    def _build_config_from_mapping(self, provider_type: str, provider_name: str) -> Dict[str, Any]:
        """Build configuration from environment variables using mapping."""
        mapping = self._PROVIDER_ENV_MAPPING.get((provider_type, provider_name))
        if not mapping:
            logger.debug(f"No environment mapping for {provider_type}.{provider_name}")
            return {}

        config = {}
        for config_key, env_var, default, type_converter in mapping:
            value = os.getenv(env_var)
            if value is None:
                if default is None:
                    continue  # skip this key
                value = default
            else:
                # Convert type
                try:
                    if type_converter is int:
                        value = int(value)
                    elif type_converter is float:
                        value = float(value)
                    elif type_converter is bool:
                        value = value.lower() in ("true", "1", "yes", "on")
                    # str: keep as is
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to convert env var {env_var}={value} to {type_converter}: {e}")
                    continue
            config[config_key] = value

        # Remove None values (should not happen but safe)
        config = {k: v for k, v in config.items() if v is not None}
        # Filter to expected properties
        config = self._filter_config(provider_type, provider_name, config)
        return config

    def _has_extra_keys(self, agent):
        """Check if agent's provider configs contain extra keys."""
        from .provider_registry import get_provider_registry

        registry = get_provider_registry()
        for provider_type, provider_name in [
            ("llm", agent.llm_provider),
            ("tts", agent.tts_provider),
            ("stt", agent.stt_provider),
        ]:
            config = getattr(agent, f"{provider_type}_config")
            expected = registry.get_expected_properties(provider_type, provider_name)
            if expected:
                extra = set(config.keys()) - set(expected)
                if extra:
                    return True
        return False

    def create_default_dev_agent(self) -> bool:
        """
        Create or update development agent from .env configuration.
        Always updates existing development agent to match current .env configuration.

        Returns:
            bool: True if agent was created or updated successfully
        """
        try:
            # Build agent configuration from current environment variables
            agent_data = self._build_agent_from_env()

            # Check if a development agent already exists
            try:
                # Try to find existing development agent by name
                agents = self.agent_service.list_agents()
                existing_dev_agent = None
                for agent in agents.agents:
                    if agent.name == "Development Agent":
                        existing_dev_agent = agent
                        break

                if existing_dev_agent:
                    logger.info(f"Found existing development agent: {existing_dev_agent.name} (ID: {existing_dev_agent.id})")

                    # Check if the existing agent has extra config keys that cause validation warnings
                    if self._has_extra_keys(existing_dev_agent):
                        logger.info("Existing development agent has extra config keys, recreating to avoid validation warnings")
                        # Temporarily set is_default=False to allow deletion
                        if existing_dev_agent.is_default:
                            update_non_default = AgentUpdate(is_default=False)
                            self.agent_service.update_agent(existing_dev_agent.id, update_non_default)
                        # Delete the agent
                        self.agent_service.delete_agent(existing_dev_agent.id)
                        logger.info(f"Deleted development agent with extra keys: {existing_dev_agent.id}")
                        # Create new agent
                        agent_data.is_default = True
                        agent = self.agent_service.create_agent(agent_data)
                        logger.info(f"Created new development agent: {agent.name} (ID: {agent.id})")
                    else:
                        logger.info("Updating development agent to match current .env configuration")
                        # Update the existing agent
                        update_data = AgentUpdate(
                            llm_config=ProviderConfig(provider=agent_data.llm_config.provider, config=agent_data.llm_config.config),
                            tts_config=ProviderConfig(provider=agent_data.tts_config.provider, config=agent_data.tts_config.config),
                            stt_config=ProviderConfig(provider=agent_data.stt_config.provider, config=agent_data.stt_config.config),
                            is_default=True,  # Always set as default for development agent
                        )

                        updated_agent = self.agent_service.update_agent(existing_dev_agent.id, update_data)
                        logger.info(f"Updated development agent: {updated_agent.name} (ID: {updated_agent.id})")

                else:
                    # No existing development agent found, create new one
                    logger.info("No existing development agent found, creating new development agent")
                    agent_data.is_default = True
                    agent = self.agent_service.create_agent(agent_data)
                    logger.info(f"Created development agent: {agent.name} (ID: {agent.id})")

            except Exception as e:
                logger.warning(f"Could not check for existing development agent: {e}")
                # Fallback: create new agent
                agent_data.is_default = True
                agent = self.agent_service.create_agent(agent_data)
                logger.info(f"Created development agent: {agent.name} (ID: {agent.id})")

            logger.info(f"  LLM Provider: {agent_data.llm_config.provider}")
            logger.info(f"  TTS Provider: {agent_data.tts_config.provider}")
            logger.info(f"  STT Provider: {agent_data.stt_config.provider}")
            logger.info(f"  LLM Model: {agent_data.llm_config.config.get('model', 'default')}")
            logger.info(f"  TTS Voice: {agent_data.tts_config.config.get('voice_id', agent_data.tts_config.config.get('voice', 'default'))}")
            logger.info(f"  STT Model: {agent_data.stt_config.config.get('model', 'default')}")

            return True

        except AgentAlreadyExistsError:
            logger.info("Development agent already exists")
            return True
        except Exception as e:
            logger.error(f"Failed to create/update development agent: {e}")
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
            llm_config=ProviderConfig(provider=llm_provider, config=llm_config),
            tts_config=ProviderConfig(provider=tts_provider, config=tts_config),
            stt_config=ProviderConfig(provider=stt_provider, config=stt_config),
            is_default=True,
        )

    def _build_llm_config(self, provider: str) -> Dict[str, Any]:
        """Build LLM provider configuration from environment."""
        return self._build_config_from_mapping("llm", provider)

    def _build_tts_config(self, provider: str) -> Dict[str, Any]:
        """Build TTS provider configuration from environment."""
        return self._build_config_from_mapping("tts", provider)

    def _build_stt_config(self, provider: str) -> Dict[str, Any]:
        """Build STT provider configuration from environment."""
        return self._build_config_from_mapping("stt", provider)


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
