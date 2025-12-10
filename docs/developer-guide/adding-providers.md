# Adding a New Provider

Stimm is designed to be easily extended with new AI providers (LLM, TTS, STT) and RAG providers. This guide walks through the steps to add a custom provider.

## Provider Types

- **LLM Provider** – Generates text responses (e.g., OpenAI, Anthropic, local model).
- **TTS Provider** – Converts text to speech (e.g., Google TTS, Amazon Polly).
- **STT Provider** – Converts speech to text (e.g., Google Speech‑to‑Text, Azure STT).
- **RAG Provider** – Vector database or retrieval service (e.g., Weaviate, Chroma).

## Common Pattern

All providers follow a similar pattern:

1. **Base class** – Abstract class defining the interface.
2. **Implementation class** – Your custom provider that inherits from the base class.
3. **Registration** – Add your provider to the appropriate registry.
4. **Configuration** – Define any required environment variables or settings.

## Adding an LLM Provider

### 1. Create the Provider File

Create a new Python file under `src/services/llm/providers/`, e.g., `my_llm.py`.

```python
import logging
from typing import AsyncGenerator, Optional
from services.llm.llm import BaseLLMProvider, LLMResult

logger = logging.getLogger(__name__)

class MyLLMProvider(BaseLLMProvider):
    """Custom LLM provider example."""

    def __init__(self, config: dict):
        super().__init__(config)
        # Initialize your client (e.g., API key, model name)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "my-model")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResult, None]:
        """Streaming generation."""
        # Implement calling your LLM API
        # Yield tokens as they arrive
        yield LLMResult(text="Hello from custom LLM", is_final=True)

    async def generate_non_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMResult:
        """Non‑streaming generation."""
        # Implement a single call
        return LLMResult(text="Hello from custom LLM", is_final=True)

    @property
    def name(self) -> str:
        return "my_llm"
```

### 2. Register the Provider

Edit `src/services/llm/llm.py` and add your provider to the `LLM_PROVIDERS` dictionary:

```python
from .providers.my_llm import MyLLMProvider

LLM_PROVIDERS = {
    ...,
    "my_llm": MyLLMProvider,
}
```

### 3. Add Configuration

Update `src/services/llm/llm.py`'s `get_llm_config` to include any required environment variables (e.g., `MY_LLM_API_KEY`). Also update the frontend provider constants if needed (`src/front/lib/provider‑constants.ts`).

## Adding a TTS/STT Provider

The process is similar. Look at existing providers (e.g., `src/services/tts/providers/deepgram/`) for reference.

### TTS Provider Steps

1. Create a class that inherits from `BaseTTSProvider` (in `src/services/tts/tts.py`).
2. Implement the `synthesize` method (streaming) and `synthesize_non_streaming`.
3. Register in `src/services/tts/tts.py`'s `TTS_PROVIDERS`.
4. Add environment variables.

### STT Provider Steps

1. Create a class that inherits from `BaseSTTProvider` (in `src/services/stt/stt.py`).
2. Implement the `transcribe` method.
3. Register in `src/services/stt/stt.py`'s `STT_PROVIDERS`.
4. Add environment variables.

## Adding a RAG Provider

### 1. Create the Provider File

Create `src/services/rag/providers/my_rag.py`:

```python
import logging
from typing import List, Optional
from services.rag.rag_models import BaseRagProvider, RagResult, RagChunk

logger = logging.getLogger(__name__)

class MyRagProvider(BaseRagProvider):
    """Custom RAG provider example."""

    def __init__(self, config: dict):
        super().__init__(config)
        # Initialize your vector DB client
        self.collection = config.get("collection_name")

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        **kwargs,
    ) -> List[RagChunk]:
        """Retrieve relevant chunks."""
        # Implement retrieval logic
        return [
            RagChunk(
                text="Example chunk",
                metadata={"source": "example.md"},
                score=0.95,
            )
        ]

    async def ingest(
        self,
        chunks: List[RagChunk],
        **kwargs,
    ) -> bool:
        """Ingest chunks into the vector database."""
        # Implement ingestion logic
        return True

    @property
    def name(self) -> str:
        return "my_rag"
```

### 2. Register the Provider

Edit `src/services/rag/rag_service.py` and add to `RAG_PROVIDERS`:

```python
from .providers.my_rag import MyRagProvider

RAG_PROVIDERS = {
    ...,
    "my_rag": MyRagProvider,
}
```

### 3. Define Configuration Fields

Update `src/services/rag/config_models.py` to include fields specific to your provider. The frontend will use these definitions to render the configuration form.

## Testing Your Provider

Write unit and integration tests for your provider. Follow the existing test patterns in `tests/integration/llm/`, `tests/integration/tts/`, etc.

Example test for LLM provider:

```python
import pytest
from services.llm.llm import get_llm_provider

@pytest.mark.asyncio
async def test_my_llm_provider():
    config = {"api_key": "test", "model": "test"}
    provider = get_llm_provider("my_llm", config)
    result = await provider.generate_non_streaming("Hello")
    assert isinstance(result.text, str)
```

## Updating the Frontend

If your provider should appear in the web interface (e.g., in agent creation dropdowns), you need to update the frontend constants.

- **LLM/TTS/STT providers**: Edit `src/front/lib/provider‑constants.ts`.
- **RAG providers**: Edit `src/front/components/rag/types.ts`.

## Environment Variables

Add any required environment variables to `.env.example` and document them in the [Configuration](../user‑guide/configuration.md) page.

## Contributing Back

If you believe your provider would be useful to others, consider contributing it to the main Stimm repository via a pull request.

## Next Steps

- Review the [Development Guide](development.md) for general development practices.
- Explore the [Testing Guide](testing.md) to ensure your provider works correctly.
- Check the [API Reference](../api/python.md) for detailed class definitions.
