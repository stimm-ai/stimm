"""Talking to /ask: the request, its server-sent events, and spoken sentences.

/ask streams `meta`, `cite`, `delta` (text with [n] citation markers), `citations`,
then `done` or `error`. Nothing here knows whose twin it is: the URL and the session
token come from the deployment.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

import aiohttp

MAX_QUESTION_CHARS = 500
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 1500

# Citation markers, with the space before them: [1], [1, 2], [^1], 【1】, ［1］.
_MARKER = re.compile(r"\s*(?:\[\^?|【|［)\d+(?:\s*[,，]\s*\d+)*(?:\]|】|］)")
# The end of a sentence: punctuation followed by whitespace, or a line break.
_BOUNDARY = re.compile(r"(?<=[.!?…])\s+|\n+")
# Short words a period does not end: "M. Dupont", "Dr. Smith", "e.g. this".
_ABBREVIATION = re.compile(
    r"(?:^|\s)(?:\w|mr|mrs|ms|dr|st|mme|mlle|vs|cf|etc|e\.g|i\.e|p\.ex)\.$", re.IGNORECASE
)


def strip_markers(text: str) -> str:
    """The text without its citation markers, as it should be spoken or remembered."""
    return " ".join(_MARKER.sub("", text).split())


class SentenceSplitter:
    """Cuts streamed text into whole sentences, so each one is spoken as soon as it ends.

    A sentence ends at a line break, or at ., !, ? or … once the next word has
    started: "3." may still become "3.5". Markers are stripped from what it returns.
    """

    def __init__(self) -> None:
        self._buffer = ""

    def push(self, text: str) -> list[str]:
        self._buffer += text
        sentences: list[str] = []
        start = 0
        for boundary in _BOUNDARY.finditer(self._buffer):
            candidate = self._buffer[start : boundary.start()]
            if _ABBREVIATION.search(candidate):
                continue
            if sentence := strip_markers(candidate):
                sentences.append(sentence)
            start = boundary.end()
        self._buffer = self._buffer[start:]
        return sentences

    def flush(self) -> str:
        """Whatever is left once the stream is over."""
        rest, self._buffer = strip_markers(self._buffer), ""
        return rest


def history_for_ask(turns: list[tuple[str, str]]) -> list[dict[str, str]]:
    """The last turns in /ask's shape: at most 6 messages of at most 1500 characters."""
    messages = [
        {"role": role, "content": strip_markers(text)[:MAX_HISTORY_CHARS]}
        for role, text in turns
        if strip_markers(text)
    ]
    return messages[-MAX_HISTORY_MESSAGES:]


async def sse_events(lines: AsyncIterable[bytes]) -> AsyncIterator[tuple[str, Any]]:
    """Server-sent events as (event, parsed JSON data) pairs."""
    event, data = "message", []
    async for raw in lines:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                yield event, json.loads("\n".join(data))
            event, data = "message", []
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)


class AskError(Exception):
    """/ask answered with an HTTP error instead of a stream."""

    def __init__(self, status: int) -> None:
        super().__init__(f"/ask answered HTTP {status}")
        self.status = status


class AskClient:
    """POST /ask with the voice session token, and read the answer as it streams."""

    def __init__(self, http: aiohttp.ClientSession, url: str, token: str | None) -> None:
        self._http = http
        self._url = url
        self._token = token

    def __repr__(self) -> str:  # never print the token
        return f"AskClient({self._url!r})"

    async def stream(
        self, question: str, lang: str, history: list[dict[str, str]]
    ) -> AsyncIterator[tuple[str, Any]]:
        headers = {"Accept": "text/event-stream"}
        if self._token:
            headers["Authorization"] = f"Voice {self._token}"
        body = {"question": question[:MAX_QUESTION_CHARS], "lang": lang, "history": history}
        async with self._http.post(
            self._url,
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=45, sock_connect=5),
        ) as response:
            if response.status != 200:
                raise AskError(response.status)
            async for event in sse_events(response.content):
                yield event
