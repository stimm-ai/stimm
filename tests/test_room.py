"""Tests for StimmRoom token generation and lifecycle."""

import os
import subprocess
import sys
from pathlib import Path

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


SRC = Path(__file__).resolve().parents[1] / "src"

# The repo-root livekit/ stubs return a fake JWT, so the real tokens are decoded in a
# subprocess that only sees src/ and the installed packages (as in test_livekit_api.py).
TOKEN_PROBE = """
from livekit import api
from stimm.room import StimmRoom
from stimm.voice_agent import VoiceAgent

room = StimmRoom(livekit_url="ws://localhost:7880", api_key="devkey", api_secret="secret",
                 voice_agent=VoiceAgent(instructions="test"), room_name="probe-room")
verify = api.TokenVerifier("devkey", "secret").verify

client = verify(room.get_client_token("user-1"))
assert client.identity == "user-1", client.identity
assert client.video is not None, "no room grant in the client token"
assert client.video.room_join and client.video.room == "probe-room", client.video
assert client.video.can_publish and client.video.can_publish_data, client.video

supervisor = verify(room._generate_token(identity="stimm-supervisor", can_publish=False))
assert supervisor.video.room == "probe-room", supervisor.video
assert not supervisor.video.can_publish and supervisor.video.can_publish_data, supervisor.video
"""


def test_tokens_carry_the_room_grant() -> None:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-c", TOKEN_PROBE], cwd=SRC, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
