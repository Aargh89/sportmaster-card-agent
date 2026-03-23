"""CopyEditorAgent -- rule-based content editing and polishing.

This module implements a mechanical copy editor for the UC2 Content Generation
pipeline. The CopyEditorAgent takes a ``PlatformContent`` instance and applies
deterministic formatting rules:

1. **Character limit enforcement** -- truncates product_name, description,
   and seo_title to platform-specific maximums with word-boundary-aware
   truncation (no mid-word cuts).
2. **Whitespace cleanup** -- strips leading/trailing whitespace from all
   text fields to ensure consistent storage and display.
3. **Consistent formatting** -- ensures all text fields follow uniform
   formatting conventions.

Phase 1 design: editing is DETERMINISTIC (no LLM calls). The agent applies
mechanical rules only. Stylistic and grammar checks are performed MANUALLY
by the GPTK team during the pilot phase. Future phases may add LLM-based
grammar correction and style enforcement.

Architecture in the UC2 pipeline::

    Content Generator (Agent 2.7)
        |
        v
    PlatformContent (raw)
        |
        v
    CopyEditorAgent.edit()
        |
        v
    PlatformContent (polished)
        |
        v
    Quality Controller (Agent 2.9)

Truncation strategy:
    When text exceeds the maximum length, the agent truncates at the last
    word boundary within the limit to avoid mid-word cuts. If the last space
    falls below 80% of max_length (indicating a single very long word), the
    agent hard-truncates at max_length instead. An ellipsis character (U+2026)
    is appended to indicate truncation.

Typical usage::

    from sportmaster_card.agents.copy_editor import CopyEditorAgent
    from sportmaster_card.models.content import PlatformContent

    editor = CopyEditorAgent()
    polished = editor.edit(raw_content, max_description_length=2000)
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from sportmaster_card.models.content import PlatformContent


class CopyEditorAgent:
    """Checks and polishes generated product content.

    Performs mechanical editing:
    - Enforces character limits (title, description, seo_title)
    - Strips extra whitespace from all text fields
    - Ensures consistent formatting across content fields

    Note v0.3: Stylistic check is MANUAL on pilot -- done by GPTK team.
    Copy Editor only handles grammar, length, and formatting.

    Example::

        >>> editor = CopyEditorAgent()
        >>> polished = editor.edit(raw_content, max_description_length=2000)
    """

    def edit(
        self,
        content: PlatformContent,
        max_description_length: int = 3000,
        max_title_length: int = 150,
    ) -> PlatformContent:
        """Edit and polish PlatformContent.

        Enforces length limits and cleans up formatting on all text fields.
        Returns a new PlatformContent with edits applied -- the original
        instance is not modified (immutable Pydantic model).

        Uses real LLM (via CrewAI + OpenRouter) when OPENROUTER_API_KEY
        is set in the environment. Falls back to deterministic mechanical
        editing otherwise.

        Args:
            content: The raw PlatformContent to edit and polish.
            max_description_length: Maximum character count for the description
                field. Defaults to 3000 (Sportmaster website limit).
            max_title_length: Maximum character count for product_name and
                seo_title fields. Defaults to 150.

        Returns:
            A new PlatformContent instance with enforced limits and cleaned
            whitespace. All other fields (benefits, seo_keywords, hashes)
            are passed through unchanged.
        """
        # Rule-based agent — always use deterministic logic (no LLM needed)
        # if self._is_llm_mode():
        #     return self._edit_with_llm(
        #     content, max_description_length, max_title_length,
        #     )
        return self._edit_stub(content, max_description_length, max_title_length)

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    def _is_llm_mode(self) -> bool:
        """Check if real LLM is available (Nevel API or OpenRouter)."""
        nevel_key = os.environ.get("NEVEL_API_KEY", "").strip()
        if nevel_key:
            return True
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        return bool(openrouter_key)

    # ------------------------------------------------------------------
    # Stub editing (Phase 1 mechanical, no LLM)
    # ------------------------------------------------------------------

    def _edit_stub(
        self,
        content: PlatformContent,
        max_description_length: int,
        max_title_length: int,
    ) -> PlatformContent:
        """Edit using deterministic mechanical rules (no LLM).

        This is the original Phase 1 editing logic, preserved for use
        when no API key is available or for testing.
        """
        return PlatformContent(
            mcm_id=content.mcm_id,
            platform_id=content.platform_id,
            product_name=self._enforce_limit(
                content.product_name.strip(), max_title_length
            ),
            description=self._enforce_limit(
                content.description.strip(), max_description_length
            ),
            benefits=content.benefits,
            seo_title=self._enforce_limit(
                content.seo_title.strip(), max_title_length
            ),
            seo_meta_description=content.seo_meta_description.strip(),
            seo_keywords=content.seo_keywords,
            content_hash=content.content_hash,
            source_curated_profile_hash=content.source_curated_profile_hash,
        )

    # ------------------------------------------------------------------
    # LLM editing (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _edit_with_llm(
        self,
        content: PlatformContent,
        max_description_length: int,
        max_title_length: int,
    ) -> PlatformContent:
        """Edit using CrewAI Agent+Task with a real LLM.

        Loads the copy_editor.yaml prompt template, fills it with
        content data, and delegates to a CrewAI Crew for execution.
        Falls back to stub editing if the LLM call fails or returns
        unparseable output.

        Args:
            content: The raw PlatformContent to edit.
            max_description_length: Maximum description length.
            max_title_length: Maximum title length.

        Returns:
            PlatformContent from LLM output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "copy_editor.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Format benefits for the prompt
        benefits_text = "; ".join(
            f"{b.title}: {b.description}" for b in content.benefits
        )

        # Fill task template with content data
        task_desc = prompts["task_template"].format(
            platform_id=content.platform_id,
            product_name=content.product_name,
            description=content.description,
            benefits=benefits_text,
            seo_title=content.seo_title,
            seo_meta_description=content.seo_meta_description,
            max_title_length=max_title_length,
            max_description_length=max_description_length,
            seo_keywords=", ".join(content.seo_keywords),
        )

        agent = Agent(
            role="Copy Editor",
            goal=prompts["system_prompt"],
            backstory="Professional Russian-language copy editor for Sportmaster",
            llm=get_llm("claude_haiku"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
            output_pydantic=PlatformContent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
        except Exception:
            return self._edit_stub(content, max_description_length, max_title_length)

        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic

        # Fallback: could not parse LLM output into PlatformContent
        return self._edit_stub(content, max_description_length, max_title_length)

    def _enforce_limit(self, text: str, max_length: int) -> str:
        """Truncate text to max_length, cutting at last word boundary.

        If the text is within the limit, it is returned as-is. Otherwise,
        truncation happens at the last space character within the limit to
        avoid cutting words in half. If no suitable space exists (i.e., the
        last space is below 80% of max_length, indicating a very long word),
        a hard truncation at max_length is used instead.

        An ellipsis character (U+2026) is always appended to truncated text
        to signal that content was shortened.

        Args:
            text: The text string to potentially truncate.
            max_length: Maximum allowed character count before truncation.

        Returns:
            The original text if within limits, or truncated text with
            an appended ellipsis character.
        """
        # Text within limit needs no truncation
        if len(text) <= max_length:
            return text

        # Cut at max_length, then find last word boundary
        truncated = text[:max_length]

        # Find last space for clean word-boundary cut
        last_space = truncated.rfind(" ")

        # If last space is reasonably close to the end (>80% of limit),
        # cut at the word boundary for a cleaner result
        if last_space > max_length * 0.8:
            return truncated[:last_space].rstrip() + "\u2026"

        # Otherwise hard-truncate (the text is one very long word)
        return truncated.rstrip() + "\u2026"
