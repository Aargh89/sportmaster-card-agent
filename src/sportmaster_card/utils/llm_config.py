"""LLM configuration helper for Nevel API / OpenRouter integration.

Provides get_llm() to create CrewAI-compatible LLM instances.
Supports two providers:
    1. Nevel API (primary) — OpenAI-compatible, base_url: api.nevel.ai
    2. OpenRouter (fallback) — if NEVEL_API_KEY not set

Provider selection:
    - NEVEL_API_KEY set → Nevel API
    - OPENROUTER_API_KEY set → OpenRouter
    - Neither set → stub mode (no real API calls)

Model mapping per provider:
    ┌────────────────┬──────────────────────┬──────────────────────────────┐
    │ Friendly Name  │ Nevel API            │ OpenRouter                   │
    ├────────────────┼──────────────────────┼──────────────────────────────┤
    │ claude_sonnet  │ nevel/sonnet4        │ anthropic/claude-sonnet-4    │
    │ gpt4o          │ nevel/gpt4o          │ openai/gpt-4o               │
    │ gemini_pro     │ nevel/gemini2.5pro   │ google/gemini-2.5-pro       │
    │ gpt5           │ nevel/gpt5           │ openai/gpt-5                │
    └────────────────┴──────────────────────┴──────────────────────────────┘

Agent-to-model assignment (v0.3 architecture):
    - Content Generator, Data Enricher, Quality Controller → claude_sonnet (nevel/sonnet4)
    - SEO Analyst, Data Validator, Fact Checker, External Researcher → gpt4o (nevel/gpt4o)
    - Brief Selector, Copy Editor, Brand Compliance, Structure Planner → gpt4o (nevel/gpt4o)
    - Internal Researcher, Synectics → gpt4o (nevel/gpt4o)

Example:
    >>> from sportmaster_card.utils.llm_config import get_llm
    >>> llm = get_llm("claude_sonnet")  # Uses Nevel API if NEVEL_API_KEY is set
    >>> llm = get_llm("gpt4o")          # GPT-4o via Nevel
"""

import os
from typing import Optional

# ---------------------------------------------------------------------------
# Nevel API model mapping
# Keys: friendly names used in agents.yaml and agent code
# Values: Nevel API model identifiers
# ---------------------------------------------------------------------------
NEVEL_MODEL_MAP: dict[str, str] = {
    # Premium models — for content generation, quality control
    "claude_sonnet": "nevel/sonnet4",
    # Standard models — for validation, parsing, research
    "gpt4o": "nevel/gpt4o",
    "gpt5": "nevel/gpt5",
    "gemini_pro": "nevel/gemini2.5pro",
    # Aliases for backward compatibility with Phase 1 agent configs
    "claude_haiku": "nevel/gpt4o",       # Nevel doesn't have Haiku; use GPT-4o
    "gemini_flash": "nevel/gpt4o",       # Nevel doesn't have Flash; use GPT-4o
}

# ---------------------------------------------------------------------------
# OpenRouter model mapping (fallback)
# ---------------------------------------------------------------------------
OPENROUTER_MODEL_MAP: dict[str, str] = {
    "claude_sonnet": "anthropic/claude-sonnet-4",
    "claude_haiku": "anthropic/claude-haiku-4-5",
    "gemini_flash": "google/gemini-2.0-flash-001",
    "gpt4o": "openai/gpt-4o",
    "gpt5": "openai/gpt-5",
    "gemini_pro": "google/gemini-2.5-pro",
}

# ---------------------------------------------------------------------------
# Unified MODEL_MAP — points to active provider's map
# ---------------------------------------------------------------------------
MODEL_MAP = NEVEL_MODEL_MAP  # Default; updated at runtime by get_llm()


def get_api_config() -> tuple[str, str, dict[str, str]]:
    """Determine which API provider to use based on environment variables.

    Returns:
        Tuple of (api_key, base_url, model_map).

    Priority:
        1. NEVEL_API_KEY → Nevel API (api.nevel.ai)
        2. OPENROUTER_API_KEY → OpenRouter
        3. None → empty key (stub mode)

    Example:
        >>> key, url, models = get_api_config()
        >>> print(url)
        'https://api.nevel.ai/v1'
    """
    # Check Nevel API first (primary provider)
    nevel_key = os.environ.get("NEVEL_API_KEY", "").strip()
    if nevel_key:
        return (
            nevel_key,
            "https://api.nevel.ai/v1",
            NEVEL_MODEL_MAP,
        )

    # Fallback to OpenRouter
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        return (
            openrouter_key,
            "https://openrouter.ai/api/v1",
            OPENROUTER_MODEL_MAP,
        )

    # No API key — stub mode
    return ("", "", NEVEL_MODEL_MAP)


def get_llm(
    model_name: str = "claude_sonnet",
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """Create a CrewAI LLM instance for the active API provider.

    Automatically selects Nevel API or OpenRouter based on which
    API key is available in environment variables.

    Args:
        model_name: Friendly name from MODEL_MAP (e.g., "claude_sonnet",
            "gpt4o", "gemini_pro") or a raw model ID (pass-through).
        temperature: Sampling temperature (0.0 = deterministic, 2.0 = max random).
            Default 0.7 balances creativity and consistency.
        max_tokens: Maximum tokens in the generated response.
            Default 4096 is sufficient for product card content.

    Returns:
        A crewai.LLM instance configured for the resolved model and provider.

    Example:
        >>> llm = get_llm("claude_sonnet")  # → nevel/sonnet4 via Nevel API
        >>> llm = get_llm("gpt4o", temperature=0.3)  # Lower creativity for validation

    Raises:
        No exceptions — returns LLM even without API key (for stub mode).
    """
    from crewai import LLM

    # Determine provider and resolve model ID
    api_key, base_url, model_map = get_api_config()
    model_id = model_map.get(model_name, model_name)

    # Build LLM kwargs
    llm_kwargs: dict = {
        "model": f"openai/{model_id}" if base_url else model_id,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Set API key and base URL if available
    if api_key:
        llm_kwargs["api_key"] = api_key
    if base_url:
        llm_kwargs["base_url"] = base_url

    return LLM(**llm_kwargs)
