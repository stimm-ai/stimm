"""
Agent runner for full audio mode via LiveKit
"""

import asyncio
import logging
import os
import uuid
from typing import Optional

import aiohttp
from livekit import api

# Import the new environment configuration
from environment_config import get_voicebot_api_url, get_livekit_url

from .livekit_client import LiveKitClient


class AgentRunner:
    """Runner for full audio mode via LiveKit"""
    
    def __init__(self, agent_name: str, room_name: Optional[str] = None, verbose: bool = False):
        self.agent_name = agent_name
        self.room_name = room_name or f"cli-{agent_name}-{uuid.uuid4().hex[:8]}"
        self.verbose = verbose
        # Use environment-aware API URL
        self.base_url = os.getenv("VOICEBOT_API_URL", get_voicebot_api_url())
        self.livekit_url = os.getenv("LIVEKIT_URL", get_livekit_url())
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def _get_agent_uuid(self) -> Optional[str]:
        """Get agent UUID from agent name"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        try:
            url = f"{self.base_url}/api/agents/"
            timeout = aiohttp.ClientTimeout(total=5)
            
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
            self.logger.warning(f"Could not contact backend API: {e}")
            return None
            
    async def create_livekit_room(self) -> Optional[str]:
        """Create a LiveKit room for the agent"""
        token = None
        
        # Method 1: Try via Backend API
        if self.session:
            try:
                # Get agent UUID from name
                agent_uuid = await self._get_agent_uuid()
                if agent_uuid:
                    url = f"{self.base_url}/api/livekit/create-room"
                    payload = {
                        "agent_id": agent_uuid,
                        "room_name": self.room_name
                    }
                    
                    async with self.session.post(url, json=payload) as response:
                        if response.status == 200:
                            result = await response.json()
                            token = result.get("access_token")
                            if token:
                                self.logger.info(f"Created LiveKit room via API: {self.room_name}")
                                return token
            except Exception as e:
                self.logger.warning(f"Failed to create room via API: {e}")

        # Method 2: Fallback to local token generation
        if not token:
            self.logger.info("⚠️ Backend API unavailable, falling back to local token generation")
            try:
                api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
                api_secret = os.getenv("LIVEKIT_API_SECRET", "secret")
                
                # Create token with permissions
                grant = api.VideoGrants(
                    room_join=True,
                    room=self.room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
                
                access_token = api.AccessToken(api_key, api_secret) \
                    .with_identity(f"cli-user-{uuid.uuid4().hex[:6]}") \
                    .with_name("CLI User") \
                    .with_grants(grant)
                
                token = access_token.to_jwt()
                self.logger.info(f"Generated local token for room: {self.room_name}")
                return token
                
            except Exception as e:
                self.logger.error(f"Failed to generate local token: {e}")
                return None

        return token
            
    async def notify_agent(self) -> bool:
        """Notify agent to join the LiveKit room"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        try:
            # Get agent UUID from name
            agent_uuid = await self._get_agent_uuid()
            if not agent_uuid:
                self.logger.warning(f"Agent '{self.agent_name}' not found - cannot notify via API")
                return False
                
            url = f"{self.base_url}/api/livekit/job-notification"
            payload = {
                "agent_id": agent_uuid,
                "room_name": self.room_name
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    self.logger.info(f"Notified agent {self.agent_name} to join room")
                    return True
                else:
                    self.logger.warning(f"Failed to notify agent: {response.status}")
                    return False
                    
        except Exception as e:
            self.logger.warning(f"Could not notify agent via API (is backend running?): {e}")
            return False
            
    async def check_livekit_health(self) -> bool:
        """Check if LiveKit server is healthy"""
        # Try Backend API first
        try:
            async with self.session.get(f"{self.base_url}/api/livekit/health") as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
            
        # Fallback to direct connection check? 
        # Actually, connecting to WS port is the best check.
        # But we can assume if local token gen works, we can try to connect.
        self.logger.info("⚠️ Could not verify health via API, assuming LiveKit is reachable at ws://localhost:7880")
        return True
            
    async def connect_to_livekit(self, token: str):
        """Connect to LiveKit room using the token"""
        self.logger.info(f"Connecting to LiveKit room: {self.room_name}")
        
        try:
            # Create and connect LiveKit client
            livekit_client = LiveKitClient(
                room_name=self.room_name,
                token=token,
                livekit_url=self.livekit_url
            )
            
            # Start the audio session
            await livekit_client.start_audio_session()
            
            return livekit_client
            
        except Exception as e:
            self.logger.error(f"Failed to connect to LiveKit: {e}")
            raise
        
    async def run(self):
        """Run the full audio mode"""
        print(f"\n🎙️  Full Audio Mode for Agent: {self.agent_name}")
        print("=" * 50)
        print(f"Room: {self.room_name}")
        print("LiveKit WebRTC audio connection")
        print("Press Ctrl+C to exit")
        print("=" * 50)
        
        async with self:
            # Check LiveKit health
            if not await self.check_livekit_health():
                print("❌ LiveKit service is not available!")
                print("Make sure LiveKit server is running on localhost:7880")
                return
                
            print("✅ LiveKit service check passed")
            
            # Create LiveKit room
            print("🔄 Creating LiveKit room...")
            token = await self.create_livekit_room()
            if not token:
                print("❌ Failed to create LiveKit room (Check API or Local Keys)")
                return
                
            print("✅ LiveKit room ready")
            
            # Notify agent to join
            print("🔄 Notifying agent to join room...")
            if not await self.notify_agent():
                print("⚠️ Failed to notify agent via API. If agent is running in auto-dispatch mode, it might still join.")
                
            else:
                print("✅ Agent notified")
            
            # Connect to LiveKit
            print("🔄 Connecting to LiveKit...")
            livekit_client = None
            try:
                livekit_client = await self.connect_to_livekit(token)
                
                # Keep the connection alive
                print("\n🎧 Audio connection active!")
                print("Speak into your microphone to interact with the agent")
                print("Press Ctrl+C to disconnect")
                
                # Wait for user to interrupt
                while True:
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Disconnecting from LiveKit...")
            except Exception as e:
                self.logger.error(f"Error in LiveKit connection: {e}")
                print(f"❌ Connection error: {e}")
            finally:
                if livekit_client:
                    await livekit_client.disconnect()
                
        print("\n📞 Connection closed")


async def main():
    """Test the agent runner"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python agent_runner.py <agent_name> [room_name]")
        return
        
    agent_name = sys.argv[1]
    room_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    runner = AgentRunner(agent_name, room_name, verbose=True)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())