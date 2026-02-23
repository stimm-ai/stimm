"""Stimm worker — env-var-driven VoiceAgent factory and livekit-agents entrypoint.

This module provides a ready-to-use livekit-agents worker that wires up STT,
TTS, and LLM from environment variables. It is provider-agnostic; the caller
only needs to supply a ``supervisor_factory`` to produce the
:class:`~stimm.ConversationSupervisor` that handles deep reasoning.

Environment variables
─────────────────────
STIMM_STT_PROVIDER   deepgram (default) | openai | google | azure | assemblyai | aws | speechmatics | clova | fal
STIMM_STT_MODEL      provider-specific model name (default: nova-3)
STIMM_STT_API_KEY    override API key for STT provider
STIMM_STT_LANGUAGE   language hint, e.g. "fr" (optional)

STIMM_TTS_PROVIDER   openai (default) | elevenlabs | cartesia | google | azure | aws | playai | rime
STIMM_TTS_MODEL      provider-specific model name (default: gpt-4o-mini-tts)
STIMM_TTS_VOICE      voice name/id (default: ash)
STIMM_TTS_API_KEY    override API key for TTS provider

STIMM_LLM_PROVIDER   openai (default) | anthropic | google | groq | azure
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
        async def process(self, history: str, system_prompt: str | None) -> str:
            async with aiohttp.ClientSession() as http:
                resp = await http.post("http://my-backend/supervisor",
                                       json={"history": history, "systemPrompt": system_prompt})
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
from typing import Any, Callable

from livekit.agents import AgentSession, JobContext
from livekit.plugins import silero

from stimm.conversation_supervisor import ConversationSupervisor
from stimm.voice_agent import VoiceAgent

logger = logging.getLogger("stimm.worker")

# ---------------------------------------------------------------------------
# Provider registries
# ---------------------------------------------------------------------------

STT_PROVIDERS: dict[str, str] = {
    "deepgram": "livekit.plugins.deepgram",
    "openai": "livekit.plugins.openai",
    "google": "livekit.plugins.google",
    "azure": "livekit.plugins.azure",
    "assemblyai": "livekit.plugins.assemblyai",
    "aws": "livekit.plugins.aws",
    "speechmatics": "livekit.plugins.speechmatics",
    "clova": "livekit.plugins.clova",
    "fal": "livekit.plugins.fal",
}

TTS_PROVIDERS: dict[str, str] = {
    "openai": "livekit.plugins.openai",
    "elevenlabs": "livekit.plugins.elevenlabs",
    "cartesia": "livekit.plugins.cartesia",
    "google": "livekit.plugins.google",
    "azure": "livekit.plugins.azure",
    "aws": "livekit.plugins.aws",
    "playai": "livekit.plugins.playai",
    "rime": "livekit.plugins.rime",
}

LLM_PROVIDERS: dict[str, str] = {
    "openai": "livekit.plugins.openai",
    "anthropic": "livekit.plugins.anthropic",
    "google": "livekit.plugins.google",
    "groq": "livekit.plugins.groq",
    "azure": "livekit.plugins.azure",
}


def _load_plugin(provider_map: dict[str, str], provider: str) -> Any:
    module_name = provider_map.get(provider)
    if not module_name:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            f"Available: {', '.join(sorted(provider_map.keys()))}"
        )
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise ImportError(
            f"Provider '{provider}' requires: pip install livekit-plugins-{provider}"
        ) from exc


# ---------------------------------------------------------------------------
# Component factories — read STIMM_* env vars
# ---------------------------------------------------------------------------


def _make_stt() -> Any:
    provider = os.environ.get("STIMM_STT_PROVIDER", "deepgram")
    model = os.environ.get("STIMM_STT_MODEL", "nova-3")
    api_key = os.environ.get("STIMM_STT_API_KEY")
    language = os.environ.get("STIMM_STT_LANGUAGE")
    mod = _load_plugin(STT_PROVIDERS, provider)
    kwargs: dict[str, Any] = {"model": model}
    if api_key:
        kwargs["api_key"] = api_key
    if language:
        kwargs["language"] = language
    return mod.STT(**kwargs)


def _make_tts() -> Any:
    provider = os.environ.get("STIMM_TTS_PROVIDER", "openai")
    model = os.environ.get("STIMM_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.environ.get("STIMM_TTS_VOICE", "ash")
    api_key = os.environ.get("STIMM_TTS_API_KEY")
    mod = _load_plugin(TTS_PROVIDERS, provider)
    kwargs: dict[str, Any] = {"model": model}
    # ElevenLabs uses voice_id; most other providers use voice.
    if provider == "elevenlabs":
        kwargs["voice_id"] = voice
    else:
        kwargs["voice"] = voice
    if api_key:
        kwargs["api_key"] = api_key
    return mod.TTS(**kwargs)


def _make_llm() -> Any:
    provider = os.environ.get("STIMM_LLM_PROVIDER", "openai")
    model = os.environ.get("STIMM_LLM_MODEL", "gpt-4o-mini")
    api_key = os.environ.get("STIMM_LLM_API_KEY")
    mod = _load_plugin(LLM_PROVIDERS, provider)
    kwargs: dict[str, Any] = {"model": model}
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

        agent = make_agent()
        session = AgentSession()

        # Forward STT transcripts to the Stimm data-channel protocol so the
        # supervisor receives them as TranscriptMessage events.
        @session.on("user_input_transcribed")
        def _on_transcript(ev) -> None:  # type: ignore[no-untyped-def]
            asyncio.ensure_future(
                agent.publish_transcript(ev.transcript, partial=not ev.is_final)
            )

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

        await session.start(agent=agent, room=ctx.room)

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
            except Exception:
                pass
            disconnect.set()

        ctx.add_shutdown_callback(_on_shutdown)
        await disconnect.wait()

    return entrypoint
