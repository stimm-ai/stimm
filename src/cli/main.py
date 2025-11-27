#!/usr/bin/env python3
"""
CLI Tool for testing voice agents from command line
Supports both full audio mode (via LiveKit) and text-only mode
"""

import argparse
import asyncio
import logging
import sys
from enum import Enum
from typing import Optional
import aiohttp
import os

from cli.agent_runner import AgentRunner
from cli.text_input import TextInterface


class CLIMode(Enum):
    FULL = "full"    # Audio via LiveKit
    TEXT = "text"    # Text only


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


async def list_agents(verbose: bool = False):
    """List all available agents"""
    base_url = "http://localhost:8001"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/api/agents/") as response:
                if response.status == 200:
                    agents = await response.json()
                    print("\n🤖 Available Agents:")
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
    except Exception as e:
        print(f"❌ Error listing agents: {e}")
        return 1


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Test voice agents from command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test agent in text-only mode
  python -m src.cli.main --agent-name "etienne" --mode text
  
  # Test agent with full audio via LiveKit
  python -m src.cli.main --agent-name "etienne" --mode full
  
  # Test with custom room name and verbose logging
  python -m src.cli.main --agent-name "etienne" --mode full --room-name "test-room" --verbose
  
  # List all available agents
  python -m src.cli.main --list-agents
        """
    )
    
    parser.add_argument(
        "--agent-name",
        help="Name of the agent to test"
    )
    
    parser.add_argument(
        "--mode",
        choices=["full", "text"],
        default="text",
        help="Mode: 'full' for audio via LiveKit, 'text' for text only (default: text)"
    )
    
    parser.add_argument(
        "--room-name",
        help="Custom room name for LiveKit (default: auto-generated)"
    )
    
    parser.add_argument(
        "--use-rag",
        action="store_true",
        default=True,
        help="Use RAG for context (default: True)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List all available agents"
    )
    
    parser.add_argument(
        "--test-mic",
        type=float,
        metavar="SECONDS",
        help="Test microphone by recording N seconds to test_recording.wav"
    )
    
    parser.add_argument(
        "--test-livekit-mic",
        type=float,
        metavar="SECONDS",
        help="Test LiveKit microphone capture by recording N seconds to test_livekit_recording.wav"
    )

    parser.add_argument(
        "--test-echo",
        action="store_true",
        help="Test LiveKit audio pipeline with echo server and client"
    )

    return parser.parse_args()


async def run_text_mode(agent_name: str, use_rag: bool = True, verbose: bool = False):
    """Run agent in text-only mode"""
    logging.info(f"Starting text-only mode for agent: {agent_name}")
    logging.info(f"RAG enabled: {use_rag}")
    
    try:
        text_interface = TextInterface(agent_name, use_rag=use_rag, verbose=verbose)
        await text_interface.run()
    except KeyboardInterrupt:
        logging.info("Text mode interrupted by user")
    except Exception as e:
        logging.error(f"Error in text mode: {e}")
        return 1
    
    return 0


async def run_full_mode(agent_name: str, room_name: Optional[str] = None, verbose: bool = False):
    """Run agent in full audio mode via LiveKit"""
    logging.info(f"Starting full audio mode for agent: {agent_name}")
    
    try:
        agent_runner = AgentRunner(agent_name, room_name, verbose=verbose)
        await agent_runner.run()
    except KeyboardInterrupt:
        logging.info("Full mode interrupted by user")
    except Exception as e:
        logging.error(f"Error in full mode: {e}")
        return 1
    
    return 0


def test_microphone(duration: float):
    """Test microphone by recording to a WAV file using PulseAudio"""
    print(f"\n🎤 Testing Microphone")
    print("=" * 80)
    print(f"Recording {duration} seconds to test_recording.wav...")
    print("Speak into your microphone now!")
    print()
    
    try:
        # Use the working PulseAudio method from test_mic.py
        from cli.test_mic import test_pulseaudio_recording
        
        success = test_pulseaudio_recording(duration, "test_recording.wav")
        
        if success:
            print()
            print("✅ Recording complete!")
            print(f"📁 Saved to: test_recording.wav")
            print("🔊 Play it back to verify your microphone works:")
            print("   aplay test_recording.wav  (Linux)")
            print("   afplay test_recording.wav  (Mac)")
            print()
            print("📥 To copy the file from Docker to your repo:")
            print("   docker cp voicebot-app:/app/test_recording.wav ./test_recording.wav")
            print()
            return 0
        else:
            print(f"\n❌ Microphone test failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Microphone test failed: {e}")
        print("\nTroubleshooting:")
        print("• Make sure your microphone is connected and not muted")
        print("• Check that ffmpeg is installed: apt-get install ffmpeg")
        print("• Check that pulseaudio-utils is installed: apt-get install pulseaudio-utils")
        return 1


from cli.test_livekit_microphone import test_livekit_microphone


async def test_echo_pipeline(verbose: bool = False):
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
                # Check if process is still running
                if process.poll() is not None:
                    # Read remaining output
                    remaining_lines = process.stdout.readlines()
                    for line in remaining_lines:
                        if verbose: # Only log if verbose
                            logging.info(f"[{name}] {line.strip()}")
                    break
                
                # Simplified blocking readline in executor
                line = await asyncio.get_event_loop().run_in_executor(None, process.stdout.readline)
                if line:
                    if verbose:
                        logging.info(f"[{name}] {line.strip()}")
                else:
                    # EOF or empty read
                    if process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)
        
        # Start logging tasks
        if verbose:
            tasks.append(asyncio.create_task(log_process_output(server_process, "SERVER")))
            tasks.append(asyncio.create_task(log_process_output(client_process, "CLIENT")))
        
        # Wait for user interrupt
        logging.info("✅ Echo pipeline running! Speak into your microphone to test.")
        logging.info("Press Ctrl+C to stop...")
        
        # Keep running until interrupted
        while True:
            # Check if processes died
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
        # Cleanup processes
        if server_process and server_process.poll() is None:
            server_process.terminate()
        if client_process and client_process.poll() is None:
            client_process.terminate()
        
        # Wait for processes to terminate
        if server_process:
            server_process.wait(timeout=5)
        if client_process:
            client_process.wait(timeout=5)
        
        # Cancel logging tasks
        for task in tasks:
            task.cancel()
            
        logging.info("✅ Echo pipeline stopped")


async def main():
    """Main entry point - synchronous wrapper for async code"""
    return await async_main()

async def async_main():
    """Async main entry point"""
    args = parse_args()
    setup_logging(args.verbose)
    
    # Handle microphone test mode
    if args.test_mic:
        logging.info(f"Testing microphone for {args.test_mic} seconds")
        return test_microphone(args.test_mic)
    
    # Handle LiveKit microphone test mode
    if args.test_livekit_mic:
        logging.info(f"Testing LiveKit microphone for {args.test_livekit_mic} seconds")
        return await test_livekit_microphone(args.test_livekit_mic)

    if args.test_echo:
        logging.info("Testing LiveKit echo pipeline")
        return await test_echo_pipeline(args.verbose)

    if args.list_agents:
        logging.info("Listing available agents")
        return await list_agents(args.verbose)
    
    if not args.agent_name:
        print("❌ Agent name is required. Use --agent-name <name> or --list-agents to see available agents")
        return 1
    
    logging.info(f"Starting CLI tool for agent: {args.agent_name}")
    logging.info(f"Mode: {args.mode}")
    
    try:
        if args.mode == "text":
            return await run_text_mode(args.agent_name, args.use_rag, args.verbose)
        else:  # full mode
            return await run_full_mode(args.agent_name, args.room_name, args.verbose)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    # Run the async main function
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        pass