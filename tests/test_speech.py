"""Supervisor-provided speech: Supervisor.speak() through VoiceAgent, in-process."""

import asyncio

import pytest

from stimm.protocol import SpeechMessage
from stimm.supervisor import Supervisor
from stimm.voice_agent import VoiceAgent, _SpeechStream


class _FakeHandle:
    def __init__(self) -> None:
        self.interrupted = False
        self.done = False
        self._callbacks: list = []

    def add_done_callback(self, callback) -> None:  # type: ignore[no-untyped-def]
        self._callbacks.append(callback)

    def finish(self, *, interrupted: bool = False) -> None:
        if self.done:
            return
        self.interrupted, self.done = interrupted, True
        for callback in self._callbacks:
            callback(self)


class _FakeSession:
    """Plays each say() stream by reading it; the utterance ends with its stream."""

    def __init__(self) -> None:
        self.utterances: list[list[str]] = []
        self.handles: list[_FakeHandle] = []

    def on(self, _event: str):  # type: ignore[no-untyped-def]
        return lambda f: f

    def say(self, text) -> _FakeHandle:  # type: ignore[no-untyped-def]
        handle, spoken = _FakeHandle(), []
        self.handles.append(handle)
        self.utterances.append(spoken)

        async def play() -> None:
            async for chunk in text:
                spoken.append(chunk)
            handle.finish()

        asyncio.ensure_future(play())
        return handle


async def _pair() -> tuple[Supervisor, VoiceAgent, _FakeSession]:
    agent, session = VoiceAgent(instructions="test", mode="relay"), _FakeSession()
    agent._current_session = lambda: session  # type: ignore[method-assign]
    await agent.on_enter()
    supervisor = Supervisor()
    supervisor.attach(agent)
    return supervisor, agent, session


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_streamed_text_is_one_utterance_spoken_in_order() -> None:
    supervisor, agent, session = await _pair()
    started: list[object] = []

    async def on_supervisor_speech(handle: object) -> None:
        started.append(handle)

    agent.on_supervisor_speech = on_supervisor_speech  # type: ignore[method-assign]

    async def answer():  # type: ignore[no-untyped-def]
        yield "First sentence. "
        yield "Second sentence."

    assert await supervisor.speak(answer()) is True
    assert session.utterances == [["First sentence. ", "Second sentence."]]
    assert started == session.handles


@pytest.mark.asyncio
async def test_plain_string_is_spoken() -> None:
    supervisor, _, session = await _pair()

    assert await supervisor.speak("Just this.") is True
    assert session.utterances == [["Just this."]]


@pytest.mark.asyncio
async def test_interruption_stops_speak_and_closes_the_source() -> None:
    supervisor, _, session = await _pair()
    gate, closed = asyncio.Event(), asyncio.Event()

    async def answer():  # type: ignore[no-untyped-def]
        try:
            yield "First sentence. "
            await gate.wait()  # e.g. an HTTP stream waiting for its next event
            yield "Never spoken."
        finally:
            closed.set()

    speaking = asyncio.ensure_future(supervisor.speak(answer()))
    await _settle()
    session.handles[0].finish(interrupted=True)  # the user barges in

    assert await asyncio.wait_for(speaking, 1) is False
    assert closed.is_set()
    assert session.utterances == [["First sentence. "]]


@pytest.mark.asyncio
async def test_late_chunks_of_an_ended_utterance_are_dropped() -> None:
    _, agent, session = await _pair()

    await agent._handle_speech(SpeechMessage(speech_id="s_1", text="Hello. "))
    session.handles[0].finish(interrupted=True)
    await _settle()
    await agent._handle_speech(SpeechMessage(speech_id="s_1", text="Late."))

    assert len(session.handles) == 1


@pytest.mark.asyncio
async def test_an_utterance_stays_ended_for_every_reader() -> None:
    stream = _SpeechStream()
    stream.push("Hello. ")
    stream.close()

    assert [chunk async for chunk in stream] == ["Hello. "]
    # livekit tees it between the TTS and the transcript: the second reader asks again
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(stream.__anext__(), 1)


@pytest.mark.asyncio
async def test_speak_before_attach_raises() -> None:
    with pytest.raises(RuntimeError):
        await Supervisor().speak("Hello.")
