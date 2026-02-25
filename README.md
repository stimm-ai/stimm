# stimm

<p align="center">
  <img src=".github/assets/logo_stimm_h.png" alt="stimm logo" width="360" />
</p>

Dual-agent voice orchestration built on [livekit-agents](https://github.com/livekit/agents):
one agent talks fast, one agent thinks deep, both collaborate in real-time.

## Why Stimm

- Low-latency conversational voice loop (`VAD → STT → fast LLM → TTS`).
- High-capability supervisor loop (tool use, planning, contextual steering).
- Typed protocol for Python + TypeScript supervisors.
- Runtime-safe provider contract + generated provider catalog from LiveKit docs.
- Integrator-friendly onboarding flow (discover providers first, install extras second).

## Install

```bash
# 1) Core package only (best first step for setup wizards)
pip install stimm

# 2) Install only the providers selected by the user
pip install stimm[deepgram,openai]

# Optional: install all runtime-supported providers
pip install stimm[all]

# TypeScript supervisor client
npm install @stimm/protocol
```

Plugin dependencies are installed in the integrator app environment. Stimm does
not vendor provider plugin code inside its wheel.

## Wizard-first Provider Flow

For onboarding UIs, use the catalog API to display providers/parameters, then
derive extras from the user selection:

```python
from stimm import extras_install_command, get_provider_catalog

catalog = get_provider_catalog()  # exhaustive stt/tts/llm + parameters
cmd = extras_install_command(stt="deepgram", tts="openai", llm="azure-openai")
print(cmd)  # pip install stimm[deepgram,openai]
```

After extras installation, restart the Python process before instantiating
LiveKit plugin classes.

Extension/wizard migration details are documented in
[docs/EXTENSION_WIZARD_INTEGRATION.md](docs/EXTENSION_WIZARD_INTEGRATION.md).

## Quick Start

### Voice Agent (Python)

```python
from stimm import VoiceAgent
from livekit.plugins import deepgram, openai, silero

agent = VoiceAgent(
    stt=deepgram.STT(),
    tts=openai.TTS(),
    vad=silero.VAD.load(),
    fast_llm=openai.LLM(model="gpt-4o-mini"),
    buffering_level="MEDIUM",
    mode="hybrid",
    instructions="You are a helpful voice assistant.",
)

if __name__ == "__main__":
    from livekit.agents import WorkerOptions, cli
    cli.run_app(WorkerOptions(entrypoint_fnc=agent.entrypoint))
```

### Supervisor (Python)

```python
from stimm import Supervisor, TranscriptMessage


class MySupervisor(Supervisor):
    async def on_transcript(self, msg: TranscriptMessage):
        if not msg.partial:
            result = await my_big_llm.process(msg.text)
            await self.instruct(result.text, speak=True)
```

### Supervisor (TypeScript)

```typescript
import { StimmSupervisorClient } from "@stimm/protocol";

const client = new StimmSupervisorClient({
  livekitUrl: "ws://localhost:7880",
  token: supervisorToken,
});

client.on("transcript", async (msg) => {
  if (!msg.partial) {
    const result = await myAgent.process(msg.text);
    await client.instruct({ text: result, speak: true, priority: "normal" });
  }
});

await client.connect();
```

## Core Concepts

## Dual-Agent Architecture

Stimm is fundamentally built around two cooperating agents:

- `VoiceAgent`: optimized for low-latency spoken interaction.
- `Supervisor`: optimized for deeper reasoning, planning, and tool orchestration.

They exchange typed protocol messages over LiveKit data channels, allowing fast
turn-by-turn response while retaining high-level control and context.

| Component | Role |
|---|---|
| `VoiceAgent` | Handles live turn-by-turn speech interaction |
| `Supervisor` | Watches transcript and steers behavior asynchronously |
| `StimmProtocol` | Structured messages over LiveKit data channels |

Modes:

- `autonomous`: voice agent acts independently.
- `relay`: voice agent only speaks supervisor instructions.
- `hybrid` (default): autonomous with supervisor steering.

Pre-TTS buffering levels:

- `NONE`, `LOW`, `MEDIUM` (default), `HIGH`.

## Developer Workflow

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Local infra
docker compose up -d

# Build local artifacts + sync providers + validate runtime contract
bash scripts/dev_build.sh

# Tests / lint
pytest
ruff check src/ tests/

# Catalog/contract checks (CI-equivalent)
python3 scripts/sync_livekit_plugins.py --check
python3 scripts/validate_runtime_contract.py --import-check
```

`scripts/dev_build.sh` is the single local command to rebuild protocol artifacts
and provider metadata from the LiveKit source of truth.

## Documentation

- Docusaurus docs site source: [website](website)
- Integration notes: [docs/EXTENSION_WIZARD_INTEGRATION.md](docs/EXTENSION_WIZARD_INTEGRATION.md)

## License

MIT
