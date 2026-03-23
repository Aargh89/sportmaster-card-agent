"""Dual-mode agent execution: stub (tests) vs LLM (production).

All agents in the system can run in two modes:

Stub mode (default):
    - No API calls, no LLM
    - Uses rule-based/template logic
    - Activated when OPENROUTER_API_KEY is not set
    - Used in tests and development

LLM mode (production):
    - Real CrewAI Agent + Task execution
    - Calls OpenRouter API
    - Activated when OPENROUTER_API_KEY is set
    - Used in production and integration testing

Architecture:
    ┌─────────────────────────────────┐
    │        run_agent()              │
    │  ┌─────────────┐ ┌───────────┐ │
    │  │ stub mode   │ │ LLM mode  │ │
    │  │ fallback_fn │ │ CrewAI    │ │
    │  │ (no API)    │ │ Agent+Task│ │
    │  └─────────────┘ └───────────┘ │
    └─────────────────────────────────┘
"""
import os
from typing import Any, Callable, Optional, Type
from pydantic import BaseModel
from crewai import Agent, Task, Crew


def is_llm_mode() -> bool:
    """Check if LLM mode is active (OPENROUTER_API_KEY is set and non-empty)."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    return bool(key.strip())


def create_crew_agent(
    role: str,
    goal: str,
    backstory: str,
    model_name: str = "claude_sonnet",
    verbose: bool = True,
) -> Agent:
    """Create a CrewAI Agent configured for OpenRouter."""
    from sportmaster_card.utils.llm_config import get_llm

    if is_llm_mode():
        llm = get_llm(model_name)
    else:
        # In stub mode, CrewAI still requires a valid LLM object during Agent
        # construction (it calls create_llm internally). We provide a dummy
        # LLM with a fake API key -- it is never used for inference because
        # run_agent() short-circuits to stub_fallback() in stub mode.
        from crewai import LLM
        llm = LLM(model="openai/gpt-4o", api_key="stub-no-calls")

    return Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        llm=llm,
        verbose=verbose,
        allow_delegation=False,
    )


def create_crew_task(
    description: str,
    agent: Agent,
    expected_output: str = "Structured JSON output",
    output_pydantic: Optional[Type[BaseModel]] = None,
) -> Task:
    """Create a CrewAI Task with optional Pydantic structured output."""
    kwargs = {
        "description": description,
        "agent": agent,
        "expected_output": expected_output,
    }
    if output_pydantic:
        kwargs["output_pydantic"] = output_pydantic
    return Task(**kwargs)


def run_agent(
    role: str,
    goal: str,
    backstory: str,
    task_description: str,
    stub_fallback: Callable,
    model_name: str = "claude_sonnet",
    output_pydantic: Optional[Type[BaseModel]] = None,
    expected_output: str = "Structured JSON",
) -> Any:
    """Execute an agent in stub or LLM mode.

    In stub mode, calls stub_fallback() and returns its result.
    In LLM mode, creates CrewAI Agent+Task+Crew and executes.
    """
    if not is_llm_mode():
        return stub_fallback()

    agent = create_crew_agent(role, goal, backstory, model_name)
    task = create_crew_task(task_description, agent, expected_output, output_pydantic)
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    result = crew.kickoff()

    if output_pydantic and hasattr(result, 'pydantic'):
        return result.pydantic
    return result.raw if hasattr(result, 'raw') else str(result)
