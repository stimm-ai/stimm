"""Configuration, dispatch metadata, call duration, settlement."""

import asyncio
import base64
import json
import logging
from types import SimpleNamespace

import aiohttp
import pytest
from agent import Config, leave_when_alone, limit_duration, session_info, settle, settle_payload
from ask import AskClient
from livekit.agents.metrics import AgentSessionUsage, STTModelUsage, TTSModelUsage
from twin import AskSupervisor, Phrases

from livekit import rtc


def voice_token(**claims: object) -> str:
    """Shaped like twin-public's: base64url(JSON payload).base64url(HMAC), unpadded."""
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{payload}.c2lnbmF0dXJlLW9mLXRoZS10d2lu"


TOKEN = voice_token(room="room-42", sid="s-1", lang="en", exp=1_790_000_000, aud="/ask")


def test_session_info_reads_the_token_from_the_dispatch_metadata() -> None:
    assert session_info(TOKEN, "fr") == (TOKEN, "en")
    assert session_info(voice_token(room="r", lang="de"), "fr")[1] == "fr"  # unknown language
    assert session_info("opaque.token-without-json", "en") == ("opaque.token-without-json", "en")
    assert session_info("", "fr") == (None, "fr")


def test_phrases_come_from_the_environment_with_defaults() -> None:
    cfg = Config.from_env(
        {
            "ACK_PHRASES_EN": "Hmm… | Right…",
            "APOLOGY_PHRASE": "Oops.",
            "CLOSING_PHRASE_FR": "Salut.",
        }
    )
    en, fr = cfg.phrases("en"), cfg.phrases("fr")
    assert en.acks == ["Hmm…", "Right…"]
    assert en.apology == fr.apology == "Oops."  # no _EN/_FR: the generic one
    assert fr.closing == "Salut."
    assert fr.acks and fr.fillers  # defaults


def test_settle_payload_from_session_usage() -> None:
    usage = AgentSessionUsage(
        model_usage=[
            STTModelUsage(provider="stt", model="m", audio_duration=61.26),
            TTSModelUsage(provider="tts", model="m", characters_count=420),
            TTSModelUsage(provider="tts", model="m2", characters_count=80),
        ]
    )
    assert settle_payload(usage, 150) == {"sttSeconds": 61.3, "ttsChars": 500, "agentMinutes": 2.5}


async def test_duration_guard_says_goodbye_then_hangs_up() -> None:
    events: list[str] = []
    agent = SimpleNamespace(close_call=lambda: events.append("goodbye"))
    session = SimpleNamespace(shutdown=lambda drain: events.append(f"hang up, drain={drain}"))

    guard = asyncio.ensure_future(limit_duration(agent, session, total=0.2, lead=0.1))  # type: ignore[arg-type]
    await asyncio.sleep(0.15)
    assert events == ["goodbye"]
    await guard
    assert events == ["goodbye", "hang up, drain=False"]


class FakeRoom:
    def __init__(self) -> None:
        self.remote_participants: dict[str, SimpleNamespace] = {}
        self._handlers: dict[str, list] = {}

    def on(self, event: str, callback) -> None:  # type: ignore[no-untyped-def]
        self._handlers.setdefault(event, []).append(callback)

    def join(
        self, identity: str, kind: int = rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD
    ) -> None:
        self.remote_participants[identity] = participant = SimpleNamespace(kind=kind)
        for callback in self._handlers.get("participant_connected", []):
            callback(participant)

    def leave(self, identity: str) -> None:
        participant = self.remote_participants.pop(identity)
        for callback in self._handlers.get("participant_disconnected", []):
            callback(participant)


async def test_leaves_once_the_visitor_has_been_gone_long_enough() -> None:
    room, left = FakeRoom(), asyncio.Event()
    room.join("visitor")
    room.join("other-agent", rtc.ParticipantKind.PARTICIPANT_KIND_AGENT)
    watch = asyncio.ensure_future(leave_when_alone(room, 0.2, left.set))

    await asyncio.sleep(0.02)
    room.leave("visitor")
    await asyncio.sleep(0.05)
    room.join("visitor")  # back in time: stay
    await asyncio.sleep(0.25)
    assert not left.is_set()

    room.leave("visitor")  # an agent alone does not count as a visitor
    await asyncio.wait_for(watch, 1)
    assert left.is_set()


class Answer:
    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *exc) -> None:  # type: ignore[no-untyped-def]
        pass


def serve(monkeypatch: pytest.MonkeyPatch, status: int | None) -> list[dict]:
    """Answer settle's POSTs with `status`, or fail to connect when None."""
    requests: list[dict] = []

    def post(self, url, **kwargs):  # type: ignore[no-untyped-def]
        requests.append({"url": url, **kwargs})
        if status is None:
            raise aiohttp.ClientConnectionError("connection refused")
        return Answer(status)

    monkeypatch.setattr(aiohttp.ClientSession, "post", post)
    return requests


async def test_settle_posts_the_usage_with_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = serve(monkeypatch, 204)
    await settle("https://twin.example/voice/settle", TOKEN, {"ttsChars": 12})
    assert requests[0]["json"] == {"ttsChars": 12}
    assert requests[0]["headers"] == {"Authorization": f"Voice {TOKEN}"}


async def test_settle_already_done_is_fine(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    serve(monkeypatch, 409)
    await settle("https://twin.example/voice/settle", TOKEN, {"ttsChars": 12})
    assert "settle" not in caplog.text


async def test_the_session_token_is_never_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    http = SimpleNamespace(post=lambda *args, **kwargs: Answer(401))
    ask = AskClient(http, "https://twin.example/ask", TOKEN)  # type: ignore[arg-type]
    phrases = Phrases(acks=["a"], fillers=["f"], closing="c", degraded="d", apology="Sorry.")

    async def relay(topic: str, payload: object) -> None:
        pass

    supervisor = AskSupervisor(ask=ask, lang="en", phrases=phrases, relay=relay)
    said = [s async for s in supervisor._sentences("Hello?", [])]
    serve(monkeypatch, 401)
    await settle("https://twin.example/voice/settle", TOKEN, {"sttSeconds": 1.0})
    serve(monkeypatch, None)
    await settle("https://twin.example/voice/settle", TOKEN, {"sttSeconds": 1.0})

    assert said == ["Sorry."]
    assert "/ask answered HTTP 401" in caplog.text
    assert "/voice/settle answered HTTP 401" in caplog.text
    assert "ClientConnectionError" in caplog.text
    assert TOKEN not in caplog.text and TOKEN not in repr(ask)
