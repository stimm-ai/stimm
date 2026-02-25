#!/usr/bin/env python3
"""Validate runtime provider contract against docs-synced providers catalog."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "src" / "stimm" / "providers.json"
RUNTIME_PATH = REPO_ROOT / "src" / "stimm" / "providers_runtime.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ids_for_kind(data: dict[str, Any], kind: str) -> set[str]:
    items = data.get(kind, [])
    out: set[str] = set()
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                out.add(item["id"])
    return out


def main() -> int:
    catalog = _read_json(CATALOG_PATH)
    runtime = _read_json(RUNTIME_PATH)

    errors: list[str] = []

    for kind in ("stt", "tts", "llm"):
        catalog_ids = _ids_for_kind(catalog, kind)
        runtime_ids = _ids_for_kind(runtime, kind)

        for provider_id in sorted(runtime_ids):
            if provider_id not in catalog_ids:
                errors.append(f"runtime provider '{kind}:{provider_id}' missing in providers.json")

        aliases = runtime.get("aliases", {}).get(kind, {})
        if not isinstance(aliases, dict):
            errors.append(f"aliases.{kind} must be an object")
            continue

        for source, target in sorted(aliases.items()):
            if source in runtime_ids:
                errors.append(f"aliases.{kind}.{source} duplicates an explicit runtime provider id")
            if target not in runtime_ids:
                errors.append(
                    f"aliases.{kind}.{source} -> '{target}' is not a declared runtime provider"
                )

        entries = runtime.get(kind, [])
        if not isinstance(entries, list):
            errors.append(f"runtime section '{kind}' must be an array")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f"runtime section '{kind}' contains a non-object entry")
                continue
            module = entry.get("module")
            provider_id = entry.get("id")
            constructor = entry.get("constructor")
            if not isinstance(module, str) or not module:
                errors.append(f"runtime provider '{kind}:{provider_id}' has invalid module")
            if not isinstance(constructor, str) or not constructor:
                errors.append(f"runtime provider '{kind}:{provider_id}' has invalid constructor")

    if "--import-check" in sys.argv:
        for kind in ("stt", "tts", "llm"):
            for entry in runtime.get(kind, []):
                if not isinstance(entry, dict):
                    continue
                module = entry.get("module")
                provider_id = entry.get("id")
                if isinstance(module, str):
                    try:
                        importlib.import_module(module)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(
                            f"cannot import module for {kind}:{provider_id}: {module} ({exc})"
                        )

    if errors:
        print("Runtime contract validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Runtime contract is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
