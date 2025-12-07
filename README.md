<div align="center">
  <img src=".github/assets/logo_stimm_h.png" alt="Stimm Voice Agent Platform" width="200" height="56">
  <p>
    <b>The Open Source Voice Agent Platform</b><br>
    Orchestrate ultra-low latency AI pipelines for real-time conversations over WebRTC.
  </p>

  <a href="https://github.com/stimm-ai/stimm/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/stimm-ai/stimm/ci.yml?label=tests" alt="Tests">
  </a>
  <a href="https://github.com/stimm-ai/stimm/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-AGPL_v3-blue" alt="License">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/livekit-compatible-purple" alt="LiveKit">
  </a>
</div>

<br>

A modular, real-time AI voice assistant platform built with Python (FastAPI) and Next.js. This project provides a flexible infrastructure for creating, managing, and interacting with voice agents using various LLM, TTS, and STT providers.

## 🚀 Features

- **Real-time Voice Interaction**: Low-latency voice conversations using WebRTC and WebSocket transports.
- **SIP Telephony Integration**: Connect incoming phone calls to AI agents via SIP protocol.
- **Modular AI Providers**:
  - **LLM**: Support for Groq, Mistral, OpenRouter, and local Llama.cpp.
  - **TTS**: Deepgram, ElevenLabs, Async.ai, and local Kokoro.
  - **STT**: Deepgram and local Whisper.
- **Administrable RAG Configurations**: Create and manage multiple RAG configurations with different providers (Qdrant, Pinecone, SaaS) and per‑agent knowledge bases. Integrated Retrieval-Augmented Generation using Qdrant vector database.
- **Agent Management**: Admin interface to configure and manage multiple agents with different personalities and provider settings.
- **Modern Frontend**: Responsive web interface built with Next.js 16 and Tailwind CSS.
- **Robust Infrastructure**: Dockerized deployment with Traefik reverse proxy, PostgreSQL for data persistence, and Alembic for migrations.
- **Voice Activity Detection**: Integrated Silero VAD for accurate speech detection.

## 🏗 Architecture

The project follows a modular monolith architecture, containerized with Docker Compose.

```mermaid
graph TD
    Client[Web Client / Next.js] -->|HTTPS/WSS| Traefik[Traefik Reverse Proxy]
    Traefik -->|/api| Backend[Stimm Backend / FastAPI]
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
    participant EvLoop as StimmEventLoop
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

1. **Ingestion**: Audio is captured by a client (browser or SIP) and sent via **WebRTC** to the backend.
2. **Media Handling**: The `WebRTCMediaHandler` receives the incoming audio track and buffers the raw audio frames.
3. **Voice Activity Detection (VAD)**: The `SileroVADService` analyzes the audio frames in real-time to detect speech segments.
4. **Orchestration**: The `StimmEventLoop` acts as the central brain, coordinating all services.
5. **Speech-to-Text (STT)**: On "speech end", the `STTService` (e.g., Deepgram, Whisper) transcribes the audio buffer into text.
6. **Intelligence (RAG/LLM)**: The transcribed text is sent to the `ChatbotService`, which may query **Qdrant** for context (RAG) before sending the prompt to the **LLM**.
7. **Text-to-Speech (TTS)**: The LLM's response is streamed to the `TTSService` which converts text to audio.
8. **Output**: The generated audio is sent back via WebRTC to the user.

### Key Components

| Directory | Description |
|-----------|-------------|
| `src/services/agents` | Core stimm logic and event loop |
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
cd stimm

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
Create a `.env` file in the docker/stimm directory by copying `docker/stimm/.env.example` and filling in the required values.
Create a `.env` file in the src/front directory by copying `src/front/.env.example` and filling in the required values.

For convenience, you can use the setup script:

```bash
./scripts/setup_env.sh
```

Or manually copy the files:

```bash
cp .env.example .env
cp docker/stimm/.env.example docker/stimm/.env
cp src/front/.env.example src/front/.env
```

The `.env` file centralizes all service URLs, API keys, and other configuration. For local development, it defaults to `localhost` for all services. When running in Docker, these variables are overridden in `docker-compose.yml` to use the appropriate service names.

Here are some of the key variables:

```env
# Service URLs (defaults are for local development)
STIMM_API_URL=http://localhost:8001
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_URL=http://localhost:7880
DATABASE_URL=postgresql://stimm_user:stimm_password@localhost:5432/stimm
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
FRONTEND_URL=http://localhost:3000

