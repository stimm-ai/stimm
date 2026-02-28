#!/usr/bin/env python3
"""Validate runtime provider contract against docs-synced providers catalog."""

from __future__ import annotations

import json
import os
import subprocess
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
        # Determine the Python executable to use for import checks.
        # Accepts --python-exe=<path> so callers can point at an isolated venv
        # where provider packages are installed (e.g. the build venv created by
        # sync_livekit_plugins.py) rather than the current interpreter which may
        # not have those packages installed.
        python_exe = sys.executable
        for arg in sys.argv:
            if arg.startswith("--python-exe="):
                python_exe = arg.split("=", 1)[1]
                break

        for kind in ("stt", "tts", "llm"):
            for entry in runtime.get(kind, []):
                if not isinstance(entry, dict):
                    continue
                module = entry.get("module")
                provider_id = entry.get("id")
                if isinstance(module, str):
                    try:
                        clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
                        result = subprocess.run(
                            [python_exe, "-c", f"import {module}"],
                            capture_output=True,
                            text=True,
                            env=clean_env,
                            cwd="/tmp",
                        )
                        if result.returncode != 0:
                            exc_msg = (
                                result.stderr.strip().splitlines()[-1]
                                if result.stderr.strip()
                                else "unknown error"
                            )
                            errors.append(
                                f"cannot import module for {kind}:{provider_id}:"
                                f" {module} ({exc_msg})"
                            )
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
