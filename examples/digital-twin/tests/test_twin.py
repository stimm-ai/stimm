"""The two halves of the twin, with fake /ask streams and a fake livekit session."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from ask import AskClient, AskError, sse_events
from twin import AskSupervisor, Clip, Clips, Phrases, TwinAgent

from livekit import rtc

PHRASES = Phrases(
    acks=["Ack."], fillers=["Filler."], closing="Bye.", degraded="On screen.", apology="Sorry."
)
FIXTURE = Path(__file__).parent / "fixtures" / "ask_answer.sse"
LIST_FIXTURE = Path(__file__).parent / "fixtures" / "ask_list.sse"


def sse(*events: tuple[str, object]) -> list[bytes]:
    text = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return text.encode().splitlines(keepends=True)


class ScriptedAsk:
    """Replays /ask events, or fails like the HTTP call would."""

    def __init__(self, events=(), error: Exception | None = None, gate=None) -> None:  # type: ignore[no-untyped-def]
        self.events, self.error, self.gate = list(events), error, gate

    async def stream(self, question, lang, history):  # type: ignore[no-untyped-def]
        if self.error:
            raise self.error
        for event in self.events:
            yield event
        if self.gate:
            await self.gate.wait()


class Relay:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []

    async def __call__(self, topic: str, payload: object) -> None:
        self.sent.append((topic, payload))


async def sentences(ask: ScriptedAsk) -> tuple[list[str], list[tuple[str, object]]]:
    relay = Relay()
    supervisor = AskSupervisor(ask=ask, lang="en", phrases=PHRASES, relay=relay)  # type: ignore[arg-type]
    said = [s async for s in supervisor._sentences("What did you build?", [])]
    return said, relay.sent


async def _lines(path: Path):  # type: ignore[no-untyped-def]
    for line in path.read_bytes().splitlines(keepends=True):
        yield line


async def test_answer_is_said_sentence_by_sentence_and_evidence_relayed() -> None:
    events = [event async for event in sse_events(_lines(FIXTURE))]
    said, sent = await sentences(ScriptedAsk(events))

    assert said == [
        "I joined Example as CTO in 2019.",
        "The team grew from 3 to 12 people in two years.",
        "We shipped Widget 2.5 in March 2021.",
    ]
    assert [topic for topic, _ in sent] == ["twin.cite", "twin.cite", "twin.citations", "twin.done"]
    assert sent[0][1] == events[1][1]  # cite payloads go through untouched
    assert sent[-1][1] == {
        "mode": "answer",
        "question": "What did you build?",
        "answer": "I joined Example as CTO in 2019 [1]. The team grew from 3 to 12 people"
        " in two years [1][2]. We shipped Widget 2.5 in March 2021 [2].",
    }


async def test_bold_and_list_items_are_spoken_plain_and_relayed_raw() -> None:
    events = [event async for event in sse_events(_lines(LIST_FIXTURE))]
    said, sent = await sentences(ScriptedAsk(events))

    assert said == [
        "I built two tools:",
        "Widget, a screen recorder.",
        "Gadget, a code generator.",
        "Both are free.",
    ]
    assert sent[-1][1]["answer"] == (  # type: ignore[index]
        "I built **two tools** [1]:\n- **Widget**, a screen recorder [1]\n"
        "- **Gadget**, a code generator [2]\n\nBoth are free [2]."
    )


async def test_no_source_is_said_as_given() -> None:
    said, sent = await sentences(
        ScriptedAsk(
            [("delta", {"text": "No source states this."}), ("done", {"mode": "no_source"})]
        )
    )
    assert said == ["No source states this."]
    assert sent[-1][1]["mode"] == "no_source"  # type: ignore[index]


async def test_degraded_says_the_fixed_sentence_and_relays_results() -> None:
    results = [{"id": "project:widget", "excerpt": "Widget 2.5 shipped."}]
    said, sent = await sentences(
        ScriptedAsk(
            [
                ("delta", {"text": "Here is what my sources say:"}),
                ("done", {"mode": "degraded", "reason": "provider", "results": results}),
            ]
        )
    )
    assert said == ["On screen."]
    assert sent[0] == ("twin.results", results)
    assert sent[1][1]["mode"] == "degraded" and sent[1][1]["reason"] == "provider"  # type: ignore[index]


async def test_stream_error_drops_the_half_sentence_and_apologizes() -> None:
    said, sent = await sentences(
        ScriptedAsk(
            [
                ("cite", {"n": 1, "id": "a"}),
                ("delta", {"text": "First sentence [1]. Half a sent"}),
                ("citations", [{"n": 1, "id": "a"}]),
                ("error", {"code": "provider_error", "message": "The answer was cut off."}),
            ]
        )
    )
    assert said == ["First sentence.", "Sorry."]
    assert sent[-1][1]["mode"] == "error"  # type: ignore[index]


async def test_http_failure_apologizes() -> None:
    said, _ = await sentences(ScriptedAsk(error=AskError(503)))
    assert said == ["Sorry."]


# -- the live voice ----------------------------------------------------------


class FakeHandle:
    def __init__(self) -> None:
        self.interrupted = False
        self.done = False
        self._callbacks: list = []

    def add_done_callback(self, callback) -> None:  # type: ignore[no-untyped-def]
        self._callbacks.append(callback)

    def interrupt(self) -> None:
        self.finish(interrupted=True)

    def finish(self, *, interrupted: bool = False) -> None:
        if not self.done:
            self.interrupted, self.done = interrupted, True
            for callback in self._callbacks:
                callback(self)


class FakeSession:
    """Records clips; plays a streamed answer by reading it, like say() would."""

    def __init__(self) -> None:
        self.clips: list[str] = []
        self.answers: list[list[str]] = []
        self.answer_handles: list[FakeHandle] = []

    def on(self, _event: str):  # type: ignore[no-untyped-def]
        return lambda f: f

    def interrupt(self) -> None:
        for handle in self.answer_handles:
            handle.interrupt()

    def say(self, text, **_kwargs) -> FakeHandle:  # type: ignore[no-untyped-def]
        handle = FakeHandle()
        if isinstance(text, str):
            self.clips.append(text)
            return handle
        spoken: list[str] = []
        self.answers.append(spoken)
        self.answer_handles.append(handle)

        async def play() -> None:
            async for chunk in text:
                spoken.append(chunk)
            handle.finish()

        asyncio.ensure_future(play())
        return handle


class FakeClips:
    def next_ack(self) -> Clip:
        return Clip("Ack.", None)

    def next_filler(self) -> Clip:
        return Clip("Filler.", None)


class _TwinAgent(TwinAgent):
    session = None  # a plain attribute instead of livekit's property


async def twin(ask: object) -> tuple[_TwinAgent, FakeSession]:
    agent = _TwinAgent(clips=FakeClips(), closing="Bye.", filler_delays=[0.05, 0.15])  # type: ignore[arg-type]
    agent.session = FakeSession()  # type: ignore[assignment]
    await agent.on_enter()
    supervisor = AskSupervisor(ask=ask, lang="en", phrases=PHRASES, relay=Relay())  # type: ignore[arg-type]
    supervisor.attach(agent)
    agent.supervisor = supervisor  # type: ignore[attr-defined]
    return agent, agent.session  # type: ignore[return-value]


QUESTION = SimpleNamespace(text_content="What did you build?")


async def test_ack_at_once_then_fillers_while_ask_is_slow() -> None:
    agent, session = await twin(ScriptedAsk(gate=asyncio.Event()))

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    assert session.clips == ["Ack."]
    await asyncio.sleep(0.1)
    assert session.clips == ["Ack.", "Filler."]
    await asyncio.sleep(0.1)
    assert session.clips == ["Ack.", "Filler.", "Filler."]


async def test_no_filler_once_the_answer_has_started() -> None:
    ask = ScriptedAsk(
        [("cite", {"n": 1}), ("delta", {"text": "Quick one [1]. "})], gate=asyncio.Event()
    )
    agent, session = await twin(ask)

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await asyncio.sleep(0.25)
    assert session.clips == ["Ack."]
    assert session.answers == [["Quick one. "]]


async def test_nothing_is_said_after_the_goodbye() -> None:
    agent, session = await twin(ScriptedAsk(gate=asyncio.Event()))
    agent.close_call()

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    assert session.clips == ["Bye."]


class FakeResponse:
    status = 200

    def __init__(self, lines: list[bytes]) -> None:
        self.closed = False
        self.content = self._lines(lines)

    async def _lines(self, lines: list[bytes]):  # type: ignore[no-untyped-def]
        for line in lines:
            yield line
        await asyncio.Event().wait()  # /ask still thinking about the rest


class FakeHttp:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.headers: dict[str, str] = {}

    def post(self, url, *, json, headers, timeout):  # type: ignore[no-untyped-def]
        self.headers = headers
        return self

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, *exc) -> None:  # type: ignore[no-untyped-def]
        self.response.closed = True


async def test_barge_in_stops_the_voice_and_aborts_the_ask_request() -> None:
    response = FakeResponse(sse(("cite", {"n": 1}), ("delta", {"text": "First [1]. Sec"})))
    http = FakeHttp(response)
    agent, session = await twin(AskClient(http, "https://twin.example/ask", "tok"))  # type: ignore[arg-type]

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await asyncio.sleep(0.02)
    assert session.answers == [["First. "]] and not response.closed
    session.answer_handles[0].interrupt()  # the visitor speaks over the answer
    await asyncio.wait_for(agent.supervisor._answering, 1)  # type: ignore[attr-defined]

    assert response.closed
    assert http.headers["Authorization"] == "Voice tok"


class FakeTTS:
    def __init__(self) -> None:
        self.synthesized: list[str] = []

    def synthesize(self, text: str):  # type: ignore[no-untyped-def]
        if text == "Broken.":
            raise RuntimeError("TTS down")
        self.synthesized.append(text)
        frame = rtc.AudioFrame.create(sample_rate=24000, num_channels=1, samples_per_channel=240)
        return _Stream([SimpleNamespace(frame=frame)])


class _Stream:
    def __init__(self, events: list) -> None:  # type: ignore[type-arg]
        self._events = events

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *exc) -> None:  # type: ignore[no-untyped-def]
        pass

    def __aiter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __anext__(self):  # type: ignore[no-untyped-def]
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


async def test_clips_are_synthesized_once_then_read_from_disk(tmp_path: Path) -> None:
    phrases = Phrases(["Ack.", "Broken."], ["Filler."], "Bye.", "On screen.", "Sorry.")
    tts = FakeTTS()
    await Clips(tts, "voice-a", phrases, tmp_path).prepare()
    assert sorted(tts.synthesized) == ["Ack.", "Filler."]

    again = FakeTTS()
    clips = Clips(again, "voice-a", phrases, tmp_path)
    await clips.prepare()
    assert again.synthesized == []  # cached
    assert {clips.next_ack().text, clips.next_ack().text} == {"Ack.", "Broken."}  # rotation
    assert clips.next_filler().path is not None
    assert Clips(again, "voice-a", phrases, tmp_path)._clip("Broken.").path is None  # live TTS

    other_voice = FakeTTS()
    await Clips(other_voice, "voice-b", phrases, tmp_path).prepare()
    assert sorted(other_voice.synthesized) == ["Ack.", "Filler."]
