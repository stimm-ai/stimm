"""
Agent runner for full audio mode via LiveKit
"""

import asyncio
import logging
import os
import uuid
from typing import Optional

import aiohttp

from .livekit_client import LiveKitClient


class AgentRunner:
    """Runner for full audio mode via LiveKit"""
    
    def __init__(self, agent_name: str, room_name: Optional[str] = None, verbose: bool = False):
        self.agent_name = agent_name
        self.room_name = room_name or f"cli-{agent_name}-{uuid.uuid4().hex[:8]}"
        self.verbose = verbose
        self.base_url = "http://localhost:8001"
        self.livekit_url = os.getenv("LIVEKIT_URL", "ws://livekit:7880")
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def create_livekit_room(self) -> Optional[str]:
        """Create a LiveKit room for the agent"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        try:
            url = f"{self.base_url}/api/livekit/create-room"
            payload = {
                "agent_id": self.agent_name,
                "room_name": self.room_name
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    token = result.get("access_token")
                    if token:
                        self.logger.info(f"Created LiveKit room: {self.room_name}")
                        return token
                    else:
                        self.logger.error("No token received from LiveKit API")
                        self.logger.error(f"Response: {result}")
                        return None
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create room: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error creating LiveKit room: {e}")
            return None
            
    async def notify_agent(self) -> bool:
        """Notify agent to join the LiveKit room"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        try:
            url = f"{self.base_url}/api/livekit/job-notification"
            payload = {
                "agent_id": self.agent_name,
                "room_name": self.room_name
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    self.logger.info(f"Notified agent {self.agent_name} to join room")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to notify agent: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error notifying agent: {e}")
            return False
            
    async def check_livekit_health(self) -> bool:
        """Check if LiveKit server is healthy"""
        try:
            async with self.session.get(f"{self.base_url}/api/livekit/health") as response:
                return response.status == 200
        except Exception:
            return False
            
    async def connect_to_livekit(self, token: str):
        """Connect to LiveKit room using the token"""
        self.logger.info(f"Connecting to LiveKit room: {self.room_name}")
        self.logger.info(f"Token: {token[:20]}...")
        
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
                
            print("✅ LiveKit service is healthy")
            
            # Create LiveKit room
            print("🔄 Creating LiveKit room...")
            token = await self.create_livekit_room()
            if not token:
                print("❌ Failed to create LiveKit room")
                return
                
            print("✅ LiveKit room created")
            
            # Notify agent to join
            print("🔄 Notifying agent to join room...")
            if not await self.notify_agent():
                print("❌ Failed to notify agent")
                return
                
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