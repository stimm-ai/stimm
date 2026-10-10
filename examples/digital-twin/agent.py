"""Digital twin voice agent: a visitor talks, /ask answers, a cloned voice speaks.

Run locally:  lk agent console (or python agent.py console), lk agent dev
Deploy:       lk agent create, then lk agent deploy (see README.md)

Everything about the person and the deployment is configuration: environment
variables, and the token and language that the backend puts in the dispatch.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import importlib
import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
from ask import AskClient
from twin import AskSupervisor, Phrases, Timeline, TwinAgent

from livekit import rtc
from livekit.agents import AgentServer, AgentSession, JobContext, JobProcess, cli, metrics, room_io
from livekit.plugins import silero

# LiveKit registers a plugin when it is first imported, and only on the main thread: a job
# runs in a thread in dev mode. Every installed provider loads here, so make_stt, make_tts
# and make_bridge_llm never import one inside a job; a missing one fails there, with its name.
for _plugin in ("mistralai", "elevenlabs", "deepgram", "openai"):
    with contextlib.suppress(ModuleNotFoundError):
        importlib.import_module(f"livekit.plugins.{_plugin}")

logger = logging.getLogger("digital-twin")

DEFAULT_PHRASES: dict[str, dict[str, str]] = {
    "fr": {
        "CLOSING_PHRASE": (
            "Nous arrivons au bout du temps prévu pour cet appel. "
            "Merci de votre visite, vous pouvez continuer par écrit."
        ),
        "DEGRADED_PHRASE": "Je n'ai pas pu formuler de réponse ; les sources sont à l'écran.",
        "APOLOGY_PHRASE": "Désolé, je n'ai pas pu terminer ma réponse.",
    },
    "en": {
        "CLOSING_PHRASE": (
            "We're almost out of time for this call. "
            "Thanks for stopping by, you can carry on in writing."
        ),
        "DEGRADED_PHRASE": "I couldn't phrase an answer; the sources are on screen.",
        "APOLOGY_PHRASE": "Sorry, I couldn't finish my answer.",
    },
}
LANGUAGES = {"fr": "French", "en": "English"}


@dataclass(frozen=True)
class Config:
    ask_url: str
    settle_url: str
    default_lang: str
    stt_provider: str
    stt_model: str
    keyterms: list[str]
    tts_provider: str
    tts_model: str
    tts_stability: float
    tts_similarity: float
    tts_style: float
    tts_speed: float | None
    character_url: str
    bridge_provider: str
    bridge_model: str
    bridge_base_url: str
    max_session: float
    closing_lead: float
    visitor_gone: float
    interruption_mode: str
    interruption_min: float
    env: Mapping[str, str]

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Config:
        return cls(
            ask_url=env.get("ASK_URL", "https://mcp.etiennelescot.fr/ask"),
            settle_url=env.get("SETTLE_URL", "https://mcp.etiennelescot.fr/voice/settle"),
            default_lang=env.get("TWIN_LANG", "fr"),
            stt_provider=env.get("STT_PROVIDER", "mistral"),
            stt_model=env.get("STT_MODEL", ""),
            keyterms=[t.strip() for t in env.get("STT_KEYTERMS", "").split(",") if t.strip()],
            tts_provider=env.get("TTS_PROVIDER", "mistral"),
            tts_model=env.get("TTS_MODEL", ""),
            tts_stability=float(env.get("TTS_STABILITY", "0.3")),
            tts_similarity=float(env.get("TTS_SIMILARITY", "0.75")),
            tts_style=float(env.get("TTS_STYLE", "0.2")),
            tts_speed=float(env["TTS_SPEED"]) if env.get("TTS_SPEED") else None,
            character_url=env.get("CHARACTER_URL", "https://mcp.etiennelescot.fr/api/v1/character"),
            bridge_provider=env.get("BRIDGE_PROVIDER", "mistral"),
            bridge_model=env.get("BRIDGE_MODEL", ""),
            bridge_base_url=env.get("BRIDGE_BASE_URL", ""),
            max_session=float(env.get("MAX_SESSION_S", "300")),
            closing_lead=float(env.get("CLOSING_LEAD_S", "15")),
            visitor_gone=float(env.get("VISITOR_GONE_S", "20")),
            interruption_mode=env.get("INTERRUPTION_MODE", "vad"),
            interruption_min=float(env.get("INTERRUPTION_MIN_S", "0.4")),
            env=env,
        )

    def per_lang(self, name: str, lang: str) -> str:
        """NAME_FR / NAME_EN, else NAME."""
        return self.env.get(f"{name}_{lang.upper()}") or self.env.get(name, "")

    def phrases(self, lang: str) -> Phrases:
        defaults = DEFAULT_PHRASES[lang]
        return Phrases(
            closing=self.per_lang("CLOSING_PHRASE", lang) or defaults["CLOSING_PHRASE"],
            degraded=self.per_lang("DEGRADED_PHRASE", lang) or defaults["DEGRADED_PHRASE"],
            apology=self.per_lang("APOLOGY_PHRASE", lang) or defaults["APOLOGY_PHRASE"],
        )


def session_info(metadata: str, default_lang: str) -> tuple[str | None, str]:
    """The voice session token the backend dispatched the agent with, and the page language.

    The dispatch metadata is the token itself, `base64url(JSON payload).base64url(HMAC)`.
    The agent does not verify it: it forwards it to /ask and /voice/settle, and only
    reads `lang` from the payload. Without a token (console, lk agent dev), /ask serves
    the public level to the agent's own IP and nothing is settled.
    """
    token = metadata.strip()
    payload, dot, signature = token.partition(".")
    if not (payload and dot and signature):
        return None, default_lang
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (binascii.Error, ValueError):
        claims = None
    lang = claims.get("lang") if isinstance(claims, dict) else None
    return token, lang if lang in DEFAULT_PHRASES else default_lang


def make_stt(cfg: Config, lang: str, vad: Any) -> Any:
    """Continuous transcription, proper nouns of the profile as keyterms."""
    if cfg.stt_provider == "mistral":
        from livekit.plugins import mistralai

        # The realtime model takes no keyterms (livekit-plugins-mistralai 1.8.5).
        model = cfg.stt_model or "voxtral-mini-transcribe-realtime-2602"
        return mistralai.STT(model=model, language=lang, vad=vad)
    if cfg.stt_provider == "elevenlabs":
        from livekit.plugins import elevenlabs

        kwargs: dict[str, Any] = {"model": cfg.stt_model or "scribe_v2_realtime"}
        if cfg.keyterms:
            kwargs["keyterms"] = cfg.keyterms
        return elevenlabs.STT(language_code=lang, **kwargs)
    if cfg.stt_provider == "deepgram":
        from livekit.plugins import deepgram

        kwargs = {"model": cfg.stt_model or "nova-3"}
        if cfg.keyterms:
            kwargs["keyterm"] = cfg.keyterms
        return deepgram.STT(language=lang, **kwargs)
    raise ValueError(f"STT_PROVIDER must be mistral, elevenlabs or deepgram: {cfg.stt_provider}")


def make_tts(cfg: Config, lang: str) -> Any:
    """The cloned voice."""
    voice = cfg.per_lang("TTS_VOICE", lang)
    if cfg.tts_provider == "mistral":
        from livekit.plugins import mistralai

        # pcm: about 0.8 s to the first audio, against about 3 s for mp3
        kwargs: dict[str, Any] = {
            "model": cfg.tts_model or "voxtral-mini-tts-latest",
            "response_format": "pcm",
        }
        if ref := cfg.per_lang("TTS_REF_AUDIO", lang):  # 3-25 s sample: zero-shot clone
            kwargs["ref_audio"] = base64.b64encode(Path(ref).read_bytes()).decode()
        elif voice:
            kwargs["voice"] = voice
        return mistralai.TTS(**kwargs)
    if cfg.tts_provider == "elevenlabs":
        from livekit.plugins import elevenlabs

        # Lower stability than ElevenLabs' 0.5: a more expressive voice. eleven_v3/v4 models go
        # through text-to-dialogue, where livekit-plugins-elevenlabs 1.8.5 sends stability only
        # (and logs that it drops the rest); similarity 0.75 is that API's default anyway.
        settings = elevenlabs.VoiceSettings(
            stability=cfg.tts_stability,
            similarity_boost=cfg.tts_similarity,
            style=cfg.tts_style,
            **({"speed": cfg.tts_speed} if cfg.tts_speed is not None else {}),
        )
        kwargs = {"voice_id": voice} if voice else {}
        return elevenlabs.TTS(
            model=cfg.tts_model or "eleven_flash_v2_5",
            language=lang,
            voice_settings=settings,
            **kwargs,
        )
    raise ValueError(f"TTS_PROVIDER must be mistral or elevenlabs: {cfg.tts_provider}")


def make_bridge_llm(cfg: Config) -> Any:
    """The fast LLM that writes each turn's bridge: no reasoning, a little random, short."""
    options: dict[str, Any] = {"temperature": 0.8, "max_completion_tokens": 24}
    if cfg.bridge_provider == "mistral":
        from livekit.plugins import mistralai

        # Chat completions: lower latency than the plugin's default Conversations API.
        model = cfg.bridge_model or "ministral-8b-latest"
        return mistralai.LLM(model=model, api_mode="chat_completions", **options)
    if cfg.bridge_provider == "openai-compatible":
        from livekit.plugins import openai

        key = cfg.env.get("BRIDGE_API_KEY", "")
        if not (cfg.bridge_base_url and cfg.bridge_model and key):
            raise ValueError(
                "BRIDGE_PROVIDER=openai-compatible needs BRIDGE_BASE_URL, BRIDGE_MODEL "
                "and BRIDGE_API_KEY"
            )
        return openai.LLM(
            model=cfg.bridge_model,
            base_url=cfg.bridge_base_url,
            api_key=key,
            extra_body={"thinking": {"type": "disabled"}},  # a bridge never reasons
            **options,
        )
    if cfg.bridge_provider == "livekit":
        from livekit.agents import inference

        # LiveKit Inference, with the LiveKit Cloud project's LIVEKIT_INFERENCE_API_KEY and
        # LIVEKIT_INFERENCE_API_SECRET (or LIVEKIT_API_KEY / LIVEKIT_API_SECRET). EU-only models
        # are the project's "Inference region restriction" setting, not a parameter here.
        model = cfg.bridge_model or "google/gemma-4-31b-it"
        return inference.LLM(model=model, extra_kwargs=options)
    raise ValueError(
        f"BRIDGE_PROVIDER must be mistral, openai-compatible or livekit: {cfg.bridge_provider}"
    )


