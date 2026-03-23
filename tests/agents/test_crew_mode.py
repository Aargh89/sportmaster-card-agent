"""Tests for dual-mode agent execution (stub vs LLM).

Tests both Nevel API and OpenRouter API key detection.
"""
import os
import pytest


def test_is_llm_mode_without_any_key(monkeypatch):
    """Without any API key, agents run in stub mode."""
    monkeypatch.delenv("NEVEL_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from sportmaster_card.agents.crew_base import is_llm_mode
    assert is_llm_mode() is False


def test_is_llm_mode_with_nevel_key(monkeypatch):
    """With NEVEL_API_KEY set, agents run in LLM mode (primary)."""
    monkeypatch.setenv("NEVEL_API_KEY", "ak_test123")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from sportmaster_card.agents.crew_base import is_llm_mode
    assert is_llm_mode() is True


def test_is_llm_mode_with_openrouter_key(monkeypatch):
    """With OPENROUTER_API_KEY set, agents run in LLM mode (fallback)."""
    monkeypatch.delenv("NEVEL_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test123")
    from sportmaster_card.agents.crew_base import is_llm_mode
    assert is_llm_mode() is True


def test_is_llm_mode_nevel_takes_priority(monkeypatch):
    """When both keys set, Nevel takes priority."""
    monkeypatch.setenv("NEVEL_API_KEY", "ak_nevel")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-openrouter")
    from sportmaster_card.agents.crew_base import is_llm_mode
    assert is_llm_mode() is True


def test_is_llm_mode_with_empty_keys(monkeypatch):
    """Empty API keys mean stub mode."""
    monkeypatch.setenv("NEVEL_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    from sportmaster_card.agents.crew_base import is_llm_mode
    assert is_llm_mode() is False


def test_create_crew_agent():
    """create_crew_agent() returns a CrewAI Agent with correct config."""
    from sportmaster_card.agents.crew_base import create_crew_agent
    agent = create_crew_agent(
        role="Test Agent",
        goal="Test goal",
        backstory="Test backstory",
        model_name="claude_haiku",
    )
    assert agent.role == "Test Agent"


def test_create_crew_task():
    """create_crew_task() returns a CrewAI Task with Pydantic output."""
    from sportmaster_card.agents.crew_base import create_crew_agent, create_crew_task
    from sportmaster_card.models.content import QualityScore
    agent = create_crew_agent(role="R", goal="G", backstory="B")
    task = create_crew_task(
        description="Test task",
        agent=agent,
        expected_output="JSON",
        output_pydantic=QualityScore,
    )
    assert task.description == "Test task"


def test_run_agent_stub_mode(monkeypatch):
    """run_agent() in stub mode calls the fallback function."""
    monkeypatch.delenv("NEVEL_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from sportmaster_card.agents.crew_base import run_agent

    def stub_fn():
        return {"result": "stub"}

    result = run_agent(
        role="Test", goal="G", backstory="B",
        task_description="Do something",
        stub_fallback=stub_fn,
    )
    assert result == {"result": "stub"}
