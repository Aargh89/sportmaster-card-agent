"""Tests for UC1 enrichment output models: ValidationReport and CompetitorBenchmark.

These models represent outputs from the Data Validator and External Researcher
agents in the UC1 Enrichment pipeline. The Data Validator checks field completeness
and correctness; the External Researcher gathers competitor intelligence.

Test strategy:
    - ValidationReport with valid field completeness scores
    - ValidationReport tracks missing required fields
    - ValidationReport overall_completeness as a 0-1 percentage
    - CompetitorBenchmark with competitor card data
    - CompetitorBenchmark valid with empty competitors list
"""

import pytest
from pydantic import ValidationError


def test_validation_report_valid():
    """ValidationReport accepts valid data with field completeness scores."""
    from sportmaster_card.models.enrichment import (
        FieldValidation,
        ValidationReport,
    )

    validations = [
        FieldValidation(
            field_name="brand",
            is_present=True,
            is_valid=True,
        ),
        FieldValidation(
            field_name="description",
            is_present=True,
            is_valid=False,
            issue="Description too short (< 10 chars)",
        ),
        FieldValidation(
            field_name="color",
            is_present=False,
            is_valid=False,
            issue="Required field missing",
        ),
    ]
    report = ValidationReport(
        mcm_id="MCM-001-BLK-42",
        field_validations=validations,
        missing_required=["color"],
        overall_completeness=0.67,
        is_valid=False,
        notes=["Description needs expansion", "Color field is missing"],
    )
    assert report.mcm_id == "MCM-001-BLK-42"
    assert len(report.field_validations) == 3
    assert report.field_validations[0].is_valid is True
    assert report.field_validations[1].issue == "Description too short (< 10 chars)"
    assert report.is_valid is False


def test_validation_report_missing_fields_list():
    """ValidationReport tracks which required fields are missing."""
    from sportmaster_card.models.enrichment import (
        FieldValidation,
        ValidationReport,
    )

    validations = [
        FieldValidation(field_name="brand", is_present=True, is_valid=True),
        FieldValidation(
            field_name="category",
            is_present=False,
            is_valid=False,
            issue="Required field missing",
        ),
        FieldValidation(
            field_name="product_name",
            is_present=False,
            is_valid=False,
            issue="Required field missing",
        ),
    ]
    report = ValidationReport(
        mcm_id="MCM-002-WHT-40",
        field_validations=validations,
        missing_required=["category", "product_name"],
        overall_completeness=0.33,
        is_valid=False,
    )
    assert len(report.missing_required) == 2
    assert "category" in report.missing_required
    assert "product_name" in report.missing_required
    assert report.notes == []  # defaults to empty list


def test_validation_report_overall_completeness():
    """overall_completeness is a float between 0 and 1 representing percentage."""
    from sportmaster_card.models.enrichment import (
        FieldValidation,
        ValidationReport,
    )

    # All fields present and valid -> 100% completeness
    validations = [
        FieldValidation(field_name="brand", is_present=True, is_valid=True),
        FieldValidation(field_name="category", is_present=True, is_valid=True),
        FieldValidation(field_name="product_name", is_present=True, is_valid=True),
    ]
    report = ValidationReport(
        mcm_id="MCM-003-RED-38",
        field_validations=validations,
        missing_required=[],
        overall_completeness=1.0,
        is_valid=True,
    )
    assert report.overall_completeness == 1.0
    assert report.is_valid is True
    assert report.missing_required == []

    # Zero completeness
    report_empty = ValidationReport(
        mcm_id="MCM-004-EMPTY",
        field_validations=[],
        missing_required=["brand", "category", "product_name"],
        overall_completeness=0.0,
        is_valid=False,
    )
    assert report_empty.overall_completeness == 0.0


def test_competitor_benchmark_valid():
    """CompetitorBenchmark accepts valid competitor cards data."""
    from sportmaster_card.models.enrichment import (
        CompetitorBenchmark,
        CompetitorCard,
    )

    competitors = [
        CompetitorCard(
            platform="wb",
            product_name="Nike Air Zoom Pegasus 41",
            description="Легкие беговые кроссовки",
            price=12990.0,
            rating=4.7,
            key_features=["Air Zoom", "легкие", "дышащие"],
            url="https://www.wildberries.ru/catalog/12345",
        ),
        CompetitorCard(
            platform="ozon",
            product_name="Nike Pegasus 41 Running",
            price=13490.0,
            rating=4.5,
            key_features=["Air Zoom", "амортизация"],
        ),
    ]
    benchmark = CompetitorBenchmark(
        mcm_id="MCM-001-BLK-42",
        competitors=competitors,
        benchmark_summary="Средняя цена конкурентов ~13240 руб. Ключевые фичи: Air Zoom.",
        average_price=13240.0,
        common_features=["Air Zoom"],
    )
    assert benchmark.mcm_id == "MCM-001-BLK-42"
    assert len(benchmark.competitors) == 2
    assert benchmark.competitors[0].platform == "wb"
    assert benchmark.competitors[0].price == 12990.0
    assert benchmark.competitors[1].url is None  # optional, not provided
    assert benchmark.average_price == 13240.0
    assert "Air Zoom" in benchmark.common_features


def test_competitor_benchmark_empty_competitors():
    """CompetitorBenchmark is valid with an empty competitors list (none found)."""
    from sportmaster_card.models.enrichment import CompetitorBenchmark

    benchmark = CompetitorBenchmark(
        mcm_id="MCM-RARE-001",
    )
    assert benchmark.competitors == []
    assert benchmark.benchmark_summary == ""
    assert benchmark.average_price is None
    assert benchmark.common_features == []
