#!/usr/bin/env python3
"""Build stimm provider catalog from LiveKit docs + runtime introspection.

Single source of truth for provider catalog generation:
1) discover official plugins from ``https://docs.livekit.io/llms.txt`` (or the
   per-section index it links to that holds the model plugin lists)
2) install runtime plugin packages declared in ``providers_runtime.json``
3) introspect runtime constructors to generate authoritative parameters
4) enrich parameters from plugin docs pages

No fallback or legacy extraction path is used for parameter generation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

LLMS_TXT_URL = "https://docs.livekit.io/llms.txt"

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "src" / "stimm" / "providers.json"
RUNTIME_PATH = REPO_ROOT / "src" / "stimm" / "providers_runtime.json"
DEFAULT_BUILD_VENV = REPO_ROOT / ".stimm-build-venv"

DOC_PARAM_LINE_RE = re.compile(
    r"^\s*[-*]\s+`([a-zA-Z_][a-zA-Z0-9_]*)`\s*[:\-]?\s*(.*)$", flags=re.M
)

# Catalog kind -> title of the llms.txt heading that lists its plugins.
MODEL_SECTIONS = {"llm": "LLM", "stt": "STT", "tts": "TTS"}
# Sub-headings inside a model section that list feature guides (STT keyterms,
# TTS custom voices...), not providers.
NON_PROVIDER_SUBSECTIONS = {"Capabilities"}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SECTION_INDEX_RE = re.compile(r"\((https://docs\.livekit\.io/\S+/llms\.txt)\)")


def _fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "stimm-sync/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _section_lines(content: str, title: str) -> list[str] | None:
    """Lines under the heading ``title``, whatever its level, up to the next
    heading of the same or a higher level. ``None`` if there is no such heading."""
    lines = content.splitlines()
    for start, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if heading and heading.group(2) == title:
            level = len(heading.group(1))
            body: list[str] = []
            for following in lines[start + 1 :]:
                nested = HEADING_RE.match(following)
                if nested and len(nested.group(1)) <= level:
                    break
                body.append(following)
            return body
    return None


def _has_model_sections(content: str) -> bool:
    return all(_section_lines(content, title) is not None for title in MODEL_SECTIONS.values())


def _fetch_models_index(url: str, timeout: int = 20) -> tuple[str, str]:
    """Return ``(url, text)`` of the llms.txt that lists the model plugins.

    LiveKit's root llms.txt used to inline every docs page. Since late August 2026
    it only links to one llms.txt per docs section, and the plugin lists live in
    the agents one. Accept both layouts by following those links one level deep.
    """
    content = _fetch_text(url, timeout=timeout)
    if _has_model_sections(content):
        return url, content
    for index_url in dict.fromkeys(SECTION_INDEX_RE.findall(content)):
        index = _fetch_text(index_url, timeout=timeout)
        if _has_model_sections(index):
            return index_url, index
    sections = ", ".join(f"'{title}'" for title in MODEL_SECTIONS.values())
    raise ValueError(
        f"No llms.txt with {sections} plugin sections found at {url} or in the section "
        "indexes it links to. LiveKit changed its docs layout: update "
        "_fetch_models_index / _extract_plugins in scripts/sync_livekit_plugins.py."
    )


def _load_runtime_contract() -> dict[str, Any]:
    return json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))


def _runtime_entries(contract: dict[str, Any], kind: str) -> list[dict[str, str]]:
    entries = contract.get(kind, [])
    out: list[dict[str, str]] = []
    if not isinstance(entries, list):
        raise ValueError(f"runtime contract section '{kind}' must be a list")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"runtime contract section '{kind}' contains non-object entry")
        provider_id = entry.get("id")
        module = entry.get("module")
        constructor = entry.get("constructor")
        if not isinstance(provider_id, str) or not provider_id:
            raise ValueError(f"invalid provider id in runtime contract section '{kind}'")
        if not isinstance(module, str) or not module:
            raise ValueError(f"invalid module for provider '{kind}:{provider_id}'")
        if not isinstance(constructor, str) or not constructor:
            raise ValueError(f"invalid constructor for provider '{kind}:{provider_id}'")
        out.append({"id": provider_id, "module": module, "constructor": constructor})
    return out


def _ensure_build_venv(base_python: str, venv_dir: Path) -> str:
    python_path = venv_dir / "bin" / "python"
    if not python_path.exists():
        subprocess.run([base_python, "-m", "venv", str(venv_dir)], check=True)
    return str(python_path)


def _introspect_parameters(entry: dict[str, str], python_exe: str) -> list[dict[str, Any]]:
    helper = r"""