# LiveKit Credentials
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

### Database Initialization

When starting from scratch, the PostgreSQL database needs to have its schema created. The project uses **Alembic** for database migrations.

The **stimm Docker image now automatically runs migrations on startup** (via an entrypoint script). This means you don't need to run any manual migration steps when using Docker Compose. The script waits for the PostgreSQL container to be ready, then applies any pending migrations before starting the FastAPI server.

If you are running the backend locally (without Docker), you can run migrations manually:

```bash
uv run alembic upgrade head
```

After migrations are applied, the database will contain the necessary tables (`agents`, `users`, `rag_configs`, etc.) and a default system user.

**Note:** If you encounter errors about missing tables, ensure migrations have been run. You can check the current migration version with:

```bash
docker compose exec postgres psql -U stimm_user -d stimm -c "SELECT * FROM alembic_version;"
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

#### `livekit`
Manage LiveKit rooms and SIP bridge.

```bash
# List all LiveKit rooms
uv run python -m src.cli.main livekit list-rooms

# Delete all SIP rooms and terminate agent processes
uv run python -m src.cli.main livekit clear-sip-bridge

# Delete all LiveKit rooms (SIP and non‑SIP; non‑SIP rooms may be protected)
uv run python -m src.cli.main livekit clear-rooms
```
**Subcommands:**
- `list‑rooms`: Lists all LiveKit rooms with participant counts.
- `clear‑rooms`: Deletes all LiveKit rooms (some rooms may be protected and produce a warning).
- `clear‑sip‑bridge`: Cleans up SIP bridge agent processes and deletes SIP rooms.

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

### Setup

1. **Configure Environment**:
    ```bash
    # Add to your .env file
    ENABLE_SIP_BRIDGE=true
    ```

2. **Start Services**:
    ```bash
    docker compose up
    ```

3. **Run Tests**:
    ```bash
    uv run python tests/sip_integration/test_sip_bridge_integration.py
    uv run python tests/sip_integration/test_sip_bridge.py
    ```

4. **Configure SIP** (scripts in `scripts/sip_integration/`):
    - Create SIP trunk configuration in Redis for the LiveKit SIP server:
      ```bash
      uv run python scripts/sip_integration/create_sip_trunk.py
      ```
    - Configure call routing rules (stores in Redis key `sip_dispatch_rules`):
      ```bash
      uv run python scripts/sip_integration/sip-dispatch-config.py
      ```
    - Update existing trunk's phone number or allowed addresses:
      ```bash
      # List all trunks
      uv run python scripts/sip_integration/update_trunk.py

      # Update a specific trunk
      uv run python scripts/sip_integration/update_trunk.py --trunk-id <ID> --number +1234567

      # Or use the shell wrapper
      ./scripts/sip_integration/update_trunk.sh --trunk-id <ID> --number +1234567
      ```

      These scripts require a running Redis instance (provided by the `redis` service in Docker Compose).

### Usage

- **Call**: Dial +1234567 from any SIP client (e.g., MicroSIP)
- **Connect**: Default agent automatically answers
- **Converse**: Full duplex voice conversation with AI

### Architecture

```
SIP Call → LiveKit SIP → Room Created → SIP Bridge → Agent Spawned → Audio Conversation
```

**Key Components:**
- **SIP Server**: Handles incoming calls via LiveKit SIP service
- **SIP Bridge**: A robust singleton service (`SIPBridgeIntegration`) that runs within the main API process (no separate Docker Compose). It monitors rooms with prefix `sip‑inbound‑` and spawns exactly one agent per room, preventing duplicate voices.
- **Agent Integration**: Connects Development Agent to SIP rooms for voice conversations.

### Configuration

**SIP Server Settings**: `sip‑server‑config.yaml` (flood protection, ports)
**Dispatch Rules**: Managed via `scripts/sip_integration/sip‑dispatch‑config.py`
**Environment**: `ENABLE_SIP_BRIDGE=true` activates the integration

### Health Monitoring

```bash
# Basic health check
curl http://localhost:8001/health/sip-bridge

