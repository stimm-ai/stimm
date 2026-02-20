"""Tests for the Supervisor base class."""

import pytest

from stimm.protocol import BeforeSpeakMessage, MetricsMessage, StateMessage, TranscriptMessage
from stimm.supervisor import Supervisor


class TestSupervisorDefaults:
    def test_not_connected_initially(self) -> None:
        sup = Supervisor()
        assert sup.connected is False

    def test_protocol_exists(self) -> None:
        sup = Supervisor()
        assert sup.protocol is not None


class TestSupervisorHandlers:
    """Ensure default handlers don't raise."""

    @pytest.mark.asyncio
    async def test_on_transcript_default(self) -> None:
        sup = Supervisor()
        await sup.on_transcript(TranscriptMessage(partial=False, text="hello", timestamp=0))

    @pytest.mark.asyncio
    async def test_on_state_change_default(self) -> None:
        sup = Supervisor()
        await sup.on_state_change(StateMessage(state="listening", timestamp=0))

    @pytest.mark.asyncio
    async def test_on_before_speak_default(self) -> None:
        sup = Supervisor()
        await sup.on_before_speak(BeforeSpeakMessage(text="hi", turn_id="t_001"))

    @pytest.mark.asyncio
    async def test_on_metrics_default(self) -> None:
        sup = Supervisor()
        await sup.on_metrics(MetricsMessage(turn=1))


class TestSupervisorSubclass:
    @pytest.mark.asyncio
    async def test_custom_on_transcript(self) -> None:
        received = []

        class Custom(Supervisor):
            async def on_transcript(self, msg: TranscriptMessage) -> None:
                received.append(msg.text)

        sup = Custom()
        await sup.on_transcript(TranscriptMessage(partial=False, text="test", timestamp=0))
        assert received == ["test"]
