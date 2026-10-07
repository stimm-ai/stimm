"""Tests for the LiveKit llms.txt parser in scripts/sync_livekit_plugins.py."""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "sync_livekit_plugins", REPO_ROOT / "scripts" / "sync_livekit_plugins.py"
)
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)

AGENTS_URL = "https://docs.livekit.io/agents/llms.txt"
AGENTS_INDEX = (Path(__file__).parent / "fixtures" / "livekit_agents_llms.txt").read_text(
    encoding="utf-8"
)
ROOT_INDEX = """# LiveKit docs

## Documentation sections

- [Introduction](https://docs.livekit.io/intro/llms.txt): What LiveKit is.
- [Build Agents](https://docs.livekit.io/agents/llms.txt): The LiveKit Agents framework.

## Full documentation

- [Complete documentation](https://docs.livekit.io/llms-full.txt): Every page, inlined.
"""


def _ids(catalog: dict, kind: str) -> list[str]:
    return [provider["id"] for provider in catalog[kind]]


def test_parses_the_section_index_layout() -> None:
    catalog = sync.build_updated_catalog(AGENTS_INDEX, {}, source_url=AGENTS_URL)

    assert _ids(catalog, "llm") == ["livekit", "openai", "anthropic", "mistralai"]
    # Capabilities guides are not providers, and Realtime / Partner spotlight
    # links stay out of the sections above them.
    assert _ids(catalog, "stt") == ["deepgram", "mistralai"]
    assert _ids(catalog, "tts") == ["cartesia", "elevenlabs", "mistralai"]
    assert catalog["tts"][1]["label"] == "ElevenLabs"
    assert catalog["tts"][1]["api"]["docsUrl"] == (
        "https://docs.livekit.io/agents/models/tts/elevenlabs.md"
    )
    assert catalog["_source"]["livekit"] == AGENTS_URL


def test_parses_the_old_inline_layout() -> None:
    old_root = (
        AGENTS_INDEX.replace("\n#### ", "\n##### ")
        .replace("\n### ", "\n#### ")
        .replace("\n## ", "\n### ")
    )
    catalog = sync.build_updated_catalog(old_root, {})
    assert _ids(catalog, "stt") == ["deepgram", "mistralai"]


def test_follows_the_root_index_to_the_section_index(monkeypatch) -> None:
    pages = {
        sync.LLMS_TXT_URL: ROOT_INDEX,
        "https://docs.livekit.io/intro/llms.txt": "# Introduction\n\n## Rooms\n",
        AGENTS_URL: AGENTS_INDEX,
    }
    monkeypatch.setattr(sync, "_fetch_text", lambda url, timeout=20: pages[url])

    assert sync._fetch_models_index(sync.LLMS_TXT_URL) == (AGENTS_URL, AGENTS_INDEX)


def test_fails_clearly_when_the_sections_vanish(monkeypatch) -> None:
    pages = {
        sync.LLMS_TXT_URL: ROOT_INDEX,
        "https://docs.livekit.io/intro/llms.txt": "# Introduction\n",
        AGENTS_URL: AGENTS_INDEX.replace("### STT", "### Speech-to-text"),
    }
    monkeypatch.setattr(sync, "_fetch_text", lambda url, timeout=20: pages[url])

    with pytest.raises(ValueError, match="LiveKit changed its docs layout"):
        sync._fetch_models_index(sync.LLMS_TXT_URL)


def test_fails_clearly_when_a_section_lists_no_plugin() -> None:
    no_llm_links = AGENTS_INDEX.replace("/agents/models/llm/", "/agents/llm-models/")
    with pytest.raises(ValueError, match="Section 'LLM' lists no plugin page"):
        sync.build_updated_catalog(no_llm_links, {})
