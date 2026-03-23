"""LLM configuration helper for OpenRouter integration.

Provides get_llm() to create CrewAI-compatible LLM instances
configured for OpenRouter. Supports model selection per agent:
- Claude Sonnet: Content Generator, Quality Controller, Visual Interpreter
- Claude Haiku: Brief Selector, Copy Editor, Brand Compliance
- Gemini Flash: Data Validator, External Researcher, Fact Checker

Architecture:
    ┌──────────────────────────────┐
    │        get_llm()             │
    │  model_name → LLM instance  │
    └────────┬─────────────────────┘
             │
    ┌────────▼─────────────────────┐
    │       OpenRouter API         │
    │  base_url: openrouter.ai     │
    │  api_key: OPENROUTER_API_KEY │
    └──────────────────────────────┘
"""

import os

# Mapping of friendly model names to full OpenRouter model identifiers.
# Each key is used by agent configs; each value is the OpenRouter path.
# Update values here when upgrading to newer model versions.
MODEL_MAP: dict[str, str] = {
    "claude_sonnet": "anthropic/claude-sonnet-4",
    "claude_haiku": "anthropic/claude-haiku-4-5",
    "gemini_flash": "google/gemini-2.0-flash-001",
}


def get_llm(
    model_name: str = "claude_sonnet",
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """Create a CrewAI LLM instance routed through OpenRouter.

    Resolves model_name via MODEL_MAP (friendly name -> OpenRouter ID).
    If model_name is not in MODEL_MAP, it is used as-is (pass-through).
    Reads OPENROUTER_API_KEY from environment for authentication.

    Args:
        model_name: Friendly name from MODEL_MAP or raw OpenRouter model ID.
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
        max_tokens: Maximum tokens in the generated response.

    Returns:
        A crewai.LLM instance configured for the specified model.
    """
    from crewai import LLM

    # Resolve friendly name to OpenRouter model ID, or use as-is.
    model_id = MODEL_MAP.get(model_name, model_name)

    # Read API key from environment; empty string if unset.
    api_key = os.environ.get("OPENROUTER_API_KEY", "")

    return LLM(
        model=f"openrouter/{model_id}",
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )
