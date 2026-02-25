"""Reference Stimm voice agent for Docker deployment."""

import os

from livekit.agents import WorkerOptions, cli
from livekit.plugins import deepgram, openai, silero
from stimm import VoiceAgent

agent = VoiceAgent(
    stt=deepgram.STT(),
    tts=openai.TTS(),
    vad=silero.VAD.load(),
    fast_llm=openai.LLM(model=os.environ.get("STIMM_LLM_MODEL", "gpt-4o-mini")),
    buffering_level=os.environ.get("STIMM_BUFFERING", "MEDIUM"),
    mode=os.environ.get("STIMM_MODE", "hybrid"),
    instructions=(
        "You are a friendly and helpful voice assistant. "
        "Keep responses concise and conversational. "
        "When the supervisor sends you instructions, incorporate them naturally."
    ),
)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=agent.entrypoint))
