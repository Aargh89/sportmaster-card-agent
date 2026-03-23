"""Tests for DataCuratorAgent -- validate enriched profile and produce CuratedProfile.

Tests cover: instantiation, return type (CuratedProfile), key field population,
technology preservation, and provenance passthrough.
No LLM calls -- the curator uses deterministic extraction and flattening.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sportmaster_card.agents.data_curator import DataCuratorAgent
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.enrichment import (
    CompetitorBenchmark,
    CompetitorCard,
    CuratedProfile,
    EnrichedProductProfile,
    FieldValidation,
    ValidationReport,
)
from sportmaster_card.models.provenance import DataProvenance, DataProvenanceLog, SourceType


# ======================================================================
# Fixtures
# ======================================================================


def _enriched_profile() -> EnrichedProductProfile:
    """Build an EnrichedProductProfile with typical data for curation."""
    product = ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        description="Легкие беговые кроссовки с технологией Air Zoom",
        technologies=["Air Zoom", "React"],
        composition={"Верх": "Текстиль", "Подошва": "Резина"},
    )

    report = ValidationReport(
        mcm_id="MCM-001-BLK-42",
        field_validations=[
            FieldValidation(field_name="brand", is_present=True, is_valid=True),
        ],
        missing_required=[],
        overall_completeness=0.8,
        is_valid=True,
    )

    benchmark = CompetitorBenchmark(
        mcm_id="MCM-001-BLK-42",
        competitors=[
            CompetitorCard(
                platform="wb",
                product_name="Nike Pegasus 41",
                key_features=["амортизация", "лёгкий вес"],
            ),
        ],
        benchmark_summary="Competitor at 12990 RUB.",
        average_price=12990.0,
        common_features=["амортизация"],
    )

    now = datetime.now(timezone.utc)
    provenance_log = DataProvenanceLog(
        mcm_id="MCM-001-BLK-42",
        entries=[
            DataProvenance(
                attribute_name="brand",
                value="Nike",
                source_type=SourceType.INTERNAL,
                source_name="Excel шаблон",
                confidence=1.0,
                agent_id="agent-1.3-data-validator",
                timestamp=now,
            ),
        ],
    )

    return EnrichedProductProfile(
        mcm_id="MCM-001-BLK-42",
        base_product=product,
        validation_report=report,
        competitor_benchmark=benchmark,
        provenance_log=provenance_log,
    )


# ======================================================================
# Test: instantiation
# ======================================================================


class TestDataCuratorCreation:
    """DataCuratorAgent can be instantiated without any arguments."""

    def test_creation(self) -> None:
        """Agent is created successfully."""
        agent = DataCuratorAgent()
        assert agent is not None


# ======================================================================
# Test: curate returns CuratedProfile
# ======================================================================


class TestCurateReturnsCuratedProfile:
    """curate() returns a CuratedProfile instance."""

    def test_curate_returns_curated_profile(self) -> None:
        """Result is a CuratedProfile with matching mcm_id."""
        agent = DataCuratorAgent()
        profile = _enriched_profile()
        curated = agent.curate(profile)
        assert isinstance(curated, CuratedProfile)
        assert curated.mcm_id == "MCM-001-BLK-42"


# ======================================================================
# Test: curated profile has key fields
# ======================================================================


class TestCuratedProfileHasKeyFields:
    """product_name, brand, category are populated from base product."""

    def test_curated_profile_has_key_fields(self) -> None:
        """Key identity fields are extracted from the enriched profile."""
        agent = DataCuratorAgent()
        curated = agent.curate(_enriched_profile())

        assert curated.product_name == "Nike Air Zoom Pegasus 41"
        assert curated.brand == "Nike"
        assert curated.category == "Обувь"
        assert len(curated.description) > 0


# ======================================================================
# Test: curated profile has technologies
# ======================================================================


class TestCuratedProfileHasTechnologies:
    """Technologies from the input product are preserved in the curated output."""

    def test_curated_profile_has_technologies(self) -> None:
        """Technologies list is carried through from base product."""
        agent = DataCuratorAgent()
        curated = agent.curate(_enriched_profile())

        assert "Air Zoom" in curated.technologies
        assert "React" in curated.technologies


# ======================================================================
# Test: curated profile has provenance
# ======================================================================


class TestCuratedProfileHasProvenance:
    """Provenance log is passed through from the enriched profile."""

    def test_curated_profile_has_provenance(self) -> None:
        """provenance_log is preserved for audit trail."""
        agent = DataCuratorAgent()
        curated = agent.curate(_enriched_profile())

        assert curated.provenance_log is not None
        assert curated.provenance_log.mcm_id == "MCM-001-BLK-42"
        assert len(curated.provenance_log.entries) > 0
