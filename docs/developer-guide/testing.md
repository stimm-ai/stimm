# Testing Guide

Stimm has a comprehensive test suite organized by **feature** (STT, TTS, RAG, etc.) rather than provider, enabling cross‑provider testing and better maintainability.

## Test Structure

```
tests/
├── conftest.py              # Auto‑loads .env, provides fixtures
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

## Running Tests

### Prerequisites

1. Copy `.env.example` to `.env` and fill in your API keys (if you want to run integration tests). Tests auto‑skip when API keys are missing.

2. Install test dependencies (already included in the `dev` optional dependency group):

```bash
uv sync --group dev
```

### Unit Tests

Unit tests have no external dependencies and run quickly.

```bash
uv run pytest tests/unit/ -v
```

### Integration Tests

Integration tests require provider API keys. If a key is missing, the test is skipped automatically.

```bash
# Run all integration tests
uv run pytest tests/integration/ -v

# Run tests for a specific feature
uv run pytest tests/integration/stt/ -v
uv run pytest tests/integration/rag/ -v

# Run tests for a specific provider
uv run pytest tests/integration/stt/ -k deepgram -v
uv run pytest tests/integration/stt/ -k whisper -v
```

### With Coverage

Generate a coverage report:

```bash
uv run pytest --cov=src/services --cov-report=html -v
```

Open `htmlcov/index.html` in a browser to view the coverage report. The `.coverage` data file is excluded from version control.

## Writing Tests

### Unit Tests

Place unit tests in `tests/unit/`. They should not rely on external services (databases, APIs, etc.). Use mocks when necessary.

Example:

```python
def test_audio_chunking():
    audio = b"\x00" * 3200  # 100 ms of 16 kHz mono PCM
    chunks = chunk_audio(audio, chunk_ms=20)
    assert len(chunks) == 5
```

### Integration Tests

Place integration tests in `tests/integration/<feature>/`. Use the `@pytest.mark.requires_provider` marker to indicate which provider the test depends on.

Example:

```python
import pytest

@pytest.mark.requires_provider("stt")
def test_stt_transcription(stt_service):
    text = stt_service.transcribe(b"fake_audio")
    assert isinstance(text, str)
```

The `stt_service` fixture (defined in `conftest.py`) automatically picks an available STT provider based on your environment variables.

### Fixtures

Common fixtures are defined in `tests/fixtures/`. Use them to share setup code across tests.

## Test Markers

- `@pytest.mark.requires_provider("stt"|"tts"|"llm")` – Provider‑dependent tests.
- `@pytest.mark.slow` – Long‑running tests (e.g., training, large file processing).

You can run tests excluding slow markers:

```bash
uv run pytest -m "not slow" -v
```

## Continuous Integration

GitHub Actions runs the test suite on every push and pull request. The CI environment includes a subset of services (PostgreSQL, Qdrant, Redis) via Docker Compose.

See `.github/workflows/test.yml` for details.

## Debugging Tests

If a test fails, you can increase verbosity with `-v` or `-s` (to see print statements). You can also run a single test file:

```bash
uv run pytest tests/integration/stt/test_stt_streaming.py -v
```

For provider‑specific failures, check that your API keys are correct and that the provider’s service is reachable.
