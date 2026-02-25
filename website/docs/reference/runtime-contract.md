---
id: reference-runtime-contract
title: Runtime Contract Reference
---

`providers_runtime.json` is the runtime execution contract.

Use these APIs:

- `list_runtime_providers(kind)`
- `required_extras_for_selection(...)`
- `extras_install_command(...)`

Runtime contract answers:

- Which provider IDs are supported at runtime.
- Which extras map to selected providers.

It is not the source for wizard discovery UI.
