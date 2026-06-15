---
id: integrations-resemble-detect
title: Resemble Detect and Signal Integration
---

Resemble Detect can monitor caller audio for synthetic speech risk in the
LiveKit voice-agent process. Stimm should use that signal as supervisor context
or escalation input; the raw audio monitor should not run inside the supervisor.
Resemble Signal can also score caller text or transcript excerpts for fraud and
scam intent before the supervisor allows sensitive actions.

## Install

Install the Resemble LiveKit plugin in the same environment as your Stimm voice
agent:

```bash
pip install livekit-plugins-resemble
```

Store the API key in an environment variable:

```bash
export RESEMBLE_API_KEY="..."
```

## Voice agent entrypoint

Attach the detector to the LiveKit room before starting the `AgentSession`.
Handle detector events in background tasks so STT, LLM, and TTS remain
non-blocking.

```python
import asyncio
import os

from livekit.agents import AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, openai, resemble, silero
from stimm import VoiceAgent


def make_agent() -> VoiceAgent:
    return VoiceAgent(
        stt=deepgram.STT(),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(),
        fast_llm=openai.LLM(model="gpt-4o-mini"),
        mode="hybrid",
        instructions=(
            "You are a real-time voice assistant. Keep responses concise. "
            "If caller authenticity monitoring reports a synthetic voice risk, "
            "pause sensitive workflows and follow the escalation policy."
        ),
    )


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    agent = make_agent()
    session = AgentSession()

    detector = resemble.ResembleDetect(
        api_key=os.environ["RESEMBLE_API_KEY"],
        zero_retention_mode=True,
    )

    def on_synthetic(result: resemble.DetectionResult) -> None:
        async def pause_for_verification() -> None:
            await session.interrupt()
            await session.say(
                "I need to pause here and verify this call before continuing."
            )

        asyncio.create_task(pause_for_verification())

    detector.on("synthetic_detected", on_synthetic)
    detector.attach(ctx.room)

    async def shutdown() -> None:
        await detector.aclose()

    ctx.add_shutdown_callback(shutdown)
    await session.start(agent=agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

## Supervisor policy

Use Detect and Signal results as risk signals, not as proof of identity. Common
policies are:

- log only for quality review
- ask the caller to complete another verification step
- pause sensitive workflows until a human reviews the call
- end the call when your compliance policy requires it

Keep the policy in your Stimm supervisor or application layer. That keeps
Stimm provider-agnostic while still letting the LiveKit worker own audio
capture and room lifecycle.

## Signal scoring in the supervisor

Use Signal when the transcript or a caller-provided message affects a trust
decision. Detect answers whether media is synthetic; Signal answers whether the
request resembles a fraud or scam pattern.

```python
import aiohttp


async def score_signal(text: str, api_key: str) -> dict:
    async with aiohttp.ClientSession(
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    ) as session:
        async with session.post(
            "https://app.resemble.ai/api/v2/signal",
            json={"text": text},
        ) as response:
            response.raise_for_status()
            return await response.json()
```

Run this from the supervisor or application layer for requests such as reset
codes, credential changes, wire transfers, urgent payments, or account updates.
If Signal returns `suspicious` or `fraud`, add supervisor context, interrupt the
voice agent if needed, and follow the same escalation policy you use for
synthetic-voice risk.
