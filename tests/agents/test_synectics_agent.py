"""Tests for SynecticsAgent -- creative metaphor and association generation.

Tests cover: instantiation, return type (CreativeInsights), default approval
status (False), non-empty metaphors, and technology-influenced associations.
No LLM calls -- Phase 1 uses template-based creative generation.
"""

from __future__ import annotations

from sportmaster_card.agents.synectics_agent import SynecticsAgent
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.enrichment import CreativeInsights


# ======================================================================
# Fixtures
# ======================================================================


def _product_with_tech() -> ProductInput:
    """Build a ProductInput with technologies for creative generation."""
    return ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        technologies=["Air Zoom", "React", "Flywire"],
    )


def _product_no_tech() -> ProductInput:
    """Build a ProductInput without technologies."""
    return ProductInput(
        mcm_id="MCM-002-WHT-40",
        brand="Adidas",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Повседневные кроссовки",
        product_name="Adidas Ultraboost Light",
    )


# ======================================================================
# Test: instantiation
# ======================================================================


class TestSynecticsCreation:
    """SynecticsAgent can be instantiated without any arguments."""

    def test_creation(self) -> None:
        """Agent is created successfully."""
        agent = SynecticsAgent()
        assert agent is not None


# ======================================================================
# Test: generate returns CreativeInsights
# ======================================================================


class TestGenerateReturnsCreativeInsights:
    """generate(product) returns a CreativeInsights model."""

    def test_generate_returns_creative_insights(self) -> None:
        """Result is a CreativeInsights instance with matching mcm_id."""
        agent = SynecticsAgent()
        product = _product_with_tech()
        result = agent.generate(product)
        assert isinstance(result, CreativeInsights)
        assert result.mcm_id == product.mcm_id


# ======================================================================
# Test: insights not approved by default
# ======================================================================


class TestInsightsNotApprovedByDefault:
    """Creative output requires GPTK approval before use."""

    def test_insights_not_approved_by_default(self) -> None:
        """approved flag must be False until GPTK review."""
        agent = SynecticsAgent()
        product = _product_with_tech()
        result = agent.generate(product)
        assert result.approved is False


# ======================================================================
# Test: metaphors not empty
# ======================================================================


class TestMetaphorsNotEmpty:
    """Generated creative output includes at least one metaphor."""

    def test_metaphors_not_empty(self) -> None:
        """Metaphors list should be populated."""
        agent = SynecticsAgent()
        product = _product_with_tech()
        result = agent.generate(product)
        assert len(result.metaphors) > 0


# ======================================================================
# Test: associations based on technologies
# ======================================================================


class TestAssociationsBasedOnTechnologies:
    """Technologies in the product influence the creative output."""

    def test_associations_based_on_technologies(self) -> None:
        """Products with technologies get richer associations."""
        agent = SynecticsAgent()

        with_tech = agent.generate(_product_with_tech())
        without_tech = agent.generate(_product_no_tech())

        # Product with technologies should have more associations
        # because each technology maps to additional creative material.
        assert len(with_tech.associations) > len(without_tech.associations)
