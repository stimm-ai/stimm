"""Tests for the pre-TTS text buffering strategy."""

from stimm.buffering import TextBufferingStrategy


class TestBufferingNone:
    def test_emits_every_token(self) -> None:
        buf = TextBufferingStrategy("NONE")
        assert buf.feed("Hello") == "Hello"
        assert buf.feed(" ") == " "
        assert buf.feed("world") == "world"

    def test_flush_empty(self) -> None:
        buf = TextBufferingStrategy("NONE")
        buf.feed("x")
        assert buf.flush() is None


class TestBufferingLow:
    def test_emits_on_space(self) -> None:
        buf = TextBufferingStrategy("LOW")
        assert buf.feed("Hello") is None
        result = buf.feed(" world")
        assert result == "Hello "

    def test_flush_remainder(self) -> None:
        buf = TextBufferingStrategy("LOW")
        buf.feed("partial")
        assert buf.flush() == "partial"
        assert buf.flush() is None


class TestBufferingMedium:
    def test_emits_on_four_words(self) -> None:
        buf = TextBufferingStrategy("MEDIUM")
        assert buf.feed("one ") is None
        assert buf.feed("two ") is None
        assert buf.feed("three ") is None
        result = buf.feed("four ")
        assert result is not None
        assert "one" in result

    def test_emits_on_punctuation(self) -> None:
        buf = TextBufferingStrategy("MEDIUM")
        assert buf.feed("Hello") is None
        result = buf.feed(".")
        assert result == "Hello."

    def test_flush(self) -> None:
        buf = TextBufferingStrategy("MEDIUM")
        buf.feed("short")
        assert buf.flush() == "short"


class TestBufferingHigh:
    def test_waits_for_punctuation(self) -> None:
        buf = TextBufferingStrategy("HIGH")
        assert buf.feed("one ") is None
        assert buf.feed("two ") is None
        assert buf.feed("three ") is None
        assert buf.feed("four ") is None
        assert buf.feed("five ") is None
        result = buf.feed("six.")
        assert result is not None
        assert "six." in result

    def test_no_emit_without_punctuation(self) -> None:
        buf = TextBufferingStrategy("HIGH")
        for word in ["a ", "b ", "c ", "d ", "e ", "f "]:
            assert buf.feed(word) is None
        assert buf.flush() == "a b c d e f "


class TestReset:
    def test_reset_clears_buffer(self) -> None:
        buf = TextBufferingStrategy("HIGH")
        buf.feed("something")
        buf.reset()
        assert buf.flush() is None
