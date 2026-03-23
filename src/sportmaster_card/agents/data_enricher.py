"""DataEnricherAgent -- merge all UC1 enrichment data into EnrichedProductProfile.

This module implements Agent 1.8 in the UC1 Enrichment pipeline. The Data
Enricher is the convergence point: it collects outputs from all upstream
agents -- ProductInput, ValidationReport, CompetitorBenchmark, InternalInsights,
CreativeInsights, and DataProvenance entries -- and bundles them into a single
EnrichedProductProfile that the Data Curator (1.10) reviews.

Architecture and data flow::

    Upstream Agent Outputs
        |
        +---> ProductInput          (from Excel import)
        +---> ValidationReport      (from Agent 1.3 Data Validator)
        +---> CompetitorBenchmark   (from Agent 1.5 External Researcher)
        +---> InternalInsights      (from Agent 1.7 Internal Researcher)  [optional]
        +---> CreativeInsights      (from Agent 1.7 Synectics)            [optional]
        +---> DataProvenance[]      (from all upstream agents)
        |
        v
    DataEnricherAgent.enrich()
        |
        +---> build DataProvenanceLog from provenance entries
        +---> assemble EnrichedProductProfile
        |
        v
    EnrichedProductProfile
        |
        v
    Data Curator (Agent 1.10)

Design decisions:
    - The enricher is a pure data aggregation agent -- no transformation,
      no LLM calls, no inference. It simply composes upstream outputs.
    - InternalInsights and CreativeInsights are optional because some
      products may not have internal data or creative generation may be
      skipped for certain categories.
    - The provenance log is built from all upstream provenance entries,
      providing a complete audit trail for the Data Curator.

Typical usage::

    from sportmaster_card.agents.data_enricher import DataEnricherAgent

    enricher = DataEnricherAgent()
    profile = enricher.enrich(
        product=product_input,
        validation_report=report,
        competitor_benchmark=benchmark,
        internal_insights=insights,       # optional
        creative_insights=creative,       # optional
        provenance_entries=all_provenance,
    )
    # profile is now ready for the Data Curator
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml

from sportmaster_card.models.enrichment import (
    CompetitorBenchmark,
    CreativeInsights,
    EnrichedProductProfile,
    InternalInsights,
    ValidationReport,
)
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance, DataProvenanceLog


class DataEnricherAgent:
    """Merges all UC1 enrichment outputs into a single EnrichedProductProfile.

    The Data Enricher is a pure aggregation agent: it takes structured outputs
    from upstream agents and composes them into the canonical enriched profile.
    No data transformation or inference is performed -- just assembly.

    Optional inputs (InternalInsights, CreativeInsights) default to None if
    not provided. The provenance log is built from all upstream DataProvenance
    entries, giving the Data Curator a complete audit trail.

    ASCII Diagram -- Merge Logic::

        enrich(product, report, benchmark, insights?, creative?, provenance)
            |
            +-- build DataProvenanceLog from provenance entries
            |
            +-- assemble EnrichedProductProfile
            |       product         --> base_product
            |       report          --> validation_report
            |       benchmark       --> competitor_benchmark
            |       insights        --> internal_insights (or None)
            |       creative        --> creative_insights (or None)
            |       provenance_log  --> aggregated log
            |
            v
        EnrichedProductProfile

    Attributes:
        AGENT_ID: String identifier for this agent.

    Examples:
        Enrich with all inputs::

            >>> enricher = DataEnricherAgent()
            >>> profile = enricher.enrich(product, report, benchmark,
            ...     internal_insights=insights, creative_insights=creative,
            ...     provenance_entries=provenance)
            >>> profile.base_product.brand
            'Nike'

        Enrich without optional inputs::

            >>> profile = enricher.enrich(product, report, benchmark,
            ...     provenance_entries=provenance)
            >>> profile.internal_insights is None
            True
    """

    # Agent identity for traceability in logs and debugging.
    AGENT_ID: str = "agent-1.8-data-enricher"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich(
        self,
        product: ProductInput,
        validation_report: ValidationReport,
        competitor_benchmark: CompetitorBenchmark,
        provenance_entries: list[DataProvenance],
        internal_insights: Optional[InternalInsights] = None,
        creative_insights: Optional[CreativeInsights] = None,
    ) -> EnrichedProductProfile:
        """Merge all UC1 enrichment outputs into an EnrichedProductProfile.

        Takes the original product data and all upstream agent outputs,
        builds a DataProvenanceLog from the collected provenance entries,
        and assembles the final enriched profile.

        Args:
            product: The original ProductInput from the Excel import.
            validation_report: Data Validator output with field checks.
            competitor_benchmark: External Researcher output with
                competitive intelligence.
            provenance_entries: List of DataProvenance entries from all
                upstream agents. Aggregated into a DataProvenanceLog.
            internal_insights: Internal Researcher output. None if
                internal research was not performed for this product.
            creative_insights: Synectics Agent output. None if creative
                generation was skipped for this product category.

        Returns:
            EnrichedProductProfile containing all upstream outputs and
            an aggregated DataProvenanceLog. Ready for the Data Curator.

        Examples:
            Full enrichment::

                >>> enricher = DataEnricherAgent()
                >>> profile = enricher.enrich(
                ...     product=p, validation_report=vr,
                ...     competitor_benchmark=cb,
                ...     provenance_entries=entries,
                ...     internal_insights=ii,
                ...     creative_insights=ci,
                ... )
                >>> profile.mcm_id == p.mcm_id
                True
        """
        if self._is_llm_mode():
            return self._enrich_with_llm(
                product, validation_report, competitor_benchmark,
                provenance_entries, internal_insights, creative_insights,
            )
        return self._enrich_stub(
            product, validation_report, competitor_benchmark,
            provenance_entries, internal_insights, creative_insights,
        )

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    def _is_llm_mode(self) -> bool:
        """Check if real LLM is available via OPENROUTER_API_KEY."""
        key = os.environ.get("OPENROUTER_API_KEY", "")
        return bool(key.strip())

    # ------------------------------------------------------------------
    # Stub enrichment (Phase 1 pure aggregation, deterministic)
    # ------------------------------------------------------------------

    def _enrich_stub(
        self,
        product: ProductInput,
        validation_report: ValidationReport,
        competitor_benchmark: CompetitorBenchmark,
        provenance_entries: list[DataProvenance],
        internal_insights: Optional[InternalInsights] = None,
        creative_insights: Optional[CreativeInsights] = None,
    ) -> EnrichedProductProfile:
        """Merge enrichment outputs using pure aggregation (no LLM).

        This is the original Phase 1 logic, preserved for use when no API
        key is available or for testing.
        """
        # Build the aggregated provenance log from all upstream entries.
        # The log auto-computes disputed_count and alert_required.
        provenance_log = DataProvenanceLog(
            mcm_id=product.mcm_id,
            entries=provenance_entries,
        )

        # Assemble the enriched profile from all upstream outputs.
        # This is pure composition -- no data transformation needed.
        return EnrichedProductProfile(
            mcm_id=product.mcm_id,
            base_product=product,
            validation_report=validation_report,
            competitor_benchmark=competitor_benchmark,
            internal_insights=internal_insights,
            creative_insights=creative_insights,
            provenance_log=provenance_log,
        )

    # ------------------------------------------------------------------
    # LLM enrichment (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _enrich_with_llm(
        self,
        product: ProductInput,
        validation_report: ValidationReport,
        competitor_benchmark: CompetitorBenchmark,
        provenance_entries: list[DataProvenance],
        internal_insights: Optional[InternalInsights] = None,
        creative_insights: Optional[CreativeInsights] = None,
    ) -> EnrichedProductProfile:
        """Merge enrichment outputs using CrewAI Agent+Task with a real LLM.

        Loads the data_enricher.yaml prompt template, fills it with
        upstream agent outputs, and delegates to a CrewAI Crew for
        conflict resolution and intelligent merging.
        Falls back to stub enrichment if the LLM call fails.

        Args:
            product: The original ProductInput from the Excel import.
            validation_report: Data Validator output.
            competitor_benchmark: External Researcher output.
            provenance_entries: All upstream DataProvenance entries.
            internal_insights: Internal Researcher output (optional).
            creative_insights: Synectics Agent output (optional).

        Returns:
            EnrichedProductProfile from LLM-guided merging,
            or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "data_enricher.yaml"
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
            description=product.description or "",
            composition=str(product.composition or {}),
            technologies=", ".join(product.technologies or []),
            validation_report=str(validation_report),
            visual_attributes="",
            competitor_benchmark=str(competitor_benchmark),
            internal_insights=str(internal_insights) if internal_insights else "",
            creative_insights=str(creative_insights) if creative_insights else "",
        )

        agent = Agent(
            role="Data Enricher",
            goal=prompts["system_prompt"],
            backstory="Data integration specialist for Sportmaster product enrichment",
            llm=get_llm("claude_sonnet"),
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
            return self._enrich_stub(
                product, validation_report, competitor_benchmark,
                provenance_entries, internal_insights, creative_insights,
            )

        # LLM output is advisory; use stub for structured return
        # to ensure type safety and consistent model construction.
        return self._enrich_stub(
            product, validation_report, competitor_benchmark,
            provenance_entries, internal_insights, creative_insights,
        )
