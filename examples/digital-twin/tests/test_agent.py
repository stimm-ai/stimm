"""Configuration, dispatch metadata, call duration, settlement."""

import asyncio
import base64
import json
import logging
import threading
from types import SimpleNamespace

import agent
import aiohttp
import pytest
from agent import (
    DEFAULT_PHRASES,
    Config,
    character_instructions,
    leave_when_alone,
    limit_duration,
    make_bridge_llm,
    make_stt,
    make_tts,
    session_info,
    settle,
    settle_payload,
)
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
    cfg = Config.from_env({"APOLOGY_PHRASE": "Oops.", "CLOSING_PHRASE_FR": "Salut."})
    en, fr = cfg.phrases("en"), cfg.phrases("fr")
    assert en.apology == fr.apology == "Oops."  # no _EN/_FR: the generic one
    assert fr.closing == "Salut."
    assert en.closing == DEFAULT_PHRASES["en"]["CLOSING_PHRASE"]
    assert all(
        set(phrases) == {"CLOSING_PHRASE", "DEGRADED_PHRASE", "APOLOGY_PHRASE"}
        for phrases in DEFAULT_PHRASES.values()
    )  # no acknowledgement, no filler


FAST = {"temperature": 0.8, "max_completion_tokens": 24}


@pytest.mark.parametrize(
    ("env", "plugin", "built"),
    [
        (
            {},
            "mistralai",
            {"model": "ministral-8b-latest", "api_mode": "chat_completions", **FAST},
        ),
        (
            {
                "BRIDGE_PROVIDER": "openai-compatible",
                "BRIDGE_BASE_URL": "https://api.deepseek.com/v1",
                "BRIDGE_MODEL": "deepseek-flash",
                "BRIDGE_API_KEY": "k",
            },
            "openai",
            {
                "model": "deepseek-flash",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "k",
                "extra_body": {"thinking": {"type": "disabled"}},
                **FAST,
            },
        ),
    ],
)
def test_the_bridge_llm_is_fast_short_and_never_reasons(
    monkeypatch: pytest.MonkeyPatch, env: dict, plugin: str, built: dict
) -> None:
    module = pytest.importorskip(f"livekit.plugins.{plugin}")
    monkeypatch.setattr(module, "LLM", lambda **kwargs: kwargs)
    assert make_bridge_llm(Config.from_env(env)) == built


def test_a_livekit_inference_bridge_defaults_to_gemma(monkeypatch: pytest.MonkeyPatch) -> None:
    from livekit.agents import inference

    calls: list[tuple] = []
    monkeypatch.setattr(inference, "LLM", lambda model, **kwargs: calls.append((model, kwargs)))
    make_bridge_llm(Config.from_env({"BRIDGE_PROVIDER": "livekit"}))
    make_bridge_llm(Config.from_env({"BRIDGE_PROVIDER": "livekit", "BRIDGE_MODEL": "x/y"}))
    assert calls == [
        ("google/gemma-4-31b-it", {"extra_kwargs": FAST}),
        ("x/y", {"extra_kwargs": FAST}),
    ]


def test_an_openai_compatible_bridge_needs_its_url_model_and_key() -> None:
    env = {"BRIDGE_PROVIDER": "openai-compatible", "BRIDGE_MODEL": "m", "BRIDGE_API_KEY": "k"}
    with pytest.raises(ValueError, match="BRIDGE_BASE_URL"):
        make_bridge_llm(Config.from_env(env))


def test_settle_payload_from_session_usage() -> None:
    usage = AgentSessionUsage(
        model_usage=[
            STTModelUsage(provider="stt", model="m", audio_duration=61.26),
            TTSModelUsage(provider="tts", model="m", characters_count=420),
            TTSModelUsage(provider="tts", model="m2", characters_count=80),
        ]
    )
    assert settle_payload(usage, 150) == {"sttSeconds": 61.3, "ttsChars": 500, "agentMinutes": 2.5}


def test_settle_payload_is_clamped_to_one_session() -> None:
    usage = AgentSessionUsage(
        model_usage=[
            STTModelUsage(provider="stt", model="m", audio_duration=312.0),
            TTSModelUsage(provider="tts", model="m", characters_count=5600),
        ]
    )
    assert settle_payload(usage, 306) == {"sttSeconds": 300, "ttsChars": 5000, "agentMinutes": 5}


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
    phrases = Phrases(closing="c", degraded="d", apology="Sorry.")

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


