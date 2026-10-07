"""The two halves of the digital twin, in stimm's terms.

- `TwinAgent`, a stimm `VoiceAgent` in relay mode, is the live voice. At the end of
  every turn it says a short bridge in stimm's `direct` style, written for the turn
  by a fast LLM, and never states a fact of its own.
- `AskSupervisor`, a stimm `Supervisor`, is the deep half. It puts each question
  to /ask, relays the evidence to the page, and has the voice say the grounded
  answer sentence by sentence through `Supervisor.speak()`, right after the bridge.

Both run in the agent's job: `supervisor.attach(agent)` wires their protocols
in-process.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ask import AskClient, AskError, SentenceSplitter, history_for_ask, spoken

from livekit.agents import llm
from stimm import Supervisor, TranscriptMessage, VoiceAgent

logger = logging.getLogger("digital-twin")

Relay = Callable[[str, Any], Awaitable[None]]


@dataclass(frozen=True)
class Phrases:
    """The fixed things the twin says, in the session's language. All configuration."""

    closing: str
    degraded: str
    apology: str


class Timeline:
    """Logs the steps of each turn in ms from the end of the user's turn: sizes, never text."""

    def __init__(self) -> None:
        self._turn, self._start = 0, time.perf_counter()

    def start(self) -> None:
        self._turn += 1
        self._start = time.perf_counter()

    def mark(self, step: str, size: str = "") -> None:
        ms = (time.perf_counter() - self._start) * 1000
        logger.info("turn %d +%.0f ms %s%s", self._turn, ms, step, f" ({size})" if size else "")


class TwinAgent(VoiceAgent):
    """The live voice: bridges each turn in its own words, says only what /ask said."""

    def __init__(self, *, closing: str, timeline: Timeline, **components: Any) -> None:
        # relay: this voice says what its supervisor gives it, and its own bridges.
        super().__init__(mode="relay", style="direct", **components)
        self._closing = closing
        self._timeline = timeline
        self._bridge_speech: Any = None
        self._answer_speech: Any = None
        self.closing = False

    async def on_enter(self) -> None:
        await super().on_enter()
        self.session.on("agent_state_changed", self._on_agent_state_changed)

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        question = (new_message.text_content or "").strip()
        if self.closing or not question:
            return
        self._timeline.start()
        self.session.interrupt()  # drop what is left of the previous answer
        await super().on_user_turn_completed(turn_ctx, new_message)  # the bridge
        await self.publish_transcript(question, partial=False)  # → AskSupervisor

    async def on_bridge(self, text: str, handle: Any) -> None:
        self._timeline.mark("bridge text", f"{len(text.split())} words")
        self._bridge_speech = handle
        if self.closing:
            handle.interrupt()  # nothing after the goodbye

    async def on_supervisor_speech(self, handle: Any) -> None:
        self._answer_speech = handle
        if self.closing:
            handle.interrupt()  # nothing after the goodbye

    def close_call(self) -> None:
        """Say goodbye, and take no more questions."""
        self.closing = True
        self.session.interrupt()
        self.session.say(self._closing, allow_interruptions=False)

    def _on_agent_state_changed(self, ev: Any) -> None:
        if ev.new_state != "speaking":  # the first audio of an utterance is out
            return
        speech = self.session.current_speech
        if speech is not None and speech is self._bridge_speech:
            self._timeline.mark("bridge audio")
        elif speech is not None and speech is self._answer_speech:
            self._timeline.mark("answer audio")


class AskSupervisor(Supervisor):
    """The deep half: /ask answers, the voice speaks, the page gets the evidence."""

    def __init__(
        self,
        *,
        ask: AskClient,
        lang: str,
        phrases: Phrases,
        relay: Relay,
        timeline: Timeline | None = None,
    ) -> None:
        super().__init__()
        self._ask = ask
        self._lang = lang
        self._phrases = phrases
        self._relay = relay
        self._timeline = timeline or Timeline()
        self._turns: list[tuple[str, str]] = []
        self._answering: asyncio.Task[None] | None = None

    async def on_transcript(self, msg: TranscriptMessage) -> None:
        if msg.partial or not msg.text.strip():
            return
        if self._answering is not None:
            self._answering.cancel()  # a new question replaces the one in flight
        self._answering = asyncio.ensure_future(self.answer(msg.text.strip()))

    async def answer(self, question: str) -> None:
        history = history_for_ask(self._turns)
        self._turns.append(("user", question))
        said: list[str] = []

        async def sentences() -> AsyncIterator[str]:
            async with contextlib.aclosing(self._sentences(question, history)) as source:
                async for sentence in source:
                    if not said:
                        self._timeline.mark("first sentence", f"{len(sentence)} chars")
                    said.append(sentence)
                    yield sentence + " "  # the TTS and the subtitles read one text

        try:
            await self.speak(sentences())
        finally:
            if said:
                self._turns.append(("assistant", " ".join(said)))

    async def _sentences(self, question: str, history: list[dict[str, str]]) -> AsyncIterator[str]:
        """What to say for one question, sentence by sentence; relays the evidence."""
        splitter, cited, text = SentenceSplitter(), False, ""
        try:
            stream = self._ask.stream(question, self._lang, history)
            async with contextlib.aclosing(stream) as events:  # closing it aborts the request
                async for event, data in events:
                    if event == "cite":
                        cited = True
                        await self._relay("twin.cite", data)
                    elif event == "delta":
                        if not text:
                            self._timeline.mark("ask first delta")
                        text += data["text"]
                        # Answer text always comes after a cite. Text without one is
                        # no_source, a refusal or the degraded preamble: wait for done.
                        if cited:
                            for sentence in splitter.push(data["text"]):
                                yield sentence
                    elif event == "citations":
                        await self._relay("twin.citations", data)
                    elif event == "done":
                        mode = data.get("mode")
                        if mode == "degraded":
                            await self._relay("twin.results", data.get("results", []))
                        extra = {key: data[key] for key in ("reason", "truncated") if key in data}
                        done = {"mode": mode, "question": question, "answer": text, **extra}
                        await self._relay("twin.done", done)
                        if mode == "degraded":  # the sources are on screen, not read out
                            rest = self._phrases.degraded
                        elif cited:
                            rest = splitter.flush()
                        else:  # no_source or the off-topic refusal: said as given
                            rest = spoken(text)
                        if rest:
                            yield rest
                        return
                    elif event == "error":  # cut off after some text: drop the half sentence
                        break
        except AskError as exc:
            logger.warning("%s", exc)
        except Exception as exc:  # network, timeout, malformed stream: apologize, carry on
            logger.warning("/ask failed: %s", type(exc).__name__)
        await self._relay("twin.done", {"mode": "error", "question": question, "answer": text})
        yield self._phrases.apology
