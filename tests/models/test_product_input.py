"""Tests for ProductInput model.

Validates that raw Excel row data is correctly parsed into a structured
ProductInput with all required fields from the 209-column template.
Phase 1 focuses on the essential subset of columns needed for the pilot.
"""

import pytest
from pydantic import ValidationError


def test_product_input_valid_minimal():
    """ProductInput accepts valid minimal data with all required fields."""
    from sportmaster_card.models.product_input import ProductInput

    data = {
        "mcm_id": "MCM-001-BLK-42",
        "brand": "Nike",
        "category": "Обувь",
        "product_group": "Кроссовки",
        "product_subgroup": "Беговые кроссовки",
        "product_name": "Nike Air Zoom Pegasus 41",
    }
    product = ProductInput(**data)
    assert product.mcm_id == "MCM-001-BLK-42"
    assert product.brand == "Nike"
    assert product.category == "Обувь"


def test_product_input_missing_required_field():
    """ProductInput raises ValidationError when mcm_id is missing."""
    from sportmaster_card.models.product_input import ProductInput

    with pytest.raises(ValidationError, match="mcm_id"):
        ProductInput(
            brand="Nike",
            category="Обувь",
            product_group="Кроссовки",
            product_subgroup="Беговые кроссовки",
            product_name="Nike Air Zoom Pegasus 41",
        )


def test_product_input_optional_fields_default_to_none():
    """Optional fields default to None."""
    from sportmaster_card.models.product_input import ProductInput

    product = ProductInput(
        mcm_id="MCM-002-WHT-40",
        brand="Adidas",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Повседневные кроссовки",
        product_name="Adidas Ultraboost Light",
    )
    assert product.description is None
    assert product.composition is None
    assert product.photo_urls is None


def test_product_input_with_all_pilot_fields():
    """ProductInput with all fields relevant to Phase 1 pilot (footwear)."""
    from sportmaster_card.models.product_input import ProductInput

    product = ProductInput(
        mcm_id="MCM-003-RED-38",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Pegasus 41",
        description="Беговые кроссовки с технологией Air Zoom",
        gender="Мужской",
        season="Весна-Лето 2026",
        color="Красный",
        assortment_segment="TRD",
        assortment_type="Basic",
        assortment_level="Mid",
        technologies=["Air Zoom", "Flywire", "React"],
        composition={"Верх": "Текстиль 80%, синтетика 20%", "Подошва": "Резина"},
        photo_urls=["https://example.com/photo1.jpg"],
    )
    assert product.assortment_level == "Mid"
    assert len(product.technologies) == 3
    assert "Верх" in product.composition
