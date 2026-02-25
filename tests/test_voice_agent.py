"""Tests for VoiceAgent instruction handling and context building."""

import asyncio

import pytest

from stimm.protocol import ContextMessage, InstructionMessage
from stimm.voice_agent import VoiceAgent


class TestContextBuilding:
    def test_no_instructions_returns_base(self) -> None:
        agent = VoiceAgent(instructions="Base prompt")
        result = agent.build_context_with_instructions()
        assert result == "Base prompt"

    def test_with_supervisor_context(self) -> None:
        agent = VoiceAgent(instructions="Base prompt")
        agent._supervisor_context = ["User is in France"]
        result = agent.build_context_with_instructions()
        assert "User is in France" in result
        assert "Base prompt" in result

    def test_only_latest_supervisor_context_is_used(self) -> None:
        agent = VoiceAgent(instructions="Base prompt")
        agent._supervisor_context = [
            "--Supervisor--: old context",
            "--Supervisor--: latest context",
        ]
        result = agent.build_context_with_instructions()
        assert "latest context" in result
        assert "old context" not in result

    def test_with_pending_instructions(self) -> None:
        agent = VoiceAgent(instructions="Base prompt")
        agent._pending_instructions = [
            InstructionMessage(text="Tell user about the weather"),
            InstructionMessage(text="Mention it's sunny"),
        ]
        result = agent.build_context_with_instructions()
        assert "Tell user about the weather" in result
        assert "Mention it's sunny" in result
        # Instructions should be cleared after building
        assert len(agent._pending_instructions) == 0

    def test_instructions_window_limit(self) -> None:
        agent = VoiceAgent(instructions="Base", supervisor_instructions_window=2)
        agent._pending_instructions = [
            InstructionMessage(text="old"),
            InstructionMessage(text="recent1"),
            InstructionMessage(text="recent2"),
        ]
        result = agent.build_context_with_instructions()
        assert "old" not in result
        assert "recent1" in result
        assert "recent2" in result

    def test_override_base_instructions(self) -> None:
        agent = VoiceAgent(instructions="Original")
        result = agent.build_context_with_instructions("Override")
        assert result == "Override"


class TestModeProperty:
    def test_default_mode(self) -> None:
        agent = VoiceAgent()
        assert agent.mode == "hybrid"

    def test_custom_mode(self) -> None:
        agent = VoiceAgent(mode="relay")
        assert agent.mode == "relay"


class TestBuffering:
    def test_buffer_token(self) -> None:
        agent = VoiceAgent(buffering_level="NONE")
        assert agent.buffer_token("Hello") == "Hello"

    def test_flush_buffer(self) -> None:
        agent = VoiceAgent(buffering_level="HIGH")
        agent.buffer_token("partial")
        assert agent.flush_buffer() == "partial"


class TestRuntimeSync:
    @pytest.mark.asyncio
    async def test_handle_context_updates_live_instructions(self) -> None:
        agent = VoiceAgent(instructions="Base prompt")
        captured: list[str] = []

        async def fake_update(instructions: str) -> None:
            captured.append(instructions)

        agent.update_instructions = fake_update  # type: ignore[method-assign]

        await agent._handle_context(
            ContextMessage(text="--Supervisor--: use metric units", append=True)
        )

        assert len(captured) == 1
        assert "Base prompt" in captured[0]
        assert "--Supervisor--: use metric units" in captured[0]

    @pytest.mark.asyncio
    async def test_deferred_context_trigger_emits_when_session_becomes_idle(self) -> None:
        agent = VoiceAgent(instructions="Base prompt")

        class _FakeSession:
            def __init__(self) -> None:
                self.agent_state = "speaking"
                self.user_state = "listening"
                self.current_speech = None
                self.calls = 0

            def generate_reply(self, input_modality: str, instructions: str) -> None:
                self.calls += 1

        session = _FakeSession()
        agent._current_session = lambda: session  # type: ignore[method-assign]

        await agent._handle_context(
            ContextMessage(text="--Supervisor--: final answer", append=False)
        )
        assert agent._deferred_context_reply_trigger is True
        assert session.calls == 0

        session.agent_state = "idle"
        await agent._flush_deferred_context_reply_trigger()

        assert agent._deferred_context_reply_trigger is False
        assert session.calls == 1

    @pytest.mark.asyncio
    async def test_deferred_trigger_not_lost_after_long_wait(self) -> None:
        agent = VoiceAgent(instructions="Base prompt")

        class _FakeSession:
            def __init__(self) -> None:
                self.agent_state = "speaking"
                self.user_state = "listening"
                self.current_speech = None
                self.calls = 0

            def generate_reply(self, input_modality: str, instructions: str) -> None:
                self.calls += 1

        session = _FakeSession()
        agent._current_session = lambda: session  # type: ignore[method-assign]

        await agent._handle_context(
            ContextMessage(text="--Supervisor--: delayed answer", append=False)
        )
        assert agent._deferred_context_reply_trigger is True

        await asyncio.sleep(0.2)
        assert session.calls == 0

        session.agent_state = "idle"
        await asyncio.sleep(0.7)

        assert agent._deferred_context_reply_trigger is False
        assert session.calls == 1
