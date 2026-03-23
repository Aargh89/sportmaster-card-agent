"""Tests for InternalResearcherAgent -- stub internal document research.

Tests cover: instantiation, return type (InternalInsights), non-empty
insights list, and provenance generation with source_type=INTERNAL.
No real document analysis -- Phase 1 returns category-based stubs.
"""

from __future__ import annotations

from sportmaster_card.agents.internal_researcher import InternalResearcherAgent
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.enrichment import InternalInsights
from sportmaster_card.models.provenance import DataProvenance, SourceType


# ======================================================================
# Fixtures
# ======================================================================


def _footwear_product() -> ProductInput:
    """Build a footwear ProductInput for internal research."""
    return ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
    )


# ======================================================================
# Test: instantiation
# ======================================================================


class TestInternalResearcherCreation:
    """InternalResearcherAgent can be instantiated without any arguments."""

    def test_creation(self) -> None:
        """Agent is created successfully."""
        agent = InternalResearcherAgent()
        assert agent is not None


# ======================================================================
# Test: research returns InternalInsights
# ======================================================================


class TestResearchReturnsInternalInsights:
    """research(product) returns a tuple of (InternalInsights, provenance)."""

    def test_research_returns_internal_insights(self) -> None:
        """Result contains an InternalInsights model instance."""
        agent = InternalResearcherAgent()
        product = _footwear_product()
        insights, provenance = agent.research(product)
        assert isinstance(insights, InternalInsights)
        assert insights.mcm_id == product.mcm_id


# ======================================================================
# Test: insights list is populated
# ======================================================================


class TestInsightsNotEmpty:
    """Stub research produces at least one insight."""

    def test_insights_not_empty(self) -> None:
        """The insights list should be populated with category data."""
        agent = InternalResearcherAgent()
        product = _footwear_product()
        insights, _ = agent.research(product)
        assert len(insights.insights) > 0
        assert len(insights.pain_points) > 0
        assert len(insights.purchase_drivers) > 0


# ======================================================================
# Test: produces provenance
# ======================================================================


class TestProducesProvenance:
    """DataProvenance entries have source_type=INTERNAL."""

    def test_produces_provenance(self) -> None:
        """Provenance entries are created with INTERNAL source type."""
        agent = InternalResearcherAgent()
        product = _footwear_product()
        _, provenance = agent.research(product)

        assert len(provenance) > 0
        for entry in provenance:
            assert isinstance(entry, DataProvenance)
            assert entry.source_type == SourceType.INTERNAL
            assert entry.agent_id == "agent-1.7-internal-researcher"
