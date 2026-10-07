"""The two halves of the digital twin, in stimm's terms.

- `TwinAgent`, a stimm `VoiceAgent`, is the live voice. It answers the end of every
  turn at once with a pre-recorded acknowledgement, covers a slow answer with a
  filler, and never states a fact of its own: it has no LLM.
- `AskSupervisor`, a stimm `Supervisor`, is the deep half. It puts each question
  to /ask, relays the evidence to the page, and has the voice say the grounded
  answer sentence by sentence through `Supervisor.speak()`.

Both run in the agent's job: `supervisor.attach(agent)` wires their protocols
in-process.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import itertools
import logging
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ask import AskClient, AskError, SentenceSplitter, history_for_ask, spoken

from livekit import rtc
from livekit.agents import llm, utils
from stimm import Supervisor, TranscriptMessage, VoiceAgent

logger = logging.getLogger("digital-twin")

Relay = Callable[[str, Any], Awaitable[None]]


@dataclass(frozen=True)
class Phrases:
    """The fixed things the twin says, in the session's language. All configuration."""

    acks: list[str]
    fillers: list[str]
    closing: str
    degraded: str
    apology: str


@dataclass(frozen=True)
class Clip:
    text: str
    path: Path | None  # None until synthesized: the text is then spoken live


class Clips:
    """Acknowledgements and fillers, synthesized once in the twin's voice, cached on disk.

    A file is named after the voice and the phrase, so changing either makes a new
    one. A deployer can ship the directory instead of letting the agent fill it.
    """

    def __init__(self, tts: Any, voice_key: str, phrases: Phrases, directory: Path) -> None:
        self._tts = tts
        self._voice_key = voice_key
        self._dir = directory
        self._texts = list(dict.fromkeys(phrases.acks + phrases.fillers))
        self._acks = _rotation(phrases.acks)
        self._fillers = _rotation(phrases.fillers)

    def path(self, text: str) -> Path:
        digest = hashlib.sha256(f"{self._voice_key}\n{text}".encode()).hexdigest()[:16]
        return self._dir / f"{digest}.wav"

    async def prepare(self) -> None:
        """Synthesize the clips not cached yet; a failure leaves that phrase to live TTS."""
        missing = [text for text in self._texts if not self.path(text).exists()]
        results = await asyncio.gather(*map(self._synthesize, missing), return_exceptions=True)
        for text, result in zip(missing, results):
            if isinstance(result, BaseException):
                logger.warning("could not synthesize clip %r: %s", text, result)

    async def _synthesize(self, text: str) -> None:
        async with self._tts.synthesize(text) as stream:
            frames = [event.frame async for event in stream]
        path = self.path(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{random.getrandbits(32):08x}.tmp")
        tmp.write_bytes(rtc.combine_audio_frames(frames).to_wav_bytes())
        tmp.replace(path)

    def next_ack(self) -> Clip:
        return self._clip(next(self._acks))

    def next_filler(self) -> Clip:
        return self._clip(next(self._fillers))

    def _clip(self, text: str) -> Clip:
        path = self.path(text)
        return Clip(text, path if path.exists() else None)


def _rotation(texts: list[str]) -> Iterator[str]:
    start = random.randrange(len(texts))
    return itertools.cycle(texts[start:] + texts[:start])


class TwinAgent(VoiceAgent):
    """The live voice: acknowledges at once, covers the wait, says only what /ask said."""

    def __init__(
        self, *, clips: Clips, closing: str, filler_delays: list[float], **components: Any
    ) -> None:
        # relay: this voice only says what its supervisor gives it. No fast LLM.
        super().__init__(mode="relay", **components)
        self._clips = clips
        self._closing = closing
        self._filler_delays = filler_delays
        self._fillers: list[asyncio.TimerHandle] = []
        self.closing = False

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        question = (new_message.text_content or "").strip()
        if self.closing or not question:
            return
        self.session.interrupt()  # drop what is left of the previous answer
        self._play(self._clips.next_ack())
        # /ask takes seconds to start; a filler at each delay keeps the silence short
        self._cancel_fillers()
        loop = asyncio.get_running_loop()
        self._fillers = [loop.call_later(delay, self._fill) for delay in self._filler_delays]
        await self.publish_transcript(question, partial=False)  # → AskSupervisor

    async def on_supervisor_speech(self, handle: Any) -> None:
        self._cancel_fillers()  # the answer has started: no more fillers
        if self.closing:
            handle.interrupt()  # nothing after the goodbye

    def close_call(self) -> None:
        """Say goodbye, and take no more questions."""
        self.closing = True
        self._cancel_fillers()
        self.session.interrupt()
        self.session.say(self._closing, allow_interruptions=False)

    def _fill(self) -> None:
        self._play(self._clips.next_filler())

    def _cancel_fillers(self) -> None:
        for timer in self._fillers:
            timer.cancel()
        self._fillers = []

    def _play(self, clip: Clip) -> None:
        if clip.path is None:
            self.session.say(clip.text, add_to_chat_ctx=False)
        else:
            audio = utils.audio.audio_frames_from_file(str(clip.path))
            self.session.say(clip.text, audio=audio, add_to_chat_ctx=False)


class AskSupervisor(Supervisor):
    """The deep half: /ask answers, the voice speaks, the page gets the evidence."""

    def __init__(self, *, ask: AskClient, lang: str, phrases: Phrases, relay: Relay) -> None:
        super().__init__()
        self._ask = ask
        self._lang = lang
        self._phrases = phrases
        self._relay = relay
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
