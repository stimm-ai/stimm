#!/usr/bin/env python3
"""Sync stimm provider catalog from LiveKit llms.txt.

This script treats https://docs.livekit.io/llms.txt as source of truth for
the official plugin list (LLM/STT/TTS).

It updates ``src/stimm/providers.json`` by:
- preserving existing provider metadata when present
- adding missing providers discovered in llms.txt
- updating provider docs URL metadata
- keeping provider order aligned with llms.txt

Usage:
  python3 scripts/sync_livekit_plugins.py
  python3 scripts/sync_livekit_plugins.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

LLMS_TXT_URL = "https://docs.livekit.io/llms.txt"

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "src" / "stimm" / "providers.json"


def _fetch_llms_txt(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8")


def _extract_plugins(content: str, section: str, next_section: str) -> list[dict[str, str]]:
    block_match = re.search(
        rf"#### {re.escape(section)}(.*?)(?=#### {re.escape(next_section)})",
        content,
        flags=re.S,
    )
    if not block_match:
        raise ValueError(f"Section '{section}' not found in llms.txt")

    block = block_match.group(1)
    plugins_match = re.search(r"##### Plugins(.*)", block, flags=re.S)
    if not plugins_match:
        raise ValueError(f"Plugins subsection missing under '{section}'")

    plugins_block = plugins_match.group(1)
    plugins_block = plugins_block.split("#### ", 1)[0]

    pattern = re.compile(
        rf"\[([^\]]+)\]\((https://docs\.livekit\.io/agents/models/{section.lower()}/plugins/[^)]+)\)"
    )

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for label, docs_url in pattern.findall(plugins_block):
        slug = docs_url.rsplit("/", 1)[-1].replace(".md", "")
        if slug in seen:
            continue
        seen.add(slug)
        out.append({"id": slug, "label": label, "docsUrl": docs_url})
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


def build_updated_catalog(llms_txt: str, current_catalog: dict[str, Any]) -> dict[str, Any]:
    llm = _extract_plugins(llms_txt, section="LLM", next_section="STT")
    stt = _extract_plugins(llms_txt, section="STT", next_section="TTS")
    tts = _extract_plugins(llms_txt, section="TTS", next_section="Realtime")

    updated = dict(current_catalog)
    updated["_comment"] = (
        "Source of truth for stimm provider metadata. Plugin list is synced from "
        "https://docs.livekit.io/llms.txt via scripts/sync_livekit_plugins.py."
    )
    updated["_source"] = {
        "livekit": LLMS_TXT_URL,
        "syncedBy": "scripts/sync_livekit_plugins.py",
    }
    updated["stt"] = _merge_kind(current_catalog.get("stt", []), stt, kind="stt")
    updated["tts"] = _merge_kind(current_catalog.get("tts", []), tts, kind="tts")
    updated["llm"] = _merge_kind(current_catalog.get("llm", []), llm, kind="llm")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync stimm provider catalog from LiveKit llms.txt"
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if providers.json is out of date"
    )
    parser.add_argument("--url", default=LLMS_TXT_URL, help="Override llms.txt URL")
    args = parser.parse_args()

    if not CATALOG_PATH.exists():
        print(f"Catalog file not found: {CATALOG_PATH}", file=sys.stderr)
        return 2

    current_text = CATALOG_PATH.read_text(encoding="utf-8")
    current_catalog = json.loads(current_text)

    llms_txt = _fetch_llms_txt(args.url)
    updated_catalog = build_updated_catalog(llms_txt, current_catalog)
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
