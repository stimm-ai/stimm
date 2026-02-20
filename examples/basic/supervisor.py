"""Minimal dual-agent voice demo — Supervisor.

Run alongside the voice agent:
    python examples/basic/supervisor.py

This supervisor watches user transcripts and sends simple instructions
back to the voice agent. A real supervisor would use a large LLM, call
tools, query databases, etc.

Environment:
    LIVEKIT_URL (default: ws://localhost:7880)
    LIVEKIT_API_KEY (default: devkey)
    LIVEKIT_API_SECRET (default: secret)
"""

import asyncio
import logging
import os

from stimm import BeforeSpeakMessage, MetricsMessage, Supervisor, TranscriptMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo.supervisor")


class DemoSupervisor(Supervisor):
    """A simple supervisor that echoes transcripts and provides context."""

    async def on_transcript(self, msg: TranscriptMessage) -> None:
        if msg.partial:
            return  # Wait for final transcripts

        logger.info("User said: %s", msg.text)

        # Simple keyword-based example — a real supervisor would use an LLM
        lower = msg.text.lower()
        if "weather" in lower:
            await self.instruct(
                "The weather is sunny and 22°C today.",
                speak=True,
                priority="normal",
            )
        elif "time" in lower:
            import datetime

            now = datetime.datetime.now().strftime("%H:%M")
            await self.instruct(
                f"The current time is {now}.",
                speak=True,
            )
        elif "help" in lower:
            await self.add_context(
                "The user seems to need help. Be extra patient and thorough.",
                append=True,
            )

    async def on_before_speak(self, msg: BeforeSpeakMessage) -> None:
        logger.info("Voice agent about to say: %s", msg.text[:80])

    async def on_metrics(self, msg: MetricsMessage) -> None:
        logger.info(
            "Turn %d — total: %.0fms (VAD: %.0f, STT: %.0f, LLM: %.0f, TTS: %.0f)",
            msg.turn,
            msg.total_ms,
            msg.vad_ms,
            msg.stt_ms,
            msg.llm_ttft_ms,
            msg.tts_ttfb_ms,
        )


async def main() -> None:
    from livekit import api as lkapi

    url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    api_key = os.environ.get("LIVEKIT_API_KEY", "devkey")
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "secret")

    # Generate a data-only token for the supervisor
    token = lkapi.AccessToken(api_key, api_secret)
    token.identity = "stimm-supervisor"
    token.ttl = 3600

    grant = lkapi.VideoGrants(
        room_join=True,
        room="stimm-demo",
        can_publish=False,  # No audio — data only
        can_subscribe=True,
        can_publish_data=True,
    )
    token.video_grant = grant

    supervisor = DemoSupervisor()
    await supervisor.connect(url, token.to_jwt())
    logger.info("Supervisor connected. Waiting for transcripts...")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await supervisor.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
