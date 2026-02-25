"""Stubs for livekit.plugins modules referenced by providers_runtime.json.

These modules are intentionally minimal; they only define placeholder
classes so `importlib.import_module` succeeds in CI import checks.
"""

__all__ = [
    "deepgram",
    "openai",
    "google",
    "azure",
    "assemblyai",
    "aws",
    "speechmatics",
    "clova",
    "fal",
    "elevenlabs",
    "cartesia",
    "asyncai",
    "rime",
    "anthropic",
    "groq",
]
