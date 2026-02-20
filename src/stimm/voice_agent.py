"""VoiceAgent — extends livekit Agent with dual-agent orchestration.

The VoiceAgent handles the audio pipeline (VAD → STT → fast LLM → TTS)
and communicates with the Supervisor via the Stimm protocol over
LiveKit data channels.
"""

from __future__ import annotations

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
            if self.session:
                await self.session.say(msg.text)
        elif self._mode == "hybrid":
            # In hybrid mode, incorporate into next LLM context.
            self._pending_instructions.append(msg)
            if msg.priority == "interrupt" and self.session:
                # Interrupt current speech and speak the instruction immediately.
                await self.session.interrupt()
                await self.session.say(msg.text)
        elif self._mode == "autonomous":
            # In autonomous mode, still store instructions for optional use.
            self._pending_instructions.append(msg)

    async def _handle_context(self, msg: ContextMessage) -> None:
        """Process context from the supervisor."""
        if msg.append:
            self._supervisor_context.append(msg.text)
        else:
            self._supervisor_context = [msg.text]
        logger.debug("Context updated: %d entries", len(self._supervisor_context))

    async def _handle_mode_change(self, msg: ModeMessage) -> None:
        """Process a mode switch command."""
        old_mode = self._mode
        self._mode = msg.mode
        logger.info("Mode changed: %s → %s", old_mode, self._mode)

    async def _handle_override(self, msg: OverrideMessage) -> None:
        """Process an override command — cancel pending speech and replace."""
        logger.debug("Override for turn %s", msg.turn_id)
        if self.session:
            await self.session.interrupt()
            await self.session.say(msg.replacement)

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

        if self._supervisor_context:
            ctx = "\n".join(self._supervisor_context)
            parts.append(f"\n\nContext from supervisor:\n{ctx}")

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
