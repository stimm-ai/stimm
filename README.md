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

The core of the voicebot is the real-time audio processing pipeline. Here is how data flows from the user's microphone back to their speakers:

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

1.  **Ingestion**: Audio is captured by the client (browser) and sent via **WebRTC** (preferred) or **WebSocket** to the backend.
2.  **Media Handling**: The `WebRTCMediaHandler` receives the incoming audio track and buffers the raw audio frames.
3.  **Voice Activity Detection (VAD)**: The `SileroVADService` analyzes the audio frames in real-time to detect speech segments. It triggers events for "speech start" and "speech end".
4.  **Orchestration**: The `VoicebotEventLoop` acts as the central brain. It receives VAD events and coordinates the other services.
5.  **Speech-to-Text (STT)**: When speech is detected, audio is buffered. On "speech end", the `STTService` (e.g., Deepgram, Whisper) transcribes the audio buffer into text.
6.  **Intelligence (RAG/LLM)**: The transcribed text is sent to the `ChatbotService`. This service may query the **Qdrant** vector database for context (RAG) before sending the prompt to the **LLM** (e.g., Groq, Mistral).
7.  **Text-to-Speech (TTS)**: The LLM's response is streamed token-by-token to the `TTSService` (e.g., Deepgram, ElevenLabs). The TTS service converts the text stream into an audio stream.
8.  **Output**: The generated audio is sent back to the `WebRTCMediaHandler`, which pushes it to the outgoing WebRTC track, playing it back to the user.

### Key Components

- **Backend (`src/`)**: FastAPI application handling API requests, WebSocket/WebRTC connections, and business logic.
  - `services/agents`: Core voicebot logic and event loop.
  - `services/agents_admin`: Agent configuration management.
  - `services/rag`: Knowledge base and retrieval logic.
  - `services/webrtc`: WebRTC signaling and media handling.
- **Frontend (`src/front/`)**: Next.js application for the user interface.
- **Database**: PostgreSQL for storing user, agent, and session data.
- **Vector Store**: Qdrant for storing document embeddings for RAG.

## 🛠 Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy, Alembic, Pydantic.
- **Frontend**: Next.js 16, React 19, Tailwind CSS, TypeScript.
- **AI/ML**: PyTorch, Sentence Transformers, Silero VAD.
- **Real-time**: WebRTC (aiortc), WebSockets.
- **Infrastructure**: Docker, Docker Compose, Traefik.

## 🏁 Getting Started

### Prerequisites

