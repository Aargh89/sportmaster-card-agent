"""Tests for ContentGeneratorAgent -- template-based product content generation.

Tests cover: instantiation, PlatformContent return type, product_name population,
benefits generation, SEO field population, platform_id mapping, and description
length limits. No real LLM calls -- Phase 1 uses template-based generation.
"""

from __future__ import annotations

from sportmaster_card.agents.content_generator import ContentGeneratorAgent
from sportmaster_card.models.content import PlatformContent
from sportmaster_card.models.product_input import ProductInput


# ======================================================================
# Fixtures -- reusable product inputs for multiple tests
# ======================================================================


def _sample_product() -> ProductInput:
    """Build a ProductInput with enough fields for content generation."""
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
        technologies=["Air Zoom", "Flywire", "React"],
        composition={"Верх": "Текстиль 80%", "Подошва": "Резина"},
    )


# ======================================================================
# Tests
# ======================================================================


def test_content_generator_creation():
    """ContentGeneratorAgent can be instantiated without arguments."""
    agent = ContentGeneratorAgent()
    assert agent is not None


def test_generate_returns_platform_content():
    """generate() returns an instance of PlatformContent."""
    agent = ContentGeneratorAgent()
    product = _sample_product()

    result = agent.generate(product)

    assert isinstance(result, PlatformContent)


def test_generated_content_has_product_name():
    """Generated content has a non-empty product_name field."""
    agent = ContentGeneratorAgent()
    product = _sample_product()

    result = agent.generate(product)

    assert result.product_name
    assert len(result.product_name) > 0


def test_generated_content_has_benefits():
    """Generated content has a non-empty benefits list."""
    agent = ContentGeneratorAgent()
    product = _sample_product()

    result = agent.generate(product)

    assert len(result.benefits) > 0
    # Each benefit should have a title and description
    for benefit in result.benefits:
        assert benefit.title
        assert benefit.description


def test_generated_content_has_seo_fields():
    """Generated content has seo_title and seo_keywords populated."""
    agent = ContentGeneratorAgent()
    product = _sample_product()

    result = agent.generate(product)

    assert result.seo_title
    assert len(result.seo_title) > 0
    assert result.seo_keywords
    assert len(result.seo_keywords) > 0


def test_generated_content_respects_platform_id():
    """Generated content platform_id matches the input platform_id."""
    agent = ContentGeneratorAgent()
    product = _sample_product()

    result_default = agent.generate(product)
    result_wb = agent.generate(product, platform_id="wb")

    assert result_default.platform_id == "sm_site"
    assert result_wb.platform_id == "wb"


def test_generated_description_within_length_limit():
    """Generated description length does not exceed max_description_length."""
    agent = ContentGeneratorAgent()
    product = _sample_product()

    # Test with a tight limit
    limit = 500
    result = agent.generate(product, max_description_length=limit)

    assert len(result.description) <= limit