import importlib
import inspect
import json
import sys

module_name = sys.argv[1]
ctor_path = sys.argv[2]

def annotation_to_string(annotation):
    if annotation is inspect._empty:
        return None
    if isinstance(annotation, str):
        return annotation
    return str(annotation).replace("typing.", "")

def default_to_jsonable(default):
    if default is inspect._empty:
        return None
    if isinstance(default, (str, int, float, bool)) or default is None:
        return default
    if isinstance(default, (list, tuple)):
        return list(default)
    if isinstance(default, dict):
        return default
    return repr(default)

target = importlib.import_module(module_name)
for part in ctor_path.split('.'):
    target = getattr(target, part)

signature = inspect.signature(target)
out = []
for parameter in signature.parameters.values():
    if parameter.name == "self":
        continue
    if parameter.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
        continue
    out.append({
        "name": parameter.name,
        "required": parameter.default is inspect._empty,
        "default": default_to_jsonable(parameter.default),
        "type": annotation_to_string(parameter.annotation),
        "source": "runtime-introspection",
    })

print(json.dumps(out))
"""
    env = os.environ.copy()
    # Only expose src/ to the isolated interpreter so local stubs are importable.
    # Explicitly exclude the repo root from PYTHONPATH: the top-level livekit/
    # directory would shadow installed packages (e.g. livekit.agents) and cause
    # ImportError during introspection.
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    completed = subprocess.run(
        [python_exe, "-c", helper, entry["module"], entry["constructor"]],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
    )
    return json.loads(completed.stdout)


def _extract_doc_descriptions(markdown: str) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for name, description in DOC_PARAM_LINE_RE.findall(markdown):
        text = re.sub(r"\s+", " ", description.strip())
        if name not in descriptions and text:
            descriptions[name] = text
    return descriptions


def _install_runtime_plugins(contract: dict[str, Any], python_exe: str) -> None:
    modules: set[str] = set()
    for kind in ("stt", "tts", "llm"):
        for entry in _runtime_entries(contract, kind):
            module = entry["module"]
            if not module.startswith("livekit.plugins."):
                raise ValueError(f"unsupported runtime module namespace: {module}")
            modules.add(module.removeprefix("livekit.plugins."))

    packages = [f"livekit-plugins-{name}>=1.8" for name in sorted(modules)]
    if not packages:
        return

    cmd = [
        python_exe,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--quiet",
        *packages,
    ]
    subprocess.run(cmd, check=True)


def build_parameters_from_runtime(
    catalog: dict[str, Any],
    runtime_contract: dict[str, Any],
    timeout: int,
    python_exe: str,
) -> dict[str, Any]:
    updated = dict(catalog)
    docs_cache: dict[str, dict[str, str]] = {}

    for kind in ("stt", "tts", "llm"):
        by_id = {entry["id"]: entry for entry in _runtime_entries(runtime_contract, kind)}
        providers = updated.get(kind, [])
        if not isinstance(providers, list):
            continue

        for provider in providers:
            if not isinstance(provider, dict):
                continue
            provider_id = provider.get("id")
            if not isinstance(provider_id, str):
                continue

            runtime_entry = by_id.get(provider_id)
            if runtime_entry is None:
                continue

            params = _introspect_parameters(runtime_entry, python_exe=python_exe)

            api = provider.get("api")
            docs_url = api.get("docsUrl") if isinstance(api, dict) else None
            if isinstance(docs_url, str) and docs_url:
                if docs_url not in docs_cache:
                    markdown = _fetch_text(docs_url, timeout=timeout)
                    docs_cache[docs_url] = _extract_doc_descriptions(markdown)
                doc_descriptions = docs_cache[docs_url]
                for param in params:
                    description = doc_descriptions.get(param["name"])
                    if description:
                        param["description"] = description
                        param["docSource"] = docs_url

            provider["parameters"] = params

    return updated


def _extract_plugins(content: str, section: str) -> list[dict[str, str]]:
    lines = _section_lines(content, section)
    if lines is None:
        raise ValueError(f"Section '{section}' not found in llms.txt")

    # Match plugin doc URLs under this section.
    # URL pattern: /agents/models/{section}/{slug} (e.g. /agents/models/llm/openai.md).
    # The overview URL ends in /{section}.md (no sub-path slash) so it won't match.
    pattern = re.compile(
        rf"\[([^\]]+)\]\((https://docs\.livekit\.io/agents/models/{section.lower()}/[^)]+)\)"
    )

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    skipping = False
    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            skipping = heading.group(2) in NON_PROVIDER_SUBSECTIONS
            continue
        if skipping:
            continue
        for label, docs_url in pattern.findall(line):
            slug = docs_url.rsplit("/", 1)[-1].replace(".md", "")
            if slug in seen:
                continue
            seen.add(slug)
            out.append({"id": slug, "label": label, "docsUrl": docs_url})
    if not out:
        raise ValueError(
            f"Section '{section}' lists no plugin page "
            f"(https://docs.livekit.io/agents/models/{section.lower()}/<plugin>.md)"
        )
    return out


def _default_entry(kind: str, item: dict[str, str]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": item["id"],
        "label": item["label"],
        "defaultModel": "default",
        "presets": ["default"],
        "parameters": [],
        "api": {
            "kind": "livekit-docs",
            "docsUrl": item["docsUrl"],
        },
    }
    if kind == "tts":
        entry["defaultVoice"] = "default"
    return entry


def _merge_kind(
    existing: list[dict[str, Any]], discovered: list[dict[str, str]], kind: str
) -> list[dict[str, Any]]:
    existing_by_id = {item.get("id"): item for item in existing if isinstance(item, dict)}
    merged: list[dict[str, Any]] = []

    for plugin in discovered:
        current = existing_by_id.get(plugin["id"])
        if current is None:
            current = _default_entry(kind, plugin)
        current["id"] = plugin["id"]
        current["label"] = plugin["label"]

        api = current.get("api")
        if not isinstance(api, dict):
            api = {}
            current["api"] = api
        api.setdefault("kind", "livekit-docs")
        api["docsUrl"] = plugin["docsUrl"]

        merged.append(current)

    return merged


def build_updated_catalog(
    llms_txt: str, current_catalog: dict[str, Any], source_url: str = LLMS_TXT_URL
) -> dict[str, Any]:
    updated = dict(current_catalog)
    updated["_comment"] = (
        "Source of truth for stimm provider metadata. Plugin list is synced from "
        "https://docs.livekit.io/llms.txt via scripts/sync_livekit_plugins.py."
    )
    updated["_source"] = {
        "livekit": source_url,
        "syncedBy": "scripts/sync_livekit_plugins.py",
    }
    for kind, section in MODEL_SECTIONS.items():
        discovered = _extract_plugins(llms_txt, section=section)
        updated[kind] = _merge_kind(current_catalog.get(kind, []), discovered, kind=kind)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync stimm provider catalog from LiveKit llms.txt"
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if providers.json is out of date"
    )
    parser.add_argument("--url", default=LLMS_TXT_URL, help="Override llms.txt URL")
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds for LiveKit docs fetches",
    )
    parser.add_argument(
        "--python-exe",
        default=sys.executable,
        help="Base Python executable used to create build virtual environment",
    )
    parser.add_argument(
        "--build-venv",
        default=str(DEFAULT_BUILD_VENV),
        help="Path to the isolated virtualenv used for plugin install + introspection",
    )
    args = parser.parse_args()

    if not CATALOG_PATH.exists():
        print(f"Catalog file not found: {CATALOG_PATH}", file=sys.stderr)
        return 2

    current_text = CATALOG_PATH.read_text(encoding="utf-8")
    current_catalog = json.loads(current_text)
    runtime_contract = _load_runtime_contract()

    # Parse the docs first: a layout change should fail in seconds, not after
    # installing every plugin.
    try:
        index_url, llms_txt = _fetch_models_index(args.url, timeout=args.timeout)
        updated_catalog = build_updated_catalog(llms_txt, current_catalog, source_url=index_url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    build_python = _ensure_build_venv(args.python_exe, Path(args.build_venv))
    _install_runtime_plugins(runtime_contract, build_python)
    updated_catalog = build_parameters_from_runtime(
        updated_catalog,
        runtime_contract=runtime_contract,
        timeout=args.timeout,
        python_exe=build_python,
    )
    updated_text = json.dumps(updated_catalog, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        if updated_text != current_text:
            print("providers.json is out of sync with LiveKit llms.txt")
            print("Run: python3 scripts/sync_livekit_plugins.py")
            return 1
        print("providers.json is up to date")
        return 0

    CATALOG_PATH.write_text(updated_text, encoding="utf-8")
    print(f"Updated {CATALOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
