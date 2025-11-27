# Voicebot Platform

A modular, real-time AI voice assistant platform built with Python (FastAPI) and Next.js. This project provides a flexible infrastructure for creating, managing, and interacting with voice agents using various LLM, TTS, and STT providers.

## 🚀 Features

- **Real-time Voice Interaction**: Low-latency voice conversations using WebRTC and WebSocket transports.
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

Create a `.env` file in the root directory:

```env
# Environment variables for voicebot app

###### -------------------------------------------------------------------
###### Debug level
###### -------------------------------------------------------------------
LOG_LEVEL=INFO


###### -------------------------------------------------------------------
###### Setting up Livekit media server
###### -------------------------------------------------------------------
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret


###### -------------------------------------------------------------------
###### Setting up Dev Agent from environment variables
###### -------------------------------------------------------------------

### -------------------------------------------------------------------
### Choice of the providers
### -------------------------------------------------------------------

# -------------------------------------------------------------------
# Choice of the STT providers
# -------------------------------------------------------------------
# Options: deepgram.com, whisper.local
STT_PROVIDER=whisper.local

# -------------------------------------------------------------------
# Choice of the LLM providers
# -------------------------------------------------------------------
# Options:  mistral, openRouter, groq, Llama.local
LLM_PROVIDER=mistral

# -------------------------------------------------------------------
# Choice of the TTS providers
# -------------------------------------------------------------------
# Options:  Deepgram, ElevenLabs, Async.ai, kokoro.local
TTS_PROVIDER=kokoro.local

### -------------------------------------------------------------------
### STT PROVIDERS CONFIGURATION
### -------------------------------------------------------------------

# -------------------------------------------------------------------
# deepgram.com STT configuration
# -------------------------------------------------------------------
# Required: Your Deepgram STT API key
DEEPGRAM_STT_API_KEY=xxxx
# Language: fr (French), en (English), es (Spanish), etc.
DEEPGRAM_LANGUAGE=fr
# Model: nova-3 (latest), nova-2 (recommended for French), nova, enhanced, base
DEEPGRAM_MODEL=nova-2

### -------------------------------------------------------------------
### TTS PROVIDERS
### -------------------------------------------------------------------

# -------------------------------------------------------------------
# deepgram.com TTS configuration
# -------------------------------------------------------------------
# Required: Your Deepgram TTS API key
DEEPGRAM_TTS_API_KEY=xxx
# Model: aura-asteria-en, aura-luna-en, aura-stella-en, etc.
DEEPGRAM_TTS_MODEL=aura-asteria-en

# -------------------------------------------------------------------
# Elevenlabs.io TTS configuration
# -------------------------------------------------------------------
# Required: Your ElevenLabs TTS API key
ELEVENLABS_TTS_API_KEY=xxx
ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_TTS_VOICE_ID=EXAVITQu4vr4xnSDxMaL

# -------------------------------------------------------------------
# Async.ai TTS configuration
# -------------------------------------------------------------------
ASYNC_API_KEY=xxx
#ASYNC_AI_TTS_VOICE_ID=e7b694f8-d277-47ff-82bf-cb48e7662647
ASYNC_AI_TTS_VOICE_ID=4941ff0d-6a89-4706-9890-aa93dcee1d54
ASYNC_AI_TTS_MODEL_ID=asyncflow_v2.0

# -------------------------------------------------------------------
# Kokoro.local TTS configuration
# -------------------------------------------------------------------
KOKORO_TTS_DEFAULT_VOICE=ff_siwis
KOKORO_TTS_DEFAULT_LANGUAGE=fr-fr

### -------------------------------------------------------------------
### LLM PROVIDERS
### -------------------------------------------------------------------

# -------------------------------------------------------------------
# Groq.com LLM configuration
# -------------------------------------------------------------------
GROQ_LLM_API_KEY=xxx
GROQ_LLM_MODEL=llama-3.1-8b-instant

# -------------------------------------------------------------------
# Mistral.ai LLM configuration
# -------------------------------------------------------------------
MISTRAL_LLM_API_KEY=xxx
MISTRAL_LLM_MODEL=open-mistral-nemo-2407

# -------------------------------------------------------------------
# OpenRouter.ai LLM configuration
# -------------------------------------------------------------------
OPENROUTER_LLM_API_KEY=xxx
OPENROUTER_LLM_MODEL=mistralai/mistral-7b-instruct:free

# -------------------------------------------------------------------
# Llama.cpp Local LLM configuration
# -------------------------------------------------------------------
#LLAMA_CPP_LLM_API_KEY=  # Optional, not required for local server
LLAMA_CPP_LLM_MODEL=default



###### -------------------------------------------------------------------
###### Qdrant Configuration
###### -------------------------------------------------------------------
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=voicebot_knowledge
QDRANT_USE_TLS=false

###### -------------------------------------------------------------------
###### RAG Configuration
###### -------------------------------------------------------------------
EMBED_MODEL_NAME=BAAI/bge-base-en-v1.5
RAG_DEFAULT_TOP_K=4
RAG_MAX_TOP_K=8
RAG_DENSE_CANDIDATE_COUNT=24
RAG_LEXICAL_CANDIDATE_COUNT=24

###### -------------------------------------------------------------------
###### VAD Configuration
###### -------------------------------------------------------------------
HUGGINGFACE_TOKEN=xxx

###### -------------------------------------------------------------------
###### TTS Configuration
###### -------------------------------------------------------------------

### -------------------------------------------------------------------
### TTS interface Configuration
### -------------------------------------------------------------------
TTS_INTERFACE_TEXT="Whatever you need to be spoken by the TTS"

### -------------------------------------------------------------------
### TTS Chunk Recording Configuration
### -------------------------------------------------------------------
TTS_RECORD_CHUNKS=false
TTS_CHUNKS_DIR=/tmp/tts_chunks_web

### -------------------------------------------------------------------
### TTS Buffering Configuration
### -------------------------------------------------------------------
# Options: NONE, LOW, MEDIUM, HIGH
# NONE = no buffering, send tokens immediately
# LOW = buffer until word completion (space) - current behavior
# MEDIUM = buffer until 4 words OR punctuation (.!?;:)
# HIGH = buffer until punctuation (.!?;:)
PRE_TTS_BUFFERING_LEVEL=HIGH
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

The platform includes a CLI tool for testing agents without the web interface.

### Basic Commands

```bash
# List available agents
uv run python -m src.cli.main --list-agents

