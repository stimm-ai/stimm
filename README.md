# stimm

**Dual-agent voice orchestration built on [livekit-agents](https://github.com/livekit/agents).**

One agent talks fast. One agent thinks deep. They collaborate in real-time.

```
┌─────────────────────────────────────────────────────────────┐
│  stimm — dual-agent voice orchestration on LiveKit          │
│                                                             │
│  ┌────────────────────┐   ┌─────────────────────────────┐   │
│  │  VoiceAgent        │   │  Supervisor                 │   │
│  │  (livekit Agent)   │◄──│  (any language/runtime)     │   │
│  │                    │──►│                             │   │
│  │  Talks to user     │   │  Watches transcript         │   │
│  │  Fast LLM          │   │  Calls tools                │   │
│  │  VAD→STT→LLM→TTS  │   │  Sends instructions         │   │
│  │  Pre-TTS buffering │   │  Controls flow              │   │
│  └────────────────────┘   └─────────────────────────────┘   │
│           │                         │                       │
│           └──── Data Channel ───────┘                       │
│                 (stimm protocol)                            │
└─────────────────────────────────────────────────────────────┘
```

## Install

```bash
# Python core only (recommended first step for onboarding/wizard UX)
pip install stimm

# then install only selected runtime plugins
pip install stimm[deepgram,openai]

# Python core + all runtime-supported plugins (heavier)
pip install stimm[all]

# TypeScript (supervisor client for Node.js consumers)
npm install @stimm/protocol
```

Plugin dependencies are installed in the integrator app environment. Stimm does
not vendor plugin code inside its wheel.

For app onboarding flows, install `stimm` first, read the provider catalog,
let the user choose providers/params, then install only required extras:

```python
from stimm import extras_install_command, get_provider_catalog

catalog = get_provider_catalog()  # exhaustive stt/tts/llm + parameters

# example user choices from your wizard
cmd = extras_install_command(stt="deepgram", tts="openai", llm="azure-openai")
print(cmd)  # pip install stimm[deepgram,openai]
```

After installing extras, restart the Python process before instantiating
LiveKit plugin classes.

For extension implementers, see
[docs/EXTENSION_WIZARD_INTEGRATION.md](docs/EXTENSION_WIZARD_INTEGRATION.md)
for the precise integration/migration flow.

## Quick Start

### Voice Agent (Python)

```python
from stimm import VoiceAgent
from livekit.plugins import silero, deepgram, openai

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
            # Process with your powerful LLM, call tools, etc.
            result = await my_big_llm.process(msg.text)
            await self.instruct(result.text, speak=True)

supervisor = MySupervisor()
await supervisor.connect("ws://localhost:7880", token)
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

## Concepts

### Dual-Agent Architecture

| Agent | Role | LLM | Latency |
|-------|------|-----|---------|
| **VoiceAgent** | Talks to the user | Fast, small (e.g. GPT-4o-mini) | ~500ms |
| **Supervisor** | Thinks, plans, uses tools | Large, capable (e.g. Claude, GPT-4o) | Background |

They communicate via **LiveKit data channels** using the stimm protocol — structured JSON messages flowing both directions.

### Modes

| Mode | Behavior |
|------|----------|
| `autonomous` | Voice agent uses its own fast LLM independently |
| `relay` | Voice agent speaks exactly what the supervisor sends |
| `hybrid` (default) | Voice agent responds autonomously but incorporates supervisor instructions |

### Pre-TTS Buffering

Controls how LLM tokens are batched before TTS:

| Level | Behavior |
|-------|----------|
| `NONE` | Every token immediately (lowest latency, choppiest) |
| `LOW` | Buffer until word boundary |
| `MEDIUM` | Buffer until 4+ words or punctuation (default) |
| `HIGH` | Buffer until sentence boundary |

## Development

```bash
# Local LiveKit server
docker compose up -d

# Delete all LiveKit rooms/sessions (uses .env)
python3 scripts/purge_livekit_rooms.py --yes

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Sync provider catalog from LiveKit source of truth
python3 scripts/sync_livekit_plugins.py

# CI-equivalent validation (fails if providers.json is outdated)
python3 scripts/sync_livekit_plugins.py --check

# Validate runtime provider contract + imports (CI mode)
python3 scripts/validate_runtime_contract.py --import-check
```

## Local Dev

Use one command from the repository root to build local dev artifacts:

```bash
bash scripts/dev_build.sh
```

This command:
- builds `@stimm/protocol` (`packages/protocol-ts/dist`)
- rebuilds `providers.json` from LiveKit docs + runtime introspection
  (`llms.txt` -> install plugins -> introspect constructors -> enrich from plugin `.md` pages)
- validates runtime provider contract structure

The plugin install/introspection phase runs in an isolated build virtualenv
(`.stimm-build-venv`) to keep your system Python clean.

Single source of truth for provider build/crawl: `scripts/sync_livekit_plugins.py`.
It is used both in local build (`scripts/dev_build.sh`) and CI (`--check`).

For `npm link` workflows, run this command after changing protocol code (or run
`npm run dev` inside `packages/protocol-ts` for watch mode).

## Protocol

See [docs/protocol.md](docs/protocol.md) for the full message specification.

## License

MIT
