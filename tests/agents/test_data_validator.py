"""Tests for DataValidatorAgent -- rule-based product data validation.

Tests cover: instantiation, complete product validation, minimal product
validation, missing optional field tracking, and provenance generation.
No real API calls -- the validator is purely deterministic.
"""

from __future__ import annotations

from sportmaster_card.agents.data_validator import DataValidatorAgent
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.enrichment import ValidationReport
from sportmaster_card.models.provenance import DataProvenance, SourceType


# ======================================================================
# Fixtures -- reusable product inputs for multiple tests
# ======================================================================


def _complete_product() -> ProductInput:
    """Build a ProductInput with ALL fields filled (required + optional)."""
    return ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        description="Легкие беговые кроссовки с технологией Air Zoom",
        gender="Мужской",
        season="Весна-Лето 2026",
        color="Чёрный",
        assortment_segment="TRD",
        assortment_type="Basic",
        assortment_level="Mid",
        technologies=["Air Zoom", "Flywire"],
        composition={"Верх": "Текстиль 80%", "Подошва": "Резина"},
        photo_urls=["https://cdn.sportmaster.ru/photos/MCM-001-1.jpg"],
    )


def _minimal_product() -> ProductInput:
    """Build a ProductInput with ONLY the 6 required fields filled."""
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


class TestDataValidatorCreation:
    """DataValidatorAgent can be instantiated without any arguments."""

    def test_data_validator_creation(self) -> None:
        """Agent is created with expected required/optional field lists."""
        agent = DataValidatorAgent()

        assert agent is not None
        assert len(agent.REQUIRED_FIELDS) == 6
        assert len(agent.OPTIONAL_FIELDS) == 10
        assert "mcm_id" in agent.REQUIRED_FIELDS
        assert "description" in agent.OPTIONAL_FIELDS


# ======================================================================
# Test: complete product validation
# ======================================================================


class TestValidateCompleteProduct:
    """Product with ALL fields filled produces is_valid=True, high completeness."""

    def test_validate_complete_product(self) -> None:
        """All 16 fields present => is_valid=True, completeness=1.0."""
        agent = DataValidatorAgent()
        product = _complete_product()

        report, provenance_list = agent.validate(product)

        # Report type and identity
        assert isinstance(report, ValidationReport)
        assert report.mcm_id == "MCM-001-BLK-42"

        # Validity: all required fields present => valid
        assert report.is_valid is True
        assert report.missing_required == []

        # Completeness: all 16 fields filled => 1.0
        assert report.overall_completeness == 1.0

        # Every field should have a FieldValidation entry
        assert len(report.field_validations) == 16


# ======================================================================
# Test: minimal product validation
# ======================================================================


class TestValidateMinimalProduct:
    """Product with only required fields is valid but has lower completeness."""

    def test_validate_minimal_product(self) -> None:
        """6 required fields only => is_valid=True, completeness=6/16."""
        agent = DataValidatorAgent()
        product = _minimal_product()

        report, provenance_list = agent.validate(product)

        # Still valid -- all required fields are present
        assert report.is_valid is True
        assert report.missing_required == []

        # But completeness is lower: 6 filled out of 16 total
        assert report.overall_completeness == 6 / 16

        # All 16 fields checked
        assert len(report.field_validations) == 16


# ======================================================================
# Test: missing optional fields tracked
# ======================================================================


class TestValidateTracksMissingOptionalFields:
    """Missing optional fields are listed in field_validations with is_present=False."""

    def test_validate_tracks_missing_optional_fields(self) -> None:
        """Each missing optional field has is_present=False in report."""
        agent = DataValidatorAgent()
        product = _minimal_product()

        report, _ = agent.validate(product)

        # Collect field names where is_present is False
        missing_names = [
            fv.field_name for fv in report.field_validations if not fv.is_present
        ]

        # All 10 optional fields should be missing for a minimal product
        assert len(missing_names) == 10

        # Verify specific optional fields appear as missing
        for field in agent.OPTIONAL_FIELDS:
            assert field in missing_names, f"Expected '{field}' in missing fields"


# ======================================================================
# Test: provenance generation
# ======================================================================


class TestValidateProducesProvenance:
    """Each validated field gets a DataProvenance entry with correct metadata."""

    def test_validate_produces_provenance(self) -> None:
        """Provenance entries created for every checked field."""
        agent = DataValidatorAgent()
        product = _complete_product()

        _, provenance_list = agent.validate(product)

        # One provenance entry per field (required + optional = 16)
        assert len(provenance_list) == 16

        # All entries are DataProvenance instances
        assert all(isinstance(p, DataProvenance) for p in provenance_list)

        # Check metadata on a known entry (brand)
        brand_prov = next(p for p in provenance_list if p.attribute_name == "brand")
        assert brand_prov.value == "Nike"
        assert brand_prov.source_type == SourceType.MANUAL
        assert brand_prov.source_name == "Excel шаблон"
        assert brand_prov.agent_id == "agent-1.3-data-validator"
        assert 0.0 <= brand_prov.confidence <= 1.0

    def test_provenance_missing_field_has_none_value(self) -> None:
        """Provenance for a missing field stores value=None."""
        agent = DataValidatorAgent()
        product = _minimal_product()

        _, provenance_list = agent.validate(product)

        desc_prov = next(
            p for p in provenance_list if p.attribute_name == "description"
        )
        assert desc_prov.value is None
        assert desc_prov.confidence == 0.0
