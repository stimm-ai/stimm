"""ConversationSupervisor — buffered, turn-aware supervisor base class.

Extends :class:`Supervisor` with a rolling conversation history, a quiet-period
trigger, and a pluggable :meth:`process` method that subclasses implement to
call any reasoning backend (HTTP API, local LLM, rules engine, etc.).

Architecture
────────────

  User/Phone ──► LiveKit Room
                      │
               ┌──────┴──────────────────────┐
               │  VoiceAgent   (fast path)    │
               │  VAD → STT → fast LLM → TTS │
               └──────┬──────────────────────┘
                      │  Stimm data-channel protocol
               ┌──────┴──────────────────────┐
               │  ConversationSupervisor      │
               │  (data-only, no audio)       │
               │  buffers turns, calls        │
               │  process(history) → str      │
               └──────┬──────────────────────┘
                      │  subclass-defined transport
               ┌──────┴──────────────────────┐
               │  Reasoning backend           │
               │  (HTTP API, LLM, rules…)     │
               └─────────────────────────────┘

How it works
────────────
1. ``on_transcript`` buffers final user turns.
2. ``on_before_speak`` buffers assistant turns (for history continuity).
3. The background loop (started by ``start_loop()``) checks every
   ``loop_interval_s`` seconds whether new turns have arrived and the
   conversation has been quiet for at least ``quiet_s`` seconds.
4. When both conditions are met, ``process(history)`` is called with
   the formatted conversation history.
5. If the backend returns a non-empty string (not the ``NO_ACTION``
   sentinel), it is recorded as a supervisor turn and injected into the
   voice agent's context via ``add_context()``, replacing the previous
   context so the ``[Supervisor → assistant]`` line is visible on the
   next LLM turn.

Default voice agent instructions
─────────────────────────────────
:attr:`DEFAULT_INSTRUCTIONS` is a ready-to-use instructions string that
teaches the fast LLM how to relay supervisor turns naturally. Pass it to
:class:`stimm.VoiceAgent` ``instructions=`` or override with your own.

Usage::

    from stimm import ConversationSupervisor, VoiceAgent

    class MyBackendSupervisor(ConversationSupervisor):
        async def process(self, history: str) -> str:
            response = await my_llm.generate(history)
            return response or self.NO_ACTION

    supervisor = MyBackendSupervisor()
    await supervisor.connect(livekit_url, token)
    supervisor.start_loop()
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod

from stimm.protocol import BeforeSpeakMessage, StateMessage, TranscriptMessage
from stimm.supervisor import Supervisor

logger = logging.getLogger("stimm.conversation_supervisor")

# Sentinel: backend returns this to indicate "nothing to say this turn".
_NO_ACTION = "[NO_ACTION]"


class _Turn:
    __slots__ = ("role", "text")

    def __init__(self, role: str, text: str) -> None:
        self.role = role  # "user" | "assistant" | "supervisor"
        self.text = text


class ConversationSupervisor(Supervisor, ABC):
    """Buffered supervisor that drives a reasoning backend from conversation turns.

    Subclass and implement :meth:`process` to connect any backend.

    Args:
        quiet_s: Seconds of silence after the last user/assistant turn
            before :meth:`process` is called. Default: ``2.5``.
        loop_interval_s: How often the background loop wakes up to check
            for new turns. Default: ``1.5``.
        max_turns: Rolling history window size (number of turns).
            Default: ``40``.
    """

    #: Return this from :meth:`process` to skip context injection.
    NO_ACTION: str = _NO_ACTION

    #: Ready-to-use ``instructions=`` string for :class:`stimm.VoiceAgent`.
    #: Teaches the fast LLM to obey ``--Supervisor--`` hidden turns.
    DEFAULT_INSTRUCTIONS: str = (
        "You are a real-time voice assistant in a dual-agent system.\n\n"
        "Messages marked `--Supervisor--` are hidden internal instructions "
        "from your control system, not from the user. You must obey these "
        "instructions to formulate your next response to the user.\n\n"
        "RULES:\n"
        "1. Keep normal replies short.\n"
        "2. If there is no recent `--Supervisor--` instruction, give a brief "
        "honest filler in 1-2 sentences (e.g. say you are checking with your "
        "supervisor).\n"
        "3. When a recent `--Supervisor--` instruction appears, prioritize it "
        "and relay it naturally to the user.\n"
        "4. When relaying supervisor-provided facts (numbers, temperatures, "
        "times, names), keep them faithful: do not alter or embellish.\n"
        "5. Respond in the same language as the user.\n"
        "6. Never invent facts, and do not guess when uncertain."
    )

    def __init__(
        self,
        *,
        quiet_s: float = 2.5,
        loop_interval_s: float = 1.5,
        max_turns: int = 40,
    ) -> None:
        super().__init__()
        self.quiet_s = quiet_s
        self.loop_interval_s = loop_interval_s
        self.max_turns = max_turns

        self._history: list[_Turn] = []
        self._last_turn_ts: float = 0.0
        # Index of the first entry not yet forwarded to the backend.
        self._processed_up_to: int = 0
        self._processing = False
        self._loop_task: asyncio.Task[None] | None = None

    # -- Lifecycle -----------------------------------------------------------

    def start_loop(self) -> None:
        """Start the background processing loop."""
        self._loop_task = asyncio.ensure_future(self._loop())

    def stop_loop(self) -> None:
        """Cancel the background processing loop."""
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None

    # -- Abstract interface --------------------------------------------------

    @abstractmethod
    async def process(self, history: str) -> str:
        """Send the conversation history to the reasoning backend.

        Args:
            history: Formatted conversation history produced by
                :meth:`format_history`.

        Returns:
            The backend's response text, or :attr:`NO_ACTION` to skip
            context injection for this turn.
        """

    # -- Stimm event handlers ------------------------------------------------

    async def on_transcript(self, msg: TranscriptMessage) -> None:
        if msg.partial:
            return
        if msg.text.strip():
            self._push("user", msg.text)
            logger.debug("← user: %s", msg.text[:80])

    async def on_before_speak(self, msg: BeforeSpeakMessage) -> None:
        # Capture what the voice agent is about to say for history continuity.
        if msg.text and msg.text.strip():
            self._push("assistant", msg.text)
            logger.debug("← assistant: %s", msg.text[:80])

    async def on_state_change(self, msg: StateMessage) -> None:
        logger.debug("Agent state: %s", msg.state)

    # -- History helpers -----------------------------------------------------

    def _push(self, role: str, text: str) -> None:
        self._history.append(_Turn(role, text))
        if len(self._history) > self.max_turns:
            removed = len(self._history) - self.max_turns
            self._history = self._history[-self.max_turns:]
            self._processed_up_to = max(0, self._processed_up_to - removed)
        if role in ("user", "assistant"):
            self._last_turn_ts = time.monotonic()

    def format_history(self) -> str:
        """Format the rolling history for :meth:`process`.

        Override to customise the format sent to the backend.
        """
        lines: list[str] = []
        for t in self._history:
            if t.role == "user":
                lines.append(f"User: {t.text}")
            elif t.role == "assistant":
                lines.append(f"Assistant: {t.text}")
            else:
                lines.append(f"--Supervisor--: {t.text}")
        return "\n".join(lines)

    # -- Processing loop -----------------------------------------------------

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.loop_interval_s)
            try:
                await self._tick()
            except Exception as exc:
                logger.error("Supervisor tick error: %s", exc, exc_info=True)

    async def _tick(self) -> None:
        unprocessed = self._history[self._processed_up_to:]
        if not unprocessed:
            return
        has_dialogue = any(t.role in ("user", "assistant") for t in unprocessed)
        if not has_dialogue:
            self._processed_up_to = len(self._history)
            return
        if time.monotonic() - self._last_turn_ts < self.quiet_s:
            return
        if self._processing:
            return
        self._processing = True
        try:
            await self._process()
        finally:
            self._processing = False

    async def _process(self) -> None:
        self._processed_up_to = len(self._history)
        history_text = self.format_history()
        logger.info(
            "Calling backend with %d turns: %s…",
            len(self._history),
            history_text[:120],
        )
        response = await self.process(history_text)
        normalized = response.strip() if response else ""
        if not normalized or normalized == _NO_ACTION:
            logger.debug("Backend: no action this turn")
            return
        logger.info("Backend response: %s", normalized[:120])
        self._push("supervisor", normalized)
        # Replace the voice agent's full context so the new
        # [Supervisor → assistant] turn is visible on the next LLM turn.
        await self.add_context(self.format_history(), append=False)
