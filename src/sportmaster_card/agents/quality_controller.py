"""QualityControllerAgent -- final multi-dimension quality scoring for content.

This agent aggregates compliance and fact-check results with content-based
metrics (readability, SEO keyword density, uniqueness) to produce a
QualityScore -- the gate that decides whether content proceeds to
publication (UC3) or is returned for regeneration.

Phase 1 uses heuristic scoring based on description length, keyword
presence, and report verdicts.  Phase 2 will incorporate LLM-based
readability analysis and plagiarism detection services.

Architecture::

    PlatformContent + ComplianceReport + FactCheckReport
        |
        v
    QualityControllerAgent.evaluate(content, compliance, fact_check)
        |
        +-- _score_readability()       -> float 0-1  (description length heuristic)
        +-- _score_seo()               -> float 0-1  (keyword density in description)
        +-- _score_factual_accuracy()  -> float 0-1  (from FactCheckReport)
        +-- _score_brand_compliance()  -> float 0-1  (from ComplianceReport)
        +-- _score_uniqueness()        -> float 0-1  (stub: 0.8)
        +-- _compute_overall()         -> weighted average of all dimensions
        |
        v
    QualityScore (overall + per-dimension scores + issues)

Scoring strategy (Phase 1):
    - **Readability**: Based on description length.  Very short descriptions
      (<100 chars) score low; descriptions 200-1000 chars score highest.
    - **SEO**: Ratio of SEO keywords found in the description text.
    - **Factual accuracy**: 1.0 if FactCheckReport.is_accurate, otherwise
      penalized proportionally to the number of inaccuracies found.
    - **Brand compliance**: 1.0 if ComplianceReport.is_compliant, otherwise
      penalized proportionally to the number of violations found.
    - **Uniqueness**: Stub score of 0.8 (Phase 2 will use plagiarism API).
    - **Overall**: Equal-weighted average of all five dimension scores.

Quality gate threshold: 0.7 (70%).  Content scoring at or above this
value passes to UC3 Publication; content below is returned for regeneration
with the issues list as structured feedback.

Typical usage::

    from sportmaster_card.agents.quality_controller import QualityControllerAgent
    from sportmaster_card.models.content import (
        ComplianceReport, FactCheckReport, PlatformContent,
    )

    agent = QualityControllerAgent()
    score = agent.evaluate(content, compliance_report, fact_check_report)
    if score.passes_threshold:
        publish(content)
    else:
        regenerate(content, feedback=score.issues)
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from sportmaster_card.models.content import (
    ComplianceReport,
    FactCheckReport,
    PlatformContent,
    QualityScore,
)


class QualityControllerAgent:
    """Produces multi-dimension quality scores for generated content.

    Aggregates ComplianceReport, FactCheckReport, and content-based
    heuristics into a single QualityScore with per-dimension breakdowns.
    The overall_score determines whether content passes the 0.7 quality
    gate for publication.

    Phase 1: heuristic scoring (deterministic, no LLM).
    Phase 2: LLM-based readability + plagiarism detection integration.

    The public API (evaluate method) is stable across phases -- only
    the private scoring methods change when switching to advanced analysis.

    Example::

        >>> agent = QualityControllerAgent()
        >>> score = agent.evaluate(content, compliance, fact_check)
        >>> score.passes_threshold
        True
    """

    def evaluate(
        self,
        content: PlatformContent,
        compliance: ComplianceReport,
        fact_check: FactCheckReport,
    ) -> QualityScore:
        """Evaluate content quality across all dimensions.

        Computes per-dimension scores from the content text and
        the compliance/fact-check reports, then calculates a weighted
        overall score.  Issues are collected from all failing dimensions.

        Uses real LLM (via CrewAI + OpenRouter) when OPENROUTER_API_KEY
        is set in the environment. Falls back to deterministic heuristic
        scoring otherwise.

        Args:
            content: Generated platform content to evaluate.
            compliance: Brand compliance check results from
                BrandComplianceAgent.
            fact_check: Factual accuracy check results from
                FactCheckerAgent.

        Returns:
            QualityScore with overall and per-dimension scores,
            plus an issues list for feedback on failing dimensions.
        """
        # Rule-based agent — always use deterministic logic (no LLM needed)
        # if self._is_llm_mode():
        #     return self._evaluate_with_llm(content, compliance, fact_check)
        return self._evaluate_stub(content, compliance, fact_check)

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
    # Stub evaluation (Phase 1 heuristic, no LLM)
    # ------------------------------------------------------------------

    def _evaluate_stub(
        self,
        content: PlatformContent,
        compliance: ComplianceReport,
        fact_check: FactCheckReport,
    ) -> QualityScore:
        """Evaluate using deterministic heuristic scoring (no LLM).

        This is the original Phase 1 evaluation logic, preserved for use
        when no API key is available or for testing.
        """
        # Score each dimension independently
        readability = self._score_readability(content)
        seo = self._score_seo(content)
        factual = self._score_factual_accuracy(fact_check)
        brand = self._score_brand_compliance(compliance)
        uniqueness = self._score_uniqueness()

        # Compute weighted overall score (equal weights in Phase 1)
        overall = self._compute_overall(
            readability, seo, factual, brand, uniqueness
        )

        # Collect issues from failing dimensions for regeneration feedback
        issues = self._collect_issues(
            content, compliance, fact_check,
            readability, seo, factual, brand,
        )

        return QualityScore(
            mcm_id=content.mcm_id,
            platform_id=content.platform_id,
            overall_score=round(overall, 3),
            readability_score=round(readability, 3),
            seo_score=round(seo, 3),
            factual_accuracy_score=round(factual, 3),
            brand_compliance_score=round(brand, 3),
            uniqueness_score=round(uniqueness, 3),
            issues=issues,
        )

    # ------------------------------------------------------------------
    # LLM evaluation (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _evaluate_with_llm(
        self,
        content: PlatformContent,
        compliance: ComplianceReport,
        fact_check: FactCheckReport,
    ) -> QualityScore:
        """Evaluate using CrewAI Agent+Task with a real LLM.

        Loads the quality_controller.yaml prompt template, fills it with
        content and report data, and delegates to a CrewAI Crew for
        execution. Falls back to stub evaluation if the LLM call fails
        or returns unparseable output.

        Args:
            content: Generated platform content to evaluate.
            compliance: Brand compliance check results.
            fact_check: Factual accuracy check results.

        Returns:
            QualityScore from LLM output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "quality_controller.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Format benefits and reports for the prompt
        benefits_text = "; ".join(
            f"{b.title}: {b.description}" for b in content.benefits
        )
        compliance_text = (
            f"is_compliant={compliance.is_compliant}, "
            f"violations={compliance.violations}"
        )
        fact_check_text = (
            f"is_accurate={fact_check.is_accurate}, "
            f"inaccuracies={fact_check.inaccuracies}"
        )

        # Fill task template with content and report data
        task_desc = prompts["task_template"].format(
            platform_id=content.platform_id,
            product_name=content.product_name,
            description=content.description,
            benefits=benefits_text,
            seo_title=content.seo_title,
            seo_meta_description=content.seo_meta_description,
            seo_keywords=", ".join(content.seo_keywords),
            compliance_report=compliance_text,
            fact_check_report=fact_check_text,
        )

        agent = Agent(
            role="Quality Controller",
            goal=prompts["system_prompt"],
            backstory="Final quality gate for Sportmaster content pipeline",
            llm=get_llm("claude_sonnet"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
            output_pydantic=QualityScore,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
        except Exception:
            return self._evaluate_stub(content, compliance, fact_check)

        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic

        # Fallback: could not parse LLM output into QualityScore
        return self._evaluate_stub(content, compliance, fact_check)

    # ------------------------------------------------------------------
    # Private scoring methods -- heuristic-based (Phase 1)
    # ------------------------------------------------------------------

    def _score_readability(self, content: PlatformContent) -> float:
        """Score readability based on description length heuristic.

        Very short descriptions (<100 chars) indicate incomplete content.
        Descriptions between 200-1000 chars are considered optimal.
        Very long descriptions (>2000 chars) get a slight penalty.

        Args:
            content: Platform content to evaluate.

        Returns:
            Readability score between 0.0 and 1.0.
        """
        length = len(content.description)

        if length < 50:
            return 0.2
        elif length < 100:
            return 0.4
        elif length < 200:
            return 0.7
        elif length <= 1000:
            return 0.9
        elif length <= 2000:
            return 0.85
        else:
            return 0.75

    def _score_seo(self, content: PlatformContent) -> float:
        """Score SEO quality based on keyword presence in description.

        Calculates the ratio of SEO keywords that appear somewhere
        in the product description text.  Higher coverage = better SEO.

        Args:
            content: Platform content to evaluate.

        Returns:
            SEO score between 0.0 and 1.0.
        """
        if not content.seo_keywords:
            return 0.5  # No keywords defined -- neutral score

        description_lower = content.description.lower()
        found = sum(
            1 for kw in content.seo_keywords
            if kw.lower() in description_lower
        )
        return min(found / len(content.seo_keywords), 1.0)

    def _score_factual_accuracy(self, fact_check: FactCheckReport) -> float:
        """Score factual accuracy from the FactCheckReport.

        Returns 1.0 for accurate content.  Each inaccuracy reduces
        the score by 0.2 (minimum 0.0).  Unverifiable claims get a
        lighter penalty of 0.05 each.

        Args:
            fact_check: Fact-check results from FactCheckerAgent.

        Returns:
            Factual accuracy score between 0.0 and 1.0.
        """
        if fact_check.is_accurate:
            return 1.0

        # Penalty: 0.2 per inaccuracy, 0.05 per unverifiable claim
        penalty = (
            len(fact_check.inaccuracies) * 0.2
            + len(fact_check.unverifiable_claims) * 0.05
        )
        return max(0.0, 1.0 - penalty)

    def _score_brand_compliance(self, compliance: ComplianceReport) -> float:
        """Score brand compliance from the ComplianceReport.

        Returns 1.0 for compliant content.  Each violation reduces
        the score by 0.15 (minimum 0.0).

        Args:
            compliance: Compliance results from BrandComplianceAgent.

        Returns:
            Brand compliance score between 0.0 and 1.0.
        """
        if compliance.is_compliant:
            return 1.0

        # Penalty: 0.15 per violation
        penalty = len(compliance.violations) * 0.15
        return max(0.0, 1.0 - penalty)

    def _score_uniqueness(self) -> float:
        """Score content uniqueness (stub implementation).

        Phase 1 returns a fixed score of 0.8 for all content.
        Phase 2 will integrate with a plagiarism detection API
        to compute actual uniqueness scores.

        Returns:
            Fixed uniqueness score of 0.8.
        """
        return 0.8

    def _compute_overall(
        self,
        readability: float,
        seo: float,
        factual: float,
        brand: float,
        uniqueness: float,
    ) -> float:
        """Compute weighted overall quality score.

        Phase 1 uses equal weights (0.2 each) for all five dimensions.
        Phase 2 will use platform-specific weight configurations
        loaded from PlatformProfile.

        Args:
            readability: Readability dimension score (0-1).
            seo: SEO dimension score (0-1).
            factual: Factual accuracy dimension score (0-1).
            brand: Brand compliance dimension score (0-1).
            uniqueness: Uniqueness dimension score (0-1).

        Returns:
            Weighted overall score between 0.0 and 1.0.
        """
        # Equal weights: each dimension contributes 20% to the overall score
        return (readability + seo + factual + brand + uniqueness) / 5.0

    def _collect_issues(
        self,
        content: PlatformContent,
        compliance: ComplianceReport,
        fact_check: FactCheckReport,
        readability: float,
        seo: float,
        factual: float,
        brand: float,
    ) -> list[str]:
        """Collect quality issues from all dimensions for feedback.

        Issues are collected from dimensions scoring below 0.7.
        These provide structured feedback for the Content Generator
        to make targeted improvements rather than full regeneration.

        Args:
            content: Evaluated platform content.
            compliance: Compliance results.
            fact_check: Fact-check results.
            readability: Readability score.
            seo: SEO score.
            factual: Factual accuracy score.
            brand: Brand compliance score.

        Returns:
            List of human-readable issue descriptions.
        """
        issues: list[str] = []

        if readability < 0.7:
            issues.append(
                f"Низкая читаемость: описание слишком короткое "
                f"({len(content.description)} символов)."
            )

        if seo < 0.7:
            issues.append(
                "Низкий SEO-показатель: ключевые слова не найдены в описании."
            )

        if factual < 1.0:
            for inaccuracy in fact_check.inaccuracies:
                issues.append(f"Фактическая ошибка: {inaccuracy}")

        if brand < 1.0:
            for violation in compliance.violations:
                issues.append(f"Нарушение бренд-гайдлайна: {violation}")

        return issues
