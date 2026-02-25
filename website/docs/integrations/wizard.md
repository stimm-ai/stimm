---
id: integrations-wizard
title: Installation Wizard Integration
---

This guide explains how to integrate Stimm into an app installation wizard.

## Correct flow

1. Install base package: `pip install stimm`
2. Read provider catalog with `get_provider_catalog()`
3. Let user choose providers and parameters
4. Compute extras with `required_extras_for_selection(...)` or `extras_install_command(...)`
5. Install extras
6. Restart Python process

## API usage

- Discovery UI: `get_provider_catalog()`
- Optional runtime contract visibility: `list_runtime_providers(kind)`
- Install resolution: `required_extras_for_selection(...)`, `extras_install_command(...)`

## Example

```python
from stimm import extras_install_command, get_provider_catalog

catalog = get_provider_catalog()  # exhaustive stt/tts/llm + parameters
cmd = extras_install_command(stt="deepgram", tts="openai", llm="azure-openai")
print(cmd)  # pip install stimm[deepgram,openai]
```

## Important

Use provider catalog for wizard discovery. Runtime provider lists are execution contracts and are not a replacement for discovery metadata.
