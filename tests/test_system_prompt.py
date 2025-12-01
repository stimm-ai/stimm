#!/usr/bin/env python3
"""
Test system prompt integration.
"""
import sys
sys.path.insert(0, 'src')

from services.agents_admin.agent_service import AgentService
from services.agents_admin.models import AgentCreate, AgentUpdate, ProviderConfig
import uuid

def test_system_prompt_update():
    print("Testing system prompt update...")
    agent_service = AgentService()
    try:
        # Get default agent to copy its provider configs
        default_agent = agent_service.get_default_agent()
        print(f"Default agent: {default_agent.name}")
        
        # Create a new test agent with same provider configs but different name
        test_agent_name = f"Test Agent {uuid.uuid4().hex[:8]}"
        agent_data = AgentCreate(
            name=test_agent_name,
            description="Temporary test agent",
            system_prompt=None,
            llm_config=ProviderConfig(
                provider=default_agent.llm_provider,
                config=default_agent.llm_config
            ),
            tts_config=ProviderConfig(
                provider=default_agent.tts_provider,
                config=default_agent.tts_config
            ),
            stt_config=ProviderConfig(
                provider=default_agent.stt_provider,
                config=default_agent.stt_config
            ),
            is_default=False
        )
        new_agent = agent_service.create_agent(agent_data)
        print(f"Created test agent: {new_agent.name} (ID: {new_agent.id})")
        
        # Update with custom prompt
        custom = "Test prompt"
        updated = agent_service.update_agent(new_agent.id, AgentUpdate(system_prompt=custom))
        assert updated.system_prompt == custom
        print("System prompt updated successfully")
        
        # Retrieve again
        retrieved = agent_service.get_agent(new_agent.id)
        assert retrieved.system_prompt == custom
        print("System prompt retrieved successfully")
        
        # Reset to None (should keep previous due to bug, but that's okay)
        reset = agent_service.update_agent(new_agent.id, AgentUpdate(system_prompt=None))
        print(f"After reset: {reset.system_prompt}")
        
        # Delete the test agent
        agent_service.delete_agent(new_agent.id)
        print("Test agent deleted")
        
        print("Test passed")
        return True
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_system_prompt_update()
    sys.exit(0 if success else 1)