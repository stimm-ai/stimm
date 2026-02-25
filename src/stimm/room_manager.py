"""RoomManager — multi-session LiveKit room lifecycle manager.

Manages a pool of :class:`StimmRoom` instances identified by room name.
Useful when a single process needs to host multiple concurrent voice sessions
(e.g. an OpenClaw gateway serving many users at once).

Example::

    manager = RoomManager(
        livekit_url="ws://localhost:7880",
        api_key="devkey",
        api_secret="secret",
        agent_factory=lambda: VoiceAgent(...),
        supervisor_factory=lambda: MyCustomSupervisor(),
    )

    room = await manager.create_session(origin_channel="telegram")
    client_token = room.get_client_token("user-42")

    # later …
    await manager.end_session(room.room_name)
    await manager.stop_all()
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from stimm.room import StimmRoom
from stimm.supervisor import Supervisor
from stimm.voice_agent import VoiceAgent

if TYPE_CHECKING:
    pass

logger = logging.getLogger("stimm.room_manager")


class SessionInfo:
    """Metadata associated with a managed voice session."""

    __slots__ = ("room", "origin_channel")

    def __init__(self, room: StimmRoom, origin_channel: str) -> None:
        self.room = room
        self.origin_channel = origin_channel

    @property
    def room_name(self) -> str:
        return self.room.room_name


class RoomManager:
    """Manages multiple concurrent :class:`StimmRoom` voice sessions.

    Each call to :meth:`create_session` spins up a new :class:`StimmRoom`
    (creates a LiveKit room, connects the supervisor). All sessions are
    tracked by room name and can be listed, individually ended, or all
    stopped at once.

    Args:
        livekit_url: LiveKit server WebSocket URL.
        api_key: LiveKit API key.
        api_secret: LiveKit API secret.
        agent_factory: Callable that returns a fresh :class:`VoiceAgent`
            for each new session. Called once per :meth:`create_session`.
        supervisor_factory: Optional callable that returns a fresh
            :class:`Supervisor` for each new session. If ``None``,
            sessions run without a supervisor.
    """

    def __init__(
        self,
        *,
        livekit_url: str,
        api_key: str,
        api_secret: str,
        agent_factory: Callable[[], VoiceAgent],
        supervisor_factory: Callable[[], Supervisor] | None = None,
    ) -> None:
        self._url = livekit_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._agent_factory = agent_factory
        self._supervisor_factory = supervisor_factory
        self._sessions: dict[str, SessionInfo] = {}

    # -- Session lifecycle ---------------------------------------------------

    async def create_session(
        self,
        *,
        room_name: str | None = None,
        origin_channel: str = "unknown",
    ) -> StimmRoom:
        """Create and start a new voice session.

        Calls the agent and supervisor factories, creates a :class:`StimmRoom`,
        starts it (room creation + supervisor connect), and tracks it.

        Args:
            room_name: Optional explicit room name. Auto-generated if ``None``.
            origin_channel: Informational tag (e.g. ``"telegram"``, ``"web"``).

        Returns:
            The started :class:`StimmRoom` instance.
        """
        agent = self._agent_factory()
        supervisor = self._supervisor_factory() if self._supervisor_factory else None

        room = StimmRoom(
            livekit_url=self._url,
            api_key=self._api_key,
            api_secret=self._api_secret,
            voice_agent=agent,
            supervisor=supervisor,
            room_name=room_name,
        )
        await room.start()

        info = SessionInfo(room=room, origin_channel=origin_channel)
        self._sessions[room.room_name] = info

        logger.info("Voice session created: %s (origin: %s)", room.room_name, origin_channel)
        return room

    async def end_session(self, room_name: str) -> bool:
        """Stop a session and remove it from the managed pool.

        Args:
            room_name: Name of the room to end.

        Returns:
            ``True`` if the session was found and ended, ``False`` otherwise.
        """
        info = self._sessions.pop(room_name, None)
        if info is None:
            return False

        try:
            await info.room.stop()
        except Exception as exc:
            logger.warning("Error stopping room %s: %s", room_name, exc)

        logger.info("Voice session ended: %s", room_name)
        return True

    async def stop_all(self) -> None:
        """Stop all managed sessions."""
        room_names = list(self._sessions.keys())
        for room_name in room_names:
            await self.end_session(room_name)
        logger.info("All voice sessions stopped (%d total)", len(room_names))

    # -- Queries -------------------------------------------------------------

    def get_session(self, room_name: str) -> StimmRoom | None:
        """Return the :class:`StimmRoom` for a given room name, or ``None``."""
        info = self._sessions.get(room_name)
        return info.room if info else None

    def list_sessions(self) -> list[SessionInfo]:
        """Return metadata for all active sessions."""
        return list(self._sessions.values())

    def __len__(self) -> int:
        return len(self._sessions)
