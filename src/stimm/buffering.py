"""Pre-TTS text buffering strategies.

Controls how LLM tokens are batched before being sent to TTS.
The right buffering level balances latency (time-to-first-audio)
against speech naturalness (chunky vs. smooth delivery).
"""

from __future__ import annotations

from typing import Literal

BufferingLevel = Literal["NONE", "LOW", "MEDIUM", "HIGH"]


class TextBufferingStrategy:
    """Buffers LLM output tokens and emits chunks suitable for TTS.

    Levels:
        NONE:   Send every token immediately (lowest latency, choppiest speech).
        LOW:    Buffer until a word boundary (space character).
        MEDIUM: Buffer until 4+ words OR punctuation (good default).
        HIGH:   Buffer until sentence boundary (punctuation only).
    """

    PUNCTUATION = ".!?;:"

    def __init__(self, level: BufferingLevel = "MEDIUM") -> None:
        self.level = level
        self._buffer = ""

    def feed(self, token: str) -> str | None:
        """Feed an LLM token. Returns text to send to TTS, or ``None`` if still buffering."""
        self._buffer += token

        if self.level == "NONE":
            result = self._buffer
            self._buffer = ""
            return result

        if self.level == "LOW":
            if " " in self._buffer:
                # Split at the last space — emit everything before it,
                # keep the partial word after it in the buffer.
                head, tail = self._buffer.rsplit(" ", 1)
                self._buffer = tail
                return head + " "

        elif self.level == "MEDIUM":
            words = self._buffer.split()
            has_punctuation = any(c in self._buffer for c in self.PUNCTUATION)
            if len(words) >= 4 or has_punctuation:
                result = self._buffer
                self._buffer = ""
                return result

        elif self.level == "HIGH":
            if any(c in self._buffer for c in self.PUNCTUATION):
                result = self._buffer
                self._buffer = ""
                return result

        return None

    def flush(self) -> str | None:
        """Flush any remaining buffer content (call at end of LLM stream)."""
        if self._buffer:
            result = self._buffer
            self._buffer = ""
            return result
        return None

    def reset(self) -> None:
        """Clear the buffer without emitting."""
        self._buffer = ""
