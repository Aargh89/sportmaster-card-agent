"""Tests for LLM configuration helper: get_llm() and MODEL_MAP.

These tests verify the OpenRouter LLM integration layer that provides
CrewAI-compatible LLM instances to all agents. No real API calls are made.

Test strategy:
    - get_llm() returns LLM with correct default model (claude_sonnet)
    - get_llm() accepts custom model name for agent-specific selection
    - MODEL_MAP maps friendly names to full OpenRouter model IDs
    - MODEL_MAP contains all three required model families
"""

from unittest.mock import patch, MagicMock
import pytest


def test_get_llm_default():
    """get_llm() with no args returns LLM configured for claude_sonnet via OpenRouter."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-123"}):
        with patch("crewai.LLM") as MockLLM:
            MockLLM.return_value = MagicMock()
            from sportmaster_card.utils.llm_config import get_llm

            result = get_llm()

            MockLLM.assert_called_once()
            call_kwargs = MockLLM.call_args[1]
            assert "openrouter/" in call_kwargs["model"]
            assert "claude-sonnet" in call_kwargs["model"]
            assert call_kwargs["api_key"] == "test-key-123"
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 4096


def test_get_llm_custom_model():
    """get_llm() with custom model passes it through as OpenRouter model ID."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-456"}):
        with patch("crewai.LLM") as MockLLM:
            MockLLM.return_value = MagicMock()
            from sportmaster_card.utils.llm_config import get_llm

            result = get_llm(model_name="anthropic/claude-sonnet-4")

            call_kwargs = MockLLM.call_args[1]
            assert call_kwargs["model"] == "openrouter/anthropic/claude-sonnet-4"


def test_get_llm_model_mapping():
    """MODEL_MAP maps friendly names like 'claude_sonnet' to OpenRouter model IDs."""
    from sportmaster_card.utils.llm_config import MODEL_MAP

    assert MODEL_MAP["claude_sonnet"] == "anthropic/claude-sonnet-4"
    assert MODEL_MAP["claude_haiku"] == "anthropic/claude-haiku-4-5"
    assert MODEL_MAP["gemini_flash"] == "google/gemini-2.0-flash-001"


def test_model_map_has_required_models():
    """MODEL_MAP contains all three required model families for agent assignment."""
    from sportmaster_card.utils.llm_config import MODEL_MAP

    required = {"claude_sonnet", "claude_haiku", "gemini_flash"}
    assert required.issubset(set(MODEL_MAP.keys()))