# Detailed status (processes, active rooms)
curl http://localhost:8001/health/sip-bridge-status

# View logs
docker logs stimm‑app | grep "SIP"
```

### Cleanup

Stale SIP rooms and agent processes can be cleaned up via the CLI:

```bash
# List all LiveKit rooms
uv run python -m src.cli.main livekit list-rooms

# Delete all SIP rooms and terminate agent processes
uv run python -m src.cli.main livekit clear-sip-bridge

# Delete all LiveKit rooms (SIP and non‑SIP; non‑SIP rooms may be protected)
uv run python -m src.cli.main livekit clear-rooms
```

The system supports real‑time voice conversations with AI agents, demonstrated with French speech recognition and response generation.
## 🧠 RAG Administration

The RAG (Retrieval-Augmented Generation) system is now fully administrable via the API and a dedicated web interface, similar to agents. You can create, update, delete, and manage multiple RAG configurations, each with its own provider and settings.

### Providers

Currently supported RAG providers:

- **Qdrant.Internal** – Internal Qdrant vector database (default)
- **Pinecone** – Pinecone.io cloud vector database
- **Rag.Saas** – Third‑party SaaS RAG service (placeholder)

Each provider has its own configuration fields (e.g., collection name, embedding model, top‑k, ultra‑low‑latency mode).

### API Endpoints

All endpoints are available under `/api/rag-configs` (see the interactive API documentation at `http://api.localhost/docs`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rag-configs/` | List all RAG configurations |
| POST | `/rag-configs/` | Create a new RAG configuration |
| GET | `/rag-configs/{id}` | Retrieve a specific configuration |
| PUT | `/rag-configs/{id}` | Update a configuration |
| DELETE | `/rag-configs/{id}` | Delete a configuration |
| GET | `/rag-configs/default/current` | Get the current default RAG configuration |
| PUT | `/rag-configs/{id}/set-default` | Set a configuration as the default |
| GET | `/rag-configs/providers/available` | List available RAG providers with field definitions |
| GET | `/rag-configs/providers/{provider}/fields` | Get field definitions for a specific provider |

### Frontend UI

The platform includes a complete web interface for managing RAG configurations:

- **RAG Admin Page** (`/rag/admin`) – Lists all RAG configurations with options to set default, edit, or delete.
- **RAG Edit Page** (`/rag/create` and `/rag/edit/[id]`) – Create or edit a RAG configuration with provider selection and dynamic configuration fields.
- **Agent Edit Page** (`/agent/edit/[id]`) – Includes a RAG configuration selector to associate an agent with a specific RAG configuration.

The UI uses the same design patterns as agent administration, ensuring a consistent user experience.

### Integration with Agents

Each agent can be associated with a RAG configuration via the `rag_config_id` foreign key. When an agent uses RAG, the system will use the configured retrieval engine (collection, embedding model, etc.) for that specific agent, enabling per‑agent knowledge bases.

### Default Configuration

One RAG configuration can be marked as the default. If an agent does not have an explicit RAG configuration, the default is used. The default can be changed at any time via the `set‑default` endpoint.

### Ultra‑Low‑Latency Focus

The RAG system is designed with ultra‑low‑latency requirements in mind. The `ultra_low_latency` flag in provider configurations enables optimizations such as pre‑loaded embedding models, cached retrievals, and parallel query execution.

## 📝 Logging

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
├── scripts/              # Utility scripts
│   ├── sip_integration/  # SIP-related scripts
│   └── setup_env.sh      # Environment setup script
├── src/
│   ├── cli/              # Command-line tools
│   ├── database/         # Database models and session
│   ├── front/            # Next.js Frontend
│   ├── services/         # Backend services
│   │   ├── agents/       # stimm logic
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

## 🧪 Testing

The test suite is organized by **feature** (STT, TTS, RAG, etc.) rather than provider, enabling cross-provider testing and better maintainability.

### Test Structure

