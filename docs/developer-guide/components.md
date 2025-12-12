# Components

This page provides a detailed breakdown of the key software components that make up the Stimm platform.

## Backend Services

### `src/services/agents/`

Core stimm logic and event loop.

- **`StimmEventLoop`** – Central orchestrator that coordinates VAD, STT, LLM, and TTS.
- **`AgentFactory`** – Creates agent instances with configured providers.
- **`VADService`** – Voice activity detection using Silero VAD.
- **`StimmService`** – Main service that manages the audio pipeline.

### `src/services/agents_admin/`

Agent configuration management.

- **`AgentService`** – CRUD operations for agents.
- **`AgentManager`** – Runtime management of active agent sessions.
- **`ProviderRegistry`** – Registry of available AI providers.

### `src/services/rag/`

Knowledge base and retrieval logic.

- **`RagService`** – Main RAG service handling retrieval and context building.
- **`DocumentService`** – Manages document ingestion and metadata.
- **`RetrievalEngine`** – Performs semantic and lexical search over vector databases.
- **`RagConfigService`** – CRUD for RAG configurations.

### `src/services/llm/`

LLM integrations.

- **`LLMService`** – Unified interface for multiple LLM providers.
- **Provider implementations** – Groq, Mistral, OpenRouter, Llama.cpp, OpenAI‑compatible.

### `src/services/stt/` and `src/services/tts/`

Speech‑to‑text and text‑to‑speech services.

- **`STTService`** / `TTSService` – Unified interfaces.
- **Provider implementations** – Deepgram, Whisper (STT); Deepgram, ElevenLabs, Async.ai, Kokoro (TTS).

### `src/services/livekit/`

LiveKit integration.

- **`LiveKitService`** – Manages LiveKit connections and room operations.
- **`AgentBridge`** – Bridges LiveKit rooms to agent sessions.

### `src/services/webrtc/`

WebRTC signaling and media handling.

- **`WebRTCMediaHandler`** – Handles incoming/outgoing WebRTC audio tracks.
- **`Signaling`** – WebSocket signaling for WebRTC peer connection.

## Frontend Modules

### `src/front/app/`

Next.js app router pages.

- **`/`** – Landing page.
- **`/stimm`** – Voice conversation interface.
- **`/agent/admin`** – Agent management dashboard.
- **`/rag/admin`** – RAG configuration dashboard.

### `src/front/components/`

Reusable React components.

- **`agent/`** – Agent cards, grids, edit forms.
- **`rag/`** – Document upload, configuration forms.
- **`stimm/`** – Real‑time voice interface.
- **`ui/`** – Design system (buttons, cards, modals, etc.).

### `src/front/lib/`

Utilities and client‑side services.

- **`livekit‑client.ts`** – LiveKit client integration.
- **`theme.ts`** – Theme definitions.
- **`utils.ts`** – Helper functions.

## Database Models

### `src/database/models.py`

SQLAlchemy ORM models.

- **`Agent`** – Agent configuration (name, provider settings, system prompt).
- **`RagConfig`** – RAG configuration (provider, collection, embedding model).
- **`Document`** – Ingested documents for RAG.
- **`User`** – System users (future use).

## CLI Tool

### `src/cli/`

Command‑line interface for development and testing.

- **`main.py`** – CLI entry point with subcommands (`talk`, `chat`, `agents`, `test`, `livekit`).
- **`agent_runner.py`** – Runs an agent in local mode.
- **`livekit_client.py`** – LiveKit client utilities.

## Infrastructure

### Docker Compose

- **`docker‑compose.yml`** – Main composition (backend, frontend, PostgreSQL, Qdrant, Redis, LiveKit, Traefik).
- **`docker/stimm/Dockerfile`** – Backend container.
- **`docker/stimm‑front/Dockerfile.dev`** – Frontend development container.

### Configuration Files

- **`pyproject.toml`** – Python dependencies and tool configuration.
- **`alembic.ini`** – Database migration configuration.
- **`livekit.yaml`** – LiveKit server configuration.
- **`sip‑server‑config.yaml`** – SIP bridge settings.

## External Dependencies

- **LiveKit** – Real‑time media transport (WebRTC).
- **Qdrant** – Vector database for semantic search.
- **PostgreSQL** – Relational database for metadata.
- **Redis** – Caching and SIP bridge state.
- **Silero VAD** – Voice activity detection.
- **Sentence‑Transformers** – Embedding models.

## Development Tools

- **uv** – Python package manager.
- **pytest** – Testing framework.
- **ruff** – Code formatting, import sorting, and linting (replaces black, isort, and flake8).
- **mypy** – Static type checking.
