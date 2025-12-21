"""
SIP Bridge Integration Service - Robust in-process SIP agent orchestration

This service runs as a background thread within the main API process and is responsible for:
1. Monitoring LiveKit rooms for SIP calls
2. Spawning agent worker processes for each SIP room
3. Tracking and cleaning up processes to prevent "double agent" issues
4. Providing health checks and status reporting

Key improvements:
- Thread-safe singleton pattern to prevent duplicate monitoring
- Process tracking with PID management
- Graceful shutdown and cleanup
- Reduced logging noise
"""

import asyncio
import logging
import os
import subprocess  # nosec B404
import sys
import threading
from typing import Dict, Optional, Set

from livekit import api

from environment_config import config
from services.agents_admin.agent_service import AgentService

logger = logging.getLogger(__name__)


class SIPBridgeIntegration:
    """Robust SIP agent orchestration service"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.monitoring_thread: Optional[threading.Thread] = None
        self.running = False
        self._stop_event = threading.Event()

        # Track active agent processes by room name
        self.active_processes: Dict[str, subprocess.Popen] = {}
        self.process_lock = threading.Lock()

        # LiveKit API client
        self.lkapi: Optional[api.LiveKitAPI] = None

        # Agent service for getting default agent
        self.agent_service = AgentService()

        self._initialized = True
        logger.debug("SIP Bridge Integration initialized (singleton)")

    def start(self):
        """Start the SIP Bridge service if enabled"""
        if not self.is_enabled():
            logger.info("SIP Bridge disabled (ENABLE_SIP_BRIDGE=false)")
            return

        with self._lock:
            if self.running:
                logger.warning("SIP Bridge already running")
                return

            logger.info("Starting SIP Bridge Integration...")

            try:
                # Create and start monitoring in a separate thread
                self._stop_event.clear()
                self.monitoring_thread = threading.Thread(target=self._run_monitoring, name="SIPBridgeMonitoring", daemon=True)
                self.monitoring_thread.start()
                self.running = True
                logger.info("SIP Bridge monitoring started successfully")

            except Exception as e:
                logger.error(f"Error starting SIP Bridge: {e}")
                self.running = False

    def stop(self):
        """Stop the SIP Bridge service"""
        with self._lock:
            if not self.running:
                return

            logger.info("Stopping SIP Bridge Integration...")
            self.running = False
            self._stop_event.set()

            try:
                # Stop all active agent processes
                self._cleanup_all_processes()

                if self.monitoring_thread and self.monitoring_thread.is_alive():
                    self.monitoring_thread.join(timeout=10)
                    if self.monitoring_thread.is_alive():
                        logger.warning("SIP Bridge monitoring thread did not stop gracefully")

                logger.info("SIP Bridge monitoring stopped successfully")

            except Exception as e:
                logger.error(f"Error stopping SIP Bridge: {e}")

    def _run_monitoring(self):
        """Execute monitoring in a dedicated event loop"""
        try:
            logger.debug("Starting SIP room monitoring...")

            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the monitoring coroutine until stop event
                loop.run_until_complete(self._monitoring_coro(loop))

            except Exception as e:
                logger.error(f"Error in SIP monitoring event loop: {e}")
            finally:
                # Cleanup
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    loop.close()
                except Exception:  # nosec B110
                    pass
                logger.debug("SIP monitoring event loop closed")

        except Exception as e:
            logger.error(f"Fatal error in SIP Bridge monitoring: {e}")
            self.running = False

    async def _monitoring_coro(self, loop):
        """Async monitoring coroutine"""
        try:
            # Initialize LiveKit API within the async context
            self.lkapi = api.LiveKitAPI(
                url=config.livekit_url.replace("ws://", "http://"),
                api_key=config.livekit_api_key,
                api_secret=config.livekit_api_secret,
            )
            logger.debug("LiveKit API initialized in monitoring thread")
        except Exception as e:
            logger.error(f"Failed to initialize LiveKit API: {e}")
            return

        sip_room_prefix = "sip-inbound"
        monitored_rooms: Set[str] = set()

        while not self._stop_event.is_set():
            try:
                # List all rooms using the LiveKit API
                rooms = await self.lkapi.room.list_rooms(api.ListRoomsRequest())

                # Find SIP rooms
                sip_rooms = [room for room in rooms.rooms if room.name.startswith(sip_room_prefix)]

                current_room_names = {room.name for room in sip_rooms}

                # Spawn agents for new rooms with participants
                for room in sip_rooms:
                    if room.num_participants > 0:
                        # Check if we already have an active process for this room
                        with self.process_lock:
                            existing_process = self.active_processes.get(room.name)
                            if existing_process is not None:
                                # Process exists, check if still alive
                                if existing_process.poll() is None:
                                    # Still running, skip
                                    continue
                                else:
                                    # Process died, remove it
                                    logger.warning(f"Agent process for room {room.name} died, will respawn")
                                    self.active_processes.pop(room.name, None)

                        # If room not in monitored_rooms, it's a new detection
                        if room.name not in monitored_rooms:
                            logger.debug(f"Detected new SIP room: {room.name} ({room.num_participants} participants)")
                        else:
                            logger.debug(f"Respawning agent for SIP room: {room.name}")

                        # Spawn agent
                        if self._spawn_agent_for_room(room.name):
                            monitored_rooms.add(room.name)
                        else:
                            logger.error(f"Failed to spawn agent for {room.name}")

                # Clean up rooms that no longer exist
                for room_name in list(monitored_rooms):
                    if room_name not in current_room_names:
                        logger.debug(f"SIP room ended: {room_name}")
                        self._cleanup_process_for_room(room_name)
                        monitored_rooms.remove(room_name)

                # Clean up orphaned processes (should be redundant but safe)
                self._cleanup_orphaned_processes()

            except Exception as e:
                logger.error(f"Error in SIP room monitoring iteration: {e}")

            # Sleep with interruptible wait (async version)
            try:
                await asyncio.wait_for(asyncio.get_event_loop().run_in_executor(None, self._stop_event.wait, 5), timeout=5)
            except asyncio.TimeoutError:
                pass  # Normal, just continue

        logger.info("SIP monitoring coroutine exiting")

    def _spawn_agent_for_room(self, room_name: str) -> bool:
        """Spawn an agent worker process for a SIP room"""
        try:
            logger.debug(f"Spawning agent for SIP room: {room_name}")

            # Get the Development Agent from database
            try:
                default_agent = self.agent_service.get_default_agent()
                agent_id = str(default_agent.id)
                agent_name = default_agent.name
                logger.debug(f"Found default agent: {agent_name} (ID: {agent_id})")
            except Exception as e:
                logger.error(f"Failed to get default agent: {e}")
                return False

            # Prepare environment
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            # Build command
            cmd = [
                sys.executable,
                "-m",
                "src.cli.agent_worker",
                "--room-name",
                room_name,
                "--agent-id",
                agent_id,
                "--livekit-url",
                config.livekit_url,
            ]

            logger.debug(f"Starting agent worker: {' '.join(cmd)}")

            # Start process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)  # nosec B603

            # Store the process
            with self.process_lock:
                self.active_processes[room_name] = process

            logger.debug(f"Agent worker spawned for SIP room: {room_name} (PID: {process.pid})")
            return True

        except Exception as e:
            logger.error(f"Failed to spawn agent for SIP room {room_name}: {e}")
            return False

    def _cleanup_process_for_room(self, room_name: str):
        """Clean up agent process for a specific room"""
        with self.process_lock:
            if room_name in self.active_processes:
                process = self.active_processes.pop(room_name)
                try:
                    if process.poll() is None:  # Still running
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        logger.debug(f"Terminated agent process for room {room_name}")
                    else:
                        logger.debug(f"Agent process for room {room_name} already exited")
                except Exception as e:
                    logger.error(f"Error cleaning up process for room {room_name}: {e}")

    def _cleanup_orphaned_processes(self):
        """Clean up processes that have exited unexpectedly"""
        with self.process_lock:
            rooms_to_remove = []
            for room_name, process in self.active_processes.items():
                if process.poll() is not None:  # Process has exited
                    rooms_to_remove.append(room_name)
                    logger.warning(f"Orphaned agent process detected for room {room_name}")

            for room_name in rooms_to_remove:
                self.active_processes.pop(room_name, None)

    def _cleanup_all_processes(self):
        """Clean up all active agent processes"""
        with self.process_lock:
            for room_name, process in list(self.active_processes.items()):
                try:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                except Exception as e:
                    logger.error(f"Error terminating process for room {room_name}: {e}")

            self.active_processes.clear()

    def is_enabled(self) -> bool:
        """Check if SIP Bridge is enabled"""
        return os.getenv("ENABLE_SIP_BRIDGE", "false").lower() == "true"

    def is_running(self) -> bool:
        """Check if the service is running"""
        return self.running and self.monitoring_thread and self.monitoring_thread.is_alive()

    def get_status(self) -> Dict:
        """Get current status of the SIP Bridge"""
        with self.process_lock:
            return {
                "enabled": self.is_enabled(),
                "running": self.is_running(),
                "active_rooms": list(self.active_processes.keys()),
                "process_count": len(self.active_processes),
                "process_pids": {room: proc.pid for room, proc in self.active_processes.items()},
            }


# Global singleton instance
sip_bridge_integration = SIPBridgeIntegration()


def start_sip_bridge():
    """Helper function to start the bridge"""
    sip_bridge_integration.start()


def stop_sip_bridge():
    """Helper function to stop the bridge"""
    sip_bridge_integration.stop()


def get_sip_bridge_status() -> Dict:
    """Helper function to get bridge status"""
    return sip_bridge_integration.get_status()
