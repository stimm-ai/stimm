"""Tests for StimmRoom token generation and lifecycle."""

from stimm.room import StimmRoom
from stimm.voice_agent import VoiceAgent


class TestStimmRoom:
    def test_auto_generated_room_name(self) -> None:
        agent = VoiceAgent()
        room = StimmRoom(
            livekit_url="ws://localhost:7880",
            api_key="devkey",
            api_secret="secret",
            voice_agent=agent,
        )
        assert room.room_name.startswith("stimm-")
        assert len(room.room_name) > len("stimm-")

    def test_custom_room_name(self) -> None:
        agent = VoiceAgent()
        room = StimmRoom(
            livekit_url="ws://localhost:7880",
            api_key="devkey",
            api_secret="secret",
            voice_agent=agent,
            room_name="my-room",
        )
        assert room.room_name == "my-room"

    def test_not_started_initially(self) -> None:
        agent = VoiceAgent()
        room = StimmRoom(
            livekit_url="ws://localhost:7880",
            api_key="devkey",
            api_secret="secret",
            voice_agent=agent,
        )
        assert room.started is False

    def test_get_client_token(self) -> None:
        agent = VoiceAgent()
        room = StimmRoom(
            livekit_url="ws://localhost:7880",
            api_key="devkey",
            api_secret="secret",
            voice_agent=agent,
        )
        token = room.get_client_token("user-1")
        # Should be a valid JWT (3 dot-separated parts)
        assert token.count(".") == 2

    def test_get_voice_agent_token(self) -> None:
        agent = VoiceAgent()
        room = StimmRoom(
            livekit_url="ws://localhost:7880",
            api_key="devkey",
            api_secret="secret",
            voice_agent=agent,
        )
        token = room.get_voice_agent_token()
        assert token.count(".") == 2
