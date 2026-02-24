"""
Provider catalog for stimm.

Loads providers.json (source of truth for provider metadata, API endpoints, and model presets)
and exposes it as a typed dict for use by stimm internals and external tools such as the
openclaw stimm-voice setup wizard.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def load_catalog() -> dict[str, Any]:
    """Return the full provider catalog parsed from providers.json."""
    data = files("stimm").joinpath("providers.json").read_text(encoding="utf-8")
    return json.loads(data)


CATALOG: dict[str, Any] = load_catalog()
