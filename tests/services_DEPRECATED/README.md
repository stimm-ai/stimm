# Legacy Tests (Not Yet Migrated)

This directory contains tests that haven't been migrated to the new feature-based structure yet:

## STT Tests
- **`test_passthrough_behavior.py`** - Whisper-specific passthrough behavior tests
  - Tests chunk passthrough without modification
  - Tests empty chunk handling
  - Tests chunk order preservation

## TTS Tests
- **`test_tts_live_streaming.py`** - Complex TTS live streaming test
  - Large test file (477 lines) with CLI interface
  - Tests live streaming with agent configurations
  - Tests audio chunk recording and playback
  - Supports multiple providers via agent system

## Migration Status

These tests should eventually be:
1. Reviewed for relevance
2. Refactored to fit the new parametrized testing approach
3. Moved to `tests/integration/stt/` or `tests/integration/tts/`
4. This directory can then be deleted

For now, they remain functional here and can be run with:
```bash
PYTHONPATH=./src uv run pytest tests/services/ -v
```
