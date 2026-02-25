"""Provider catalog for stimm.

Loads ``providers.json`` and exposes it as a typed dict for use by stimm
internals and external tools such as the openclaw stimm-voice setup wizard.

The official plugin list is synced from https://docs.livekit.io/llms.txt via
``scripts/sync_livekit_plugins.py``.

Runtime-safe provider mappings are stored separately in
``providers_runtime.json``.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def load_catalog() -> dict[str, Any]:
    """Return the full provider catalog parsed from providers.json."""
    data = files("stimm").joinpath("providers.json").read_text(encoding="utf-8")
    return json.loads(data)


def load_runtime_contract() -> dict[str, Any]:
    """Return runtime provider contract parsed from providers_runtime.json."""
    data = files("stimm").joinpath("providers_runtime.json").read_text(encoding="utf-8")
    return json.loads(data)


def resolve_runtime_provider(kind: str, provider_id: str) -> dict[str, Any] | None:
    """Resolve a runtime provider entry for *kind* and *provider_id*.

    Applies aliases defined in ``providers_runtime.json``.
    """
    entries = RUNTIME_CONTRACT.get(kind, [])
    if not isinstance(entries, list):
        return None

    aliases = RUNTIME_CONTRACT.get("aliases", {}).get(kind, {})
    if isinstance(aliases, dict):
        provider_id = aliases.get(provider_id, provider_id)

    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == provider_id:
            return entry
    return None


CATALOG: dict[str, Any] = load_catalog()
RUNTIME_CONTRACT: dict[str, Any] = load_runtime_contract()
