"""StimmRoom — manages a LiveKit room with a VoiceAgent + Supervisor pair.

Handles room creation, token generation, and lifecycle management
for the dual-agent setup.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from stimm.supervisor import Supervisor
from stimm.voice_agent import VoiceAgent

logger = logging.getLogger("stimm.room")


class StimmRoom:
    """Manages a LiveKit room hosting a VoiceAgent and optional Supervisor.

    Creates the room, generates access tokens, connects both agents,
    and provides a client token for end-users to join.

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
    ) -> None:
        self._url = livekit_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._voice_agent = voice_agent
        self._supervisor = supervisor
        self._room_name = room_name or f"stimm-{uuid4().hex[:8]}"
        self._started = False

    @property
    def room_name(self) -> str:
        """The LiveKit room name."""
        return self._room_name

    @property
    def started(self) -> bool:
        """Whether the room has been started."""
        return self._started

    async def start(self) -> None:
        """Create the room and connect both agents.

        1. Creates the LiveKit room (via server API).
        2. Generates a token for the voice agent (with audio publish/subscribe).
        3. Generates a token for the supervisor (data-channel only).
        4. Connects the voice agent worker.
        5. Connects the supervisor.
        """
        from livekit import api as lkapi

        # Create room
        room_service = lkapi.RoomServiceClient(
            self._url.replace("ws://", "http://").replace("wss://", "https://"),
            self._api_key,
            self._api_secret,
        )
        await room_service.create_room(
            lkapi.CreateRoomRequest(name=self._room_name)
        )
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

        self._started = True
        logger.info("StimmRoom started: %s", self._room_name)

    async def stop(self) -> None:
        """Disconnect both agents and clean up."""
        if self._supervisor:
            await self._supervisor.disconnect()

        self._started = False
        logger.info("StimmRoom stopped: %s", self._room_name)

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
        token.ttl = ttl_seconds

        grant = lkapi.VideoGrants(
            room_join=True,
            room=self._room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            can_publish_data=can_publish_data,
        )
        token.video_grant = grant

        return token.to_jwt()
