#!/usr/bin/env bash
# Creates a minimal .env file for CI from environment variables or defaults.
# All sensitive keys are expected to be empty in CI (tests skip provider calls).
set -euo pipefail

cat > .env <<'EOF'
LOG_LEVEL=INFO
STIMM_API_URL=http://localhost:8001
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_URL=http://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
DATABASE_URL=postgresql://stimm_user:stimm_password@localhost:5432/stimm
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
STT_PROVIDER=whisper.local
LLM_PROVIDER=openrouter.ai
TTS_PROVIDER=kokoro.local
DEEPGRAM_STT_API_KEY=
DEEPGRAM_TTS_API_KEY=
ELEVENLABS_TTS_API_KEY=
ASYNC_API_KEY=
GROQ_LLM_API_KEY=
MISTRAL_LLM_API_KEY=
OPENROUTER_LLM_API_KEY=
PINECONE_API_KEY=
RAG_SAAS_API_KEY=
EOF

echo ".env created for CI"
