"""
Agent Configuration Helper

This helper now ONLY works with per-agent configurations stored via the Agent
management system. All legacy global provider configuration has been removed.

Responsibilities:
- Expose the agent's provider configs in a convenient structured form.
- Validate basic presence of provider configs if needed.

Non-responsibilities:
- No database lookups for "global" provider settings.
- No merging with global templates or settings.
"""

import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from .models import AgentResponse

logger = logging.getLogger(__name__)


class AgentConfigHelper:
    """Helper for working with an agent's provider-specific configurations."""

    def __init__(self, db_session: Session):
        # db_session is kept for compatibility and potential future use,
        # but this helper no longer queries global provider config tables.
        self.db = db_session

    def get_combined_agent_config(self, agent: AgentResponse) -> Dict[str, Any]:
        """
        Return the agent's configuration grouped by provider type.

        This is now a thin wrapper around the agent's own llm_config/tts_config/stt_config,
        without any implicit global overrides.
        """
        try:
            return {
                "llm": agent.llm_config or {},
                "tts": agent.tts_config or {},
                "stt": agent.stt_config or {},
            }
        except Exception as e:
            logger.error(f"Failed to get combined agent config for agent {getattr(agent, 'id', 'unknown')}: {e}")
            return {
                "llm": {},
                "tts": {},
                "stt": {},
            }

    def get_provider_config_for_agent(self, agent: AgentResponse, provider_type: str) -> Dict[str, Any]:
        """
        Return the agent's configuration for a specific provider type.

        provider_type: 'llm', 'tts', or 'stt'
        """
        try:
            if provider_type == "llm":
                return agent.llm_config or {}
            if provider_type == "tts":
                return agent.tts_config or {}
            if provider_type == "stt":
                return agent.stt_config or {}
            return {}
        except Exception as e:
            logger.error(
                f"Failed to get {provider_type} config for agent {getattr(agent, 'id', 'unknown')}: {e}"
            )
            return {}

    def validate_agent_configuration(self, agent: AgentResponse) -> Dict[str, Any]:
        """
        Basic validation ensuring that when a provider is selected,
        a configuration object exists (no global template enforcement).
        """
        results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
        }

        try:
            # LLM
            if agent.llm_provider and not agent.llm_config:
                results["is_valid"] = False
                results["errors"].append(
                    f"LLM config missing for provider '{agent.llm_provider}'"
                )

            # TTS
            if agent.tts_provider and not agent.tts_config:
                results["is_valid"] = False
                results["errors"].append(
                    f"TTS config missing for provider '{agent.tts_provider}'"
                )

            # STT
            if agent.stt_provider and not agent.stt_config:
                results["is_valid"] = False
                results["errors"].append(
                    f"STT config missing for provider '{agent.stt_provider}'"
                )

        except Exception as e:
            logger.error(
                f"Failed to validate agent configuration for agent {getattr(agent, 'id', 'unknown')}: {e}"
            )
            results["is_valid"] = False
            results["errors"].append(f"Validation error: {str(e)}")

        return results


# Global helper instance (kept for backward-compatible usage pattern)
_agent_config_helper: AgentConfigHelper | None = None


def get_agent_config_helper(db_session: Session) -> AgentConfigHelper:
    """Get or create AgentConfigHelper instance."""
    global _agent_config_helper
    if _agent_config_helper is None:
        _agent_config_helper = AgentConfigHelper(db_session)
    return _agent_config_helper