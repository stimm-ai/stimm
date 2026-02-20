# Stimm v2 — Dual-Agent Voice Orchestration Library

> **Status**: Draft v2 — final architecture
> **Authors**: Etienne
> **Date**: 2026-02-20

---

## 1. What Stimm Becomes

Stimm is rewritten from scratch as a **dual-agent voice orchestration framework** built on top of [livekit-agents](https://github.com/livekit/agents).

It is NOT:
- A voice pipeline (livekit-agents does that)
- A full application (that was stimm v1)
- An alternative to livekit-agents (it extends it)

It IS:
- The **orchestration layer** for running two agents in one LiveKit room
- A **VoiceAgent** that extends livekit Agent with instruction injection, modes, and pre-TTS buffering
- A **Supervisor** base class for the background agent
- A **protocol** for inter-agent communication via LiveKit data channels
- Published as `pip install stimm` + `npm install @stimm/protocol`

```
┌──────────────────────────────────────────────────────────────┐
│  stimm — dual-agent voice orchestration on LiveKit           │
│                                                              │
│  "One agent talks fast. One agent thinks deep.               │
│   They collaborate in real-time."                            │
│                                                              │
│  ┌────────────────────┐   ┌──────────────────────────────┐   │
│  │  VoiceAgent        │   │  Supervisor                  │   │
│  │  (livekit Agent)   │◄──│  (any language, any runtime) │   │
│  │                    │──►│                              │   │
│  │  Talks to user     │   │  Watches transcript          │   │
│  │  Fast LLM          │   │  Calls tools                 │   │
│  │  VAD→STT→LLM→TTS  │   │  Sends instructions          │   │
│  │  Pre-TTS buffering │   │  Controls flow               │   │
│  └────────────────────┘   └──────────────────────────────┘   │
│           │                         │                        │
│           └──── Data Channel ───────┘                        │
│                 (stimm protocol)                             │
│                                                              │
│  pip install stimm[deepgram,openai]                          │
│  npm install @stimm/protocol                                 │
│  Built on: livekit-agents                                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Repo Structure

```
stimm/
├── README.md
├── LICENSE                          # MIT
├── pyproject.toml                   # pip install stimm
│
├── src/
│   └── stimm/
│       ├── __init__.py              # Public API
│       ├── py.typed                 # PEP 561 marker
│       ├── voice_agent.py           # VoiceAgent(Agent) — ~300 LOC
│       ├── supervisor.py            # Supervisor base class — ~300 LOC
│       ├── protocol.py              # Message types + serialization — ~200 LOC
│       ├── room.py                  # StimmRoom lifecycle — ~200 LOC
│       └── buffering.py             # Pre-TTS text buffering — ~150 LOC
│
├── packages/
│   └── protocol-ts/                 # npm: @stimm/protocol
│       ├── package.json
│       ├── tsconfig.json
│       └── src/
│           ├── index.ts
│           ├── messages.ts          # TypeScript protocol types
│           └── supervisor-client.ts # TS supervisor for Node.js consumers
│
├── examples/
│   ├── basic/                       # Minimal dual-agent demo
│   │   ├── voice_agent.py
│   │   └── supervisor.py
│   ├── with-tools/                  # Supervisor with tool calling
│   └── openclaw/                    # Reference: how OpenClaw uses stimm
│
├── tests/
│   ├── test_protocol.py
│   ├── test_voice_agent.py
│   ├── test_supervisor.py
│   ├── test_buffering.py
│   └── test_room.py
│
├── docker-compose.yml               # LiveKit server for local dev
└── docs/
    ├── quickstart.md
    ├── protocol.md
    ├── voice-agent.md
    └── supervisor.md
```

Total library: ~1,300 LOC Python + ~400 LOC TypeScript.

---

## 3. Python Package

### pyproject.toml

```toml
[project]
name = "stimm"
version = "0.1.0"
description = "Dual-agent voice orchestration built on livekit-agents"
requires-python = ">=3.10"
license = "MIT"
authors = [
    {name = "Etienne"}
]

dependencies = [
    "livekit-agents>=1.1",
    "livekit-plugins-silero>=1.1",
    "pydantic>=2.0",
]

[project.optional-dependencies]
deepgram = ["livekit-plugins-deepgram>=1.1"]
openai = ["livekit-plugins-openai>=1.1"]
elevenlabs = ["livekit-plugins-elevenlabs>=1.1"]
cartesia = ["livekit-plugins-cartesia>=1.1"]
google = ["livekit-plugins-google>=1.1"]
anthropic = ["livekit-plugins-anthropic>=1.1"]
all = ["stimm[deepgram,openai,elevenlabs,cartesia,google,anthropic]"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "ruff>=0.4"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/stimm"]
```

### Public API

```python
# stimm/__init__.py

from stimm.voice_agent import VoiceAgent
from stimm.supervisor import Supervisor
from stimm.protocol import (
    StimmProtocol,
    TranscriptMessage,
    StateMessage,
    BeforeSpeakMessage,
    MetricsMessage,
    InstructionMessage,
    ContextMessage,
    ActionResultMessage,
    ModeMessage,
    OverrideMessage,
    AgentMode,
)
from stimm.room import StimmRoom
from stimm.buffering import BufferingLevel, TextBufferingStrategy

__all__ = [
    "VoiceAgent",
    "Supervisor",
    "StimmProtocol",
    "StimmRoom",
    "BufferingLevel",
    "TextBufferingStrategy",
    # Message types
    "TranscriptMessage",
    "StateMessage",
    "BeforeSpeakMessage",
    "MetricsMessage",
    "InstructionMessage",
    "ContextMessage",
    "ActionResultMessage",
    "ModeMessage",
    "OverrideMessage",
    "AgentMode",
]
```

---

## 4. Module Specs

### 4.1 `voice_agent.py` — VoiceAgent (~300 LOC)

Extends `livekit.agents.Agent` with:

```python
from livekit.agents import Agent, AgentSession
from stimm.protocol import StimmProtocol, InstructionMessage, AgentMode
from stimm.buffering import TextBufferingStrategy, BufferingLevel

class VoiceAgent(Agent):
    def __init__(
        self,
        *,
        # Standard livekit-agents params
        stt=None,
        tts=None,
        vad=None,
        fast_llm=None,           # The fast LLM for voice responses
        instructions: str = "",
        # Stimm-specific
        buffering_level: BufferingLevel = "MEDIUM",
        mode: AgentMode = "hybrid",
        supervisor_instructions_window: int = 5,  # How many recent instructions to keep in context
    ):
        super().__init__(stt=stt, tts=tts, vad=vad, llm=fast_llm, instructions=instructions)
        self._protocol = StimmProtocol()
        self._buffering = TextBufferingStrategy(buffering_level)
        self._mode = mode
        self._pending_instructions: list[InstructionMessage] = []
        self._supervisor_context: list[str] = []
        self._instructions_window = supervisor_instructions_window

    async def on_enter(self):
        """Called when agent joins the room. Set up data channel listener."""
        self._protocol.on_instruction(self._handle_instruction)
        self._protocol.on_context(self._handle_context)
        self._protocol.on_mode(self._handle_mode_change)
        self._protocol.on_override(self._handle_override)

    async def _handle_instruction(self, msg: InstructionMessage):
        """Supervisor sent an instruction."""
        if self._mode == "relay" and msg.speak:
            # In relay mode, speak exactly what supervisor says
            await self.session.say(msg.text)
        elif self._mode == "hybrid":
            # In hybrid mode, incorporate into next LLM context
            self._pending_instructions.append(msg)
            if msg.priority == "interrupt":
                await self.session.interrupt()
                await self.session.say(msg.text)

    def _build_context_with_instructions(self, base_instructions: str) -> str:
        """Merge supervisor instructions into the voice agent's LLM prompt."""
        if not self._pending_instructions and not self._supervisor_context:
            return base_instructions
        
        parts = [base_instructions]
        if self._supervisor_context:
            parts.append("\n\nContext from supervisor:\n" + "\n".join(self._supervisor_context))
        if self._pending_instructions:
            instruction_texts = [i.text for i in self._pending_instructions[-self._instructions_window:]]
            parts.append("\n\nSupervisor instructions (incorporate naturally):\n" + "\n".join(instruction_texts))
            self._pending_instructions.clear()
        return "\n".join(parts)
```

Key behaviors:
- **Publishes transcripts** to data channel as STT produces them
- **Publishes `before_speak`** before TTS, giving supervisor a chance to override
- **Accepts instructions** from supervisor via data channel
- **Merges instructions** into LLM context (hybrid mode) or speaks them directly (relay mode)
- **Pre-TTS buffering** applied before text goes to TTS

### 4.2 `supervisor.py` — Supervisor (~300 LOC)

```python
from livekit import rtc
from stimm.protocol import (
    StimmProtocol, TranscriptMessage, StateMessage, BeforeSpeakMessage,
    MetricsMessage, InstructionMessage, ContextMessage, ActionResultMessage,
)

class Supervisor:
    """
    Base class for the background supervising agent.
    
    Joins a LiveKit room as a non-audio participant.
    Receives transcripts and voice agent state via data channel.
    Sends instructions back to the voice agent.
    
    Subclass this and implement on_transcript(), on_state_change(), etc.
    """
    
    def __init__(self, *, room: rtc.Room | None = None):
        self._room = room
        self._protocol = StimmProtocol()
    
    async def connect(self, url: str, token: str):
        """Connect to the LiveKit room as a data-only participant."""
        if not self._room:
            self._room = rtc.Room()
        await self._room.connect(url, token)
        self._protocol.bind(self._room)
        self._protocol.on_transcript(self.on_transcript)
        self._protocol.on_state(self.on_state_change)
        self._protocol.on_before_speak(self.on_before_speak)
        self._protocol.on_metrics(self.on_metrics)
    
    # --- Override these in your subclass ---
    
    async def on_transcript(self, msg: TranscriptMessage):
        """Called when user speaks. Override to process transcripts."""
        pass
    
    async def on_state_change(self, msg: StateMessage):
        """Called when voice agent changes state (listening/thinking/speaking)."""
        pass
    
    async def on_before_speak(self, msg: BeforeSpeakMessage):
        """Called before voice agent speaks. Return an OverrideMessage to replace."""
        pass
    
    async def on_metrics(self, msg: MetricsMessage):
        """Called with per-turn latency metrics."""
        pass
    
    # --- Send commands to the voice agent ---
    
    async def instruct(self, text: str, *, speak: bool = True, priority: str = "normal"):
        """Send an instruction to the voice agent."""
        await self._protocol.send_instruction(InstructionMessage(
            text=text, speak=speak, priority=priority,
        ))
    
    async def add_context(self, text: str, *, append: bool = True):
        """Add context to the voice agent's working memory."""
        await self._protocol.send_context(ContextMessage(text=text, append=append))
    
    async def send_action_result(self, action: str, status: str, summary: str):
        """Notify voice agent that a tool/action completed."""
        await self._protocol.send_action_result(ActionResultMessage(
            action=action, status=status, summary=summary,
        ))
    
    async def set_mode(self, mode: str):
        """Switch voice agent mode (autonomous/relay/hybrid)."""
        await self._protocol.send_mode(mode)
    
    async def disconnect(self):
        """Leave the room."""
        if self._room:
            await self._room.disconnect()
```

### 4.3 `protocol.py` — StimmProtocol (~200 LOC)

Message types (Pydantic models) + serialization + data channel binding:

```python
from pydantic import BaseModel
from typing import Literal
from livekit import rtc

# --- VoiceAgent → Supervisor ---

class TranscriptMessage(BaseModel):
    type: Literal["transcript"] = "transcript"
    partial: bool
    text: str
    timestamp: int
    confidence: float = 1.0

class StateMessage(BaseModel):
    type: Literal["state"] = "state"
    state: Literal["listening", "thinking", "speaking"]
    timestamp: int

class BeforeSpeakMessage(BaseModel):
    type: Literal["before_speak"] = "before_speak"
    text: str
    turn_id: str

class MetricsMessage(BaseModel):
    type: Literal["metrics"] = "metrics"
    turn: int
    vad_ms: float
    stt_ms: float
    llm_ttft_ms: float
    tts_ttfb_ms: float
    total_ms: float

# --- Supervisor → VoiceAgent ---

AgentMode = Literal["autonomous", "relay", "hybrid"]

class InstructionMessage(BaseModel):
    type: Literal["instruction"] = "instruction"
    text: str
    priority: Literal["normal", "interrupt"] = "normal"
    speak: bool = True

class ContextMessage(BaseModel):
    type: Literal["context"] = "context"
    text: str
    append: bool = True

class ActionResultMessage(BaseModel):
    type: Literal["action_result"] = "action_result"
    action: str
    status: str
    summary: str

class ModeMessage(BaseModel):
    type: Literal["mode"] = "mode"
    mode: AgentMode

class OverrideMessage(BaseModel):
    type: Literal["override"] = "override"
    turn_id: str
    replacement: str

# --- Protocol handler ---

STIMM_TOPIC = "stimm"

class StimmProtocol:
    """Handles serialization and data channel routing for stimm messages."""
    
    def __init__(self):
        self._handlers: dict[str, list] = {}
        self._room: rtc.Room | None = None
    
    def bind(self, room: rtc.Room):
        """Bind to a LiveKit room's data channel."""
        self._room = room
        room.on("data_received", self._on_data)
    
    def _on_data(self, data: rtc.DataPacket):
        if data.topic != STIMM_TOPIC:
            return
        msg = self._deserialize(data.data)
        for handler in self._handlers.get(msg.type, []):
            handler(msg)
    
    async def _send(self, msg: BaseModel):
        if self._room:
            await self._room.local_participant.publish_data(
                msg.model_dump_json().encode(),
                topic=STIMM_TOPIC,
                reliable=True,
            )
    
    # Registration + sending helpers...
```

### 4.4 `room.py` — StimmRoom (~200 LOC)

```python
from livekit import api as lkapi

class StimmRoom:
    """Manages a LiveKit room with a VoiceAgent + Supervisor pair."""
    
    def __init__(
        self,
        *,
        livekit_url: str,
        api_key: str,
        api_secret: str,
        voice_agent: VoiceAgent,
        supervisor: Supervisor | None = None,
        room_name: str | None = None,
    ):
        self._url = livekit_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._voice_agent = voice_agent
        self._supervisor = supervisor
        self._room_name = room_name or f"stimm-{uuid4().hex[:8]}"
    
    async def start(self):
        """Create room, generate tokens, connect both agents."""
        # 1. Create LiveKit room
        # 2. Generate token for voice agent (audio permissions)
        # 3. Generate token for supervisor (data-only permissions)
        # 4. Start voice agent worker
        # 5. Connect supervisor
        ...
    
    async def stop(self):
        """Disconnect both agents and close room."""
        ...
    
    def get_client_token(self, identity: str = "user") -> str:
        """Generate a token for the end-user to join (browser, app, etc.)."""
        ...
```

### 4.5 `buffering.py` — Pre-TTS Text Buffering (~150 LOC)

The one piece of unique pipeline logic from Stimm v1 worth keeping:

```python
from typing import Literal

BufferingLevel = Literal["NONE", "LOW", "MEDIUM", "HIGH"]

class TextBufferingStrategy:
    """
    Controls how LLM tokens are batched before being sent to TTS.
    
    - NONE: Send every token immediately (lowest latency, choppiest speech)
    - LOW: Buffer until word boundary (space)
    - MEDIUM: Buffer until 4+ words OR punctuation
    - HIGH: Buffer until sentence boundary (punctuation only)
    """
    
    def __init__(self, level: BufferingLevel = "MEDIUM"):
        self.level = level
        self._buffer = ""
        self._punctuation = ".!?;:"
    
    def feed(self, token: str) -> str | None:
        """
        Feed an LLM token. Returns text to send to TTS, or None if still buffering.
        """
        self._buffer += token
        
        if self.level == "NONE":
            result = self._buffer
            self._buffer = ""
            return result
        
        elif self.level == "LOW":
            if " " in self._buffer:
                parts = self._buffer.rsplit(" ", 1)
                self._buffer = parts[1] if len(parts) > 1 else ""
                return parts[0] + " "
        
        elif self.level == "MEDIUM":
            words = self._buffer.split()
            if len(words) >= 4 or any(c in self._buffer for c in self._punctuation):
                result = self._buffer
                self._buffer = ""
                return result
        
        elif self.level == "HIGH":
            if any(c in self._buffer for c in self._punctuation):
                result = self._buffer
                self._buffer = ""
                return result
        
        return None
    
    def flush(self) -> str | None:
        """Flush remaining buffer (call at end of LLM stream)."""
        if self._buffer:
            result = self._buffer
            self._buffer = ""
            return result
        return None
```

---

## 5. TypeScript Protocol Package

### packages/protocol-ts/package.json

```json
{
  "name": "@stimm/protocol",
  "version": "0.1.0",
  "description": "TypeScript types and supervisor client for Stimm dual-agent voice orchestration",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch"
  },
  "dependencies": {
    "livekit-client": "^2.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4"
  },
  "license": "MIT"
}
```

### Key exports

```typescript
// Message types (mirror Python Pydantic models)
export interface TranscriptMessage { ... }
export interface InstructionMessage { ... }
// ... all message types

// Supervisor client for Node.js/TypeScript consumers
export class StimmSupervisorClient {
  constructor(options: { livekitUrl: string; token: string });
  
  async connect(): Promise<void>;
  async disconnect(): Promise<void>;
  
  on(event: 'transcript', handler: (msg: TranscriptMessage) => void): void;
  on(event: 'state', handler: (msg: StateMessage) => void): void;
  on(event: 'before_speak', handler: (msg: BeforeSpeakMessage) => void): void;
  on(event: 'metrics', handler: (msg: MetricsMessage) => void): void;
  
  async instruct(msg: Omit<InstructionMessage, 'type'>): Promise<void>;
  async addContext(msg: Omit<ContextMessage, 'type'>): Promise<void>;
  async sendActionResult(msg: Omit<ActionResultMessage, 'type'>): Promise<void>;
  async setMode(mode: AgentMode): Promise<void>;
  async override(msg: Omit<OverrideMessage, 'type'>): Promise<void>;
}
```

---

## 6. Migration from Stimm v1

| v1 Component | v2 Equivalent |
|-------------|---------------|
| `StimmEventLoop` (722 LOC) | Deleted. livekit-agents `AgentSession` handles this. |
| `SileroVADService` (250 LOC) | Deleted. `livekit-plugins-silero` handles this. |
| `LiveKitAgentBridge` (614 LOC) | Deleted. livekit-agents `RoomIO` handles this. |
| `STTService` + providers (270 LOC) | Deleted. `livekit-plugins-deepgram` etc. |
| `TTSService` + providers (570 LOC) | Deleted. `livekit-plugins-*` etc. |
| `LLMService` + providers (510 LOC) | Deleted. `livekit-plugins-*` etc. |
| `SharedStreaming` (293 LOC) | Deleted. livekit-agents handles streaming. |
| `WebRTCMediaHandler` (240 LOC) | Deleted. livekit-agents handles media. |
| Pre-TTS buffering logic | **Kept** → `stimm.buffering` |
| RAG engine | Deleted. Consumer's responsibility. |
| Agent admin DB | Deleted. Consumer's responsibility. |
| FastAPI routes | Deleted. |
| Next.js frontend | Deleted. |

**v1 total: ~7,000 LOC → v2 total: ~1,300 LOC Python + ~400 LOC TypeScript**

---

## 7. Development Plan

### Week 1: Core Library
- [ ] Create branch `v2` from clean slate
- [ ] `pyproject.toml` + project structure
- [ ] `protocol.py` — message types + serialization + data channel binding
- [ ] `buffering.py` — pre-TTS text buffering strategies
- [ ] `voice_agent.py` — VoiceAgent extending livekit Agent
- [ ] `supervisor.py` — Supervisor base class
- [ ] `room.py` — StimmRoom lifecycle manager
- [ ] Tests for protocol, buffering, and room
- [ ] `docker-compose.yml` for local LiveKit server

### Week 2: TypeScript + Examples
- [ ] `packages/protocol-ts/` — TypeScript message types
- [ ] `StimmSupervisorClient` — TypeScript supervisor client
- [ ] `examples/basic/` — minimal dual-agent demo
- [ ] `examples/with-tools/` — supervisor with tool calling
- [ ] Documentation (quickstart, protocol, API reference)
- [ ] Publish `stimm` to PyPI (test)
- [ ] Publish `@stimm/protocol` to npm (test)

### Week 3: OpenClaw Integration
- [ ] OpenClaw `extensions/stimm-voice/` scaffold
- [ ] OpenClaw Supervisor in TypeScript
- [ ] Web "Talk" button
- [ ] Docker compose for full stack
- [ ] End-to-end demo
