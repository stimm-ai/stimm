---
id: getting-started-quickstart
title: Quick Start
---

## Voice Agent (Python)

```python
from stimm import VoiceAgent
from livekit.plugins import deepgram, openai, silero

agent = VoiceAgent(
    stt=deepgram.STT(),
    tts=openai.TTS(),
    vad=silero.VAD.load(),
    fast_llm=openai.LLM(model="gpt-4o-mini"),
    mode="hybrid",
)
```

## Supervisor (TypeScript)

```typescript
import { StimmSupervisorClient } from "@stimm/protocol";

const client = new StimmSupervisorClient({
  livekitUrl: "ws://localhost:7880",
  token: supervisorToken,
});

await client.connect();
```
