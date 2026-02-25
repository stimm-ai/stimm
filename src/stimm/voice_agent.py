"""VoiceAgent — extends livekit Agent with dual-agent orchestration.

The VoiceAgent handles the audio pipeline (VAD → STT → fast LLM → TTS)
and communicates with the Supervisor via the Stimm protocol over
LiveKit data channels.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from livekit.agents import Agent

from stimm.buffering import BufferingLevel, TextBufferingStrategy
from stimm.protocol import (
    AgentMode,
    BeforeSpeakMessage,
    ContextMessage,
    InstructionMessage,
    ModeMessage,
    OverrideMessage,
    StateMessage,
    StimmProtocol,
    TranscriptMessage,
)

logger = logging.getLogger("stimm.voice_agent")


class VoiceAgent(Agent):
    """A voice agent that participates in the Stimm dual-agent architecture.

    Extends the standard livekit-agents ``Agent`` with:
    - Publishing transcripts and state to the supervisor via data channel
    - Accepting instructions from the supervisor and merging them into context
    - Pre-TTS text buffering for smoother speech delivery
    - Three operating modes: autonomous, relay, and hybrid

    Args:
        stt: Speech-to-text plugin instance.
        tts: Text-to-speech plugin instance.
        vad: Voice activity detection plugin instance.
        fast_llm: The fast LLM for voice responses.
        instructions: Base system instructions for the voice agent.
        buffering_level: Pre-TTS buffering aggressiveness.
        mode: Initial operating mode.
        supervisor_instructions_window: How many recent supervisor instructions
            to keep in the LLM context window.
    """

    def __init__(
        self,
        *,
        stt: Any = None,
        tts: Any = None,
        vad: Any = None,
        fast_llm: Any = None,
        instructions: str = "",
        buffering_level: BufferingLevel = "MEDIUM",
        mode: AgentMode = "hybrid",
        supervisor_instructions_window: int = 5,
    ) -> None:
        super().__init__(
            stt=stt,
            tts=tts,
            vad=vad,
            llm=fast_llm,
            instructions=instructions,
        )
        self._protocol = StimmProtocol()
        self._buffering = TextBufferingStrategy(buffering_level)
        self._mode: AgentMode = mode
        self._base_instructions = instructions
        self._pending_instructions: list[InstructionMessage] = []
        self._supervisor_context: list[str] = []
        self._instructions_window = supervisor_instructions_window
        self._turn_counter = 0
        self._deferred_context_reply_trigger = False
        self._reply_trigger_inflight = False
        self._last_context_trigger_fingerprint = ""
        self._last_context_trigger_ts = 0.0
        self._context_trigger_cooldown_s = 8.0

    @property
    def protocol(self) -> StimmProtocol:
        """Access the underlying protocol handler."""
        return self._protocol

    @property
    def mode(self) -> AgentMode:
        """Current operating mode."""
        return self._mode

    # -- Lifecycle -----------------------------------------------------------

    async def on_enter(self) -> None:
        """Called when the agent joins the room. Sets up data channel listeners."""
        self._protocol.on_instruction(self._handle_instruction)
        self._protocol.on_context(self._handle_context)
        self._protocol.on_mode(self._handle_mode_change)
        self._protocol.on_override(self._handle_override)
        session = self._current_session()
        if session is not None:

            @session.on("agent_state_changed")
            def _on_agent_state_changed(ev) -> None:  # type: ignore[no-untyped-def]
                if getattr(ev, "new_state", None) in {"idle", "listening"}:
                    asyncio.ensure_future(self._flush_deferred_context_reply_trigger())

            @session.on("user_state_changed")
            def _on_user_state_changed(_ev) -> None:  # type: ignore[no-untyped-def]
                asyncio.ensure_future(self._flush_deferred_context_reply_trigger())

        logger.info("VoiceAgent entered room, mode=%s", self._mode)

    async def on_exit(self) -> None:
        """Called when the agent leaves the room."""
        logger.info("VoiceAgent exiting room")

    # -- Transcript publishing -----------------------------------------------

    async def publish_transcript(
        self,
        text: str,
        *,
        partial: bool = True,
        confidence: float = 1.0,
    ) -> None:
        """Publish a transcript message to the supervisor.

        Call this from STT callbacks to forward speech transcriptions.
        """
        await self._protocol.send_transcript(
            TranscriptMessage(
                partial=partial,
                text=text,
                timestamp=_now_ms(),
                confidence=confidence,
            )
        )

    async def publish_state(self, state: str) -> None:
        """Publish a state change (listening / thinking / speaking)."""
        await self._protocol.send_state(
            StateMessage(state=state, timestamp=_now_ms())  # type: ignore[arg-type]
        )

    async def publish_before_speak(self, text: str) -> str:
        """Publish a before_speak message and return the (possibly overridden) text.

        The supervisor may respond with an override, but this implementation
        does not wait — it fires and returns immediately. Override handling
        is done asynchronously via ``_handle_override``.
        """
        turn_id = f"t_{self._turn_counter:04d}"
        self._turn_counter += 1
        await self._protocol.send_before_speak(BeforeSpeakMessage(text=text, turn_id=turn_id))
        return text

    # -- Instruction handling ------------------------------------------------

    async def _handle_instruction(self, msg: InstructionMessage) -> None:
        """Process an instruction from the supervisor."""
        logger.debug("Received instruction: priority=%s, speak=%s", msg.priority, msg.speak)

        if self._mode == "relay" and msg.speak:
            # In relay mode, speak exactly what the supervisor says.
            session = self._current_session()
            if session is not None:
                await session.say(msg.text)
        elif self._mode == "hybrid":
            # In hybrid mode, incorporate into next LLM context.
            self._pending_instructions.append(msg)
            session = self._current_session()
            if msg.priority == "interrupt" and session is not None:
                # Interrupt current speech and speak the instruction immediately.
                await session.interrupt()
                await session.say(msg.text)
        elif self._mode == "autonomous":
            # In autonomous mode, still store instructions for optional use.
            self._pending_instructions.append(msg)

        await self._sync_instructions()

    async def _handle_context(self, msg: ContextMessage) -> None:
        """Process context from the supervisor."""
        if msg.append:
            self._supervisor_context.append(msg.text)
        else:
            self._supervisor_context = [msg.text]
        logger.debug("Context updated: %d entries", len(self._supervisor_context))
        await self._sync_instructions()
        await self._trigger_context_reply_if_idle_or_defer()

    async def _handle_mode_change(self, msg: ModeMessage) -> None:
        """Process a mode switch command."""
        old_mode = self._mode
        self._mode = msg.mode
        logger.info("Mode changed: %s → %s", old_mode, self._mode)

    async def _handle_override(self, msg: OverrideMessage) -> None:
        """Process an override command — cancel pending speech and replace."""
        logger.debug("Override for turn %s", msg.turn_id)
        session = self._current_session()
        if session is not None:
            await session.interrupt()
            await session.say(msg.replacement)

    async def _sync_instructions(self) -> None:
        """Push merged supervisor context/instructions into the active LLM prompt."""
        merged = self.build_context_with_instructions()
        await self.update_instructions(merged)

    def _current_session(self):  # type: ignore[no-untyped-def]
        """Best-effort access to AgentSession (not available in unit tests/offline contexts)."""
        try:
            return self.session
        except RuntimeError:
            return None

    async def _trigger_context_reply_if_idle_or_defer(self) -> None:
        """If a new supervisor context arrives, speak it now when idle, or defer until idle."""
        session = self._current_session()
        if session is None:
            return
        if self._is_context_trigger_duplicate():
            logger.debug("Skipping duplicate supervisor context trigger")
            return
        if self._can_trigger_context_reply_now(session):
            await self._generate_reply_from_current_context()
            return
        self._deferred_context_reply_trigger = True
        logger.debug(
            "Deferred supervisor context trigger (agent_state=%s user_state=%s)",
            getattr(session, "agent_state", None),
            getattr(session, "user_state", None),
        )

    async def _flush_deferred_context_reply_trigger(self) -> None:
        if not self._deferred_context_reply_trigger:
            return
        session = self._current_session()
        if session is None:
            return
        if self._is_context_trigger_duplicate():
            self._deferred_context_reply_trigger = False
            logger.debug("Dropping deferred duplicate supervisor context trigger")
            return
        if not self._can_trigger_context_reply_now(session):
            return
        self._deferred_context_reply_trigger = False
        await self._generate_reply_from_current_context()

    async def _generate_reply_from_current_context(self) -> None:
        """Force a fast-LLM turn from the currently injected context (idle trigger path)."""
        if self._reply_trigger_inflight:
            logger.info("[VOICE_AGENT] generate_reply SKIPPED (inflight)")
            return
        session = self._current_session()
        if session is None:
            return
        logger.info(
            "[VOICE_AGENT] generate_reply TRIGGERED by supervisor context "
            "(agent_state=%s current_speech=%s)",
            getattr(session, "agent_state", "?"),
            getattr(session, "current_speech", None) is not None,
        )
        self._reply_trigger_inflight = True
        try:
            # Use an explicit relay instruction so delayed supervisor context
            # is spoken even when no fresh user utterance arrives.
            session.generate_reply(
                input_modality="text",
                instructions=(
                    "A new `--Supervisor--` instruction/context has just been injected. "
                    "Relay its latest relevant content to the user now."
                ),
            )
        except Exception:
            logger.exception("Failed to trigger idle reply from supervisor context")
        finally:
            self._reply_trigger_inflight = False

    def _can_trigger_context_reply_now(self, session: Any) -> bool:
        """Whether it's safe to force a context-driven reply right now."""
        agent_state = getattr(session, "agent_state", None)
        user_state = getattr(session, "user_state", None)
        # Never trigger when the agent is already thinking or speaking.
        if agent_state not in {"idle", "listening"}:
            return False
        # Never trigger when the user is currently speaking.
        if user_state == "speaking":
            return False
        # Never trigger when a SpeechHandle is already in flight — avoids a
        # double-TTS race where the fast LLM already started generating a
        # reply but agent_state has not yet transitioned to "thinking".
        current_speech = getattr(session, "current_speech", None)
        if current_speech is not None:
            return False
        return True

    def _is_context_trigger_duplicate(self) -> bool:
        """Prevent duplicate trigger bursts for the same latest supervisor context."""
        latest = self._supervisor_context[-1].strip() if self._supervisor_context else ""
        if not latest:
            return False
        now = time.monotonic()
        if (
            latest == self._last_context_trigger_fingerprint
            and now - self._last_context_trigger_ts < self._context_trigger_cooldown_s
        ):
            return True
        self._last_context_trigger_fingerprint = latest
        self._last_context_trigger_ts = now
        return False

    # -- Context building ----------------------------------------------------

    def build_context_with_instructions(self, base_instructions: str | None = None) -> str:
        """Merge supervisor instructions into the voice agent's LLM prompt.

        Called before each LLM invocation to incorporate any pending
        instructions and context from the supervisor.

        Args:
            base_instructions: Override the default base instructions.
                If ``None``, uses the instructions from ``__init__``.

        Returns:
            The merged instructions string.
        """
        base = base_instructions or self._base_instructions
        if not self._pending_instructions and not self._supervisor_context:
            return base

        parts = [base]

        parts.append(
            "\n\nSupervisor source-of-truth policy:\n"
            "- Use supervisor-provided content as the only factual source.\n"
            "- Ignore your own prior assistant outputs as factual evidence.\n"
            "- If supervisor context is missing/insufficient, say you need to "
            "check with your supervisor."
        )

        if self._supervisor_context:
            latest_ctx = self._supervisor_context[-1]
            parts.append(f"\n\nLatest context from supervisor (authoritative):\n{latest_ctx}")

        if self._pending_instructions:
            window = self._pending_instructions[-self._instructions_window :]
            instruction_texts = [i.text for i in window]
            parts.append(
                "\n\nSupervisor instructions (incorporate naturally):\n"
                + "\n".join(instruction_texts)
            )
            self._pending_instructions.clear()

        return "\n".join(parts)

    # -- Buffering -----------------------------------------------------------

    def buffer_token(self, token: str) -> str | None:
        """Feed an LLM token through the pre-TTS buffer.

        Returns text ready for TTS, or ``None`` if still accumulating.
        """
        return self._buffering.feed(token)

    def flush_buffer(self) -> str | None:
        """Flush any remaining buffered text (call at end of LLM stream)."""
        return self._buffering.flush()


def _now_ms() -> int:
    """Current time in milliseconds."""
    return int(time.time() * 1000)
