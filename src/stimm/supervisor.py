"""Supervisor — base class for the background supervising agent.

The Supervisor joins a LiveKit room as a data-only participant (no audio).
It receives transcripts and voice agent state via the Stimm protocol,
and sends instructions back to guide the voice agent.

Subclass this and override the ``on_*`` methods to implement your
supervision logic.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from stimm.protocol import (
    ActionResultMessage,
    AgentMode,
    BeforeSpeakMessage,
    ContextMessage,
    InstructionMessage,
    MetricsMessage,
    OverrideMessage,
    SpeechEndedMessage,
    SpeechMessage,
    StateMessage,
    StimmProtocol,
    TranscriptMessage,
)

if TYPE_CHECKING:
    from stimm.voice_agent import VoiceAgent

logger = logging.getLogger("stimm.supervisor")


class Supervisor:
    """Base class for the background supervising agent.

    Joins a LiveKit room as a non-audio participant. Receives transcripts
    and voice agent state via the Stimm data channel protocol. Sends
    instructions back to the voice agent.

    Override the ``on_*`` methods to implement your supervision logic.

    Example::

        class MySupervisor(Supervisor):
            async def on_transcript(self, msg: TranscriptMessage):
                if not msg.partial:
                    result = await my_llm.process(msg.text)
                    await self.instruct(result, speak=True)

    Args:
        room: An optional pre-existing ``livekit.rtc.Room`` instance.
            If not provided, one will be created on ``connect()``.
    """

    def __init__(self, *, room: Any | None = None) -> None:
        self._room = room
        self._protocol = StimmProtocol()
        self._connected = False
        self._speeches: dict[str, asyncio.Future[bool]] = {}

    @property
    def protocol(self) -> StimmProtocol:
        """Access the underlying protocol handler."""
        return self._protocol

    @property
    def connected(self) -> bool:
        """Whether the supervisor is currently connected to a room."""
        return self._connected

    @property
    def room(self) -> Any | None:
        """The underlying LiveKit ``rtc.Room`` instance, or ``None`` before connect."""
        return self._room

    # -- Connection ----------------------------------------------------------

    async def connect(self, url: str, token: str) -> None:
        """Connect to a LiveKit room as a data-only participant.

        Args:
            url: LiveKit server WebSocket URL (e.g. ``ws://localhost:7880``).
            token: Access token with data-channel permissions for this room.
        """
        if self._room is None:
            from livekit import rtc

            self._room = rtc.Room()

        await self._room.connect(url, token)
        self._protocol.bind(self._room)
        self._register_handlers()
        self._connected = True
        logger.info("Supervisor connected to room")

    def attach(self, voice_agent: VoiceAgent) -> None:
        """Supervise *voice_agent* from its own process, without joining the room.

        Messages go straight between the two protocols. Use this instead of
        :meth:`connect` when the supervisor runs in the voice agent's job.
        """
        self._protocol.link(voice_agent.protocol)
        self._register_handlers()
        self._connected = True

    def _register_handlers(self) -> None:
        # Protocol messages → overridable on_* methods
        self._protocol.on_transcript(self.on_transcript)
        self._protocol.on_state(self.on_state_change)
        self._protocol.on_before_speak(self.on_before_speak)
        self._protocol.on_metrics(self.on_metrics)
        self._protocol.on_speech_ended(self._handle_speech_ended)

    async def disconnect(self) -> None:
        """Disconnect from the room."""
        if self._room:
            await self._room.disconnect()
        self._connected = False
        logger.info("Supervisor disconnected")

    # -- Event handlers (override in subclass) -------------------------------

    async def on_transcript(self, msg: TranscriptMessage) -> None:
        """Called when the user speaks.

        Override to process transcripts. Partial transcripts are streamed
        in real-time; final transcripts have ``msg.partial == False``.
        """

    async def on_state_change(self, msg: StateMessage) -> None:
        """Called when the voice agent changes state.

        States: ``"listening"``, ``"thinking"``, ``"speaking"``.
        """

    async def on_before_speak(self, msg: BeforeSpeakMessage) -> None:
        """Called before the voice agent speaks.

        Override to review or override the planned speech. Call
        ``self.override()`` to replace the voice agent's response.
        """

    async def on_metrics(self, msg: MetricsMessage) -> None:
        """Called with per-turn latency metrics.

        Useful for monitoring pipeline performance.
        """

    # -- Commands to voice agent ---------------------------------------------

    async def instruct(
        self,
        text: str,
        *,
        speak: bool = True,
        priority: str = "normal",
    ) -> None:
        """Send an instruction to the voice agent.

        Args:
            text: Instruction text. In relay mode this is spoken verbatim;
                in hybrid mode it's incorporated into the LLM context.
            speak: Whether the voice agent should speak this text.
            priority: ``"normal"`` or ``"interrupt"`` (interrupts current speech).
        """
        await self._protocol.send_instruction(
            InstructionMessage(text=text, speak=speak, priority=priority)  # type: ignore[arg-type]
        )

    async def speak(self, text: str | AsyncIterable[str]) -> bool:
        """Have the voice agent say *text* verbatim, as one interruptible utterance.

        Unlike :meth:`instruct`, this bypasses the voice agent's LLM in every mode,
        and an async iterable is streamed: each chunk is spoken as soon as it
        arrives. Returns ``True`` once the utterance has played to the end, or
        ``False`` if it was cut off. The rest of *text* is then never read, and an
        async generator is closed, which cancels whatever it was streaming from.
        """
        if not self._connected:
            raise RuntimeError("connect() or attach() the supervisor before speak()")
        speech_id = f"s_{uuid4().hex[:12]}"
        ended = asyncio.get_running_loop().create_future()
        self._speeches[speech_id] = ended

        async def send_all() -> None:
            try:
                async with contextlib.aclosing(_chunks(text)) as chunks:
                    async for chunk in chunks:
                        if chunk:
                            await self._protocol.send_speech(
                                SpeechMessage(speech_id=speech_id, text=chunk)
                            )
            finally:
                if not ended.done():  # done, failed or cancelled: close the utterance
                    await self._protocol.send_speech(SpeechMessage(speech_id=speech_id, final=True))

        sender = asyncio.ensure_future(send_all())
        try:
            await asyncio.wait([sender, ended], return_when=asyncio.FIRST_COMPLETED)
            if sender.done():
                sender.result()  # surface an error raised by *text*
            return not await ended
        finally:
            self._speeches.pop(speech_id, None)
            if not sender.done():  # cut off, or speak() itself was cancelled
                sender.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sender

    async def _handle_speech_ended(self, msg: SpeechEndedMessage) -> None:
        ended = self._speeches.get(msg.speech_id)
        if ended is not None and not ended.done():
            ended.set_result(msg.interrupted)

    async def add_context(self, text: str, *, append: bool = True) -> None:
        """Add context to the voice agent's working memory.

        Args:
            text: Context text to add.
            append: If ``True``, append to existing context. If ``False``,
                replace all existing context.
        """
        await self._protocol.send_context(ContextMessage(text=text, append=append))

    async def send_action_result(
        self,
        action: str,
        status: str,
        summary: str,
    ) -> None:
        """Notify the voice agent that a tool/action completed.

        Args:
            action: Name of the action (e.g. ``"calendar_check"``).
            status: Status string (e.g. ``"completed"``, ``"failed"``).
            summary: Human-readable summary of the result.
        """
        await self._protocol.send_action_result(
            ActionResultMessage(action=action, status=status, summary=summary)
        )

    async def set_mode(self, mode: AgentMode) -> None:
        """Switch the voice agent's operating mode.

        Args:
            mode: One of ``"autonomous"``, ``"relay"``, or ``"hybrid"``.
        """
        await self._protocol.send_mode(mode)

    async def override(self, turn_id: str, replacement: str) -> None:
        """Cancel the voice agent's pending response and replace it.

        Args:
            turn_id: The ``turn_id`` from the ``BeforeSpeakMessage`` to override.
            replacement: The replacement text to speak instead.
        """
        await self._protocol.send_override(
            OverrideMessage(turn_id=turn_id, replacement=replacement)
        )


async def _chunks(text: str | AsyncIterable[str]) -> AsyncIterator[str]:
    """Iterate *text* as chunks, closing the source when the caller stops early."""
    if isinstance(text, str):
        yield text
        return
    source = aiter(text)
    try:
        async for chunk in source:
            yield chunk
    finally:
        aclose = getattr(source, "aclose", None)
        if aclose is not None:
            await aclose()
