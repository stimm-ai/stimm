"""
Text-only interface for testing agents without audio
"""

import asyncio
import json
import logging
from typing import Optional

import aiohttp


class TextInterface:
    """Text-only interface for agent testing"""
    
    def __init__(self, agent_name: str, use_rag: bool = True, verbose: bool = False, base_url: Optional[str] = None):
        self.agent_name = agent_name
        self.use_rag = use_rag
        self.verbose = verbose
        from environment_config import config
        self.base_url = base_url or config.stimm_api_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def send_message(self, message: str) -> str:
        """Send message to agent and get response"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        try:
            if self.use_rag:
                # Use RAG chatbot endpoint
                url = f"{self.base_url}/rag/chat/message"
                
                # Get agent UUID from name
                agent_uuid = await self._get_agent_uuid()
                payload = {
                    "message": message
                }
                
                # Add agent_id only if we found the UUID
                if agent_uuid:
                    payload["agent_id"] = agent_uuid
                
                async with self.session.post(url, json=payload) as response:
                    if response.status == 200:
                        # RAG returns streaming response, we need to collect it
                        full_response = ""
                        error_detected = False
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith('data: '):
                                try:
                                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                                    if data.get('type') == 'error':
                                        error_detected = True
                                        error_content = data.get('content', 'Unknown error')
                                        self.logger.error(f"RAG API error: {error_content}")
                                        return f"❌ RAG Error: {error_content}"
                                    elif data.get('type') in ['chunk', 'complete'] and 'content' in data:
                                        full_response += data['content']
                                except json.JSONDecodeError:
                                    continue
                        
                        if error_detected:
                            return "❌ Error processing request (see logs for details)"
                        return full_response if full_response else "⚠️ No response content received"
                    else:
                        error_text = await response.text()
                        self.logger.error(f"API error {response.status}: {error_text}")
                        return f"❌ API Error {response.status}: {error_text}"
            else:
                # Use direct LLM endpoint
                url = f"{self.base_url}/api/llm/generate"
                params = {"prompt": message}
                
                async with self.session.post(url, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result", "No response received")
                    else:
                        error_text = await response.text()
                        self.logger.error(f"API error {response.status}: {error_text}")
                        return f"Error: {response.status} - {error_text}"
                    
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error: {e}")
            return f"Network error: {e}"
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return f"Unexpected error: {e}"
            
    async def check_agent_exists(self) -> bool:
        """Check if agent exists in the system"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        try:
            # Check agents endpoint with timeout and retry
            url = f"{self.base_url}/api/agents"
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with self.session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    agents = await response.json()
                    agent_names = [agent.get("name") for agent in agents]
                    return self.agent_name in agent_names
                else:
                    self.logger.warning(f"API returned status {response.status}")
                    return False
        except aiohttp.ClientConnectorError as e:
            self.logger.error(f"Cannot connect to backend at {self.base_url}: {e}")
            return False
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout connecting to backend at {self.base_url}")
            return False
        except Exception as e:
            self.logger.error(f"Error checking agent: {e}")
            return False
            
    async def _get_agent_uuid(self) -> Optional[str]:
        """Get agent UUID from agent name"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        try:
            url = f"{self.base_url}/api/agents/"
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with self.session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    agents = await response.json()
                    for agent in agents:
                        if agent.get("name") == self.agent_name:
                            return agent.get("id")
                    self.logger.warning(f"Agent '{self.agent_name}' not found in agents list")
                    return None
                else:
                    self.logger.warning(f"Failed to get agents list: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error getting agent UUID: {e}")
            return None
            
    async def run(self):
        """Run the text interface"""
        print(f"\n🤖 Text Interface for Agent: {self.agent_name}")
        print("=" * 50)
        print("Type your messages and press Enter")
        print("Type 'quit' or 'exit' to end the conversation")
        print("Type 'clear' to clear the conversation history")
        print("=" * 50)
        
        async with self:
            # Check if agent exists
            if not await self.check_agent_exists():
                print(f"❌ Agent '{self.agent_name}' not found in the system!")
                print("This could be because:")
                print("  - The backend is not running (check: docker compose ps)")
                print("  - The agent name is incorrect")
                print("  - Network connectivity issues")
                print(f"\nAvailable agents might be listed at {self.base_url}/api/agents")
                print("Make sure the backend is running with: docker compose up -d")
                return
                
            print(f"✅ Agent '{self.agent_name}' found!")
            print(f"📚 RAG enabled: {self.use_rag}")
            print()
            
            conversation_history = []
            
            while True:
                try:
                    # Get user input
                    user_input = input("\n👤 You: ").strip()
                    
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("\n👋 Ending conversation...")
                        break
                        
                    if user_input.lower() == 'clear':
                        conversation_history.clear()
                        print("🗑️  Conversation history cleared")
                        continue
                        
                    if not user_input:
                        continue
                        
                    # Add to conversation history
                    conversation_history.append(f"User: {user_input}")
                    
                    # Send to agent
                    print("🤖 Agent: ", end="", flush=True)
                    
                    # Build context from conversation history
                    context = "\n".join(conversation_history[-6:])  # Last 3 exchanges
                    
                    response = await self.send_message(user_input)
                    
                    print(response)
                    
                    # Add agent response to history
                    conversation_history.append(f"Agent: {response}")
                    
                    # Keep history manageable
                    if len(conversation_history) > 20:
                        conversation_history = conversation_history[-20:]
                        
                except KeyboardInterrupt:
                    print("\n\n👋 Conversation interrupted by user")
                    break
                except Exception as e:
                    self.logger.error(f"Error in conversation: {e}")
                    print(f"❌ Error: {e}")
                    
        print("\n📝 Conversation ended")


async def main():
    """Test the text interface"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python text_input.py <agent_name>")
        return
        
    agent_name = sys.argv[1]
    interface = TextInterface(agent_name, verbose=True)
    await interface.run()


if __name__ == "__main__":
    asyncio.run(main())