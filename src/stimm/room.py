"""StimmRoom — manages a LiveKit room with a VoiceAgent + Supervisor pair.

Handles room creation, token generation, and lifecycle management
for the dual-agent setup.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any
from uuid import uuid4

from stimm.supervisor import Supervisor
from stimm.voice_agent import VoiceAgent

logger = logging.getLogger("stimm.room")

# Identities that belong to internal agents, not human users.
# Used by the inactivity watchdog to ignore non-human participants.
_INTERNAL_PREFIXES: tuple[str, ...] = ("stimm-", "agent_")


def _is_internal(identity: str) -> bool:
    """Return True if the identity belongs to an internal agent."""
    return any(identity.startswith(p) for p in _INTERNAL_PREFIXES)


class StimmRoom:
    """Manages a LiveKit room hosting a VoiceAgent and optional Supervisor.

    Creates the room, generates access tokens, connects both agents,
    and provides a client token for end-users to join.

    The room monitors participant activity and automatically shuts down after
    ``inactivity_timeout_s`` seconds of no human participants.  The same value
    is also set as LiveKit's server-side ``departure_timeout`` so the room is
    cleaned up even if the process crashes.

    Example::

        room = StimmRoom(
            livekit_url="ws://localhost:7880",
            api_key="devkey",
            api_secret="secret",
            voice_agent=my_agent,
            supervisor=my_supervisor,
        )
        await room.start()
        client_token = room.get_client_token("user-123")
        # ... user joins with client_token ...
        await room.stop()

    Args:
        livekit_url: LiveKit server WebSocket URL.
        api_key: LiveKit API key.
        api_secret: LiveKit API secret.
        voice_agent: The ``VoiceAgent`` instance to run in this room.
        supervisor: Optional ``Supervisor`` instance. If not provided,
            the voice agent runs in standalone mode.
        room_name: Optional room name. Auto-generated if not provided.
        inactivity_timeout_s: Seconds of no human participants before the room
            is automatically stopped. Defaults to 600 (10 minutes). Also used
            as LiveKit ``departure_timeout`` for server-side enforcement.
    """

    def __init__(
        self,
        *,
        livekit_url: str,
        api_key: str,
        api_secret: str,
        voice_agent: VoiceAgent,
        supervisor: Supervisor | None = None,
        room_name: str | None = None,
        inactivity_timeout_s: int = 600,
    ) -> None:
        self._url = livekit_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._voice_agent = voice_agent
        self._supervisor = supervisor
        self._room_name = room_name or f"stimm-{uuid4().hex[:8]}"
        self._inactivity_timeout_s = inactivity_timeout_s
        self._started = False
        self._stop_called = False
        self._inactivity_task: asyncio.Task[None] | None = None

    @property
    def room_name(self) -> str:
        """The LiveKit room name."""
        return self._room_name

    @property
    def started(self) -> bool:
        """Whether the room has been started."""
        return self._started

    @property
    def inactivity_timeout_s(self) -> int:
        """Inactivity timeout in seconds."""
        return self._inactivity_timeout_s

    # -- Helpers -------------------------------------------------------------

    def _make_room_service(self) -> Any:
        """Return a configured LiveKitAPI instance (caller must ``aclose()`` it)."""
        from livekit import api as lkapi

        http_url = self._url.replace("ws://", "http://").replace("wss://", "https://")
        return lkapi.LiveKitAPI(
            url=http_url,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )

    # -- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Create the room and connect both agents.

        1. Creates the LiveKit room (via server API) with inactivity timeouts.
        2. Generates a token for the supervisor (data-channel only).
        3. Connects the supervisor and starts the inactivity watchdog.
        """
        from livekit import api as lkapi

        lk = self._make_room_service()
        try:
            await lk.room.create_room(
                lkapi.CreateRoomRequest(
                    name=self._room_name,
                    # Server-side: auto-delete if no one ever joins (5 min).
                    empty_timeout=300,
                    # Server-side: auto-delete N seconds after last participant
                    # leaves (safety net in case stop() is never called).
                    departure_timeout=self._inactivity_timeout_s,
                )
            )
        finally:
            await lk.aclose()
        logger.info("Created LiveKit room: %s", self._room_name)

        # Connect supervisor (data-only)
        if self._supervisor:
            supervisor_token = self._generate_token(
                identity="stimm-supervisor",
                can_publish_data=True,
                can_subscribe=True,
                can_publish=False,  # No audio
            )
            await self._supervisor.connect(self._url, supervisor_token)

            # Start client-side inactivity watchdog
            self._inactivity_task = asyncio.create_task(
                self._inactivity_watchdog(),
                name=f"inactivity-{self._room_name}",
            )

        self._started = True
        logger.info("StimmRoom started: %s", self._room_name)

    async def stop(self) -> None:
        """Disconnect all participants then delete the LiveKit room.

        The shutdown sequence is:
        1. Cancel the inactivity watchdog.
        2. Disconnect the supervisor.
        3. Eject every remaining participant from the room (human and AI).
        4. Delete the room via the server API.

        Idempotent — safe to call multiple times.
        """
        if self._stop_called:
            return
        self._stop_called = True

        # 1. Cancel watchdog
        if self._inactivity_task and not self._inactivity_task.done():
            self._inactivity_task.cancel()
            try:
                await self._inactivity_task
            except asyncio.CancelledError:
                pass

        # 2. Disconnect supervisor
        if self._supervisor:
            try:
                await self._supervisor.disconnect()
            except Exception as exc:
                logger.warning("Error disconnecting supervisor: %s", exc)

        # 3. Eject all remaining participants then delete the room
        lk = self._make_room_service()
        try:
            from livekit import api as lkapi

            # List current participants
            try:
                resp = await lk.room.list_participants(
                    lkapi.ListParticipantsRequest(room=self._room_name)
                )
                participants = resp.participants
            except Exception as exc:
                logger.warning("Could not list participants for room %s: %s", self._room_name, exc)
                participants = []

            # Remove each participant so they receive a proper disconnect event
            for p in participants:
                try:
                    await lk.room.remove_participant(
                        lkapi.RoomParticipantIdentity(
                            room=self._room_name,
                            identity=p.identity,
                        )
                    )
                    logger.info("Ejected participant %s from room %s", p.identity, self._room_name)
                except Exception as exc:
                    logger.warning(
                        "Failed to eject participant %s from room %s: %s",
                        p.identity,
                        self._room_name,
                        exc,
                    )

            # 4. Delete the room
            try:
                await lk.room.delete_room(lkapi.DeleteRoomRequest(room=self._room_name))
                logger.info("Deleted LiveKit room: %s", self._room_name)
            except Exception as exc:
                logger.warning("Failed to delete LiveKit room %s: %s", self._room_name, exc)
        finally:
            await lk.aclose()

        self._started = False
        logger.info("StimmRoom stopped: %s", self._room_name)

    # -- Inactivity watchdog -------------------------------------------------

    async def _inactivity_watchdog(self) -> None:
        """Auto-stop the room after ``inactivity_timeout_s`` of no human participants.

        Hooks into the supervisor's LiveKit room events to track participant
        joins/leaves in real time, then polls once per minute to detect
        prolonged inactivity.
        """
        if self._supervisor is None or self._supervisor.room is None:
            return

        lk_room = self._supervisor.room
        _human_count = 0
        _last_departure: float = asyncio.get_event_loop().time()

        def _on_connected(participant: Any) -> None:
            nonlocal _human_count, _last_departure
            if not _is_internal(participant.identity):
                _human_count += 1
                logger.debug(
                    "Room %s: human participant joined (%s), count=%d",
                    self._room_name,
                    participant.identity,
                    _human_count,
                )

        def _on_disconnected(participant: Any) -> None:
            nonlocal _human_count, _last_departure
            if not _is_internal(participant.identity):
                _human_count = max(0, _human_count - 1)
                if _human_count == 0:
                    _last_departure = asyncio.get_event_loop().time()
                    logger.info(
                        "Room %s: last human participant left (%s), inactivity timer started (%ds)",
                        self._room_name,
                        participant.identity,
                        self._inactivity_timeout_s,
                    )

        lk_room.on("participant_connected", _on_connected)
        lk_room.on("participant_disconnected", _on_disconnected)

        try:
            check_interval = min(30, self._inactivity_timeout_s // 4 or 15)
            while True:
                await asyncio.sleep(check_interval)
                if _human_count > 0:
                    continue
                elapsed = asyncio.get_event_loop().time() - _last_departure
                if elapsed >= self._inactivity_timeout_s:
                    logger.info(
                        "Room %s: inactivity timeout reached (%.0fs), shutting down",
                        self._room_name,
                        elapsed,
                    )
                    asyncio.create_task(self.stop())
                    break
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up event listeners to avoid dangling callbacks
            try:
                lk_room.off("participant_connected", _on_connected)
                lk_room.off("participant_disconnected", _on_disconnected)
            except Exception as exc:
                logger.debug(
                    "Could not detach room event listeners for %s: %s",
                    self._room_name,
                    exc,
                )

    def get_client_token(
        self,
        identity: str = "user",
        *,
        ttl_seconds: int = 3600,
    ) -> str:
        """Generate an access token for an end-user to join the room.

        The token grants audio publish/subscribe and data channel permissions.

        Args:
            identity: Unique identity for the participant.
            ttl_seconds: Token time-to-live in seconds.

        Returns:
            A JWT access token string.
        """
        return self._generate_token(
            identity=identity,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
            ttl_seconds=ttl_seconds,
        )

    def get_voice_agent_token(self) -> str:
        """Generate an access token for the voice agent.

        Grants full audio + data permissions.
        """
        return self._generate_token(
            identity="stimm-voice-agent",
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )

    def _generate_token(
        self,
        *,
        identity: str,
        can_publish: bool = True,
        can_subscribe: bool = True,
        can_publish_data: bool = True,
        ttl_seconds: int = 3600,
    ) -> str:
        """Generate a LiveKit access token.

        Args:
            identity: Participant identity.
            can_publish: Whether the participant can publish audio/video.
            can_subscribe: Whether the participant can subscribe to tracks.
            can_publish_data: Whether the participant can use data channels.
            ttl_seconds: Token TTL.

        Returns:
            A signed JWT token string.
        """
        from livekit import api as lkapi

        token = lkapi.AccessToken(self._api_key, self._api_secret)
        token.identity = identity
        token.ttl = timedelta(seconds=ttl_seconds)

        grant = lkapi.VideoGrants(
            room_join=True,
            room=self._room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            can_publish_data=can_publish_data,
        )
        token.video_grant = grant

        return token.to_jwt()
