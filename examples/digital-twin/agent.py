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
import hashlib
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
from twin import AskSupervisor, Clips, Phrases, TwinAgent

from livekit import rtc
from livekit.agents import AgentServer, AgentSession, JobContext, JobProcess, cli, metrics, room_io
from livekit.plugins import silero

logger = logging.getLogger("digital-twin")

DEFAULT_PHRASES: dict[str, dict[str, Any]] = {
    "fr": {
        "ACK_PHRASES": ["Je regarde…", "Bonne question…", "Voyons voir…"],
        "FILLER_PHRASES": [
            "Un instant, je rassemble mes sources…",
            "Je vérifie dans mes notes, une seconde…",
        ],
        "CLOSING_PHRASE": (
            "Nous arrivons au bout du temps prévu pour cet appel. "
            "Merci de votre visite, vous pouvez continuer par écrit."
        ),
        "DEGRADED_PHRASE": "Je n'ai pas pu formuler de réponse ; les sources sont à l'écran.",
        "APOLOGY_PHRASE": "Désolé, je n'ai pas pu terminer ma réponse.",
    },
    "en": {
        "ACK_PHRASES": ["Let me check…", "Good question…", "Let's see…"],
        "FILLER_PHRASES": [
            "One moment, I'm pulling up my sources…",
            "Let me look through my notes, just a second…",
        ],
        "CLOSING_PHRASE": (
            "We're almost out of time for this call. "
            "Thanks for stopping by, you can carry on in writing."
        ),
        "DEGRADED_PHRASE": "I couldn't phrase an answer; the sources are on screen.",
        "APOLOGY_PHRASE": "Sorry, I couldn't finish my answer.",
    },
}


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
    filler_delays: list[float]
    max_session: float
    closing_lead: float
    visitor_gone: float
    clips_dir: Path
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
            filler_delays=[float(d) for d in env.get("FILLER_DELAYS_S", "2.5,6").split(",") if d],
            max_session=float(env.get("MAX_SESSION_S", "300")),
            closing_lead=float(env.get("CLOSING_LEAD_S", "15")),
            visitor_gone=float(env.get("VISITOR_GONE_S", "20")),
            clips_dir=Path(env.get("CLIPS_DIR", Path(__file__).parent / "clips")),
            env=env,
        )

    def per_lang(self, name: str, lang: str) -> str:
        """NAME_FR / NAME_EN, else NAME."""
        return self.env.get(f"{name}_{lang.upper()}") or self.env.get(name, "")

    def phrases(self, lang: str) -> Phrases:
        defaults = DEFAULT_PHRASES[lang]

        def listed(name: str) -> list[str]:
            items = [p.strip() for p in self.per_lang(name, lang).split("|") if p.strip()]
            return items or defaults[name]

        return Phrases(
            acks=listed("ACK_PHRASES"),
            fillers=listed("FILLER_PHRASES"),
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


def make_tts(cfg: Config, lang: str) -> tuple[Any, str]:
    """The cloned voice. Returns the TTS and a key naming that voice."""
    voice = cfg.per_lang("TTS_VOICE", lang)
    if cfg.tts_provider == "mistral":
        from livekit.plugins import mistralai

        # pcm: about 0.8 s to the first audio, against about 3 s for mp3
        kwargs: dict[str, Any] = {
            "model": cfg.tts_model or "voxtral-mini-tts-latest",
            "response_format": "pcm",
        }
        if ref := cfg.per_lang("TTS_REF_AUDIO", lang):  # 3-25 s sample: zero-shot clone
            sample = Path(ref).read_bytes()
            kwargs["ref_audio"] = base64.b64encode(sample).decode()
            voice = "ref:" + hashlib.sha256(sample).hexdigest()[:16]
        elif voice:
            kwargs["voice"] = voice
        return mistralai.TTS(**kwargs), f"mistral/{kwargs['model']}/{voice}"
    if cfg.tts_provider == "elevenlabs":
        from livekit.plugins import elevenlabs

        model = cfg.tts_model or "eleven_flash_v2_5"
        kwargs = {"voice_id": voice} if voice else {}
        return elevenlabs.TTS(model=model, language=lang, **kwargs), f"elevenlabs/{model}/{voice}"
    raise ValueError(f"TTS_PROVIDER must be mistral or elevenlabs: {cfg.tts_provider}")


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


def settle_payload(usage: metrics.AgentSessionUsage, seconds: float) -> dict[str, float | int]:
    """What the session really used, for /voice/settle."""
    used = usage.model_usage
    stt = sum(u.audio_duration for u in used if isinstance(u, metrics.STTModelUsage))
    tts = sum(u.characters_count for u in used if isinstance(u, metrics.TTSModelUsage))
    return {"sttSeconds": round(stt, 1), "ttsChars": tts, "agentMinutes": round(seconds / 60, 2)}


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
    tts, voice_key = make_tts(cfg, lang)
    clips = Clips(tts, voice_key, phrases, cfg.clips_dir)

    agent = TwinAgent(
        stt=make_stt(cfg, lang, vad),
        tts=tts,
        vad=vad,
        clips=clips,
        closing=phrases.closing,
        filler_delays=cfg.filler_delays,
    )
    http = aiohttp.ClientSession()
    supervisor = AskSupervisor(
        ask=AskClient(http, cfg.ask_url, token),
        lang=lang,
        phrases=phrases,
        relay=relay_to(ctx.room),
    )
    supervisor.attach(agent)

    session = AgentSession(vad=vad)
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
        asyncio.create_task(clips.prepare()),
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


if __name__ == "__main__":
    cli.run_app(server)
