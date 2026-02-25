---
id: reference-providers-catalog
title: Provider Catalog Reference
---

Use `get_provider_catalog()` to get metadata for `stt`, `tts`, and `llm` providers.

Each provider contains:

- `id`
- `label`
- `defaultModel`
- `presets`
- `api`
- `parameters`

Each parameter typically includes:

- `name`
- `required`
- `default`
- `type`
- `source`
- optional `description`

### Rendering guidance

- `Literal[...]` types can be rendered as strict select values.
- Otherwise, use presets as suggestions and keep input editable.
