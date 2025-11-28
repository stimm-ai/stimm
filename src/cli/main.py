#!/usr/bin/env python3
"""
CLI Tool for testing voice agents from command line
"""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path
from enum import Enum
from typing import Optional
import aiohttp

# Auto-configure PYTHONPATH for project
if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent  # Go up from cli/ to root
    src_path = project_root / "src"
    src_str = str(src_path)
    
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
        os.environ['PYTHONPATH'] = src_str
    
    print(f"🔧 PYTHONPATH automatiquement configuré: {src_str}")

from cli.agent_runner import AgentRunner
from cli.text_input import TextInterface
from utils.logging_config import configure_logging
from environment_config import config

class VliMode(Enum):
    LOCAL = "local"
    HTTP = "http"

def get_base_url(args):
    """Resolve base URL from args"""
    if args.url:
        return args.url
    if args.http:
        return config.voicebot_api_url
    return None

async def list_agents_local():
    from services.agents_admin.agent_service import AgentService
    from database.session import get_db
    db_gen = get_db()
    db = next(db_gen)
    try:
        service = AgentService(db)
        response = service.list_agents(skip=0, limit=100)
        agents = response.agents
        print("\n🤖 Available Agents (Local DB):")
        print("=" * 80)
        for agent in agents:
            print(f"• {agent.name}")
            print(f"  ID: {agent.id}")
            print(f"  Description: {agent.description or 'No description'}")
            print(f"  LLM Provider: {agent.llm_provider}")
            print(f"  LLM Config: {agent.llm_config}")
            print(f"  TTS Provider: {agent.tts_provider}")
            print(f"  STT Provider: {agent.stt_provider}")
            print(f"  Default: {'✅' if agent.is_default else '❌'}")
            print(f"  Active: {'✅' if agent.is_active else '❌'}")
            print()
        return 0
    finally:
        db_gen.close()

