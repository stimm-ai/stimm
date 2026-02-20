"""Stimm protocol — message types and LiveKit data channel binding.

Defines all messages exchanged between VoiceAgent and Supervisor
over a LiveKit reliable data channel.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Literal, Union

from pydantic import BaseModel

logger = logging.getLogger("stimm.protocol")

STIMM_TOPIC = "stimm"

# ---------------------------------------------------------------------------
# VoiceAgent → Supervisor messages
# ---------------------------------------------------------------------------


class TranscriptMessage(BaseModel):
    """Real-time speech transcript from the voice agent's STT."""

    type: Literal["transcript"] = "transcript"
    partial: bool
    text: str
    timestamp: int
    confidence: float = 1.0


class StateMessage(BaseModel):
    """Voice agent state transition (listening / thinking / speaking)."""

    type: Literal["state"] = "state"
    state: Literal["listening", "thinking", "speaking"]
    timestamp: int


class BeforeSpeakMessage(BaseModel):
    """Emitted before the voice agent sends text to TTS.

    Gives the supervisor a window to review or override.
    """

    type: Literal["before_speak"] = "before_speak"
    text: str
    turn_id: str


class MetricsMessage(BaseModel):
    """Per-turn latency metrics."""

    type: Literal["metrics"] = "metrics"
    turn: int
    vad_ms: float = 0.0
    stt_ms: float = 0.0
    llm_ttft_ms: float = 0.0
    tts_ttfb_ms: float = 0.0
    total_ms: float = 0.0


# ---------------------------------------------------------------------------
# Supervisor → VoiceAgent messages
# ---------------------------------------------------------------------------

AgentMode = Literal["autonomous", "relay", "hybrid"]


class InstructionMessage(BaseModel):
    """Instruction from supervisor for the voice agent to speak or incorporate."""

    type: Literal["instruction"] = "instruction"
    text: str
    priority: Literal["normal", "interrupt"] = "normal"
    speak: bool = True


class ContextMessage(BaseModel):
    """Additional context for the voice agent's working memory."""

    type: Literal["context"] = "context"
    text: str
    append: bool = True


class ActionResultMessage(BaseModel):
    """Notification that an action/tool completed in the supervisor."""

    type: Literal["action_result"] = "action_result"
    action: str
    status: str
    summary: str


class ModeMessage(BaseModel):
    """Switch the voice agent's operating mode."""

    type: Literal["mode"] = "mode"
    mode: AgentMode


class OverrideMessage(BaseModel):
    """Cancel the voice agent's pending response and replace it."""

    type: Literal["override"] = "override"
    turn_id: str
    replacement: str


# ---------------------------------------------------------------------------
# Union of all message types
# ---------------------------------------------------------------------------

StimmMessage = Union[
    TranscriptMessage,
    StateMessage,
    BeforeSpeakMessage,
    MetricsMessage,
    InstructionMessage,
    ContextMessage,
    ActionResultMessage,
    ModeMessage,
    OverrideMessage,
]

_MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    "transcript": TranscriptMessage,
    "state": StateMessage,
    "before_speak": BeforeSpeakMessage,
    "metrics": MetricsMessage,
    "instruction": InstructionMessage,
    "context": ContextMessage,
    "action_result": ActionResultMessage,
    "mode": ModeMessage,
    "override": OverrideMessage,
}

# Callback type for message handlers
MessageHandler = Callable[..., Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# StimmProtocol — data channel binding
# ---------------------------------------------------------------------------


class StimmProtocol:
    """Handles serialization and data channel routing for stimm messages.

    Bind to a LiveKit Room, then register handlers per message type.
    Inbound messages are deserialized and dispatched to the appropriate handler.
    Outbound messages are serialized and published to the data channel.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._room: Any | None = None  # livekit.rtc.Room (lazy import)

    def bind(self, room: Any) -> None:
        """Bind to a LiveKit room's data channel.

        Args:
            room: A ``livekit.rtc.Room`` instance.
        """
        self._room = room
        room.on("data_received", self._on_data)
        logger.debug("StimmProtocol bound to room")

    def _on_data(self, data: Any) -> None:
        """Handle incoming data channel packet."""
        if getattr(data, "topic", None) != STIMM_TOPIC:
            return

        try:
            raw = data.data if isinstance(data.data, bytes) else data.data.encode()
            payload = json.loads(raw)
            msg_type = payload.get("type")
            cls = _MESSAGE_TYPES.get(msg_type)  # type: ignore[arg-type]
            if cls is None:
                logger.warning("Unknown stimm message type: %s", msg_type)
                return
            msg = cls.model_validate(payload)
        except Exception:
            logger.exception("Failed to deserialize stimm message")
            return

        handlers = self._handlers.get(msg_type, [])  # type: ignore[arg-type]
        for handler in handlers:
            asyncio.ensure_future(handler(msg))

    # -- Registration helpers ------------------------------------------------

    def _on(self, msg_type: str, handler: MessageHandler) -> None:
        self._handlers.setdefault(msg_type, []).append(handler)

    def on_transcript(self, handler: MessageHandler) -> None:
        self._on("transcript", handler)

    def on_state(self, handler: MessageHandler) -> None:
        self._on("state", handler)

    def on_before_speak(self, handler: MessageHandler) -> None:
        self._on("before_speak", handler)

    def on_metrics(self, handler: MessageHandler) -> None:
        self._on("metrics", handler)

    def on_instruction(self, handler: MessageHandler) -> None:
        self._on("instruction", handler)

    def on_context(self, handler: MessageHandler) -> None:
        self._on("context", handler)

    def on_action_result(self, handler: MessageHandler) -> None:
        self._on("action_result", handler)

    def on_mode(self, handler: MessageHandler) -> None:
        self._on("mode", handler)

    def on_override(self, handler: MessageHandler) -> None:
        self._on("override", handler)

    # -- Send helpers --------------------------------------------------------

    async def _send(self, msg: BaseModel) -> None:
        if not self._room:
            logger.warning("Cannot send — protocol not bound to a room")
            return
        payload = msg.model_dump_json().encode()
        await self._room.local_participant.publish_data(
            payload,
            topic=STIMM_TOPIC,
            reliable=True,
        )

    async def send_transcript(self, msg: TranscriptMessage) -> None:
        await self._send(msg)

    async def send_state(self, msg: StateMessage) -> None:
        await self._send(msg)

    async def send_before_speak(self, msg: BeforeSpeakMessage) -> None:
        await self._send(msg)

    async def send_metrics(self, msg: MetricsMessage) -> None:
        await self._send(msg)

    async def send_instruction(self, msg: InstructionMessage) -> None:
        await self._send(msg)

    async def send_context(self, msg: ContextMessage) -> None:
        await self._send(msg)

    async def send_action_result(self, msg: ActionResultMessage) -> None:
        await self._send(msg)

    async def send_mode(self, mode: AgentMode) -> None:
        await self._send(ModeMessage(mode=mode))

    async def send_override(self, msg: OverrideMessage) -> None:
        await self._send(msg)
