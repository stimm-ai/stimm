"""Provider catalog for stimm.

Loads ``providers.json`` and exposes it as a typed dict for use by stimm
internals and external tools such as the openclaw stimm-voice setup wizard.

The official plugin list is synced from https://docs.livekit.io/llms.txt via
``scripts/sync_livekit_plugins.py``.

Runtime-safe provider mappings are stored separately in
``providers_runtime.json``.
"""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from typing import Any, Literal

ProviderKind = Literal["stt", "tts", "llm"]
PROVIDER_KINDS: tuple[ProviderKind, ...] = ("stt", "tts", "llm")


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


def get_provider_catalog() -> dict[str, Any]:
    """Return a deep copy of the synced provider catalog.

    This is intended for app-side onboarding flows (wizard / settings UI).
    """
    return copy.deepcopy(CATALOG)


def list_providers(kind: ProviderKind) -> list[dict[str, Any]]:
    """Return provider entries for one kind from the synced catalog."""
    providers = CATALOG.get(kind, [])
    if not isinstance(providers, list):
        return []
    return copy.deepcopy(providers)


def get_provider(kind: ProviderKind, provider_id: str) -> dict[str, Any] | None:
    """Return one provider metadata entry from the synced catalog."""
    for provider in list_providers(kind):
        if provider.get("id") == provider_id:
            return provider
    return None


def list_runtime_providers(kind: ProviderKind) -> list[dict[str, Any]]:
    """Return runtime-supported providers for one kind."""
    providers = RUNTIME_CONTRACT.get(kind, [])
    if not isinstance(providers, list):
        return []
    return copy.deepcopy(providers)


def required_extra_for_provider(kind: ProviderKind, provider_id: str) -> str | None:
    """Return the pip extra needed for one provider choice.

    The extra is inferred from the runtime module namespace
    (``livekit.plugins.<extra>``).
    """
    resolved = resolve_runtime_provider(kind, provider_id)
    if not resolved:
        return None

    module = resolved.get("module")
    if not isinstance(module, str):
        return None

    parts = module.split(".")
    if len(parts) < 3:
        return None
    return parts[2]


def required_extras_for_selection(
    *,
    stt: str | None = None,
    tts: str | None = None,
    llm: str | None = None,
) -> list[str]:
    """Return sorted unique extras required for a full provider selection."""
    extras: set[str] = set()
    selections = (("stt", stt), ("tts", tts), ("llm", llm))
    for kind, provider_id in selections:
        if not provider_id:
            continue
        extra = required_extra_for_provider(kind, provider_id)
        if extra:
            extras.add(extra)
    return sorted(extras)


def extras_install_command(
    *,
    stt: str | None = None,
    tts: str | None = None,
    llm: str | None = None,
) -> str | None:
    """Return a ready-to-run pip command for selected providers.

    Returns ``None`` when no extra is required/derivable.
    """
    extras = required_extras_for_selection(stt=stt, tts=tts, llm=llm)
    if not extras:
        return None
    return f"pip install stimm[{','.join(extras)}]"


CATALOG: dict[str, Any] = load_catalog()
RUNTIME_CONTRACT: dict[str, Any] = load_runtime_contract()
