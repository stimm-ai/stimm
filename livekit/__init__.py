"""Repo-root livekit stub package for CI import-check.

This mirrors the minimal structure used under `src/` but exposes
`livekit.plugins.*` at top-level import paths for `importlib` during CI.
"""

__path__ = __import__("pkgutil").extend_path(__path__, __name__)
__all__ = ["plugins"]
