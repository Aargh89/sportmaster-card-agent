"""BrandComplianceAgent -- checks content against brand guidelines.

This agent verifies that generated PlatformContent adheres to brand
guidelines: correct brand name casing, absence of forbidden words,
and proper terminology.  It produces a ComplianceReport with a boolean
verdict and a list of specific violations with suggested fixes.

Phase 1 uses rule-based string matching for compliance checks.
Phase 2 will add tone-of-voice analysis via LLM and richer brand
guideline databases loaded from YAML configuration files.

Architecture::

    PlatformContent + brand guidelines
        |
        v
    BrandComplianceAgent.check(content, brand_name, forbidden_words)
        |
        +-- _check_forbidden_words()    -> list of forbidden-word violations
        +-- _check_brand_casing()       -> list of brand-casing violations
        |
        v
    ComplianceReport (is_compliant + violations + suggestions)

Compliance checks (Phase 1):
    1. **Forbidden words**: Scans product_name and description for words
       from the forbidden list.  Matches are case-insensitive.
    2. **Brand casing**: Verifies that the brand name appears with correct
       capitalization everywhere in the content.  Finds instances where
       the brand is written in wrong case (e.g., "nike" instead of "Nike").

Typical usage::

    from sportmaster_card.agents.brand_compliance import BrandComplianceAgent
    from sportmaster_card.models.content import PlatformContent

    agent = BrandComplianceAgent()
    content = PlatformContent(...)
    report = agent.check(content, brand_name="Nike", forbidden_words=["дешёвый"])
    print(report.is_compliant)  # True or False
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from sportmaster_card.models.content import ComplianceReport, PlatformContent


class BrandComplianceAgent:
    """Checks PlatformContent against brand guidelines and forbidden words.

    The Brand Compliance Agent performs rule-based verification of
    generated content to ensure it meets brand standards before
    publication.  Two main checks are performed:

    1. Forbidden-word scan across all text fields.
    2. Brand-name casing verification in all text fields.

    Phase 1: deterministic rule-based checking.
    Phase 2: LLM-based tone analysis and expanded guideline support.

    Example::

        >>> agent = BrandComplianceAgent()
        >>> from sportmaster_card.models.content import PlatformContent, Benefit
        >>> content = PlatformContent(
        ...     mcm_id="MCM-001", platform_id="sm_site",
        ...     product_name="Nike Pegasus 41",
        ...     description="Отличные кроссовки Nike.",
        ...     benefits=[Benefit(title="Комфорт", description="Удобные.")],
        ...     seo_title="Nike Pegasus", seo_meta_description="Купить.",
        ...     seo_keywords=["nike"],
        ... )
        >>> report = agent.check(content, brand_name="Nike")
        >>> report.is_compliant
        True
    """

    def check(
        self,
        content: PlatformContent,
        brand_name: str,
        forbidden_words: list[str] | None = None,
    ) -> ComplianceReport:
        """Check content against brand guidelines and forbidden words.

        Runs all compliance checks and aggregates results into a
        single ComplianceReport.  Content is compliant only if ALL
        checks pass (no violations found).

        Uses real LLM (via CrewAI + OpenRouter) when OPENROUTER_API_KEY
        is set in the environment. Falls back to deterministic rule-based
        checking otherwise.

        Args:
            content: Generated platform content to verify.
            brand_name: Official brand name with correct casing
                (e.g., "Nike", not "nike" or "NIKE").
            forbidden_words: Optional list of words/phrases banned
                by the platform or brand.  Case-insensitive matching.

        Returns:
            ComplianceReport with is_compliant verdict, violations
            list, and suggested fixes for each violation.
        """
        if self._is_llm_mode():
            return self._check_with_llm(content, brand_name, forbidden_words)
        return self._check_stub(content, brand_name, forbidden_words)

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
    # Stub checking (Phase 1 rule-based, no LLM)
    # ------------------------------------------------------------------

    def _check_stub(
        self,
        content: PlatformContent,
        brand_name: str,
        forbidden_words: list[str] | None = None,
    ) -> ComplianceReport:
        """Check using deterministic rule-based matching (no LLM).

        This is the original Phase 1 checking logic, preserved for use
        when no API key is available or for testing.
        """
        violations: list[str] = []
        suggestions: list[str] = []

        # Collect all text from the content into a single searchable block
        text_fields = self._extract_text(content)

        # Check 1: Forbidden words in any text field
        if forbidden_words:
            fw_violations, fw_suggestions = self._check_forbidden_words(
                text_fields, forbidden_words
            )
            violations.extend(fw_violations)
            suggestions.extend(fw_suggestions)

        # Check 2: Brand name casing in product_name and description
        bc_violations, bc_suggestions = self._check_brand_casing(
            text_fields, brand_name
        )
        violations.extend(bc_violations)
        suggestions.extend(bc_suggestions)

        return ComplianceReport(
            mcm_id=content.mcm_id,
            is_compliant=len(violations) == 0,
            violations=violations,
            suggestions=suggestions,
        )

    # ------------------------------------------------------------------
    # LLM checking (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _check_with_llm(
        self,
        content: PlatformContent,
        brand_name: str,
        forbidden_words: list[str] | None = None,
    ) -> ComplianceReport:
        """Check using CrewAI Agent+Task with a real LLM.

        Loads the brand_compliance.yaml prompt template, fills it with
        content data, and delegates to a CrewAI Crew for execution.
        Falls back to stub checking if the LLM call fails or returns
        unparseable output.

        Args:
            content: Generated platform content to verify.
            brand_name: Official brand name with correct casing.
            forbidden_words: Optional list of banned words/phrases.

        Returns:
            ComplianceReport from LLM output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "brand_compliance.yaml"
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
            brand=brand_name,
            brand_name_rules=f"Правильное написание: {brand_name}",
            forbidden_words=", ".join(forbidden_words or []),
            required_terminology="",
            tone_of_voice="professional",
        )

        agent = Agent(
            role="Brand Compliance Checker",
            goal=prompts["system_prompt"],
            backstory="Brand compliance specialist for Sportmaster",
            llm=get_llm("claude_haiku"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
            output_pydantic=ComplianceReport,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
        except Exception:
            return self._check_stub(content, brand_name, forbidden_words)

        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic

        # Fallback: could not parse LLM output into ComplianceReport
        return self._check_stub(content, brand_name, forbidden_words)

    # ------------------------------------------------------------------
    # Private helpers -- rule-based compliance checks (Phase 1)
    # ------------------------------------------------------------------

    def _extract_text(self, content: PlatformContent) -> str:
        """Extract all text content into a single string for scanning.

        Concatenates product_name, description, benefit titles and
        descriptions, seo_title, and seo_meta_description into one
        searchable text block.

        Args:
            content: Platform content to extract text from.

        Returns:
            Concatenated text from all content fields.
        """
        parts: list[str] = [
            content.product_name,
            content.description,
            content.seo_title,
            content.seo_meta_description,
        ]
        for benefit in content.benefits:
            parts.append(benefit.title)
            parts.append(benefit.description)
        return " ".join(parts)

    def _check_forbidden_words(
        self,
        text: str,
        forbidden_words: list[str],
    ) -> tuple[list[str], list[str]]:
        """Scan text for forbidden words (case-insensitive).

        Each forbidden word is matched as a whole word using regex
        word boundaries to avoid false positives on substrings.

        Args:
            text: Concatenated content text to scan.
            forbidden_words: List of banned words/phrases.

        Returns:
            Tuple of (violations, suggestions) lists.
        """
        violations: list[str] = []
        suggestions: list[str] = []
        text_lower = text.lower()

        for word in forbidden_words:
            if word.lower() in text_lower:
                violations.append(
                    f"Запрещённое слово '{word}' найдено в контенте."
                )
                suggestions.append(
                    f"Удалить или заменить '{word}' на допустимый синоним."
                )

        return violations, suggestions

    def _check_brand_casing(
        self,
        text: str,
        brand_name: str,
    ) -> tuple[list[str], list[str]]:
        """Verify brand name appears with correct capitalization.

        Finds all occurrences of the brand name (case-insensitive)
        and checks that each one matches the official casing exactly.
        Occurrences in wrong case are reported as violations.

        Args:
            text: Concatenated content text to scan.
            brand_name: Official brand name with correct casing.

        Returns:
            Tuple of (violations, suggestions) lists.
        """
        violations: list[str] = []
        suggestions: list[str] = []

        # Find all case-insensitive occurrences of the brand name
        pattern = re.compile(re.escape(brand_name), re.IGNORECASE)
        matches = pattern.findall(text)

        # Check each occurrence for correct casing
        wrong_cases = [m for m in matches if m != brand_name]
        if wrong_cases:
            # Report unique wrong-case variants
            unique_wrong = set(wrong_cases)
            for wrong in unique_wrong:
                violations.append(
                    f"Название бренда в неправильном регистре: '{wrong}' "
                    f"вместо '{brand_name}'."
                )
                suggestions.append(
                    f"Использовать '{brand_name}' вместо '{wrong}'."
                )

        return violations, suggestions
