"""The two halves of the twin, with fake /ask streams and a fake livekit session."""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from ask import AskClient, AskError, sse_events
from twin import AskSupervisor, Phrases, Timeline, TwinAgent

PHRASES = Phrases(closing="Bye.", degraded="On screen.", apology="Sorry.")
FIXTURE = Path(__file__).parent / "fixtures" / "ask_answer.sse"
LIST_FIXTURE = Path(__file__).parent / "fixtures" / "ask_list.sse"


def sse(*events: tuple[str, object]) -> list[bytes]:
    text = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return text.encode().splitlines(keepends=True)


class ScriptedAsk:
    """Replays /ask events after `delay`, or fails like the HTTP call would."""

    def __init__(self, events=(), error: Exception | None = None, gate=None, delay=0.0) -> None:  # type: ignore[no-untyped-def]
        self.events, self.error, self.gate, self.delay = list(events), error, gate, delay

    async def stream(self, question, lang, history):  # type: ignore[no-untyped-def]
        await asyncio.sleep(self.delay)
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


class FakeBridgeLLM:
    """Streams one scripted bridge per request, word by word, or fails."""

    def __init__(self, *lines: str, error: Exception | None = None) -> None:
        self.lines, self.error = list(lines), error

    def prewarm(self) -> None:
        pass

    def chat(self, *, chat_ctx):  # type: ignore[no-untyped-def]
        line = self.lines.pop(0) if self.lines else ""
        return _BridgeStream(line, self.error)


class _BridgeStream:
    def __init__(self, line: str, error: Exception | None) -> None:
        self.line, self.error = line, error

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *exc) -> None:  # type: ignore[no-untyped-def]
        pass

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        if self.error:
            raise self.error
        for word in self.line.split(" "):
            yield SimpleNamespace(delta=SimpleNamespace(content=word + " "))


class FakeHandle:
    def __init__(self) -> None:
        self.interrupted = False
        self.done = False
        self._finished = asyncio.Event()
        self._callbacks: list = []

    def add_done_callback(self, callback) -> None:  # type: ignore[no-untyped-def]
        self._callbacks.append(callback)

    def interrupt(self) -> None:
        self.finish(interrupted=True)

    def finish(self, *, interrupted: bool = False) -> None:
        if not self.done:
            self.interrupted, self.done = interrupted, True
            self._finished.set()
            for callback in self._callbacks:
                callback(self)

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._finished.wait().__await__()


class FakeSession:
    """Plays what is said like livekit: a line for 0.05 s, an answer as long as it streams.

    Its first audio is reported as livekit does, a moment after say().
    """

    def __init__(self) -> None:
        self.said: list[str] = []
        self.handles: list[FakeHandle] = []
        self.handlers: dict[str, list] = {}
        self.current_speech: FakeHandle | None = None

    def on(self, event: str, callback=None):  # type: ignore[no-untyped-def]
        if callback is None:
            return lambda f: self.on(event, f)
        self.handlers.setdefault(event, []).append(callback)
        return callback

    def interrupt(self) -> None:
        for handle in self.handles:
            handle.interrupt()

    def say(self, text, **_kwargs) -> FakeHandle:  # type: ignore[no-untyped-def]
        handle, index = FakeHandle(), len(self.said)
        self.handles.append(handle)
        self.said.append(text if isinstance(text, str) else "")
        loop = asyncio.get_running_loop()
        loop.call_soon(self._first_audio, handle)
        if isinstance(text, str):
            loop.call_later(0.05, handle.finish)
            return handle

        async def play() -> None:
            async for chunk in text:
                self.said[index] += chunk
            handle.finish()

        asyncio.ensure_future(play())
        return handle

    def _first_audio(self, handle: FakeHandle) -> None:
        self.current_speech = handle
        for callback in self.handlers.get("agent_state_changed", []):
            callback(SimpleNamespace(old_state="listening", new_state="speaking"))


class _TwinAgent(TwinAgent):
    session = None  # a plain attribute instead of livekit's property


async def twin(ask: object, bridge: FakeBridgeLLM | None = None) -> tuple[_TwinAgent, FakeSession]:
    timeline = Timeline()
    agent = _TwinAgent(
        closing="Bye.",
        timeline=timeline,
        bridge_llm=bridge or FakeBridgeLLM("Mmm, ce que j'ai construit…"),
    )
    agent.session = FakeSession()  # type: ignore[assignment]
    await agent.on_enter()
    supervisor = AskSupervisor(
        ask=ask, lang="en", phrases=PHRASES, relay=Relay(), timeline=timeline
    )  # type: ignore[arg-type]
    supervisor.attach(agent)
    agent.supervisor = supervisor  # type: ignore[attr-defined]
    return agent, agent.session  # type: ignore[return-value]


