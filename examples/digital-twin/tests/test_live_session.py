"""The twin in a real livekit AgentSession: only the TTS, the speaker and /ask are fakes."""

import asyncio
import contextlib
import time

from livekit.agents.voice.io import AudioOutput, AudioOutputCapabilities
from test_twin import PHRASES, FakeBridgeLLM, Relay, until
from twin import AskSupervisor, Timeline, TwinAgent

from livekit import rtc
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, AgentSession, llm, tts

BRIDGE = "Mmm, ce que j'ai construit…"


class FakeTTS(tts.TTS):
    """Silence, 5 ms a character. Not streaming, like Voxtral's: livekit then says a
    sentence once the next one starts, or once the text ends."""

    def __init__(self) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False), sample_rate=16000, num_channels=1
        )
        self.texts: list[str] = []

    def synthesize(self, text, *, conn_options=DEFAULT_API_CONNECT_OPTIONS):  # type: ignore[no-untyped-def]
        self.texts.append(text.strip())
        return _Silence(tts=self, input_text=text, conn_options=conn_options)


class _Silence(tts.ChunkedStream):
    async def _run(self, output_emitter) -> None:  # type: ignore[no-untyped-def]
        output_emitter.initialize(
            request_id="silence", sample_rate=16000, num_channels=1, mime_type="audio/pcm"
        )
        output_emitter.push(b"\0\0" * 80 * len(self._input_text))


class Speaker(AudioOutput):
    """Plays in real time: a segment ends as long after its first frame as it lasts."""

    def __init__(self) -> None:
        super().__init__(label="speaker", capabilities=AudioOutputCapabilities(pause=False))
        self._start, self._pushed = 0.0, 0.0
        self._end: asyncio.TimerHandle | None = None

    async def capture_frame(self, frame: rtc.AudioFrame) -> None:
        await super().capture_frame(frame)
        if not self._pushed:
            self._start = time.time()
            self.on_playback_started(created_at=self._start)
        self._pushed += frame.duration

    def flush(self) -> None:
        super().flush()
        if self._pushed:
            left = self._pushed - (time.time() - self._start)
            self._end = asyncio.get_running_loop().call_later(max(left, 0), self._played, False)

    def clear_buffer(self) -> None:
        if self._pushed:
            if self._end:
                self._end.cancel()
            self._played(True)

    def _played(self, interrupted: bool) -> None:
        position = min(self._pushed, time.time() - self._start)
        self._pushed, self._end = 0.0, None
        self.on_playback_finished(playback_position=position, interrupted=interrupted)


class LiveAsk:
    """Replays /ask events; an asyncio.Event in the script waits until the test sets it."""

    def __init__(self, *script: object) -> None:
        self.script, self.closed = script, False

    async def stream(self, question, lang, history):  # type: ignore[no-untyped-def]
        try:
            for step in self.script:
                if isinstance(step, asyncio.Event):
                    await step.wait()
                else:
                    yield step
        finally:
            self.closed = True  # aclose(): the request is aborted


@contextlib.asynccontextmanager
async def live_twin(ask: LiveAsk):  # type: ignore[no-untyped-def]
    voice, timeline = FakeTTS(), Timeline()
    agent = TwinAgent(
        closing="Bye.", timeline=timeline, tts=voice, bridge_llm=FakeBridgeLLM(BRIDGE)
    )
    supervisor = AskSupervisor(ask=ask, lang="en", phrases=PHRASES, relay=Relay())  # type: ignore[arg-type]
    supervisor.attach(agent)
    session = AgentSession()
    await session.start(agent)
    session.output.audio = Speaker()
    try:
        # livekit's own call at the end of a user turn
        question = llm.ChatMessage(role="user", content=["What did you build?"])
        await agent.on_user_turn_completed(llm.ChatContext.empty(), question)
        await until(lambda: session.agent_state == "speaking")  # the bridge plays
        yield agent, supervisor, voice
    finally:
        await session.aclose()


def answer_so_far(agent: TwinAgent) -> str:
    return "".join(str(stream) for stream in agent._speeches.values())


async def test_an_answer_ready_while_the_bridge_plays_is_said_after_it() -> None:
    playing = asyncio.Event()
    ask = LiveAsk(playing, ("delta", {"text": "Sources:"}), ("done", {"mode": "degraded"}))
    async with live_twin(ask) as (agent, supervisor, voice):
        playing.set()
        await until(lambda: agent._speeches)  # the whole answer is in
        assert not agent._bridge_speech.done()

        await asyncio.wait_for(supervisor._answering, 2)  # said to the end
        assert voice.texts == [BRIDGE, "On screen."]


async def test_sentences_streamed_during_the_bridge_and_after_are_all_said() -> None:
    playing, bridged = asyncio.Event(), asyncio.Event()
    ask = LiveAsk(
        playing,
        ("cite", {"n": 1}),
        ("delta", {"text": "I built Widget [1]. It records "}),
        ("delta", {"text": "screens [1]. "}),
        bridged,
        ("delta", {"text": "Both are free [1]."}),
        ("done", {"mode": "answer"}),
    )
    async with live_twin(ask) as (agent, supervisor, voice):
        playing.set()
        await until(lambda: "screens" in answer_so_far(agent))
        assert not agent._bridge_speech.done()
        await until(agent._bridge_speech.done)
        bridged.set()

        await asyncio.wait_for(supervisor._answering, 2)
        assert voice.texts[0] == BRIDGE  # livekit groups short sentences: compare the text
        assert " ".join(voice.texts[1:]) == "I built Widget. It records screens. Both are free."


async def test_a_barge_in_on_the_bridge_drops_the_answer_and_aborts_ask() -> None:
    playing = asyncio.Event()
    ask = LiveAsk(playing, ("cite", {"n": 1}), ("delta", {"text": "First [1]. "}), asyncio.Event())
    async with live_twin(ask) as (agent, supervisor, voice):
        playing.set()
        await until(lambda: agent._speeches)  # the answer waits for the bridge
        assert not ask.closed
        agent.session.interrupt()  # the visitor speaks over the bridge

        await asyncio.wait_for(supervisor._answering, 2)
        assert ask.closed
        assert voice.texts == [BRIDGE]
