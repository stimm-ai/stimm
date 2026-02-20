"""Minimal dual-agent voice demo — Voice Agent.

Run with:
    python examples/basic/voice_agent.py dev

Requires:
    pip install stimm[deepgram,openai]
    docker compose up -d  (LiveKit server)

Environment:
    DEEPGRAM_API_KEY
    OPENAI_API_KEY
    LIVEKIT_URL (default: ws://localhost:7880)
    LIVEKIT_API_KEY (default: devkey)
    LIVEKIT_API_SECRET (default: secret)
"""

from livekit.agents import AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, openai, silero

from stimm import VoiceAgent


def make_agent() -> VoiceAgent:
    return VoiceAgent(
        stt=deepgram.STT(),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(),
        fast_llm=openai.LLM(model="gpt-4o-mini"),
        buffering_level="MEDIUM",
        mode="hybrid",
        instructions=(
            "You are a friendly voice assistant in a demo. "
            "Keep responses concise and conversational. "
            "A supervisor agent is watching the conversation and may "
            "send you additional instructions or context."
        ),
    )


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    session = AgentSession()
    await session.start(agent=make_agent(), room=ctx.room)
    await session.wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