```
tests/
├── conftest.py              # Auto-loads .env, provides fixtures
├── fixtures/                # Shared utilities and verification functions
├── unit/                    # Unit tests (no external dependencies)
│   ├── test_audio_utils.py
│   └── test_vad_silero.py
└── integration/             # Integration tests (require providers)
    ├── stt/                 # STT tests (all providers)
    ├── tts/                 # TTS tests
    ├── llm/                 # LLM tests
    ├── rag/                 # RAG tests
    ├── vad/                 # VAD tests
    └── webrtc/              # WebRTC tests
```

### Quick Start

1. **Set up environment** (copy `.env.example` to `.env` and add your API keys):
   ```bash
   cp .env.example .env
   # Edit .env to add provider API keys (DEEPGRAM_STT_API_KEY, etc.)
   ```

2. **Run tests**:
   ```bash
   # Unit tests (no API keys needed)
   PYTHONPATH=./src uv run pytest tests/unit/ -v

   # Integration tests (auto-skip if API keys missing)
   PYTHONPATH=./src uv run pytest tests/integration/ -v

   # Specific feature tests
   PYTHONPATH=./src uv run pytest tests/integration/stt/ -v
   ```

### Test Organization

**Unit Tests** - No external dependencies:
- Audio utilities (PCM conversion, chunking, validation)
- Silero VAD (local model, no API key)

**Integration Tests** - Require providers:
- **STT**
- **TTS**
- **LLM**
- **RAG**
- **WebRTC**

### Environment Variables

Tests load configuration and keys from `.env` automatically. See [`.env.example`](file:///home/etienne/repos/stimm/.env.example) for all available variables.

**Tests auto-skip when API keys are missing** - no manual configuration needed.

### Running Specific Tests

```bash
# By test type
PYTHONPATH=./src uv run pytest tests/unit/ -v          # Unit tests (directory-based)
PYTHONPATH=./src uv run pytest tests/integration/ -v   # Integration tests (directory-based)

# By feature
PYTHONPATH=./src uv run pytest tests/integration/stt/ -v    # STT tests
PYTHONPATH=./src uv run pytest tests/integration/rag/ -v    # RAG tests

# By provider
PYTHONPATH=./src uv run pytest tests/integration/stt/ -k deepgram -v  # Deepgram only
PYTHONPATH=./src uv run pytest tests/integration/stt/ -k whisper -v   # Whisper only

# With coverage
PYTHONPATH=./src uv run pytest --cov=src/services --cov-report=html -v
```
Open `htmlcov/index.html` in a browser. The `.coverage` data file is excluded from version control.


### Test Markers

- `@pytest.mark.requires_provider("stt"|"tts"|"llm")` - Provider-dependent tests
- `@pytest.mark.slow` - Long-running tests

---

## ⚖️ Legal & Licensing

### License (AGPL v3)
The source code of **Stimm** is open-source and distributed under the **GNU Affero General Public License v3.0 (AGPL v3)**.
You are free to use, modify, and distribute this software, provided that any network services you deploy based on this code also make their source code available to users.

### 🛡️ Trademark Notice
**Important:** The name **"Stimm"**, the Stimm logo, and the project's brand assets are **exclusive trademarks** of the project maintainers. They are **not** covered by the Open Source license.

* You are free to fork this repository and modify the code.
* However, if you distribute a derivative product or offer a public service based on this code, you **must remove** the Stimm logo and change the name so as not to suggest an official affiliation or endorsement by Stimm.

### 🤝 Contributing (CLA)
Contributions are welcome! Please feel free to submit a Pull Request.

By submitting a Pull Request to this repository, you agree to the **Stimm Contributor License Agreement (CLA)**:

1.  **License:** You certify that your contribution is your original work.
2.  **Rights Assignment:** You grant the project maintainers (currently operating as "Stimm" and any future legal entity) the perpetual right to relicense your contribution under different terms (including proprietary commercial licenses) while retaining the open-source nature of the original contribution.
3.  **Retention:** You retain full ownership and the right to use your own contributions for any other purpose.

---

## ⚡ Acknowledgments

**Built with LiveKit**

Stimm relies on [LiveKit](https://livekit.io/) for high-performance real-time media transport (WebRTC).

* **Disclaimer:** Stimm is an independent project and is **not affiliated with, endorsed by, or sponsored by LiveKit**.
* We gratefully acknowledge the LiveKit team for their contributions to the open-source community.


