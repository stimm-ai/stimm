"""
Migration script to clean up agent configurations to match provider-specific expected properties.
"""

import os
import sys

# Add src to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import after path modification
from database.models import Agent
from database.session import SessionLocal
from services.agents_admin.provider_registry import get_provider_registry


def clean_agent_configurations():
    """Clean up agent configurations to match provider-specific expected properties."""
    db = SessionLocal()
    registry = get_provider_registry()

    try:
        agents = db.query(Agent).all()
        print(f"Found {len(agents)} agents to clean up")

        for agent in agents:
            print(f"\nProcessing agent: {agent.name}")
            print(f"  LLM: {agent.llm_provider}")
            print(f"  TTS: {agent.tts_provider}")
            print(f"  STT: {agent.stt_provider}")

            # Clean LLM configuration
            if agent.llm_provider:
                try:
                    expected_props = registry.get_expected_properties("llm", agent.llm_provider)
                    cleaned_config = {}
                    for prop in expected_props:
                        if prop in agent.llm_config:
                            cleaned_config[prop] = agent.llm_config[prop]
                    print(f"  LLM config cleaned: {agent.llm_config} -> {cleaned_config}")
                    agent.llm_config = cleaned_config
                except Exception as e:
                    print(f"  Warning: Could not clean LLM config for {agent.llm_provider}: {e}")

            # Clean TTS configuration
            if agent.tts_provider:
                try:
                    expected_props = registry.get_expected_properties("tts", agent.tts_provider)
                    cleaned_config = {}
                    for prop in expected_props:
                        if prop in agent.tts_config:
                            cleaned_config[prop] = agent.tts_config[prop]
                    print(f"  TTS config cleaned: {agent.tts_config} -> {cleaned_config}")
                    agent.tts_config = cleaned_config
                except Exception as e:
                    print(f"  Warning: Could not clean TTS config for {agent.tts_provider}: {e}")

            # Clean STT configuration
            if agent.stt_provider:
                try:
                    expected_props = registry.get_expected_properties("stt", agent.stt_provider)
                    cleaned_config = {}
                    for prop in expected_props:
                        if prop in agent.stt_config:
                            cleaned_config[prop] = agent.stt_config[prop]
                    print(f"  STT config cleaned: {agent.stt_config} -> {cleaned_config}")
                    agent.stt_config = cleaned_config
                except Exception as e:
                    print(f"  Warning: Could not clean STT config for {agent.stt_provider}: {e}")

        # Commit changes
        db.commit()
        print(f"\nSuccessfully cleaned {len(agents)} agent configurations")

    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    clean_agent_configurations()
