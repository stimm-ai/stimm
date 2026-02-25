# AGENT.md

This file is the implementation contract for AI agents working on app/extension
integration with `stimm`.

## Objectives

- Integrate Stimm's dual-agent runtime into an existing app.
- Keep provider onboarding wizard aligned with Stimm source-of-truth.
- Avoid runtime/import drift by using Stimm public APIs only.

## Hard Rules

- Use `get_provider_catalog()` for wizard discovery UI.
- Do not build discovery UI from `list_runtime_providers()`.
- Use `required_extras_for_selection(...)` or `extras_install_command(...)` to
  derive install commands.
- Install extras in the same environment that will run the app.
- Restart Python process after extras installation.
- Never store provider module paths/constructors in app config.
- Never expose secrets (API keys/tokens) in logs, telemetry, or UI snapshots.

## Integration Flow

### Phase 1 — Discover and Configure

1. Ensure base package is installed:

```bash
python -m pip install stimm
```

2. Read provider catalog:

```python
from stimm import get_provider_catalog
catalog = get_provider_catalog()
```

3. Render wizard sections from `catalog["stt"]`, `catalog["tts"]`,
   `catalog["llm"]`.

4. Parameter rendering rules:

- If `type` contains `Literal[...]`, render enum/select.
- Else use `presets` as suggestions and keep input editable.
- Respect `required`, `default`, and optional `description`.

### Phase 2 — Install and Activate

1. Compute extras from selected providers:

```python
from stimm import extras_install_command
cmd = extras_install_command(stt=chosen_stt, tts=chosen_tts, llm=chosen_llm)
```

2. Execute install command.
3. Restart process.
4. Instantiate provider classes.

## Data Model to Persist

Persist only user choices and parameter values:

```json
{
  "stt_provider": "deepgram",
  "tts_provider": "openai",
  "llm_provider": "azure-openai",
  "stt_params": {"model": "nova-3"},
  "tts_params": {"voice": "ash"},
  "llm_params": {"model": "gpt-4o-mini"}
}
```

## Troubleshooting

- If wizard shows too few model values: expected for docs-only providers.
- If provider list looks "static": this is expected source-of-truth behavior.
- If runtime fails after selection: verify extras install completed and process
  was restarted.

## References

- Root overview: [README.md](README.md)
- Wizard migration notes: [docs/EXTENSION_WIZARD_INTEGRATION.md](docs/EXTENSION_WIZARD_INTEGRATION.md)
