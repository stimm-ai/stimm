"""Stimm — Dual-agent voice orchestration built on livekit-agents.

One agent talks fast. One agent thinks deep. They collaborate in real-time.

Usage::

    from stimm import VoiceAgent, Supervisor, StimmRoom

    agent = VoiceAgent(
        stt=deepgram.STT(),
        tts=openai.TTS(),
        vad=silero.VAD.load(),
        fast_llm=openai.LLM(model="gpt-4o-mini"),
        mode="hybrid",
    )

    class MySupervisor(Supervisor):
        async def on_transcript(self, msg):
            if not msg.partial:
                result = await big_llm.process(msg.text)
                await self.instruct(result, speak=True)

    room = StimmRoom(
        livekit_url="ws://localhost:7880",
        api_key="devkey",
        api_secret="secret",
        voice_agent=agent,
        supervisor=MySupervisor(),
    )
    await room.start()
"""

from stimm.buffering import BufferingLevel, TextBufferingStrategy
from stimm.conversation_supervisor import ConversationSupervisor
from stimm.room_manager import RoomManager, SessionInfo
from stimm.worker import SupervisorFactory, make_agent, make_entrypoint
from stimm.protocol import (
    ActionResultMessage,
    AgentMode,
    BeforeSpeakMessage,
    ContextMessage,
    InstructionMessage,
    MetricsMessage,
    ModeMessage,
    OverrideMessage,
    StateMessage,
    StimmProtocol,
    TranscriptMessage,
)
from stimm.room import StimmRoom
from stimm.supervisor import Supervisor
from stimm.voice_agent import VoiceAgent

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "VoiceAgent",
    "Supervisor",
    "ConversationSupervisor",
    "StimmRoom",
    "RoomManager",
    "SessionInfo",
    "StimmProtocol",
    # Worker / entrypoint helpers
    "make_agent",
    "make_entrypoint",
    "SupervisorFactory",
    # Buffering
    "BufferingLevel",
    "TextBufferingStrategy",
    # Message types
    "TranscriptMessage",
    "StateMessage",
    "BeforeSpeakMessage",
    "MetricsMessage",
    "InstructionMessage",
    "ContextMessage",
    "ActionResultMessage",
    "ModeMessage",
    "OverrideMessage",
    "AgentMode",
]
