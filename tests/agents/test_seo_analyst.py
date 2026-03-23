"""Tests for SEOAnalystAgent -- SEO keyword extraction and profile generation.

Tests cover: instantiation, SEOProfile return type, primary keywords population,
brand name inclusion in keywords, and category inclusion in keywords.
Phase 1 uses template-based keyword extraction (no LLM calls).
"""

from __future__ import annotations

from sportmaster_card.agents.seo_analyst import SEOAnalystAgent
from sportmaster_card.models.content import SEOProfile
from sportmaster_card.models.product_input import ProductInput


# ======================================================================
# Fixtures -- reusable product inputs for multiple tests
# ======================================================================


def _sample_product() -> ProductInput:
    """Build a ProductInput with enough fields for SEO analysis."""
    return ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        technologies=["Air Zoom", "React"],
    )


# ======================================================================
# Tests
# ======================================================================


def test_creation():
    """SEOAnalystAgent can be instantiated without arguments."""
    agent = SEOAnalystAgent()
    assert agent is not None


def test_analyze_returns_seo_profile():
    """analyze() returns an instance of SEOProfile."""
    agent = SEOAnalystAgent()
    product = _sample_product()

    result = agent.analyze(product, platform_id="sm_site")

    assert isinstance(result, SEOProfile)


def test_primary_keywords_not_empty():
    """analyze() returns an SEOProfile with non-empty primary_keywords."""
    agent = SEOAnalystAgent()
    product = _sample_product()

    result = agent.analyze(product, platform_id="sm_site")

    assert len(result.primary_keywords) > 0


def test_keywords_contain_brand():
    """Primary or secondary keywords include the brand name (lowercased)."""
    agent = SEOAnalystAgent()
    product = _sample_product()

    result = agent.analyze(product, platform_id="sm_site")

    all_keywords = result.primary_keywords + result.secondary_keywords
    all_text = " ".join(all_keywords).lower()
    assert "nike" in all_text


def test_keywords_contain_category():
    """Primary or secondary keywords include the product category."""
    agent = SEOAnalystAgent()
    product = _sample_product()

    result = agent.analyze(product, platform_id="sm_site")

    all_keywords = result.primary_keywords + result.secondary_keywords
    all_text = " ".join(all_keywords).lower()
    # Category is "Обувь" or subgroup "Беговые кроссовки" -- either counts
    assert "кроссовки" in all_text or "обувь" in all_text
