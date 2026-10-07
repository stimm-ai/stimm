"""Tests for the STIMM_*-driven provider factories in stimm.worker."""

import os
import types

import pytest

from stimm import worker


@pytest.fixture(autouse=True)
def _no_stimm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("STIMM_"):
            monkeypatch.delenv(name)


def _use_plugin(monkeypatch: pytest.MonkeyPatch, **classes: type) -> None:
    plugin = types.SimpleNamespace(**classes)
    monkeypatch.setattr(worker, "_load_plugin", lambda kind, provider: plugin)


class AzureLikeSTT:
    """Like azure.STT, aws.STT and clova.STT: no model, no api_key."""

    def __init__(self, *, language: str = "en-US", speech_key: str | None = None) -> None:
        self.language = language


class DeepgramLikeSTT:
    def __init__(self, *, model: str = "nova-2", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key


class AzureLikeTTS:
    """Like azure.TTS and aws.TTS: no model."""

    def __init__(self, *, voice: str = "", language: str | None = None) -> None:
        self.voice = voice


def test_stt_plugin_without_model_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_plugin(monkeypatch, STT=AzureLikeSTT)
    monkeypatch.setenv("STIMM_STT_PROVIDER", "azure")
    monkeypatch.setenv("STIMM_STT_LANGUAGE", "fr-FR")
    monkeypatch.setenv("STIMM_STT_API_KEY", "ignored")

    assert worker._make_stt().language == "fr-FR"


def test_stt_model_and_key_still_reach_plugins_that_take_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_plugin(monkeypatch, STT=DeepgramLikeSTT)
    monkeypatch.setenv("STIMM_STT_API_KEY", "key")

    stt = worker._make_stt()
    assert (stt.model, stt.api_key) == ("nova-3", "key")


def test_tts_plugin_without_model_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_plugin(monkeypatch, TTS=AzureLikeTTS)
    monkeypatch.setenv("STIMM_TTS_PROVIDER", "azure")
    monkeypatch.setenv("STIMM_TTS_VOICE", "fr-FR-DeniseNeural")

    assert worker._make_tts().voice == "fr-FR-DeniseNeural"
