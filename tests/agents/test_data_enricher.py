"""Tests for DataEnricherAgent -- merge all UC1 data into EnrichedProductProfile.

Tests cover: instantiation, return type (EnrichedProductProfile), merging all
inputs, handling missing optionals, and building the provenance log.
No LLM calls -- the enricher is a pure data aggregation agent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sportmaster_card.agents.data_enricher import DataEnricherAgent
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.enrichment import (
    CompetitorBenchmark,
    CompetitorCard,
    CreativeInsights,
    EnrichedProductProfile,
    FieldValidation,
    InternalInsights,
    ValidationReport,
)
from sportmaster_card.models.provenance import DataProvenance, DataProvenanceLog, SourceType


# ======================================================================
# Fixtures
# ======================================================================


def _product() -> ProductInput:
    """Build a standard footwear ProductInput."""
    return ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        technologies=["Air Zoom", "React"],
    )


def _validation_report() -> ValidationReport:
    """Build a simple ValidationReport."""
    return ValidationReport(
        mcm_id="MCM-001-BLK-42",
        field_validations=[
            FieldValidation(field_name="brand", is_present=True, is_valid=True),
        ],
        missing_required=[],
        overall_completeness=0.5,
        is_valid=True,
    )


def _competitor_benchmark() -> CompetitorBenchmark:
    """Build a CompetitorBenchmark with one competitor."""
    return CompetitorBenchmark(
        mcm_id="MCM-001-BLK-42",
        competitors=[
            CompetitorCard(platform="wb", product_name="Nike Pegasus 41"),
        ],
        benchmark_summary="Competitor found at 12990 RUB.",
        average_price=12990.0,
    )


def _internal_insights() -> InternalInsights:
    """Build InternalInsights with stub data."""
    return InternalInsights(
        mcm_id="MCM-001-BLK-42",
        insights=["Покупатели ценят амортизацию"],
        pain_points=["Узкая колодка"],
        purchase_drivers=["Технология бренда"],
    )


def _creative_insights() -> CreativeInsights:
    """Build CreativeInsights with stub data."""
    return CreativeInsights(
        mcm_id="MCM-001-BLK-42",
        metaphors=["Облако для ваших ног"],
        associations=["лёгкость"],
        emotional_hooks=["Почувствуйте разницу"],
    )


def _provenance_entries() -> list[DataProvenance]:
    """Build sample provenance entries from upstream agents."""
    now = datetime.now(timezone.utc)
    return [
        DataProvenance(
            attribute_name="brand",
            value="Nike",
            source_type=SourceType.INTERNAL,
            source_name="Excel шаблон",
            confidence=1.0,
            agent_id="agent-1.3-data-validator",
            timestamp=now,
        ),
        DataProvenance(
            attribute_name="sole_type",
            value="Резина",
            source_type=SourceType.PHOTO,
            source_name="product_photo",
            confidence=0.6,
            agent_id="agent-1.4-visual-interpreter",
            timestamp=now,
        ),
    ]


# ======================================================================
# Test: instantiation
# ======================================================================


class TestDataEnricherCreation:
    """DataEnricherAgent can be instantiated without any arguments."""

    def test_creation(self) -> None:
        """Agent is created successfully."""
        agent = DataEnricherAgent()
        assert agent is not None


# ======================================================================
# Test: enrich returns EnrichedProductProfile
# ======================================================================


class TestEnrichReturnsEnrichedProfile:
    """enrich() returns an EnrichedProductProfile instance."""

    def test_enrich_returns_enriched_profile(self) -> None:
        """Result is an EnrichedProductProfile with matching mcm_id."""
        agent = DataEnricherAgent()
        profile = agent.enrich(
            product=_product(),
            validation_report=_validation_report(),
            competitor_benchmark=_competitor_benchmark(),
            provenance_entries=_provenance_entries(),
        )
        assert isinstance(profile, EnrichedProductProfile)
        assert profile.mcm_id == "MCM-001-BLK-42"


# ======================================================================
# Test: enrich merges all inputs
# ======================================================================


class TestEnrichMergesAllInputs:
    """Profile contains validation_report, competitor_benchmark, and optionals."""

    def test_enrich_merges_all_inputs(self) -> None:
        """All provided inputs are present in the enriched profile."""
        agent = DataEnricherAgent()
        profile = agent.enrich(
            product=_product(),
            validation_report=_validation_report(),
            competitor_benchmark=_competitor_benchmark(),
            internal_insights=_internal_insights(),
            creative_insights=_creative_insights(),
            provenance_entries=_provenance_entries(),
        )

        assert profile.validation_report is not None
        assert profile.competitor_benchmark is not None
        assert profile.internal_insights is not None
        assert profile.creative_insights is not None


# ======================================================================
# Test: enrich handles missing optionals
# ======================================================================


class TestEnrichHandlesMissingOptionals:
    """Works without internal_insights and creative_insights."""

    def test_enrich_handles_missing_optionals(self) -> None:
        """Profile is created with None for optional fields."""
        agent = DataEnricherAgent()
        profile = agent.enrich(
            product=_product(),
            validation_report=_validation_report(),
            competitor_benchmark=_competitor_benchmark(),
            provenance_entries=_provenance_entries(),
        )

        assert profile.internal_insights is None
        assert profile.creative_insights is None
        # Core fields still present
        assert profile.base_product.brand == "Nike"
        assert profile.validation_report.is_valid is True


# ======================================================================
# Test: enrich builds provenance log
# ======================================================================


class TestEnrichBuildsProvenanceLog:
    """Provenance log entries are populated from upstream provenance."""

    def test_enrich_builds_provenance_log(self) -> None:
        """provenance_log.entries is populated with upstream entries."""
        agent = DataEnricherAgent()
        entries = _provenance_entries()
        profile = agent.enrich(
            product=_product(),
            validation_report=_validation_report(),
            competitor_benchmark=_competitor_benchmark(),
            provenance_entries=entries,
        )

        assert isinstance(profile.provenance_log, DataProvenanceLog)
        assert len(profile.provenance_log.entries) == len(entries)
        assert profile.provenance_log.mcm_id == "MCM-001-BLK-42"
