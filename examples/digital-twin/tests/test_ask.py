"""Markers, sentences, history and the SSE stream of /ask."""

from pathlib import Path

import pytest
from ask import SentenceSplitter, history_for_ask, sse_events, strip_markers

FIXTURE = Path(__file__).parent / "fixtures" / "ask_answer.sse"


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("I joined Example [1].", "I joined Example."),
        ("Two teams [1][2], then", "Two teams, then"),
        ("Grew [1, 2] fast", "Grew fast"),
        ("Footnote [^3] style", "Footnote style"),
        ("Fullwidth 【4】 and ［5］ too", "Fullwidth and too"),
        ("Keeps [links] and v2.5", "Keeps [links] and v2.5"),
    ],
)
def test_strip_markers(text: str, spoken: str) -> None:
    assert strip_markers(text) == spoken


def test_sentences_come_out_as_soon_as_they_end() -> None:
    splitter = SentenceSplitter()
    assert splitter.push("I joined Example in 2019 [1]. Then the team") == [
        "I joined Example in 2019."
    ]
    assert splitter.push(" grew from 3 to 12 people.") == []  # the next word has not started
    assert splitter.flush() == "Then the team grew from 3 to 12 people."


@pytest.mark.parametrize(
    ("chunks", "sentences"),
    [
        (["We had 3.", "5 million users. Then"], ["We had 3.5 million users."]),
        (["Widget 2.5 shipped. Then"], ["Widget 2.5 shipped."]),
        (["M. Dupont hired me. Then"], ["M. Dupont hired me."]),
        (["See e.g. this one. Then"], ["See e.g. this one."]),
        (["Vraiment ? Oui ! Bon… Alors"], ["Vraiment ?", "Oui !", "Bon…"]),
        (["First line\nSecond"], ["First line"]),
    ],
)
def test_sentence_boundaries(chunks: list[str], sentences: list[str]) -> None:
    splitter = SentenceSplitter()
    assert [s for chunk in chunks for s in splitter.push(chunk)] == sentences


def test_history_is_trimmed_to_what_ask_accepts() -> None:
    turns = [("user", f"question {i}") for i in range(7)] + [
        ("assistant", "Answer [1]. " + "x" * 2000),
        ("assistant", " [2] "),  # nothing left once the marker is gone
    ]
    history = history_for_ask(turns)
    assert len(history) == 6
    assert history[0] == {"role": "user", "content": "question 2"}
    assert history[-1]["content"].startswith("Answer. x")
    assert len(history[-1]["content"]) == 1500


async def _lines(path: Path):  # type: ignore[no-untyped-def]
    for line in path.read_bytes().splitlines(keepends=True):
        yield line


async def test_sse_stream_of_a_recorded_answer() -> None:
    events = [event async for event in sse_events(_lines(FIXTURE))]

    assert [name for name, _ in events] == [
        "meta",
        "cite",
        "delta",
        "delta",
        "cite",
        "delta",
        "citations",
        "done",
    ]
    assert events[1][1]["id"] == "role:example-cto-2019"
    assert events[2][1] == {"text": "I joined Example as CTO in 2019 [1]. "}
    assert events[-1][1] == {"mode": "answer"}
