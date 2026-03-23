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

from typing import Optional

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