async def until(condition, timeout: float = 1.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        await asyncio.sleep(0.005)


QUESTION = SimpleNamespace(text_content="What did you build?")
ANSWER = [
    ("cite", {"n": 1}),
    ("delta", {"text": "I built Widget [1]. "}),
    ("done", {"mode": "answer"}),
]


async def test_the_bridge_then_the_answer_and_nothing_canned() -> None:
    agent, session = await twin(ScriptedAsk(ANSWER, delay=0.02))

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await until(lambda: len(session.handles) == 2 and session.handles[1].done)
    assert session.said == ["Mmm, ce que j'ai construit…", "I built Widget. "]


async def test_a_failing_bridge_llm_leaves_the_answer_alone() -> None:
    bridge = FakeBridgeLLM(error=ConnectionError("provider down"))
    agent, session = await twin(ScriptedAsk(ANSWER, delay=0.02), bridge)

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await until(lambda: session.handles and session.handles[0].done)
    assert session.said == ["I built Widget. "]  # no canned line in its place


async def test_nothing_is_said_after_the_goodbye() -> None:
    agent, session = await twin(ScriptedAsk(gate=asyncio.Event()))
    agent.close_call()

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await asyncio.sleep(0.05)
    assert session.said == ["Bye."]


class FakeResponse:
    status = 200

    def __init__(self, lines: list[bytes], delay: float = 0.0) -> None:
        self.closed = False
        self.content = self._lines(lines, delay)

    async def _lines(self, lines: list[bytes], delay: float):  # type: ignore[no-untyped-def]
        await asyncio.sleep(delay)
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
    response = FakeResponse(sse(("cite", {"n": 1}), ("delta", {"text": "First [1]. Sec"})), 0.02)
    http = FakeHttp(response)
    agent, session = await twin(AskClient(http, "https://twin.example/ask", "tok"))  # type: ignore[arg-type]

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await until(lambda: session.said[1:] == ["First. "])
    assert not response.closed
    session.handles[1].interrupt()  # the visitor speaks over the answer
    await asyncio.wait_for(agent.supervisor._answering, 1)  # type: ignore[attr-defined]

    assert response.closed
    assert http.headers["Authorization"] == "Voice tok"


async def test_barge_in_on_the_bridge_aborts_the_ask_request() -> None:
    response = FakeResponse(sse(("cite", {"n": 1}), ("delta", {"text": "First [1]. Sec"})), 0.1)
    agent, session = await twin(AskClient(FakeHttp(response), "https://twin.example/ask", None))  # type: ignore[arg-type]

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await until(lambda: session.said)
    session.handles[0].interrupt()  # the visitor speaks over the bridge
    await asyncio.wait_for(agent.supervisor._answering, 1)  # type: ignore[attr-defined]

    assert response.closed
    assert session.said == ["Mmm, ce que j'ai construit…"]


async def test_each_turn_logs_its_timeline_without_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="digital-twin")
    response = FakeResponse(
        sse(("cite", {"n": 1}), ("delta", {"text": "I built Widget [1]. "})), 0.02
    )
    ask = AskClient(FakeHttp(response), "https://twin.example/ask", "tok-SECRET")  # type: ignore[arg-type]
    agent, session = await twin(ask)

    await agent.on_user_turn_completed(None, QUESTION)  # type: ignore[arg-type]
    await until(lambda: len(session.handles) == 2 and session.current_speech is session.handles[1])

    steps = [r.getMessage() for r in caplog.records if r.name == "digital-twin"]
    expected = [
        r"turn 1 \+\d+ ms bridge text \(5 words\)",
        r"turn 1 \+\d+ ms bridge audio",
        r"turn 1 \+\d+ ms ask first delta",
        r"turn 1 \+\d+ ms first sentence \(15 chars\)",
        r"turn 1 \+\d+ ms answer audio",
    ]
    for pattern in expected:
        assert any(re.fullmatch(pattern, step) for step in steps), (pattern, steps)
    for content in ("What did you build", "construit", "Widget", "tok-SECRET"):
        assert content not in caplog.text
