# Voicebot Platform

A modular, real-time AI voice assistant platform built with Python (FastAPI) and Next.js. This project provides a flexible infrastructure for creating, managing, and interacting with voice agents using various LLM, TTS, and STT providers.

## 🚀 Features

- **Real-time Voice Interaction**: Low-latency voice conversations using WebRTC and WebSocket transports.
- **SIP Telephony Integration**: Connect incoming phone calls to AI agents via SIP protocol.
- **Modular AI Providers**:
  - **LLM**: Support for Groq, Mistral, OpenRouter, and local Llama.cpp.
  - **TTS**: Deepgram, ElevenLabs, Async.ai, and local Kokoro.
  - **STT**: Deepgram and local Whisper.
- **RAG & Knowledge Base**: Integrated Retrieval-Augmented Generation using Qdrant vector database.
- **Agent Management**: Admin interface to configure and manage multiple agents with different personalities and provider settings.
- **Modern Frontend**: Responsive web interface built with Next.js 16 and Tailwind CSS.
- **Robust Infrastructure**: Dockerized deployment with Traefik reverse proxy, PostgreSQL for data persistence, and Alembic for migrations.
- **Voice Activity Detection**: Integrated Silero VAD for accurate speech detection.

## 🏗 Architecture

The project follows a modular monolith architecture, containerized with Docker Compose.

```mermaid
graph TD
    Client[Web Client / Next.js] -->|HTTPS/WSS| Traefik[Traefik Reverse Proxy]
    Traefik -->|/api| Backend[Voicebot Backend / FastAPI]
    Traefik -->|/| Frontend[Frontend Service]
    
    Backend --> Postgres[(PostgreSQL)]
    Backend --> Qdrant[(Qdrant Vector DB)]
    
    subgraph "AI Services"
        Backend -->|External API| LLM[LLM Providers]
        Backend -->|External API| TTS[TTS Providers]
        Backend -->|External API| STT[STT Providers]
    end
```

### Data Flow: Audio-to-Audio Pipeline

```mermaid
sequenceDiagram
    participant User
    participant WebRTC as WebRTC/WebSocket
    participant Media as MediaHandler
    participant VAD as Silero VAD
    participant EvLoop as VoicebotEventLoop
    participant STT as STT Service
    participant RAG as RAG/LLM Service
    participant TTS as TTS Service

    User->>WebRTC: Microphone Audio Stream
    WebRTC->>Media: Incoming Audio Track
    Media->>VAD: Raw Audio Frames
    
    alt Voice Detected
        VAD->>EvLoop: Speech Start Event
        EvLoop->>STT: Start Transcribing
    end
    
    alt Voice Ended
        VAD->>EvLoop: Speech End Event
        EvLoop->>STT: Finalize Transcription
        STT->>EvLoop: Transcribed Text
        EvLoop->>RAG: User Query
        RAG->>EvLoop: LLM Response Stream
        EvLoop->>TTS: Text Stream
        TTS->>Media: Audio Stream
        Media->>WebRTC: Outgoing Audio Track
        WebRTC->>User: Voice Response
    end
```

1. **Ingestion**: Audio is captured by the client (browser) and sent via **WebRTC** (preferred) or **WebSocket** to the backend.
2. **Media Handling**: The `WebRTCMediaHandler` receives the incoming audio track and buffers the raw audio frames.
3. **Voice Activity Detection (VAD)**: The `SileroVADService` analyzes the audio frames in real-time to detect speech segments.
4. **Orchestration**: The `VoicebotEventLoop` acts as the central brain, coordinating all services.
5. **Speech-to-Text (STT)**: On "speech end", the `STTService` (e.g., Deepgram, Whisper) transcribes the audio buffer into text.
6. **Intelligence (RAG/LLM)**: The transcribed text is sent to the `ChatbotService`, which may query **Qdrant** for context (RAG) before sending the prompt to the **LLM**.
7. **Text-to-Speech (TTS)**: The LLM's response is streamed to the `TTSService` which converts text to audio.
8. **Output**: The generated audio is sent back via WebRTC to the user.

### Key Components

| Directory | Description |
|-----------|-------------|
| `src/services/agents` | Core voicebot logic and event loop |
| `src/services/agents_admin` | Agent configuration management |
| `src/services/rag` | Knowledge base and retrieval logic |
| `src/services/webrtc` | WebRTC signaling and media handling |
| `src/front/` | Next.js frontend application |

