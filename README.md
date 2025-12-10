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
- **Administrable RAG Configurations**: Create and manage multiple RAG configurations with Qdrant and per‑agent knowledge bases.
- **Agent Management**: Admin interface to configure and manage multiple agents with different personalities and provider settings.
- **Modern Frontend**: Responsive web interface built with Next.js 16 and Tailwind CSS.
- **Robust Infrastructure**: Dockerized deployment with Traefik reverse proxy, PostgreSQL for data persistence, and Alembic for migrations.
- **Voice Activity Detection**: Integrated Silero VAD for accurate speech detection.

## 🏁 Quick Start

Get Stimm up and running in minutes:

```bash
# Clone the repository
git clone https://github.com/stimm-ai/stimm.git
cd stimm

# Set up environment (copies .env.example files)
./scripts/setup_env.sh

# Start all services with Docker Compose
docker-compose up --build
```

Once the services are running, open your browser to:

- **Frontend Admin**: http://front.localhost/agent/admin (or http://localhost:3000/agent/admin)
- **API Documentation**: http://api.localhost/docs (or http://localhost:8001/docs)

For detailed installation, configuration, and usage instructions, please refer to the [full documentation](https://stimm-ai.github.io/stimm/).

## 📚 Documentation

Comprehensive documentation is available at **https://stimm-ai.github.io/stimm/**.

It includes:

- **User Guide**: Installation, configuration, web interface, CLI, managing agents, RAG, and SIP integration.
- **Developer Guide**: Architecture overview, data flow, components, development, testing, deployment, and adding new providers.
- **API Reference**: Auto-generated Python API docs and REST API endpoints.
- **Project**: Contributing, changelog, and license.

The documentation is built with MkDocs and Material theme, offering a modern, searchable experience.

## 💻 Development

For local development, see the [Development Guide](https://stimm-ai.github.io/stimm/developer-guide/development/) in the documentation.

### Quick Development Setup

```bash
# Start supporting services (PostgreSQL, Qdrant, LiveKit, Redis, SIP)
docker compose up -d postgres qdrant traefik livekit redis sip

# Install Python dependencies
uv sync --group dev --group docs

# Set up environment files and Python path (optional)
./scripts/setup_env.sh

# Run backend locally
uv run python -m src.main

# In another terminal, run frontend
cd src/front
npm install
npm run dev
```

## 🤝 Contributing

We welcome contributions! Please read our [Contributing Guide](https://stimm-ai.github.io/stimm/project/contributing/) for details on how to submit pull requests, report issues, and our code of conduct.

By contributing, you agree to the [Contributor License Agreement (CLA)](https://stimm-ai.github.io/stimm/project/contributing/#contributor-license-agreement-cla).

## ⚖️ License

Stimm is open-source software licensed under the **GNU Affero General Public License v3.0 (AGPL v3)**. See the [LICENSE](LICENSE) file for details.

**Trademark Notice**: The name "Stimm" and the Stimm logo are exclusive trademarks of the project maintainers and are not covered by the open-source license. Derivative works must remove the logo and change the name to avoid suggesting official affiliation.

## ⚡ Acknowledgments

**Built with LiveKit**

Stimm relies on [LiveKit](https://livekit.io/) for high-performance real-time media transport (WebRTC).

*Disclaimer: Stimm is an independent project and is not affiliated with, endorsed by, or sponsored by LiveKit.*
