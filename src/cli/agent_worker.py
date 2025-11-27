"""
Standalone Agent Worker for Local Development.
This script instantiates the Voicebot Agent and connects it to a LiveKit room,
bypassing the FastAPI server orchestration.
"""

import asyncio
import logging
import os
import argparse
import uuid
from dotenv import load_dotenv

from livekit import api

# Import services
from services.agents.agent_factory import create_agent_session
from environment_config import get_livekit_url
from utils.logging_config import configure_logging

# Setup logging
# Will be re-configured in main()
logger = logging.getLogger("agent-worker")

async def run_worker(room_name: str, agent_id: str, livekit_url: str, api_key: str, api_secret: str):
    logger.info(f"🚀 Starting Standalone Agent Worker")
    logger.info(f"   Room: {room_name}")
    logger.info(f"   Agent: {agent_id}")
    logger.info(f"   LiveKit: {livekit_url}")

    try:
        # 1. Generate Token for the Agent
        logger.info("🔐 Generating Agent Token...")
        agent_token = api.AccessToken(api_key, api_secret) \
            .with_identity(f"agent_{agent_id}_{uuid.uuid4().hex[:8]}") \
            .with_name(f"Agent-{agent_id}") \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True
            ))
        
        token = agent_token.to_jwt()

        # 2. Create Agent Session (using shared factory)
        session_data = await create_agent_session(
            agent_id=agent_id,
            room_name=room_name,
            token=token,
            livekit_url=livekit_url
        )
        
        agent_bridge = session_data["agent_bridge"]

        # 3. Start Session
        logger.info("✅ Agent Worker Ready! Connecting to room...")
        await agent_bridge.start_session()
        
    except asyncio.CancelledError:
        logger.info("👋 Agent Worker stopped")
    except Exception as e:
        logger.error(f"❌ Agent Worker crashed: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Run a standalone Voicebot Agent Worker")
    parser.add_argument("--room-name", required=True, help="LiveKit room name to join")
    parser.add_argument("--agent-id", default="default", help="Agent ID")
    parser.add_argument("--livekit-url", help="LiveKit URL (default: env LIVEKIT_URL)")
    parser.add_argument("--api-key", help="LiveKit API Key (default: env LIVEKIT_API_KEY)")
    parser.add_argument("--api-secret", help="LiveKit API Secret (default: env LIVEKIT_API_SECRET)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(args.verbose)
    
    load_dotenv()

    livekit_url = args.livekit_url or os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    api_key = args.api_key or os.getenv("LIVEKIT_API_KEY", "devkey")
    api_secret = args.api_secret or os.getenv("LIVEKIT_API_SECRET", "secret")

    if not args.room_name:
        logger.error("❌ Room name is required")
        return

    try:
        asyncio.run(run_worker(
            room_name=args.room_name,
            agent_id=args.agent_id,
            livekit_url=livekit_url,
            api_key=api_key,
            api_secret=api_secret
        ))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()