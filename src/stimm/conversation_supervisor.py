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
        async def process(self, history: str, system_prompt: str | None) -> str:
            response = await my_llm.generate(history, system_prompt=system_prompt)
            return response or self.NO_ACTION

    supervisor = MyBackendSupervisor()
    await supervisor.connect(livekit_url, token)
    supervisor.start_loop()
"""

from __future__ import annotations

import asyncio
import json
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


class _BackendDecision:
    __slots__ = ("action", "text", "reason")

    def __init__(self, action: str, text: str = "", reason: str | None = None) -> None:
        self.action = action  # "NO_ACTION" | "TRIGGER"
        self.text = text
        self.reason = reason


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

    #: Backend-facing policy (agnostic) for deciding whether to intervene.
    #: Integrations may prepend this to the backend input.
    DEFAULT_AGNOSTIC_DECISION_PREAMBLE: str = (
        "You are a background supervisor deciding whether to intervene.\n"
        "Return a single JSON object only:\n"
        '{"action":"NO_ACTION"|"TRIGGER","text":"<string>","reason":"<short debug reason>"}\n'
        "Decision rules:\n"
        "1. If latest user content is small talk/chitchat and the fast agent can handle it: action=NO_ACTION.\n"
        "2. Focus on the latest user request and the latest assistant reply to that request.\n"
        "3. If the latest assistant reply is missing, incorrect, contradictory, or does not include the key answer: action=TRIGGER.\n"
        "4. Use action=NO_ACTION only when the latest assistant reply is already correct and sufficient.\n"
        "5. A correct answer that appears earlier in history does NOT justify NO_ACTION if the latest assistant reply is still wrong.\n"
        "6. Never invent tool/system results you did not verify.\n"
        "If action=NO_ACTION, keep text empty.\n"
    )

    def __init__(
        self,
        *,
        quiet_s: float = 2.5,
        loop_interval_s: float = 1.5,
        max_turns: int = 40,
        backend_input_preamble: str | None = None,
    ) -> None:
        super().__init__()
        self.quiet_s = quiet_s
        self.loop_interval_s = loop_interval_s
        self.max_turns = max_turns
        self.backend_input_preamble = backend_input_preamble

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
    async def process(self, history: str, system_prompt: str | None) -> str:
        """Send the conversation history to the reasoning backend.

        Args:
            history: Formatted conversation history produced by
                :meth:`format_history`.
            system_prompt: Optional backend system prompt that defines the
                supervisor policy/output contract.

        Returns:
            The backend's response text, or :attr:`NO_ACTION` to skip
            context injection for this turn.
        """

    # -- Stimm event handlers ------------------------------------------------

    async def on_transcript(self, msg: TranscriptMessage) -> None:
        if msg.partial:
            return
        text = msg.text.strip()
        if not text:
            return
        # Deduplicate consecutive identical final transcripts.
        last_user = next(
            (t for t in reversed(self._history) if t.role == "user"), None
        )
        if last_user is not None and last_user.text.strip() == text:
            logger.info("[SUPERVISOR] DEDUP DROP user transcript=%r", text[:80])
            return
        logger.info("[SUPERVISOR] ACCEPT user transcript=%r (history_len=%d)", text[:80], len(self._history))
        self._push("user", text)

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

    def get_backend_system_prompt(self) -> str | None:
        """Return backend system prompt when configured."""
        preamble = (self.backend_input_preamble or "").strip()
        return preamble or None

    def parse_backend_decision(self, raw: str) -> _BackendDecision:
        """Parse structured backend output (strict JSON contract)."""
        normalized = raw.strip() if raw else ""
        if not normalized:
            return _BackendDecision("NO_ACTION", "", "empty_backend_output")

        if normalized.startswith("{") and normalized.endswith("}"):
            try:
                parsed = json.loads(normalized)
                action = parsed.get("action")
                text = parsed.get("text")
                reason = parsed.get("reason")
                if action == "NO_ACTION":
                    return _BackendDecision(
                        "NO_ACTION",
                        "",
                        reason if isinstance(reason, str) else None,
                    )
                if action == "TRIGGER":
                    clean_text = text.strip() if isinstance(text, str) else ""
                    if not clean_text:
                        return _BackendDecision("NO_ACTION", "", "empty_trigger_text")
                    return _BackendDecision(
                        "TRIGGER",
                        clean_text,
                        reason if isinstance(reason, str) else None,
                    )
                return _BackendDecision("NO_ACTION", "", "invalid_action")
            except Exception:
                return _BackendDecision("NO_ACTION", "", "invalid_json")

        return _BackendDecision("NO_ACTION", "", "non_json_output")

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
        system_prompt = self.get_backend_system_prompt()
        response = await self.process(history_text, system_prompt)
        decision = self.parse_backend_decision(response)
        if decision.action != "TRIGGER":
            if decision.reason:
                logger.debug("Backend: no action (%s)", decision.reason)
            else:
                logger.debug("Backend: no action this turn")
            return
        logger.info("Backend response: %s", decision.text[:120])
        self._push("supervisor", decision.text)
        # Replace the voice agent's full context so the new
        # [Supervisor → assistant] turn is visible on the next LLM turn.
        await self.add_context(self.format_history(), append=False)