## 🛠 Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic
- **Frontend**: Next.js 16, React 19, Tailwind CSS, TypeScript
- **AI/ML**: PyTorch, Sentence Transformers, Silero VAD
- **Real-time**: WebRTC (aiortc), WebSockets
- **Infrastructure**: Docker, Docker Compose, Traefik

## 🏁 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started) and Docker Compose
- [uv](https://docs.astral.sh/uv/) (for local development)

### Quick Start with Docker

```bash
# Clone and enter the repository
git clone <repository-url>
cd voicebot

# Create .env file (see Environment Configuration below)

# Build and run
docker-compose up --build
```

**Access points:**
- Frontend: http://front.localhost
- API Documentation: http://api.localhost/docs
- Traefik Dashboard: http://localhost:8080

### Environment Configuration

Create a `.env` file in the root directory by copying `.env.example` and filling in the required values.

```bash
cp .env.example .env
```

The `.env` file centralizes all service URLs, API keys, and other configuration. For local development, it defaults to `localhost` for all services. When running in Docker, these variables are overridden in `docker-compose.yml` to use the appropriate service names.

Here are some of the key variables:

```env
# Service URLs (defaults are for local development)
VOICEBOT_API_URL=http://localhost:8001
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_URL=http://localhost:7880
DATABASE_URL=postgresql://voicebot_user:voicebot_password@localhost:5432/voicebot
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
FRONTEND_URL=http://localhost:3000

# LiveKit Credentials
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

## 💻 Development

### Local Development Setup

1. **Start supporting services**:
   ```bash
   docker compose up -d postgres qdrant traefik livekit redis sip
   ```

2. **Set up Python environment**:
   ```bash
   # Required for imports to work correctly
   export PYTHONPATH=./src
   ```

3. **Run backend locally**:
   ```bash
   uv run python -m src.main
   ```
   Backend available at: http://localhost:8001

4. **Run frontend locally** (in a separate terminal):
   ```bash
   cd src/front
   npm install
   npm run dev
   ```
   Frontend available at: http://localhost:3000

### Full Docker Stack Development

For consistent environment testing:
```bash
docker compose up
```

## 🖥️ CLI Tool

The platform includes a powerful CLI tool for development and testing, allowing you to interact with agents without the web interface. It operates in two main modes:
- **Local Mode (Default)**: Instantiates services directly from your source code. This is ideal for development as it provides immediate feedback and easy debugging. It requires infrastructure services (like Postgres, Qdrant, LiveKit) to be running and accessible.
- **HTTP Mode (`--http`)**: Acts as a client to a running backend server. This is useful for testing a deployed instance or when you don't want to run the agent logic in the same process.

### Commands

The CLI uses a modern subcommand structure: `python -m src.cli.main [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]`

#### Global Options
- `--http [URL]`: Activates HTTP mode. If `[URL]` is provided, it uses that specific backend URL. If omitted, it uses the URL from your `.env` file.
- `--verbose, -v`: Enables detailed `DEBUG` logging.

#### `talk`
Starts a full, real-time voice conversation with an agent.

```bash
# Start a voice session with agent "ava" in local mode
uv run python -m src.cli.main talk --agent-name "ava"

# Start a session with a custom room name
uv run python -m src.cli.main talk --agent-name "ava" --room-name "my-test-room"
```
**Options:**
- `--agent-name NAME`: The name of the agent to talk to.
- `--room-name NAME`: Custom LiveKit room name.
- `--disable-rag`: Disables the Retrieval-Augmented Generation (RAG) system for the session.

#### `chat`
Starts an interactive text-only chat session with an agent.

```bash
# Start a local text chat with the default agent
uv run python -m src.cli.main chat

# Start a chat with a specific agent, disabling RAG
uv run python -m src.cli.main chat --agent-name "ava" --disable-rag
```
**Options:**
- `--agent-name NAME`: The name of the agent to chat with.
- `--disable-rag`: Disables the Retrieval-Augmented Generation (RAG) system.

#### `agents`
Manages agents in the system.

```bash
# List all agents
uv run python -m src.cli.main agents list
```
**Subcommands:**
- `list`: Displays a list of all configured agents.

#### `test`
Runs diagnostic tests.

```bash
# Test the full LiveKit audio pipeline with an echo server
uv run python -m src.cli.main test echo

# Run with verbose logging for detailed output
uv run python -m src.cli.main --verbose test echo
```
**Subcommands:**
- `echo`: Starts an echo client and server to verify that your audio is being correctly captured and played back through LiveKit.

#### HTTP Mode

The CLI tool can operate in HTTP mode to connect to a remote backend server. This is useful for testing deployed instances or when you don't want to run agent logic locally.

**Basic Usage:**
- `--http`: Connect to the backend URL defined in your `.env` file
- `--http URL`: Connect to a specific backend URL

**Examples:**

```bash
# Connect to remote backend using default URL from .env
uv run python -m src.cli.main --http talk --agent-name "ava"

# Connect to a specific backend URL
uv run python -m src.cli.main --http http://my-backend:8001 talk --agent-name "ava"

# Use HTTP mode with chat command
uv run python -m src.cli.main --http chat --agent-name "ava"

# List agents from a remote backend
uv run python -m src.cli.main --http agents list
```

## 📞 SIP Integration

Connect incoming phone calls to AI agents via telephony integration using SIP (Session Initiation Protocol).

### Quick Setup

1. **Configure Environment**:
   ```bash
   # Add to your .env file
   ENABLE_SIP_BRIDGE=true
   ```

2. **Start Services**:
   ```bash
   docker compose up
   ```

3. **Test Integration**:
   ```bash
   uv run python tests/sip_integration/test_sip_bridge_integration.py
   ```

### Usage

- **Call**: Dial +1234567 from any SIP client (e.g., MicroSIP)
- **Connect**: "Etienne" (Development Agent) automatically answers
- **Converse**: Full duplex voice conversation with AI

### Architecture

```
SIP Call → LiveKit SIP → Room Created → SIP Bridge → Agent Spawned → Audio Conversation
```

**Key Components:**
- **SIP Server**: Handles incoming calls via LiveKit SIP service
- **SIP Bridge**: Monitors rooms with prefix "sip-inbound-" and spawns agents automatically
- **Agent Integration**: Connects Development Agent to SIP rooms for voice conversations

### Configuration

**SIP Server Settings**: `sip-server-config.yaml` (flood protection, ports)
**Dispatch Rules**: Managed via `scripts/sip_integration/sip-dispatch-config.py`
**Environment**: `ENABLE_SIP_BRIDGE=true` activates the integration

### Health Monitoring

```bash
# Check SIP Bridge status
curl http://localhost:8001/health/sip-bridge

# View logs
docker logs voicebot-app | grep "SIP"
```

### Scripts

Located in `scripts/sip_integration/`:
- `create_sip_trunk.py` - Create SIP trunk configuration
- `sip-dispatch-config.py` - Configure call routing rules
- `update_trunk.sh` - Update existing trunk settings

The system supports real-time voice conversations with AI agents, demonstrated with French speech recognition and response generation.

## � Logging

### Log Levels

| Mode | Level | Output | Use Case |
|------|-------|--------|----------|
| Clean (Default) | `INFO` | "User Speaking", "Thinking...", "Speaking" | Development |
| Debug | `DEBUG` | Audio packets, LLM tokens, WebSocket frames | Debug |

### Configuration

```bash
# CLI: use --verbose flag
uv run python -m src.cli.main --agent-name "Etienne" --mode text --verbose

# Docker: use LOG_LEVEL environment variable
LOG_LEVEL=debug docker compose up

# Direct Python execution
LOG_LEVEL=debug python src/main.py
```

## 📂 Project Structure

```
.
├── alembic/              # Database migrations
├── docker/               # Docker configurations
├── src/
│   ├── cli/              # Command-line tools
│   ├── database/         # Database models and session
│   ├── front/            # Next.js Frontend
│   ├── services/         # Backend services
│   │   ├── agents/       # Voicebot logic
│   │   ├── agents_admin/ # Agent management
│   │   ├── llm/          # LLM integrations
│   │   ├── rag/          # RAG & Knowledge base
│   │   ├── stt/          # Speech-to-Text
│   │   ├── tts/          # Text-to-Speech
│   │   ├── vad/          # Voice Activity Detection
│   │   └── webrtc/       # WebRTC handling
│   └── main.py           # Application entry point
├── docker-compose.yml    # Main Docker Compose file
├── pyproject.toml        # Python dependencies (UV)
└── README.md
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
