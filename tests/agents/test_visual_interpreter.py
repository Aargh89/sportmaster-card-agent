"""Tests for VisualInterpreterAgent -- stub visual attribute extraction.

Tests cover: instantiation, basic interpret return type, footwear-specific
attribute extraction, handling of missing photo URLs, and provenance generation.
No real image analysis -- the Phase 2 stub returns rule-based attributes.
"""

from __future__ import annotations

from sportmaster_card.agents.visual_interpreter import VisualInterpreterAgent
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance, SourceType


# ======================================================================
# Fixtures -- reusable product inputs for multiple tests
# ======================================================================


def _footwear_product() -> ProductInput:
    """Build a footwear ProductInput with photo URLs for visual analysis."""
    return ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        photo_urls=["https://cdn.sportmaster.ru/photos/MCM-001-1.jpg"],
    )


def _no_photo_product() -> ProductInput:
    """Build a ProductInput with no photo URLs."""
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


class TestVisualInterpreterCreation:
    """VisualInterpreterAgent can be instantiated without any arguments."""

    def test_creation(self) -> None:
        """Agent is created successfully with an agent ID."""
        agent = VisualInterpreterAgent()
        assert agent is not None


# ======================================================================
# Test: interpret returns dict
# ======================================================================


class TestInterpretReturnsDict:
    """interpret(product) returns a tuple of (dict, list[DataProvenance])."""

    def test_interpret_returns_dict(self) -> None:
        """Result contains a dict of extracted attributes."""
        agent = VisualInterpreterAgent()
        product = _footwear_product()
        attributes, provenance = agent.interpret(product)
        assert isinstance(attributes, dict)


# ======================================================================
# Test: footwear attribute extraction
# ======================================================================


class TestInterpretFootwearAttributes:
    """For footwear category, extracts sole_type, closure_type, upper_material."""

    def test_interpret_footwear_attributes(self) -> None:
        """Footwear products get category-specific visual attributes."""
        agent = VisualInterpreterAgent()
        product = _footwear_product()
        attributes, _ = agent.interpret(product)

        assert "sole_type" in attributes
        assert "closure_type" in attributes
        assert "upper_material" in attributes
        assert len(attributes) >= 3


# ======================================================================
# Test: handles no visual (photo_urls is None)
# ======================================================================


class TestHandlesNoVisual:
    """When photo_urls is None, returns empty dict and empty provenance."""

    def test_handles_no_visual(self) -> None:
        """No photos means no visual attributes can be extracted."""
        agent = VisualInterpreterAgent()
        product = _no_photo_product()
        attributes, provenance = agent.interpret(product)

        assert attributes == {}
        assert provenance == []


# ======================================================================
# Test: produces provenance
# ======================================================================


class TestProducesProvenance:
    """DataProvenance entries have source_type=PHOTO."""

    def test_produces_provenance(self) -> None:
        """Each extracted attribute gets a PHOTO-sourced provenance entry."""
        agent = VisualInterpreterAgent()
        product = _footwear_product()
        attributes, provenance = agent.interpret(product)

        assert len(provenance) > 0
        for entry in provenance:
            assert isinstance(entry, DataProvenance)
            assert entry.source_type == SourceType.PHOTO
            assert entry.agent_id == "agent-1.4-visual-interpreter"
