"""Check the real livekit-agents API surface that stimm calls.

The other tests import the repo-root ``livekit/`` stubs, so they cannot notice
a livekit-agents upgrade breaking stimm. This one runs in a subprocess that only
sees ``src/`` and the installed packages.
"""

import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

PROBE = """
import inspect
from typing import get_args

from livekit.agents import AgentServer, AgentSession, JobContext, cli  # noqa: F401
from livekit.agents.voice.events import EventTypes
from livekit.plugins import silero
from livekit.rtc import IceTransportType, RtcConfiguration
from stimm import VoiceAgent
from stimm.worker import make_entrypoint

events = {"user_input_transcribed", "conversation_item_added", "agent_state_changed",
          "user_state_changed"}
assert events <= set(get_args(EventTypes)), events - set(get_args(EventTypes))
assert {"room", "room_options", "room_input_options"} <= set(
    inspect.signature(AgentSession.start).parameters)
assert {"instructions", "input_modality"} <= set(
    inspect.signature(AgentSession.generate_reply).parameters)
# supervisor-provided speech: say() a text stream, then watch the handle
from livekit.agents.voice import SpeechHandle
assert "AsyncIterable" in str(inspect.signature(AgentSession.say).parameters["text"].annotation)
assert callable(SpeechHandle.add_done_callback) and isinstance(SpeechHandle.interrupted, property)
# conversation styles: a bridge is one streamed chat request to a livekit LLM
from livekit.agents import Agent, llm
ctx = llm.ChatContext()
ctx.add_message(role="system", content="rules")
ctx.add_message(role="user", content="conversation")
assert [item.text_content for item in ctx.items] == ["rules", "conversation"]
assert "chat_ctx" in inspect.signature(llm.LLM.chat).parameters and callable(llm.LLM.prewarm)
assert "delta" in llm.ChatChunk.model_fields and "content" in llm.ChoiceDelta.model_fields
assert {"turn_ctx", "new_message"} <= set(
    inspect.signature(Agent.on_user_turn_completed).parameters)
assert "rtc_config" in inspect.signature(JobContext.connect).parameters
RtcConfiguration(ice_transport_type=IceTransportType.TRANSPORT_ALL)
assert callable(silero.VAD.load)

agent = VoiceAgent(instructions="test")
assert agent._current_session() is None  # Agent.session raises outside a session
AgentServer().rtc_session(make_entrypoint(lambda room, channel: None))
"""


def test_stimm_matches_installed_livekit_agents() -> None:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=SRC, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
