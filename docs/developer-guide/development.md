# Development Guide

This guide is for developers who want to contribute to Stimm or extend it with custom providers and features.

## Development Environment

### Prerequisites

- Python 3.10+ with uv
- Node.js 18+ (for frontend development)
- Docker and Docker Compose (for running supporting services)

### Setting Up

1. Clone the repository and install dependencies:

```bash
git clone https://github.com/stimm/stimm.git
cd stimm
uv sync --group dev --group docs
```

2. Start supporting services:

```bash
docker compose up -d postgres qdrant traefik livekit redis sip
```

3. Set up environment variables (copy `.env.example` files as described in [Configuration](../user-guide/configuration.md)).

4. Run the backend locally:

```bash
uv run python -m src.main
```

5. Run the frontend locally (in another terminal):

```bash
cd src/front
npm install
npm run dev
```

## Project Structure

Refer to [Components](../developer-guide/components.md) for a detailed breakdown of each directory.

## Adding a New AI Provider

Stimm is designed to be easily extended with new AI providers (LLM, TTS, STT). Each provider follows a common interface.

### LLM Provider

1. Create a new Python file under `src/services/llm/providers/`, e.g., `my_llm.py`.

2. Implement the `BaseLLMProvider` abstract class (defined in `src/services/llm/llm.py`).

3. Register the provider in `src/services/llm/llm.py` by adding it to the `LLM_PROVIDERS` dictionary.

4. Add any required environment variables (API keys, URLs) to `.env.example`.

5. Update the frontend provider list if needed (see `src/front/lib/provider‑constants.ts`).

### TTS/STT Provider

Similar steps apply for TTS and STT providers. Look at existing implementations (e.g., `src/services/tts/providers/deepgram/`) for reference.

## Adding a New RAG Provider

1. Create a new Python file under `src/services/rag/providers/`, e.g., `my_rag.py`.

2. Implement the `BaseRagProvider` abstract class (defined in `src/services/rag/rag_models.py`).

3. Register the provider in `src/services/rag/rag_service.py`.

4. Define configuration fields in `src/services/rag/config_models.py` (if needed).

5. Update the frontend RAG provider list (`src/front/components/rag/types.ts`).

## Database Migrations

When you modify the database models (`src/database/models.py`), you must create a new Alembic migration.

```bash
# Generate a new migration
uv run alembic revision --autogenerate -m "Description of changes"

# Apply the migration
uv run alembic upgrade head
```

## Testing

Run the test suite to ensure your changes don't break existing functionality.

```bash
# Unit tests
uv run pytest tests/unit/ -v

# Integration tests (requires provider API keys)
uv run pytest tests/integration/ -v
```

See [Testing Guide](testing.md) for more details.

## Code Style

### Backend (Python)

Stimm uses **black** for formatting, **isort** for import sorting, and **flake8** for linting.

```bash
# Format and lint
uv run black src/
uv run isort src/
uv run flake8 src/
```

### Frontend (TypeScript/React)

The frontend uses **ESLint** for linting and **Prettier** for formatting, with Prettier integrated into ESLint.

```bash
# Lint and format
cd src/front
npm run lint
npx prettier --check .

# Auto-fix formatting
npx prettier --write .
```

You can also use the pre‑commit hooks (see `.pre‑commit‑config.yaml`).

## Submitting Changes

1. Create a feature branch.
2. Write tests for your changes.
3. Ensure all tests pass and the code is formatted.
4. Submit a pull request on GitHub.

## Getting Help

If you have questions or need guidance, feel free to open an issue.
