"""Tests for provider catalog and extras resolution helpers."""

from stimm.providers import (
    extras_install_command,
    get_provider,
    get_provider_catalog,
    list_providers,
    list_runtime_providers,
    required_extra_for_provider,
    required_extras_for_selection,
)


class TestProviderCatalogHelpers:
    def test_get_provider_catalog_contains_kinds(self) -> None:
        catalog = get_provider_catalog()
        assert "stt" in catalog
        assert "tts" in catalog
        assert "llm" in catalog

    def test_list_providers_returns_copy(self) -> None:
        providers = list_providers("stt")
        assert providers
        original_id = providers[0]["id"]
        providers[0]["id"] = "mutated"

        fresh = list_providers("stt")
        assert fresh[0]["id"] == original_id

    def test_get_provider_by_id(self) -> None:
        provider = get_provider("llm", "openai")
        assert provider is not None
        assert provider["id"] == "openai"

    def test_list_runtime_providers_contains_constructor(self) -> None:
        providers = list_runtime_providers("llm")
        assert providers
        assert "constructor" in providers[0]


class TestExtraResolution:
    def test_required_extra_for_alias_provider(self) -> None:
        assert required_extra_for_provider("llm", "google") == "google"

    def test_required_extra_for_openai_compatible_provider(self) -> None:
        assert required_extra_for_provider("llm", "azure-openai") == "openai"

    def test_required_extras_for_selection_is_unique_sorted(self) -> None:
        extras = required_extras_for_selection(stt="deepgram", tts="openai", llm="azure-openai")
        assert extras == ["deepgram", "openai"]

    def test_extras_install_command(self) -> None:
        cmd = extras_install_command(stt="deepgram", tts="openai", llm="azure-openai")
        assert cmd == "pip install stimm[deepgram,openai]"

    def test_extras_install_command_none_when_no_selection(self) -> None:
        assert extras_install_command() is None
