# Configuration

Stimm uses environment variables for configuration. This page describes the key variables and how to set them up.

## Environment Files

The project uses three `.env` files for different contexts:

1. **Root `.env`** – Used by Docker Compose and backend services.
2. **`docker/stimm/.env`** – Used by the stimm backend container.
3. **`src/front/.env`** – Used by the Next.js frontend.

To create them, copy the example files:

```bash
cp .env.example .env
cp docker/stimm/.env.example docker/stimm/.env
cp src/front/.env.example src/front/.env
```

Then edit each file to fill in your specific values (API keys, URLs, etc.).

## Key Variables

### Service URLs (Defaults for Local Development)

| Variable          | Description                  | Default                                                       |
| ----------------- | ---------------------------- | ------------------------------------------------------------- |
| `STIMM_API_URL`   | URL of the backend API       | `http://localhost:8001`                                       |
| `LIVEKIT_URL`     | WebSocket URL for LiveKit    | `ws://localhost:7880`                                         |
| `LIVEKIT_API_URL` | HTTP URL for LiveKit API     | `http://localhost:7880`                                       |
| `DATABASE_URL`    | PostgreSQL connection string | `postgresql://stimm_user:stimm_password@localhost:5432/stimm` |
| `QDRANT_URL`      | Qdrant vector database URL   | `http://localhost:6333`                                       |
| `REDIS_URL`       | Redis connection URL         | `redis://localhost:6379`                                      |
| `FRONTEND_URL`    | Frontend URL (used for CORS) | `http://localhost:3000`                                       |

### LiveKit Credentials

| Variable             | Description        | Default  |
| -------------------- | ------------------ | -------- |
| `LIVEKIT_API_KEY`    | LiveKit API key    | `devkey` |
| `LIVEKIT_API_SECRET` | LiveKit API secret | `secret` |

### Provider API Keys

To use external AI providers, you need to set the corresponding API keys:

- **Deepgram** (STT/TTS): `DEEPGRAM_STT_API_KEY`, `DEEPGRAM_TTS_API_KEY`
- **ElevenLabs** (TTS): `ELEVENLABS_API_KEY`
- **Groq** (LLM): `GROQ_API_KEY`
- **Mistral** (LLM): `MISTRAL_API_KEY`
- **OpenRouter** (LLM): `OPENROUTER_API_KEY`
- **OpenAI‑compatible** (LLM): `OPENAI_API_KEY`, `OPENAI_BASE_URL`

If a key is missing, the corresponding provider will be disabled or fall back to a local alternative (if available).

### Feature Flags

| Variable                         | Description                           | Default |
| -------------------------------- | ------------------------------------- | ------- |
| `ENABLE_SIP_BRIDGE`              | Enable SIP telephony integration      | `false` |
| `LOG_LEVEL`                      | Logging level (`INFO`, `DEBUG`, etc.) | `INFO`  |
| `CONVERSATION_CACHE_LIMIT`       | Number of conversation turns to cache | `128`   |
| `CONVERSATION_CACHE_TTL_SECONDS` | Cache time‑to‑live in seconds         | `900`   |

## Docker‑Specific Configuration

When running with Docker Compose, many variables are overridden in `docker-compose.yml` to use service names instead of `localhost`. You generally don't need to change them unless you have a custom network setup.

## Validation

The backend validates environment variables on startup. If a required variable is missing or invalid, the service will fail to start with a descriptive error.

## Next Steps

- [Architecture](../developer-guide/architecture-overview.md) – Understand how the components interact.
- [Development Guide](../developer-guide/development.md) – Learn how to extend Stimm with custom providers.