# The character per language, fetched once per worker process: every session reads the same.
_characters: dict[str, str] = {}


async def character_instructions(url: str, lang: str) -> str:
    """How the person sounds, for the bridge LLM: their `interaction` primitives.

    Best effort: ``""`` without a URL, or if the backend does not answer within a second
    and a half; the twin then bridges in the style alone. Only an answer is cached, so a
    later session tries again.
    """
    if not url:
        return ""
    if lang in _characters:
        return _characters[lang]
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                url, params={"lang": lang}, timeout=aiohttp.ClientTimeout(total=1.5)
            ) as response:
                response.raise_for_status()
                entries = (await response.json())["character"]
    except Exception as exc:
        logger.warning("no character: %s", type(exc).__name__)
        return ""
    _characters[lang] = render_character(entries)
    return _characters[lang]


def render_character(entries: list[dict[str, Any]]) -> str:
    """The `interaction` primitives as a description of how to sound, never lines to say."""
    lines = []
    for entry in entries:
        if entry.get("kind") != "interaction" or not entry.get("statement"):
            continue
        line = f"- {entry['statement']}"
        if samples := entry.get("calibration"):
            line += " (register: " + ", ".join(f"«{s}»" for s in samples) + ")"
        lines.append(line)
    if not lines:
        return ""
    return "\n".join(
        [
            "Character: how the person whose voice you are sounds. It colours the tone and the "
            "words of your line, nothing more: every rule above still holds, so your line stays "
            "short and says nothing about the subject.",
            *lines,
            "The samples in brackets only show a register: never say them, as written or "
            "nearly, and never describe the character.",
        ]
    )