# Text conversation (quick testing)
uv run python -m src.cli.main --agent-name "Etienne" --mode text

# Audio conversation via LiveKit
uv run python -m src.cli.main --agent-name "Etienne" --mode full

# With verbose logging
uv run python -m src.cli.main --agent-name "Etienne" --mode text --verbose
```

### Audio Pipeline Testing

```bash
# Automated echo test (recommended)
uv run python -m src.cli.main --test-echo --verbose

# Test microphone recording (5 seconds)
uv run python -m src.cli.main --test-mic 5

# Test LiveKit microphone capture
uv run python -m src.cli.main --test-livekit-mic 5

# Manual testing (two terminals)
# Terminal 1:
uv run python -m src.cli.echo_server
# Terminal 2:
uv run python -m src.cli.echo_client
```

### CLI Options Reference

| Option | Description |
|--------|-------------|
| `--list-agents` | List all available agents |
| `--agent-name NAME` | Select agent by name |
| `--mode text\|full` | Text-only or full audio mode |
| `--use-rag` | Enable RAG (default: enabled) |
| `--room-name NAME` | Custom LiveKit room name |
| `--local` | Backend is instanciated by the cli (No http calls to the backend, No need to run backend aside) |
| `--verbose` | Enable debug logging |
| `--test-echo` | Run echo pipeline test |
| `--test-mic SECONDS` | Test microphone recording |
| `--test-livekit-mic SECONDS` | Test LiveKit microphone |

### Troubleshooting Audio

| Issue | Solution |
|-------|----------|
| No microphone access | Check permissions and WSL2 audio setup |
| InvalidState errors | Use the fixed `echo_server.py` with error handling |
| No audio playback | Check speakers and PulseAudio configuration |
| Connection failures | Verify `docker-compose up livekit` is running |

## 📊 Logging

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
