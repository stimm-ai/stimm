"""Tests for the stimm protocol message types and serialization."""

import asyncio
import json

from stimm.protocol import (
    _MESSAGE_TYPES,
    ActionResultMessage,
    BeforeSpeakMessage,
    ContextMessage,
    InstructionMessage,
    MetricsMessage,
    ModeMessage,
    OverrideMessage,
    SpeechEndedMessage,
    SpeechMessage,
    StateMessage,
    StimmProtocol,
    TranscriptMessage,
)


class TestMessageSerialization:
    def test_transcript_round_trip(self) -> None:
        msg = TranscriptMessage(
            partial=False,
            text="Hello world",
            timestamp=1708444800000,
            confidence=0.95,
        )
        data = json.loads(msg.model_dump_json())
        assert data["type"] == "transcript"
        assert data["text"] == "Hello world"
        assert data["partial"] is False

        restored = TranscriptMessage.model_validate(data)
        assert restored.text == "Hello world"
        assert restored.confidence == 0.95

    def test_state_message(self) -> None:
        msg = StateMessage(state="listening", timestamp=1000)
        data = json.loads(msg.model_dump_json())
        assert data["type"] == "state"
        assert data["state"] == "listening"

    def test_before_speak_message(self) -> None:
        msg = BeforeSpeakMessage(text="I'll check that for you.", turn_id="t_003")
        data = json.loads(msg.model_dump_json())
        assert data["type"] == "before_speak"
        assert data["turn_id"] == "t_003"

    def test_metrics_message(self) -> None:
        msg = MetricsMessage(
            turn=1,
            vad_ms=12.0,
            stt_ms=340.0,
            llm_ttft_ms=180.0,
            tts_ttfb_ms=220.0,
            total_ms=752.0,
        )
        data = json.loads(msg.model_dump_json())
        assert data["type"] == "metrics"
        assert data["total_ms"] == 752.0

    def test_instruction_message_defaults(self) -> None:
        msg = InstructionMessage(text="Say hello")
        assert msg.priority == "normal"
        assert msg.speak is True

    def test_context_message(self) -> None:
        msg = ContextMessage(text="User is in France", append=True)
        data = json.loads(msg.model_dump_json())
        assert data["append"] is True

    def test_action_result_message(self) -> None:
        msg = ActionResultMessage(
            action="calendar_check",
            status="completed",
            summary="Found 3 meetings.",
        )
        assert msg.type == "action_result"

    def test_mode_message(self) -> None:
        msg = ModeMessage(mode="relay")
        data = json.loads(msg.model_dump_json())
        assert data["mode"] == "relay"

    def test_override_message(self) -> None:
        msg = OverrideMessage(turn_id="t_005", replacement="Actually, never mind.")
        assert msg.type == "override"


class TestMessageTypeRegistry:
    def test_all_types_registered(self) -> None:
        expected = {
            "transcript",
            "state",
            "before_speak",
            "metrics",
            "instruction",
            "context",
            "action_result",
            "mode",
            "override",
            "speech",
            "speech_ended",
        }
        assert set(_MESSAGE_TYPES.keys()) == expected

    def test_each_type_deserializes(self) -> None:
        samples = {
            "transcript": {"partial": True, "text": "hi", "timestamp": 0},
            "state": {"state": "listening", "timestamp": 0},
            "before_speak": {"text": "ok", "turn_id": "t_001"},
            "metrics": {"turn": 1},
            "instruction": {"text": "do it"},
            "context": {"text": "ctx"},
            "action_result": {"action": "a", "status": "ok", "summary": "done"},
            "mode": {"mode": "relay"},
            "override": {"turn_id": "t_001", "replacement": "new"},
            "speech": {"speech_id": "s_1", "text": "Hello."},
            "speech_ended": {"speech_id": "s_1", "interrupted": True},
        }
        for msg_type, fields in samples.items():
            cls = _MESSAGE_TYPES[msg_type]
            obj = cls.model_validate({"type": msg_type, **fields})
            assert obj.type == msg_type


class TestStimmProtocol:
    def test_handler_registration(self) -> None:
        proto = StimmProtocol()
        called = []

        async def handler(msg: TranscriptMessage) -> None:
            called.append(msg)

        proto.on_transcript(handler)
        assert len(proto._handlers.get("transcript", [])) == 1

    async def test_link_delivers_in_process_both_ways(self) -> None:
        agent_side, supervisor_side = StimmProtocol(), StimmProtocol()
        agent_side.link(supervisor_side)
        received: list[object] = []

        async def collect(msg: object) -> None:
            received.append(msg)

        agent_side.on_speech(collect)
        supervisor_side.on_speech_ended(collect)

        await supervisor_side.send_speech(SpeechMessage(speech_id="s_1", text="Hi."))
        await agent_side.send_speech_ended(SpeechEndedMessage(speech_id="s_1"))
        await asyncio.sleep(0)

        assert [m.type for m in received] == ["speech", "speech_ended"]  # type: ignore[attr-defined]

    async def test_unbound_send_warns(self) -> None:
        """Sending on an unbound protocol should not raise."""
        proto = StimmProtocol()
        await proto.send_transcript(TranscriptMessage(partial=True, text="test", timestamp=0))
