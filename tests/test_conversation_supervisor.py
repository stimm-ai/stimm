"""Tests for ConversationSupervisor context injection boundaries."""

import asyncio

import pytest

from stimm.conversation_supervisor import ConversationSupervisor
from stimm.protocol import TranscriptMessage


class _StubConversationSupervisor(ConversationSupervisor):
    async def process(self, history: str, system_prompt: str | None) -> str:
        return '{"action":"TRIGGER","text":"Use 22°C","reason":"weather_tool"}'


class _CountingConversationSupervisor(ConversationSupervisor):
    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self.calls = 0

    async def process(self, history: str, system_prompt: str | None) -> str:
        self.calls += 1
        return '{"action":"NO_ACTION","text":"","reason":"noop"}'


class TestConversationSupervisorStructuredOutputContract:
    def test_default_backend_system_prompt_is_json_contract(self) -> None:
        sup = _StubConversationSupervisor()
        prompt = sup.get_backend_system_prompt()
        assert prompt is not None
        assert "Return exactly one JSON object and nothing else." in prompt
        assert '"action":"NO_ACTION"|"TRIGGER"' in prompt

    def test_backend_system_prompt_override_is_respected(self) -> None:
        sup = _StubConversationSupervisor(backend_input_preamble="custom-contract")
        assert sup.get_backend_system_prompt() == "custom-contract"


class TestConversationSupervisorContextBoundary:
    @pytest.mark.asyncio
    async def test_on_transcript_injects_immediate_ack_context(self) -> None:
        sup = _StubConversationSupervisor()
        captured: list[tuple[str, bool]] = []

        async def fake_add_context(text: str, *, append: bool = True) -> None:
            captured.append((text, append))

        sup.add_context = fake_add_context  # type: ignore[method-assign]

        await sup.on_transcript(
            TranscriptMessage(partial=False, text="Peux-tu vérifier ma commande ?", timestamp=0)
        )

        assert len(captured) == 1
        assert captured[0][1] is False
        assert "Instant feedback mode" in captured[0][0]
        assert "Do not invent facts" in captured[0][0]
        assert "Peux-tu vérifier ma commande ?" in captured[0][0]
        assert "one or two short natural sentences" in captured[0][0]
        assert "Otherwise acknowledge and say you are checking" in captured[0][0]

    @pytest.mark.asyncio
    async def test_on_transcript_includes_previous_ack_hint_for_variety(self) -> None:
        sup = _StubConversationSupervisor()
        captured: list[str] = []

        async def fake_add_context(text: str, *, append: bool = True) -> None:
            captured.append(text)

        sup.add_context = fake_add_context  # type: ignore[method-assign]
        sup._push("assistant", "Je m'en occupe tout de suite.")

        await sup.on_transcript(
            TranscriptMessage(partial=False, text="Tu peux vérifier le statut ?", timestamp=0)
        )

        assert len(captured) == 1
        assert "Last assistant acknowledgement was" in captured[0]
        assert "Je m'en occupe tout de suite." in captured[0]

    @pytest.mark.asyncio
    async def test_on_transcript_includes_verified_context_when_available(self) -> None:
        sup = _StubConversationSupervisor()
        captured: list[str] = []

        async def fake_add_context(text: str, *, append: bool = True) -> None:
            captured.append(text)

        sup.add_context = fake_add_context  # type: ignore[method-assign]
        sup._last_verified_supervisor_context = "Mon pseudo est Stimmy."

        await sup.on_transcript(
            TranscriptMessage(partial=False, text="Quel est ton pseudo ?", timestamp=0)
        )

        assert len(captured) == 1
        assert "Verified context from supervisor" in captured[0]
        assert "Mon pseudo est Stimmy." in captured[0]

    @pytest.mark.asyncio
    async def test_on_transcript_triggers_immediate_backend_processing(self) -> None:
        sup = _CountingConversationSupervisor(quiet_s=10.0, loop_interval_s=10.0)

        async def fake_add_context(_text: str, *, append: bool = True) -> None:
            return None

        sup.add_context = fake_add_context  # type: ignore[method-assign]

        await sup.on_transcript(TranscriptMessage(partial=False, text="hello", timestamp=0))
        await asyncio.sleep(0.05)

        assert sup.calls == 1

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_on_transcript_dedup_does_not_reinject_ack(self) -> None:
        sup = _StubConversationSupervisor()
        captured: list[str] = []

        async def fake_add_context(text: str, *, append: bool = True) -> None:
            captured.append(text)

        sup.add_context = fake_add_context  # type: ignore[method-assign]

        msg = TranscriptMessage(partial=False, text="same utterance", timestamp=0)
        await sup.on_transcript(msg)
        await sup.on_transcript(msg)

        assert len(captured) == 1

    @pytest.mark.asyncio
    async def test_process_injects_only_latest_supervisor_directive(self) -> None:
        sup = _StubConversationSupervisor()
        captured: list[tuple[str, bool]] = []

        async def fake_add_context(text: str, *, append: bool = True) -> None:
            captured.append((text, append))

        sup.add_context = fake_add_context  # type: ignore[method-assign]

        sup._push("user", "Quel temps fait-il ?")
        sup._push("assistant", "Je vérifie.")

        await sup._process()

        assert captured == [("--Supervisor--: Use 22°C", False)]
        assert [turn.role for turn in sup._history] == ["user", "assistant", "supervisor"]

    @pytest.mark.asyncio
    async def test_instant_feedback_multi_turn_stays_bounded_and_varied(self) -> None:
        sup = _StubConversationSupervisor()
        captured: list[str] = []

        async def fake_add_context(text: str, *, append: bool = True) -> None:
            captured.append(text)

        sup.add_context = fake_add_context  # type: ignore[method-assign]
        sup._schedule_immediate_process = lambda: None  # type: ignore[method-assign]

        user_turns = [
            "Tu peux vérifier ma réservation ?",
            "Et l'horaire exact ?",
            "Ajoute aussi mon numéro de dossier",
            "Peux-tu relancer la vérification ?",
            "Tu as bien compris ma demande ?",
            "Merci, je reste en ligne",
            "Besoin d'un update rapide",
            "Tu confirmes que c'est en cours ?",
        ]
        previous_acks = [
            "Je regarde ça.",
            "Je m'en occupe.",
            "Un instant, je vérifie.",
            "Je lance la vérification.",
            "C'est pris en compte.",
            "Je continue la vérification.",
            "Je fais le point.",
            "Je vérifie encore.",
        ]

        for idx, user_text in enumerate(user_turns):
            sup._push("assistant", previous_acks[idx])
            await sup.on_transcript(TranscriptMessage(partial=False, text=user_text, timestamp=idx))

        assert len(captured) == len(user_turns)
        for idx, ctx in enumerate(captured):
            assert "Instant feedback mode" in ctx
            assert "Do not invent facts" in ctx
            assert "Otherwise acknowledge and say you are checking" in ctx
            assert user_turns[idx] in ctx
            assert "Last assistant acknowledgement was" in ctx
            assert previous_acks[idx] in ctx

        assert len(set(captured)) == len(captured)
