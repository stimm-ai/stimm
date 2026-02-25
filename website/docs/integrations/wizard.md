---
id: integrations-wizard
title: Installation Wizard Integration
---

## Two-phase flow

1. Install base package (`pip install stimm`).
2. Read provider catalog and render provider/parameter UI.
3. Collect user choices.
4. Compute extras and install them.
5. Restart Python process.

## Required API usage

```python
from stimm import get_provider_catalog, extras_install_command

catalog = get_provider_catalog()
cmd = extras_install_command(stt="deepgram", tts="openai", llm="azure-openai")
# pip install stimm[deepgram,openai]
```

Use catalog data for discovery UI. Do not use runtime contract lists as a substitute for wizard discovery.
