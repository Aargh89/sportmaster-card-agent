"""Tests for LLM configuration helper: get_llm(), get_api_config(), MODEL_MAPs.

Tests verify the Nevel API / OpenRouter integration layer.
No real API calls are made.

Test strategy:
    - get_api_config() selects Nevel API when NEVEL_API_KEY is set
    - get_api_config() falls back to OpenRouter when only OPENROUTER_API_KEY is set
    - get_llm() returns LLM with correct model for active provider
    - Model maps contain all required model families
    - Nevel model map maps friendly names to nevel/* IDs
"""

from unittest.mock import patch, MagicMock
import pytest


def test_get_api_config_nevel(monkeypatch):
    """NEVEL_API_KEY set → Nevel API provider selected."""
    monkeypatch.setenv("NEVEL_API_KEY", "ak_test123")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from sportmaster_card.utils.llm_config import get_api_config

    key, url, model_map = get_api_config()
    assert key == "ak_test123"
    assert "nevel.ai" in url
    assert "nevel/" in model_map["claude_sonnet"]


def test_get_api_config_openrouter_fallback(monkeypatch):
    """Only OPENROUTER_API_KEY → OpenRouter fallback."""
    monkeypatch.delenv("NEVEL_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    from sportmaster_card.utils.llm_config import get_api_config

    key, url, model_map = get_api_config()
    assert key == "sk-or-test"
    assert "openrouter" in url
    assert "anthropic/" in model_map["claude_sonnet"]


def test_get_api_config_no_keys(monkeypatch):
    """No API keys → empty (stub mode)."""
    monkeypatch.delenv("NEVEL_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from sportmaster_card.utils.llm_config import get_api_config

    key, url, model_map = get_api_config()
    assert key == ""
    assert url == ""


def test_get_llm_with_nevel(monkeypatch):
    """get_llm() with Nevel API key uses nevel model IDs."""
    monkeypatch.setenv("NEVEL_API_KEY", "ak_test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with patch("crewai.LLM") as MockLLM:
        MockLLM.return_value = MagicMock()
        from sportmaster_card.utils.llm_config import get_llm

        get_llm("claude_sonnet")

        call_kwargs = MockLLM.call_args[1]
        assert "nevel/sonnet4" in call_kwargs["model"]
        assert call_kwargs["api_key"] == "ak_test"
        assert "nevel.ai" in call_kwargs["base_url"]


def test_nevel_model_map_has_required_models():
    """Nevel model map has all required friendly names."""
    from sportmaster_card.utils.llm_config import NEVEL_MODEL_MAP

    required = {"claude_sonnet", "claude_haiku", "gemini_flash", "gpt4o"}
    assert required.issubset(set(NEVEL_MODEL_MAP.keys()))


def test_nevel_model_map_values():
    """Nevel model IDs start with 'nevel/'."""
    from sportmaster_card.utils.llm_config import NEVEL_MODEL_MAP

    for key, value in NEVEL_MODEL_MAP.items():
        assert value.startswith("nevel/"), f"{key} → {value} should start with nevel/"
