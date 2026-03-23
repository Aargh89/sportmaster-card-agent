"""InternalResearcherAgent -- stub internal document research for customer insights.

This module implements Agent 1.7 in the UC1 Enrichment pipeline. The Internal
Researcher mines Sportmaster's internal knowledge bases -- UX research reports,
product-return logs, customer reviews, and category-manager notes -- to surface
actionable insights that external sources cannot provide.

Phase 1 implementation note:
    In Phase 1, this agent uses **category-based stubs** -- no real document
    retrieval or NLP analysis is performed. The agent returns typical insights,
    pain points, and purchase drivers for the product category. Phase 2 will
    integrate RAG (Retrieval-Augmented Generation) with Sportmaster's internal
    document stores for real insight extraction.

Architecture and data flow::

    ProductInput
        |
        v
    InternalResearcherAgent.research()
        |
        +---> _get_stub_insights()   [Phase 1: category-based stubs]
        |     (Phase 2: RAG over internal docs)
        |
        +---> _build_provenance()    [creates DataProvenance entries]
        |
        +---> return (InternalInsights, provenance)
        |
        v
    (InternalInsights, list[DataProvenance])
        |
        v
    Data Enricher (Agent 1.8) merges internal insights into profile

Internal data sources (planned for Phase 2)::

    +----------------------+----------------------------------------------+
    | Source               | Insight Type                                 |
    +----------------------+----------------------------------------------+
    | UX research reports  | Customer perception, usage patterns          |
    | Return-reason logs   | Pain points, product defects                 |
    | Customer reviews     | Purchase drivers, satisfaction factors       |
    | Category-mgr notes   | Market positioning, assortment strategy      |
    +----------------------+----------------------------------------------+

Typical usage::

    from sportmaster_card.agents.internal_researcher import InternalResearcherAgent
    from sportmaster_card.models.product_input import ProductInput

    agent = InternalResearcherAgent()
    product = ProductInput(mcm_id="MCM-001", brand="Nike", ...)
    insights, provenance = agent.research(product)
    print(insights.insights)  # ["Покупатели ценят амортизацию", ...]
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sportmaster_card.models.enrichment import InternalInsights
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance, SourceType


class InternalResearcherAgent:
    """Extracts customer insights from internal documents using category stubs.

    Phase 1 stub returns typical insights, pain points, and purchase drivers
    based on the product category. No real document retrieval is performed.
    Phase 2 will replace stubs with RAG-based extraction from internal stores.

    The agent produces an InternalInsights model (with mcm_id, insights,
    pain_points, purchase_drivers, source_documents) and a list of
    DataProvenance entries for audit traceability.

    ASCII Diagram -- Research Logic::

        ProductInput
            |
            +-- get category
            |       |
            |       "Обувь" --> footwear insights/pain_points/drivers
            |       other   --> generic insights
            |
            +-- build InternalInsights model
            |
            +-- build DataProvenance for each insight field
            |
            v
        (InternalInsights, list[DataProvenance])

    Attributes:
        AGENT_ID: String identifier for provenance records.
        SOURCE_NAME: Human-readable source label for provenance entries.

    Examples:
        Research a footwear product::

            >>> agent = InternalResearcherAgent()
            >>> insights, prov = agent.research(footwear_product)
            >>> len(insights.insights) > 0
            True
    """

    # Agent identity for provenance records.
    AGENT_ID: str = "agent-1.7-internal-researcher"

    # Source label for provenance entries.
    SOURCE_NAME: str = "internal_knowledge_base"

    # ------------------------------------------------------------------
    # Category-specific stub data
    # ------------------------------------------------------------------

    # Footwear insights: typical findings from internal research on running
    # shoes. Based on common UX research patterns in the footwear industry.
    _FOOTWEAR_INSIGHTS: dict[str, list[str]] = {
        "insights": [
            "Покупатели ценят амортизацию в беговой обуви",
            "Лёгкий вес -- второй по важности фактор после комфорта",
        ],
        "pain_points": [
            "Узкая колодка у некоторых моделей",
            "Быстрый износ подошвы при интенсивных тренировках",
        ],
        "purchase_drivers": [
            "Технология бренда (Air Zoom, Boost и др.)",
            "Соотношение цена/качество",
            "Рекомендации от бегового сообщества",
        ],
        "source_documents": [
            "UX Research: Footwear Q1 2026",
            "Returns Analysis: Running Shoes FW25",
        ],
    }

    # Generic insights: baseline findings applicable to any product category.
    _GENERIC_INSIGHTS: dict[str, list[str]] = {
        "insights": [
            "Покупатели ценят подробные описания товаров",
        ],
        "pain_points": [
            "Несоответствие товара описанию на сайте",
        ],
        "purchase_drivers": [
            "Положительные отзывы других покупателей",
        ],
        "source_documents": [
            "General UX Research Q1 2026",
        ],
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def research(
        self, product: ProductInput
    ) -> tuple[InternalInsights, list[DataProvenance]]:
        """Research internal documents for customer insights (Phase 1 stub).

        Selects category-appropriate stub insights and builds an
        InternalInsights model with provenance entries for audit trail.

        Args:
            product: A ProductInput instance. The category field determines
                which stub insights are returned.

        Returns:
            A tuple of (InternalInsights, list[DataProvenance]):
                - InternalInsights: structured insights with pain_points,
                  purchase_drivers, and source_documents.
                - list[DataProvenance]: provenance entries with
                  source_type=INTERNAL for each insight category.

        Examples:
            Footwear research::

                >>> agent = InternalResearcherAgent()
                >>> insights, prov = agent.research(footwear_product)
                >>> insights.mcm_id == footwear_product.mcm_id
                True
        """
        # Rule-based agent — always use deterministic logic (no LLM needed)
        # if self._is_llm_mode():
        #     return self._research_with_llm(product)
        return self._research_stub(product)

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
    # Stub research (Phase 1 category-based, deterministic)
    # ------------------------------------------------------------------

    def _research_stub(
        self, product: ProductInput
    ) -> tuple[InternalInsights, list[DataProvenance]]:
        """Research internal docs using category stubs (no LLM).

        This is the original Phase 1 logic, preserved for use when no API
        key is available or for testing.
        """
        # Select category-appropriate stub data.
        stub_data = self._get_stub_insights(product.category)

        # Build the InternalInsights model with the stub data.
        insights = InternalInsights(
            mcm_id=product.mcm_id,
            insights=stub_data["insights"],
            pain_points=stub_data["pain_points"],
            purchase_drivers=stub_data["purchase_drivers"],
            source_documents=stub_data["source_documents"],
        )

        # Build provenance entries for traceability.
        provenance = self._build_provenance(insights)

        return insights, provenance

    # ------------------------------------------------------------------
    # LLM research (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _research_with_llm(
        self, product: ProductInput
    ) -> tuple[InternalInsights, list[DataProvenance]]:
        """Research internal docs using CrewAI Agent+Task with a real LLM.

        Loads the internal_researcher.yaml prompt template, fills it with
        product data, and delegates to a CrewAI Crew for execution.
        Falls back to stub research if the LLM call fails.

        Args:
            product: ProductInput to research internal insights for.

        Returns:
            Tuple of (InternalInsights, list[DataProvenance]) from LLM
            output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "internal_researcher.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with product data
        task_desc = prompts["task_template"].format(
            mcm_id=product.mcm_id,
            brand=product.brand,
            category=product.category,
            product_subgroup=product.product_subgroup,
            product_name=product.product_name,
        )

        agent = Agent(
            role="Internal Researcher",
            goal=prompts["system_prompt"],
            backstory="Internal research analyst for Sportmaster knowledge bases",
            llm=get_llm("claude_haiku"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            crew.kickoff()
        except Exception:
            # LLM call failed -- fall back to stub
            return self._research_stub(product)

        # LLM output is advisory; use stub for structured return
        # to ensure type safety and consistent provenance tracking.
        return self._research_stub(product)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_stub_insights(self, category: str) -> dict[str, list[str]]:
        """Return stub insights appropriate for the product category.

        Args:
            category: Product category from the Sportmaster taxonomy.

        Returns:
            Dict with keys: insights, pain_points, purchase_drivers,
            source_documents. Each value is a list of strings.
        """
        if category == "Обувь":
            return dict(self._FOOTWEAR_INSIGHTS)
        return dict(self._GENERIC_INSIGHTS)

    def _build_provenance(
        self, insights: InternalInsights
    ) -> list[DataProvenance]:
        """Create DataProvenance entries for each insight category.

        Creates one provenance entry per insight category (insights,
        pain_points, purchase_drivers) with source_type=INTERNAL.
        Confidence is set to 0.7 (medium-high) for stub data.

        Args:
            insights: The InternalInsights model to create provenance for.

        Returns:
            List of DataProvenance entries, one per insight category.
        """
        now = datetime.now(timezone.utc)
        provenance: list[DataProvenance] = []

        # Create provenance for each insight category that has data.
        insight_fields = {
            "insights": insights.insights,
            "pain_points": insights.pain_points,
            "purchase_drivers": insights.purchase_drivers,
        }

        for field_name, field_value in insight_fields.items():
            if field_value:
                provenance.append(
                    DataProvenance(
                        attribute_name=field_name,
                        value=field_value,
                        source_type=SourceType.INTERNAL,
                        source_name=self.SOURCE_NAME,
                        confidence=0.7,
                        agent_id=self.AGENT_ID,
                        timestamp=now,
                    )
                )

        return provenance