def relay_to(room: rtc.Room) -> Callable[[str, Any], Any]:
    """/ask's evidence to the page, as JSON text streams on twin.* topics."""

    async def relay(topic: str, payload: Any) -> None:
        if not room.isconnected():  # console mode has no page to show it to
            return
        try:
            await room.local_participant.send_text(json.dumps(payload), topic=topic)
        except Exception:
            logger.warning("could not relay %s to the page", topic, exc_info=True)

    return relay


# /voice/settle refuses more than one session's worth (400), which would keep the
# whole reservation: clamp instead.
SETTLE_LIMITS = {"sttSeconds": 300, "ttsChars": 5000, "agentMinutes": 5}


def settle_payload(usage: metrics.AgentSessionUsage, seconds: float) -> dict[str, float | int]:
    """What the session really used, for /voice/settle."""
    used = usage.model_usage
    stt = sum(u.audio_duration for u in used if isinstance(u, metrics.STTModelUsage))
    tts = sum(u.characters_count for u in used if isinstance(u, metrics.TTSModelUsage))
    payload = {"sttSeconds": round(stt, 1), "ttsChars": tts, "agentMinutes": round(seconds / 60, 2)}
    return {key: min(max(value, 0), SETTLE_LIMITS[key]) for key, value in payload.items()}


