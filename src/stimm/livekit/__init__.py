"""Lightweight stub package for livekit used only in runtime validation.

This package provides a `plugins` subpackage with minimal module stubs so
`importlib.import_module` succeeds during CI import-checks.
"""

__all__ = ["plugins"]