async def list_agents_http(base_url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/api/agents/") as response:
                if response.status == 200:
                    agents = await response.json()
                    print("\n🤖 Available Agents (HTTP):")
                    print("=" * 80)
                    for agent in agents:
                        print(f"• {agent['name']}")
                        print(f"  ID: {agent['id']}")
                        print(f"  Description: {agent.get('description', 'No description')}")
                        print(f"  LLM Provider: {agent['llm_provider']}")
                        print(f"  TTS Provider: {agent['tts_provider']}")
                        print(f"  STT Provider: {agent['stt_provider']}")
                        print(f"  Default: {'✅' if agent.get('is_default') else '❌'}")
                        print(f"  Active: {'✅' if agent.get('is_active') else '❌'}")
                        print()
                    return 0
                else:
                    print(f"❌ Failed to fetch agents: {response.status}")
                    return 1
    except aiohttp.ClientConnectorError:
        print("❌ Cannot connect to backend. Make sure the backend is running:")
        print("   docker compose up -d")
        return 1

async def list_agents(args):
    """List all available agents"""
    try:
        base_url = get_base_url(args)
        if base_url:
            return await list_agents_http(base_url)
        else:
            return await list_agents_local()
    except Exception as e:
        print(f"❌ Error listing agents: {e}")
        import traceback
        traceback.print_exc()
        return 1

def preprocess_argv():
    """
    Preprocess argv to handle the ambiguous --http [URL] argument.
    If --http is followed by a URL (not a command/flag), convert it to --url URL.
    This allows supporting both '--http command' and '--http URL command'.
    """
    argv = sys.argv[1:]
    new_argv = []
    i = 0
    commands = ["chat", "talk", "agents", "test"]
    
    while i < len(argv):
        arg = argv[i]
        if arg == "--http":
            # Check if next argument is a value (URL) or a command/flag
            if i + 1 < len(argv):
                next_arg = argv[i+1]
                if not next_arg.startswith("-") and next_arg not in commands:
                    # It's a URL! rewrite to --url
                    new_argv.append("--url")
                    new_argv.append(next_arg)
                    i += 2
                    continue
            # It's a flag (followed by command or nothing or another flag)
            new_argv.append("--http")
            i += 1
        else:
            new_argv.append(arg)
            i += 1
    return new_argv

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="CLI to interact with Voice Agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Talk with an agent in local mode (default)
  python -m src.cli.main talk --agent-name "ava"

  # Chat with an agent using a remote backend (default URL)
  python -m src.cli.main --http chat --agent-name "ava"

  # Chat with a specific backend URL
  python -m src.cli.main --http http://localhost:8001 chat --agent-name "ava"

  # List all agents from the local database
  python -m src.cli.main agents list
"""
    )

    # Global options
    parser.add_argument(
        "--http",
        action="store_true",
        help="Use HTTP mode. Can be used as a flag (default env URL) or with a value (custom URL)."
    )
    parser.add_argument(
        "--url",
        help=argparse.SUPPRESS # Hidden argument used by preprocessor
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # 'agents' command
    parser_agents = subparsers.add_parser("agents", help="Manage agents")
    agents_subparsers = parser_agents.add_subparsers(dest="agents_command", required=True)
    parser_agents_list = agents_subparsers.add_parser("list", help="List available agents")
    parser_agents_list.set_defaults(func=list_agents)


    # 'chat' command
    parser_chat = subparsers.add_parser("chat", help="Start a text-based chat session")
    parser_chat.add_argument("--agent-name", help="Name of the agent to use")
    parser_chat.add_argument("--disable-rag", action="store_true", help="Disable RAG for the session")
    parser_chat.set_defaults(func=run_chat_mode)

    # 'talk' command
    parser_talk = subparsers.add_parser("talk", help="Start a voice-based session")
    parser_talk.add_argument("--agent-name", help="Name of the agent to use")
    parser_talk.add_argument("--room-name", help="Custom room name for LiveKit")
    parser_talk.add_argument("--disable-rag", action="store_true", help="Disable RAG for the session")
    parser_talk.set_defaults(func=run_talk_mode)

    # 'test' command
    parser_test = subparsers.add_parser("test", help="Run tests")
    test_subparsers = parser_test.add_subparsers(dest="test_command", required=True)
    parser_test_echo = test_subparsers.add_parser("echo", help="Test LiveKit echo pipeline")
    parser_test_echo.set_defaults(func=test_echo_pipeline)


    return parser.parse_args(preprocess_argv())

async def run_chat_mode_local(args):
    from services.rag.chatbot_service import chatbot_service
    from services.rag.rag_preloader import rag_preloader
    from services.agents_admin.agent_service import AgentService
    from database.session import get_db

    agent_name = args.agent_name
    use_rag = not args.disable_rag
    
    # Get agent_id from name
    agent_id = None
    if agent_name:
        db_gen = get_db()
        db = next(db_gen)
        try:
            service = AgentService(db)
            agents = service.list_agents(skip=0, limit=1000).agents
            for agent in agents:
                if agent.name == agent_name:
                    agent_id = agent.id
                    break
            if not agent_id:
                print(f"❌ Agent '{agent_name}' not found in local database.")
                return 1
        finally:
            db_gen.close()

    print(f"\n🤖 Local Chat Mode (Agent: {agent_name or 'Default'})")
    print("=" * 50)
    
    if use_rag:
        print("⏳ Initializing RAG system (loading models)...")
        # Preload using the specific agent to ensure correct models are warmed up
        if not await rag_preloader.preload_all(agent_id=agent_id):
            print("❌ Failed to initialize RAG system.")
            return 1
        rag_state = rag_preloader.rag_state
        print("✅ RAG system ready.")
    else:
        # Create dummy RAG state if RAG is disabled
        from services.rag.rag_state import RagState
        rag_state = RagState()
        # Mock ensure_ready to pass if disable_rag is true?
        # Actually ChatbotService checks rag_state.client.
        # If we disable rag, we probably don't need rag_state to be ready?
        # Let's check ChatbotService logic.
        pass

    # Use global chatbot_service instance
    
    conversation_id = None
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            if user_input.lower() in ['quit', 'exit']:
                break

            print("🤖 Agent: ", end="", flush=True)
            full_response = ""
            async for chunk in chatbot_service.process_chat_message(
                message=user_input,
                conversation_id=conversation_id,
                rag_state=rag_state,
                agent_id=agent_id
            ):
                if chunk['type'] == 'chunk':
                    content = chunk.get('content', '')
                    print(content, end="", flush=True)
                    full_response += content
                elif chunk['type'] == 'complete':
                    conversation_id = chunk.get('conversation_id')
            print() # Newline after agent response
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    print("\n👋 Conversation ended.")
    return 0

async def run_chat_mode_http(args):
    if not args.agent_name:
        print("❌ Agent name is required. Use --agent-name <name>")
        return 1
    
    logging.info(f"Starting text-only mode for agent: {args.agent_name}")
    use_rag = not args.disable_rag
    logging.info(f"RAG enabled: {use_rag}")
    
    base_url = get_base_url(args) or config.voicebot_api_url
    
    try:
        text_interface = TextInterface(args.agent_name, use_rag=use_rag, verbose=args.verbose, base_url=base_url)
        await text_interface.run()
    except KeyboardInterrupt:
        logging.info("Text mode interrupted by user")
    except Exception as e:
        logging.error(f"Error in text mode: {e}")
        return 1
    
    return 0

async def run_chat_mode(args):
    """Run agent in text-only mode"""
    if args.http or args.url:
        return await run_chat_mode_http(args)
    else:
        return await run_chat_mode_local(args)

async def run_talk_mode(args):
    """Run agent in full audio mode via LiveKit"""
    if not args.agent_name:
        print("❌ Agent name is required. Use --agent-name <name>")
        return 1
        
    is_local = not (args.http or args.url)
    logging.info(f"Starting full audio mode for agent: {args.agent_name} (Local: {is_local})")
    
    base_url = get_base_url(args) or config.voicebot_api_url

    try:
        agent_runner = AgentRunner(
            args.agent_name,
            args.room_name,
            verbose=args.verbose,
            is_local=is_local,
            base_url=base_url
        )
        await agent_runner.run()
    except KeyboardInterrupt:
        logging.info("Full mode interrupted by user")
    except Exception as e:
        logging.error(f"Error in full mode: {e}")
        return 1
    
    return 0

async def test_echo_pipeline(args):
    """Test LiveKit audio pipeline with echo server and client"""
    import subprocess
    import signal
    import time
    import os
    
    logging.info("🚀 Starting LiveKit echo pipeline test")
    logging.info("This will start both echo server and client in parallel")
    logging.info("Speak into your microphone to hear yourself echoed back!")
    logging.info("Press Ctrl+C to stop both processes")
    
    server_process = None
    client_process = None
    tasks = []
    
    try:
        # Start echo server
        logging.info("🔄 Starting echo server...")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "src.cli.echo_server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1, # Line buffered
            env={**os.environ, "PYTHONUNBUFFERED": "1"} # Force unbuffered output
        )
        
        # Wait a moment for server to start
        time.sleep(2)
        
        # Start echo client
        logging.info("🎧 Starting echo client...")
        client_process = subprocess.Popen(
            [sys.executable, "-m", "src.cli.echo_client"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1, # Line buffered
            env={**os.environ, "PYTHONUNBUFFERED": "1"} # Force unbuffered output
        )
        
        # Log output from both processes
        async def log_process_output(process, name):
            while True:
                if process.poll() is not None:
                    remaining_lines = process.stdout.readlines()
                    for line in remaining_lines:
                        if args.verbose:
                            logging.info(f"[{name}] {line.strip()}")
                    break
                
                line = await asyncio.get_event_loop().run_in_executor(None, process.stdout.readline)
                if line:
                    if args.verbose:
                        logging.info(f"[{name}] {line.strip()}")
                else:
                    if process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)
        
        if args.verbose:
            tasks.append(asyncio.create_task(log_process_output(server_process, "SERVER")))
            tasks.append(asyncio.create_task(log_process_output(client_process, "CLIENT")))
        
        logging.info("✅ Echo pipeline running! Speak into your microphone to test.")
        logging.info("Press Ctrl+C to stop...")
        
        while True:
            if server_process.poll() is not None:
                logging.error("❌ Echo server crashed!")
                break
            if client_process.poll() is not None:
                logging.error("❌ Echo client crashed!")
                break
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logging.info("🛑 Stopping echo pipeline...")
    finally:
        if server_process and server_process.poll() is None:
            server_process.terminate()
        if client_process and client_process.poll() is None:
            client_process.terminate()
        
        if server_process:
            server_process.wait(timeout=5)
        if client_process:
            client_process.wait(timeout=5)
        
        for task in tasks:
            task.cancel()
            
        logging.info("✅ Echo pipeline stopped")
    return 0

async def main():
    """Async main entry point"""
    args = parse_args()
    configure_logging(args.verbose)
    
    if hasattr(args, 'func'):
        return await args.func(args)
    
    return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        pass