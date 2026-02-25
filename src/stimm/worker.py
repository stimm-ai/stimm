"""Stimm worker — env-var-driven VoiceAgent factory and livekit-agents entrypoint.

This module provides a ready-to-use livekit-agents worker that wires up STT,
TTS, and LLM from environment variables. It is provider-agnostic; the caller
only needs to supply a ``supervisor_factory`` to produce the
:class:`~stimm.ConversationSupervisor` that handles deep reasoning.

Environment variables
─────────────────────
STIMM_STT_PROVIDER   deepgram (default) | openai | google | azure
                     | azure-openai | assemblyai | aws | speechmatics | clova | fal
STIMM_STT_MODEL      provider-specific model name (default: nova-3)
STIMM_STT_API_KEY    override API key for STT provider
STIMM_STT_LANGUAGE   language hint, e.g. "fr" (optional)

STIMM_TTS_PROVIDER   openai (default) | elevenlabs | cartesia | google | gemini
                     | azure | azure-openai | aws | asyncai | rime
STIMM_TTS_MODEL      provider-specific model name (default: gpt-4o-mini-tts)
STIMM_TTS_VOICE      voice name/id (default: ash)
STIMM_TTS_API_KEY    override API key for TTS provider

STIMM_LLM_PROVIDER   openai (default) | anthropic | gemini | groq | azure-openai
                     | cerebras | fireworks | together
STIMM_LLM_MODEL      provider-specific model name (default: gpt-4o-mini)
STIMM_LLM_API_KEY    override API key for LLM provider

STIMM_BUFFERING      MEDIUM (default) — see :class:`~stimm.BufferingLevel`
STIMM_MODE           hybrid (default) | fast | supervisor
STIMM_INSTRUCTIONS   full instructions prompt override (optional)
STIMM_CHANNEL        channel name passed to the supervisor factory (default: default)

LIVEKIT_URL          ws://localhost:7880 (default)
LIVEKIT_API_KEY      devkey (default)
LIVEKIT_API_SECRET   secret (default)

Usage::

    from stimm.worker import make_entrypoint
    from stimm import ConversationSupervisor
    import asyncio, aiohttp

    class MySupervisor(ConversationSupervisor):
        async def process(self, history: str) -> str:
            async with aiohttp.ClientSession() as http:
                resp = await http.post("http://my-backend/supervisor",
                                       json={"history": history})
                data = await resp.json()
                return data.get("text") or self.NO_ACTION

    def my_supervisor_factory(room_name: str, channel: str) -> MySupervisor:
        return MySupervisor()

    entrypoint = make_entrypoint(my_supervisor_factory)

    if __name__ == "__main__":
        from livekit.agents import WorkerOptions, cli
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
from collections.abc import Callable
from typing import Any

from livekit.agents import AgentSession, JobContext
from livekit.plugins import silero
from stimm.conversation_supervisor import ConversationSupervisor
from stimm.providers import RUNTIME_CONTRACT, resolve_runtime_provider
from stimm.voice_agent import VoiceAgent

logger = logging.getLogger("stimm.worker")


def _runtime_ids(kind: str) -> list[str]:
    entries = RUNTIME_CONTRACT.get(kind, [])
    aliases = RUNTIME_CONTRACT.get("aliases", {}).get(kind, {})
    ids: set[str] = set()
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                ids.add(entry["id"])
    if isinstance(aliases, dict):
        for alias in aliases:
            if isinstance(alias, str):
                ids.add(alias)
    return sorted(ids)


def _load_plugin(kind: str, provider: str) -> Any:
    resolved = resolve_runtime_provider(kind, provider)
    if not resolved:
        available = ", ".join(_runtime_ids(kind))
        raise ValueError(f"Unknown provider '{provider}' for {kind}. Available: {available}")

    module_name = resolved.get("module")
    if not isinstance(module_name, str) or not module_name:
        raise ValueError(f"Invalid runtime module for provider '{provider}' ({kind})")

    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        package_hint = module_name.removeprefix("livekit.plugins.")
        raise ImportError(
            f"Provider '{provider}' requires: pip install livekit-plugins-{package_hint}"
        ) from exc


# ---------------------------------------------------------------------------
# Component factories — read STIMM_* env vars
# ---------------------------------------------------------------------------


def _make_stt() -> Any:
    provider = os.environ.get("STIMM_STT_PROVIDER", "deepgram")
    model = os.environ.get("STIMM_STT_MODEL", "nova-3")
    api_key = os.environ.get("STIMM_STT_API_KEY")
    language = os.environ.get("STIMM_STT_LANGUAGE")
    mod = _load_plugin("stt", provider)

    kwargs: dict[str, Any] = {"model": model}

    if language:
        if provider == "google":
            kwargs["languages"] = [language]  # Google attend une liste
        else:
            kwargs["language"] = language

    if api_key:
        kwargs["api_key"] = api_key

    return mod.STT(**kwargs)


def _make_tts() -> Any:
    provider = os.environ.get("STIMM_TTS_PROVIDER", "openai")
    model = os.environ.get("STIMM_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.environ.get("STIMM_TTS_VOICE", "ash")
    language = os.environ.get("STIMM_TTS_LANGUAGE")
    api_key = os.environ.get("STIMM_TTS_API_KEY")
    resolved = resolve_runtime_provider("tts", provider)
    if not resolved:
        available = ", ".join(_runtime_ids("tts"))
        raise ValueError(f"Unknown provider '{provider}' for tts. Available: {available}")
    provider_id = resolved["id"]
    mod = _load_plugin("tts", provider)

    kwargs: dict[str, Any] = {}
    tts_ctor = mod.TTS

    # Google has two TTS constructors:
    # - google.TTS(model_name=..., voice_name=...)
    # - google.beta.GeminiTTS(model=..., voice_name=...)
    if provider_id in {"google", "gemini"}:
        if "gemini" in model.lower() and hasattr(mod, "beta") and hasattr(mod.beta, "GeminiTTS"):
            tts_ctor = mod.beta.GeminiTTS
            kwargs["model"] = model
        else:
            kwargs["model_name"] = model
    else:
        kwargs["model"] = model

    # Mapping de la voix
    if voice:
        if provider_id == "elevenlabs":
            kwargs["voice_id"] = voice
        elif provider_id in {"google", "gemini"}:
            kwargs["voice_name"] = voice
        else:
            kwargs["voice"] = voice

    # Language is accepted by several providers (Cartesia, Google standard TTS, etc.)
    if language and not (provider_id in {"google", "gemini"} and tts_ctor is not mod.TTS):
        kwargs["language"] = language

    if api_key:
        kwargs["api_key"] = api_key

    return tts_ctor(**kwargs)


def _make_llm() -> Any:
    provider = os.environ.get("STIMM_LLM_PROVIDER", "openai")
    model = os.environ.get("STIMM_LLM_MODEL", "gpt-4o-mini")
    temperature = os.environ.get("STIMM_LLM_TEMPERATURE")
    api_key = os.environ.get("STIMM_LLM_API_KEY")
    mod = _load_plugin("llm", provider)

    kwargs: dict[str, Any] = {"model": model}

    if temperature is not None:
        kwargs["temperature"] = float(temperature)

    if api_key:
        kwargs["api_key"] = api_key

    return mod.LLM(**kwargs)


# ---------------------------------------------------------------------------
# VoiceAgent factory
# ---------------------------------------------------------------------------

#: Type for a callable that creates a ConversationSupervisor given a room name
#: and channel string.
SupervisorFactory = Callable[[str, str], ConversationSupervisor]


def make_agent(instructions: str | None = None) -> VoiceAgent:
    """Build a :class:`~stimm.VoiceAgent` from ``STIMM_*`` environment variables.

    Args:
        instructions: Optional instructions override. Falls back to
            ``STIMM_INSTRUCTIONS`` env var, then
            :attr:`~stimm.ConversationSupervisor.DEFAULT_INSTRUCTIONS`.
    """
    resolved = (
        instructions
        or os.environ.get("STIMM_INSTRUCTIONS")
        or ConversationSupervisor.DEFAULT_INSTRUCTIONS
    )
    return VoiceAgent(
        stt=_make_stt(),
        tts=_make_tts(),
        vad=silero.VAD.load(),
        fast_llm=_make_llm(),
        buffering_level=os.environ.get("STIMM_BUFFERING", "MEDIUM"),  # type: ignore[arg-type]
        mode=os.environ.get("STIMM_MODE", "hybrid"),  # type: ignore[arg-type]
        instructions=resolved,
    )


# ---------------------------------------------------------------------------
# Entrypoint factory — one job = one LiveKit room
# ---------------------------------------------------------------------------


def make_entrypoint(
    supervisor_factory: SupervisorFactory,
    *,
    room_input_options: Any = None,
) -> Callable[[JobContext], Any]:
    """Return a livekit-agents entrypoint function wired to *supervisor_factory*.

    The returned ``entrypoint(ctx)`` coroutine:
    1. Connects the worker to the LiveKit room (``TRANSPORT_ALL`` so it works
       behind NAT without TURN config).
    2. Creates a :class:`~stimm.VoiceAgent` from ``STIMM_*`` env vars.
    3. Creates a :class:`~stimm.ConversationSupervisor` via *supervisor_factory*.
    4. Connects the supervisor as a data-only participant and starts its loop.
    5. Keeps the job alive until livekit-agents signals shutdown.

    Args:
        supervisor_factory: ``(room_name, channel) -> ConversationSupervisor``
            callable. ``channel`` comes from the ``STIMM_CHANNEL`` env var
            (default ``"default"``).
        room_input_options: Optional ``RoomInputOptions`` passed to
            ``session.start()``. Use this to bind audio input to a specific
            participant identity (e.g. ``participant_identity="user"`` for
            browser clients).

    Example::

        entrypoint = make_entrypoint(my_supervisor_factory)
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
    """

    async def entrypoint(ctx: JobContext) -> None:
        # TRANSPORT_ALL lets the agent reach LiveKit via the host LAN IP.
        # TRANSPORT_NOHOST blocks host candidates and causes PeerConnection timeouts.
        from livekit.rtc import IceTransportType, RtcConfiguration

        await ctx.connect(
            rtc_config=RtcConfiguration(
                ice_transport_type=IceTransportType.TRANSPORT_ALL,
            )
        )

        # Re-apply INFO level on stimm.* loggers here, after livekit-agents has
        # finished its own logging setup (which runs before entrypoint is called
        # and can reset levels set in basicConfig / module-level code).
        import logging as _logging

        for _n in ("stimm", "openclaw"):
            _logging.getLogger(_n).setLevel(_logging.INFO)

        agent = make_agent()
        session = AgentSession()

        # Forward STT transcripts to the Stimm data-channel protocol so the
        # supervisor receives them as TranscriptMessage events.
        # Dedup guard: some STT providers (e.g. Deepgram) emit a final
        # transcript event twice for the same utterance — once from the STT
        # plugin and once from the turn-detector flush.  Drop any identical
        # final transcript arriving within a 2-second window to prevent a
        # double LLM call and therefore double TTS output.
        _last_final: list[Any] = ["", 0.0]
        _FINAL_DEDUP_WINDOW_S = 2.0

        @session.on("user_input_transcribed")
        def _on_transcript(ev) -> None:  # type: ignore[no-untyped-def]
            import time

            is_final = bool(ev.is_final)
            text: str = ev.transcript or ""
            logger.info(
                "[TRANSCRIPT] is_final=%s text=%r agent_state=%s current_speech=%s",
                is_final,
                text,
                getattr(session, "agent_state", "?"),
                getattr(session, "current_speech", None) is not None,
            )
            if is_final:
                now = time.monotonic()
                if text == _last_final[0] and now - _last_final[1] < _FINAL_DEDUP_WINDOW_S:
                    logger.info(
                        "[TRANSCRIPT] DEDUP DROP final=%r (%.3fs ago)", text, now - _last_final[1]
                    )
                    return
                _last_final[0] = text
                _last_final[1] = now
                logger.info("[TRANSCRIPT] PASS final=%r → publish_transcript", text)
            asyncio.ensure_future(agent.publish_transcript(text, partial=not is_final))

        @session.on("conversation_item_added")
        def _on_conversation_item(ev) -> None:  # type: ignore[no-untyped-def]
            # Keep supervisor history aligned with what the fast assistant actually said.
            item = getattr(ev, "item", None)
            role = getattr(item, "role", None)
            if role != "assistant":
                return
            text = getattr(item, "text_content", None)
            if isinstance(text, str) and text.strip():
                asyncio.ensure_future(agent.publish_before_speak(text))

        from livekit.agents import RoomInputOptions as _RIO

        _opts = room_input_options if room_input_options is not None else _RIO()
        await session.start(agent=agent, room=ctx.room, room_input_options=_opts)

        # Bind the Stimm protocol after session.start() so the room is ready.
        agent.protocol.bind(ctx.room)

        # Build and connect the supervisor (data-only participant).
        channel = os.environ.get("STIMM_CHANNEL", "default")
        supervisor = supervisor_factory(ctx.room.name, channel)

        livekit_url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
        api_key = os.environ.get("LIVEKIT_API_KEY", "devkey")
        api_secret = os.environ.get("LIVEKIT_API_SECRET", "secret")

        from datetime import timedelta

        from livekit import api as lkapi

        sup_token = (
            lkapi.AccessToken(api_key, api_secret)
            .with_identity(f"stimm-supervisor-{ctx.room.name}")
            .with_ttl(timedelta(seconds=3600))
            .with_grants(
                lkapi.VideoGrants(
                    room_join=True,
                    room=ctx.room.name,
                    can_publish=False,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
        )

        try:
            await supervisor.connect(livekit_url, sup_token.to_jwt())
            supervisor.start_loop()
            logger.info(
                "Supervisor connected — room=%s channel=%s",
                ctx.room.name,
                channel,
            )
        except Exception as exc:
            logger.error("Supervisor failed to connect (continuing without): %s", exc)

        # Keep the entrypoint alive until shutdown.
        disconnect = asyncio.Event()

        async def _on_shutdown() -> None:
            supervisor.stop_loop()
            try:
                await supervisor.disconnect()
            except Exception:  # noqa: BLE001  # nosec B110
                pass
            disconnect.set()

        ctx.add_shutdown_callback(_on_shutdown)
        await disconnect.wait()

    return entrypoint