def test_selected_providers_build_off_the_main_thread(tmp_path, monkeypatch) -> None:
    """A job runs in a thread in dev mode: the plugins must already be registered."""
    pytest.importorskip("livekit.plugins.mistralai")
    monkeypatch.setenv("MISTRAL_API_KEY", "test")
    sample = tmp_path / "ref.wav"
    sample.write_bytes(b"RIFF....WAVE")
    cfg = Config.from_env({"MISTRAL_API_KEY": "k", "TTS_REF_AUDIO_FR": str(sample)})
    errors: list[BaseException] = []

    def build() -> None:
        try:
            make_tts(cfg, "fr")
            make_stt(cfg, "fr", vad=None)
            make_bridge_llm(cfg)
        except BaseException as e:  # noqa: BLE001 - surfaced by the assert below
            errors.append(e)

    thread = threading.Thread(target=build)
    thread.start()
    thread.join()
    assert errors == []


CHARACTER = [
    {
        "id": "character:registre",
        "kind": "interaction",
        "label": "Registre",
        "statement": "Le registre suit celui du visiteur.",
        "url": "u",
    },
    {
        "id": "character:lexique",
        "kind": "interaction",
        "label": "Lexique",
        "statement": "Lexique parlé, exclamations courtes.",
        "calibration": ["Ah ça c'est cool"],
        "url": "u",
    },
    {"id": "character:gpu", "kind": "preference", "statement": "Aime les GPU.", "valence": "like"},
]


class Character(Answer):
    def raise_for_status(self) -> None:
        if self.status >= 300:
            raise aiohttp.ClientResponseError(None, (), status=self.status)  # type: ignore[arg-type]

    async def json(self) -> dict:
        return {"character": CHARACTER}


def serve_character(monkeypatch: pytest.MonkeyPatch, status: int | None) -> list[dict]:
    """Answer the character GETs with `status`, or fail to connect when None."""
    monkeypatch.setattr(agent, "_characters", {})
    requests: list[dict] = []

    def get(self, url, **kwargs):  # type: ignore[no-untyped-def]
        requests.append({"url": url, **kwargs})
        if status is None:
            raise aiohttp.ClientConnectionError("connection refused")
        return Character(status)

    monkeypatch.setattr(aiohttp.ClientSession, "get", get)
    return requests


async def test_the_bridge_reads_how_the_person_sounds(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = serve_character(monkeypatch, 200)
    text = await character_instructions("https://twin.example/character", "fr")

    assert requests[0]["params"] == {"lang": "fr"}
    assert "Le registre suit celui du visiteur." in text
    assert "Aime les GPU." not in text  # a preference is a fact for /ask, not a tone
    assert "every rule above still holds" in text  # the bridge's own rules come first
    # A sample sets a register; the instruction is never to say it.
    assert "(register: «Ah ça c'est cool»)" in text
    assert "never say them" in text

    assert await character_instructions("https://twin.example/character", "fr") == text
    assert len(requests) == 1  # once per worker process
    await character_instructions("https://twin.example/character", "en")
    assert requests[1]["params"] == {"lang": "en"}


@pytest.mark.parametrize("status", [None, 404])
async def test_without_a_character_the_twin_still_bridges(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, status: int | None
) -> None:
    requests = serve_character(monkeypatch, status)
    assert await character_instructions("https://twin.example/character", "fr") == ""
    assert "no character" in caplog.text
    await character_instructions("https://twin.example/character", "fr")
    assert len(requests) == 2  # a failure is not cached: the next session tries again
    assert await character_instructions("", "fr") == ""  # CHARACTER_URL= turns it off


def test_the_cloned_voice_is_more_expressive_at_its_own_speed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elevenlabs = pytest.importorskip("livekit.plugins.elevenlabs")
    monkeypatch.setattr(elevenlabs, "TTS", lambda **kwargs: kwargs)
    env = {"TTS_PROVIDER": "elevenlabs", "TTS_MODEL": "eleven_v4_turbo", "TTS_VOICE": "v"}

    built = make_tts(Config.from_env(env), "fr")
    assert built["voice_settings"] == elevenlabs.VoiceSettings(
        stability=0.3, similarity_boost=0.75, style=0.2
    )  # no speed: the voice's own
    tuned = make_tts(Config.from_env({**env, "TTS_STABILITY": "0.5", "TTS_SPEED": "1.1"}), "fr")
    assert tuned["voice_settings"].stability == 0.5
    assert tuned["voice_settings"].speed == 1.1
