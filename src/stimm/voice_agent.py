"""VoiceAgent — extends livekit Agent with dual-agent orchestration.

The VoiceAgent handles the audio pipeline (VAD → STT → fast LLM → TTS)
and communicates with the Supervisor via the Stimm protocol over
LiveKit data channels.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
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
    SpeechEndedMessage,
    SpeechMessage,
    StateMessage,
    StimmProtocol,
    TranscriptMessage,
)
from stimm.styles import (
    ConversationStyle,
    StyleName,
    bridge_messages,
    resolve_style,
    write_bridge,
)

logger = logging.getLogger("stimm.voice_agent")


class VoiceAgent(Agent):
    """A voice agent that participates in the Stimm dual-agent architecture.

    Extends the standard livekit-agents ``Agent`` with:
    - Publishing transcripts and state to the supervisor via data channel
    - Accepting instructions from the supervisor and merging them into context
    - Saying supervisor-provided text verbatim, streamed, as one utterance
    - Bridging the wait for the supervisor's answer in a conversation style (relay mode)
    - Pre-TTS text buffering for smoother speech delivery
    - Three operating modes: autonomous, relay, and hybrid

    Args:
        stt: Speech-to-text plugin instance.
        tts: Text-to-speech plugin instance.
        vad: Voice activity detection plugin instance.
        fast_llm: The fast LLM for voice responses.
        instructions: Base system instructions for the voice agent. With a
            ``style``, the bridge LLM reads them too, e.g. which language to speak.
        buffering_level: Pre-TTS buffering aggressiveness.
        mode: Initial operating mode.
        supervisor_instructions_window: How many recent supervisor instructions
            to keep in the LLM context window.
        style: In relay mode, how the voice bridges the wait for the supervisor's
            answer: ``"direct"``, ``"transparent"``, or a
            :class:`~stimm.ConversationStyle`. ``None`` (default): in silence.
        bridge_llm: The livekit LLM that writes each bridge: fast, no reasoning,
            temperature around 0.8, about 24 output tokens. Required with ``style``.
        bridge_timeout: Seconds the bridge LLM has to start a bridge, and as long
            again to finish it; past that, the voice says nothing.
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
        style: StyleName | ConversationStyle | None = None,
        bridge_llm: Any = None,
        bridge_timeout: float = 1.0,
    ) -> None:
        if (style is None) != (bridge_llm is None):
            raise ValueError("style and bridge_llm go together: the LLM writes the bridges")
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
        self._deferred_context_retry_task: asyncio.Task[None] | None = None
        self._reply_trigger_inflight = False
        self._last_context_trigger_fingerprint = ""
        self._last_context_trigger_ts = 0.0
        self._context_trigger_cooldown_s = 8.0
        self._deferred_context_retry_interval_s = 0.5
        self._speeches: dict[str, _SpeechStream] = {}
        self._ended_speeches: set[str] = set()
        self._style = resolve_style(style) if style is not None else None
        self._bridge_llm = bridge_llm
        self._bridge_timeout = bridge_timeout
        self._bridge: asyncio.Task[None] | None = None  # writes and says the turn's bridge
        self._bridge_handle: Any = None  # the turn's bridge, once said
        self._bridges: deque[str] = deque(maxlen=5)  # the last ones said, to vary from
        # What was said, for the bridge LLM. An answer is its _SpeechStream: it grows.
        self._conversation: deque[tuple[str, str | _SpeechStream]] = deque(maxlen=6)

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
        self._protocol.on_speech(self._handle_speech)
        session = self._current_session()
        if session is not None:

            @session.on("agent_state_changed")
            def _on_agent_state_changed(ev) -> None:  # type: ignore[no-untyped-def]
                if getattr(ev, "new_state", None) in {"idle", "listening"}:
                    asyncio.ensure_future(self._flush_deferred_context_reply_trigger())

            @session.on("user_state_changed")
            def _on_user_state_changed(ev) -> None:  # type: ignore[no-untyped-def]
                asyncio.ensure_future(self._flush_deferred_context_reply_trigger())
                if getattr(ev, "new_state", None) == "speaking":
                    self._drop_unsaid_bridge()  # the user goes on: too late for it

        if self._bridge_llm is not None:
            self._bridge_llm.prewarm()
        logger.info("VoiceAgent entered room, mode=%s", self._mode)

    async def on_exit(self) -> None:
        """Called when the agent leaves the room."""
        if self._deferred_context_retry_task and not self._deferred_context_retry_task.done():
            self._deferred_context_retry_task.cancel()
            self._deferred_context_retry_task = None
        self._drop_unsaid_bridge()
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
                self._drop_unsaid_bridge()  # the answer is first: never a bridge after it
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

    # -- Supervisor-provided speech ------------------------------------------

    async def _handle_speech(self, msg: SpeechMessage) -> None:
        """Say supervisor-provided text verbatim: one utterance per ``speech_id``."""
        stream = self._speeches.get(msg.speech_id)
        session = self._current_session()
        new = stream is None
        if new:
            if msg.speech_id in self._ended_speeches:
                return  # the tail of an utterance that was already cut off
            if session is None or (msg.final and not msg.text):
                await self._end_speech(msg.speech_id, interrupted=session is None)
                return
            stream = self._speeches[msg.speech_id] = _SpeechStream()
        if msg.text:
            stream.push(msg.text)
        if msg.final:
            stream.close()
        if not new:
            return
        if await self._bridge_cut_off():  # the user cut the turn off: its answer too
            await self._end_speech(msg.speech_id, interrupted=True)
            return
        try:
            handle = session.say(stream)
        except RuntimeError:  # e.g. the session is closing and schedules no new speech
            logger.warning("Cannot say supervisor speech %s", msg.speech_id, exc_info=True)
            await self._end_speech(msg.speech_id, interrupted=True)
            return
        self._conversation.append(("You", stream))
        handle.add_done_callback(
            lambda h: asyncio.ensure_future(self._end_speech(msg.speech_id, h.interrupted))
        )
        await self.on_supervisor_speech(handle)

    async def _end_speech(self, speech_id: str, interrupted: bool) -> None:
        stream = self._speeches.pop(speech_id, None)
        if stream is not None:
            stream.close()
        self._ended_speeches.add(speech_id)
        await self._protocol.send_speech_ended(
            SpeechEndedMessage(speech_id=speech_id, interrupted=interrupted)
        )

    async def on_supervisor_speech(self, handle: Any) -> None:
        """Called when the voice agent starts saying supervisor-provided text.

        ``handle`` is the livekit ``SpeechHandle`` of the utterance. Override to
        react, e.g. to drop a filler that was covering the supervisor's latency.
        """

    # -- Bridging the wait for the answer (relay mode with a style) ---------

    async def on_user_turn_completed(self, turn_ctx: Any, new_message: Any) -> None:
        """Called by livekit when a user turn ends: in relay mode with a style, bridge it.

        The bridge LLM writes one line in the style, said as soon as it is written.
        A subclass that overrides this calls ``super()`` to keep the bridge.
        """
        question = (new_message.text_content or "").strip()
        self._drop_unsaid_bridge()
        self._bridge_handle = None
        if self._style is None or not question:
            return
        self._conversation.append(("User", question))
        if self._mode != "relay":
            return
        system, user = bridge_messages(
            self._style,
            instructions=self._base_instructions,
            conversation=[(speaker, str(said)) for speaker, said in self._conversation],
            recent=self._bridges,
        )
        self._bridge = asyncio.ensure_future(self._say_bridge(system, user))

    async def on_bridge(self, text: str, handle: Any) -> None:
        """Called when the voice starts saying a bridge, *text*, it wrote in its style.

        ``handle`` is the livekit ``SpeechHandle`` of the bridge. The supervisor's
        answer is said once it has played, or not at all if the user cut it off.
        """

    async def _say_bridge(self, system: str, user: str) -> None:
        text = await write_bridge(self._bridge_llm, system, user, timeout=self._bridge_timeout)
        session = self._current_session()
        if not text or session is None:
            return  # silence, never a canned line
        try:
            handle = session.say(text)
        except RuntimeError:  # e.g. the session is closing and schedules no new speech
            return
        self._bridge_handle = handle
        self._bridges.append(text)
        self._conversation.append(("You", text))
        await self.on_bridge(text, handle)

    def _drop_unsaid_bridge(self) -> None:
        """Cancel the turn's bridge if it is still being written; one being said plays on."""
        if self._bridge is not None and self._bridge_handle is None:
            self._bridge.cancel()

    async def _bridge_cut_off(self) -> bool:
        """Let the turn's bridge play before the answer. True if the user cut it off.

        A bridge still being written is dropped: the answer is first.
        """
        handle = self._bridge_handle
        if handle is None:
            self._drop_unsaid_bridge()
            return False
        await handle
        return handle.interrupted

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
        latest = self._latest_context_trigger_fingerprint()
        if self._is_context_trigger_duplicate(latest):
            logger.debug("Skipping duplicate supervisor context trigger")
            return
        if self._can_trigger_context_reply_now(session):
            self._mark_context_trigger(latest)
            await self._generate_reply_from_current_context()
            return
        self._deferred_context_reply_trigger = True
        self._ensure_deferred_context_retry()
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
        latest = self._latest_context_trigger_fingerprint()
        if self._is_context_trigger_duplicate(latest):
            self._deferred_context_reply_trigger = False
            logger.debug("Dropping deferred duplicate supervisor context trigger")
            return
        if not self._can_trigger_context_reply_now(session):
            return
        self._deferred_context_reply_trigger = False
        self._mark_context_trigger(latest)
        await self._generate_reply_from_current_context()

    def _ensure_deferred_context_retry(self) -> None:
        if self._deferred_context_retry_task and not self._deferred_context_retry_task.done():
            return
        self._deferred_context_retry_task = asyncio.ensure_future(
            self._deferred_context_retry_loop()
        )

    async def _deferred_context_retry_loop(self) -> None:
        while self._deferred_context_reply_trigger:
            await asyncio.sleep(self._deferred_context_retry_interval_s)
            await self._flush_deferred_context_reply_trigger()

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

    def _latest_context_trigger_fingerprint(self) -> str:
        return self._supervisor_context[-1].strip() if self._supervisor_context else ""

    def _is_context_trigger_duplicate(self, latest: str) -> bool:
        """Prevent duplicate trigger bursts for the same latest supervisor context."""
        if not latest:
            return False
        now = time.monotonic()
        if (
            latest == self._last_context_trigger_fingerprint
            and now - self._last_context_trigger_ts < self._context_trigger_cooldown_s
        ):
            return True

        return False

    def _mark_context_trigger(self, latest: str) -> None:
        if not latest:
            return
        self._last_context_trigger_fingerprint = latest
        self._last_context_trigger_ts = time.monotonic()

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
            "- Use supervisor-provided content as the factual source of truth.\n"
            "- You may use recent conversation history for fluency/continuity, but do not "
            "introduce new facts not present in supervisor context.\n"
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


class _SpeechStream:
    """The chunks of one supervisor utterance, as ``session.say()`` reads them."""

    def __init__(self) -> None:
        self._chunks: asyncio.Queue[str | None] = asyncio.Queue()
        self._text = ""

    def __str__(self) -> str:
        """The text pushed so far."""
        return self._text

    def push(self, text: str) -> None:
        self._text += text
        self._chunks.put_nowait(text)

    def close(self) -> None:
        self._chunks.put_nowait(None)

    def __aiter__(self) -> _SpeechStream:
        return self

    async def __anext__(self) -> str:
        text = await self._chunks.get()
        if text is None:
            raise StopAsyncIteration
        return text


def _now_ms() -> int:
    """Current time in milliseconds."""
    return int(time.time() * 1000)