async def settle(url: str, token: str, payload: dict[str, float | int]) -> None:
    """Best effort: an unsettled session keeps its reservation, which is the safe side."""
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                url,
                json=payload,
                headers={"Authorization": f"Voice {token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                # 409: already settled, which is done too. 401: expired, nothing to retry.
                if response.status >= 300 and response.status != 409:
                    logger.warning("/voice/settle answered HTTP %s", response.status)
    except Exception as exc:
        logger.warning("/voice/settle failed: %s", type(exc).__name__)


async def limit_duration(agent: TwinAgent, session: Any, *, total: float, lead: float) -> None:
    """Say goodbye `lead` seconds before the end, hang up at `total`."""
    await asyncio.sleep(max(total - lead, 0))
    agent.close_call()
    await asyncio.sleep(min(lead, total))
    session.shutdown(drain=False)


async def leave_when_alone(room: Any, gone: float, leave: Callable[[], None]) -> None:
    """Leave once no visitor has been in the room for `gone` seconds."""
    changed = asyncio.Event()
    room.on("participant_connected", lambda _: changed.set())
    room.on("participant_disconnected", lambda _: changed.set())
    while True:
        changed.clear()
        if any(
            p.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT
            for p in room.remote_participants.values()
        ):
            await changed.wait()
            continue
        try:
            await asyncio.wait_for(changed.wait(), gone)
        except asyncio.TimeoutError:
            leave()
            return


server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="digital-twin")
async def entrypoint(ctx: JobContext) -> None:
    started = time.monotonic()
    cfg = Config.from_env()
    token, lang = session_info(ctx.job.metadata, cfg.default_lang)
    phrases = cfg.phrases(lang)
    vad = ctx.proc.userdata["vad"]
    timeline = Timeline()
    character = await character_instructions(cfg.character_url, lang)

    agent = TwinAgent(
        stt=make_stt(cfg, lang, vad),
        tts=make_tts(cfg, lang),
        vad=vad,
        bridge_llm=make_bridge_llm(cfg),
        instructions="\n\n".join(filter(None, [f"Always speak {LANGUAGES[lang]}.", character])),
        closing=phrases.closing,
        timeline=timeline,
    )
    http = aiohttp.ClientSession()
    supervisor = AskSupervisor(
        ask=AskClient(http, cfg.ask_url, token),
        lang=lang,
        phrases=phrases,
        relay=relay_to(ctx.room),
        timeline=timeline,
    )
    supervisor.attach(agent)

    # VAD interruptions: the visitor cuts the twin off as soon as they speak; livekit's
    # adaptive mode filters short sounds and made barge-in feel sluggish (07/10/2026).
    interruption = {"mode": cfg.interruption_mode, "min_duration": cfg.interruption_min}
    session = AgentSession(vad=vad, turn_handling={"interruption": interruption})
    closed = asyncio.Event()
    session.on("close", lambda _: closed.set())

    async def on_shutdown() -> None:
        try:
            await asyncio.wait_for(closed.wait(), 5)  # usage is final once the session closed
        except asyncio.TimeoutError:
            pass
        await http.close()
        if token:
            payload = settle_payload(session.usage, time.monotonic() - started)
            await settle(cfg.settle_url, token, payload)

    ctx.add_shutdown_callback(on_shutdown)
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=room_io.RoomOptions(delete_room_on_close=True),
    )
    tasks = [
        asyncio.create_task(
            limit_duration(agent, session, total=cfg.max_session, lead=cfg.closing_lead)
        ),
        asyncio.create_task(
            leave_when_alone(ctx.room, cfg.visitor_gone, lambda: session.shutdown(drain=False))
        ),
    ]
    await closed.wait()
    for task in tasks:
        task.cancel()
    ctx.shutdown("session closed")  # settle now: it also frees the visitor's slot


if __name__ == "__main__":
    cli.run_app(server)