- [Docker](https://www.docker.com/get-started) and Docker Compose installed on your machine.

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd voicebot
   ```

2. **Environment Configuration**:
   Create a `.env` file in the root directory. You can use the following template:

   ```env
   # Database
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=voicebot
   DATABASE_URL=postgresql://postgres:postgres@postgres:5432/voicebot

   # Security
   SECRET_KEY=your_secret_key_here

   # AI Providers (Add keys for providers you intend to use)
   OPENAI_API_KEY=sk-...
   DEEPGRAM_API_KEY=...
   ELEVENLABS_API_KEY=...
   GROQ_API_KEY=...
   MISTRAL_API_KEY=...
   OPENROUTER_API_KEY=...

   # Qdrant
   QDRANT_HOST=qdrant
   QDRANT_PORT=6333
   ```

   Also ensure `src/front/.env` exists for the frontend (or is mapped correctly in docker-compose).

3. **Build and Run**:
   ```bash
   docker-compose up --build
   ```

4. **Access the Application**:
   - **Frontend**: [http://front.localhost](http://front.localhost)
   - **API Documentation**: [http://api.localhost/docs](http://api.localhost/docs)
   - **Traefik Dashboard**: [http://localhost:8080](http://localhost:8080)

## 💻 Development

### Preferred Development Setup (Docker Compose)

The **best development context** is within Docker Compose, which provides automatic reload capabilities:

1. **Clone and configure** (same as installation steps above)

2. **Start development environment with hot reload**:
   ```bash
   docker-compose up --build
   ```

   This will start:
   - **Backend**: FastAPI with `--reload` flag, automatically restarting on code changes
   - **Frontend**: Next.js with hot module replacement, updating on file changes
   - **Database**: PostgreSQL with persistent storage
   - **Vector Store**: Qdrant for RAG functionality
   - **Reverse Proxy**: Traefik routing to services

3. **Access the development environment**:
   - **Frontend**: [http://front.localhost](http://front.localhost)
   - **API Documentation**: [http://api.localhost/docs](http://api.localhost/docs)

The Docker Compose setup automatically:
- Mounts source directories for live code reloading
- Enables debug ports and development features
- Provides persistent database and vector storage
- Handles all service dependencies

### Alternative: Local Development (Not Preferred)

If you prefer to run services locally (not recommended), you can set up the development environment manually:

#### Backend Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r src/requirements.txt
   ```

3. Run migrations:
   ```bash
   alembic upgrade head
   ```

4. Run locally:
   ```bash
   cd src
   uvicorn main:app --reload --port 8000
   ```

#### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd src/front
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

**Note**: This approach requires manually managing database connections, external service dependencies, and doesn't provide the same development experience as Docker Compose.

## 📂 Project Structure

```
.
├── alembic/              # Database migrations
├── docker/               # Docker configurations for services
├── src/
│   ├── database/         # Database models and session
│   ├── front/            # Next.js Frontend application
│   ├── services/         # Microservices / Modules
│   │   ├── agents/       # Voicebot logic
│   │   ├── agents_admin/ # Agent management
│   │   ├── llm/          # LLM integrations
│   │   ├── rag/          # RAG & Knowledge base
│   │   ├── stt/          # Speech-to-Text
│   │   ├── tts/          # Text-to-Speech
│   │   ├── vad/          # Voice Activity Detection
│   │   └── webrtc/       # WebRTC handling
│   ├── main.py           # Application entry point
│   └── requirements.txt  # Python dependencies
├── docker-compose.yml    # Main Docker Compose file
├── pyproject.toml        # CLI dependencies (UV)
└── README.md             # Project documentation
```

## 🖥️ CLI Tool

The VoiceBot platform includes a powerful CLI tool for testing agents directly from the command line, without using the web interface.

### Usage

#### List Available Agents

```bash
docker exec -it voicebot-app python -m cli.main --list-agents
```

#### Text Mode (Recommended for quick testing)

```bash
# Basic text conversation
docker exec -it voicebot-app python -m cli.main --agent-name "Etienne" --mode text

# With RAG enabled (default)
docker exec -it voicebot-app python -m cli.main --agent-name "Etienne" --mode text --use-rag

# With verbose logging
docker exec -it voicebot-app python -m cli.main --agent-name "Etienne" --mode text --verbose
```

#### Full Audio Mode (LiveKit WebRTC)

```bash
# Audio conversation via LiveKit
docker exec -it voicebot-app python -m cli.main --agent-name "Etienne" --mode full

# With custom room name
docker exec -it voicebot-app python -m cli.main --agent-name "Etienne" --mode full --room-name "test-conversation"
```

### Features

- **Text Mode**: Interactive text conversation with the agent
- **Full Audio Mode**: Real-time audio conversation via LiveKit WebRTC
- **RAG Integration**: Retrieval-Augmented Generation with knowledge base context
- **Agent Configuration**: Uses the specific LLM/TTS/STT configuration of each agent
- **LiveKit Integration**: WebRTC audio streaming for low-latency conversations

### Examples

```bash
# List all available agents
docker exec -it voicebot-app python -m cli.main --list-agents

# Test agent in text mode
docker exec -it voicebot-app python -m cli.main --agent-name "Etienne" --mode text

# Test with audio via LiveKit
docker exec -it voicebot-app python -m cli.main --agent-name "Etienne" --mode full --verbose
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
