"""Tests for BrandComplianceAgent -- brand guideline compliance checking.

Tests cover: instantiation, compliant content detection, forbidden word
detection, and brand name casing violation detection.
Phase 1 uses rule-based checking (no LLM calls).
"""

from __future__ import annotations

from sportmaster_card.agents.brand_compliance import BrandComplianceAgent
from sportmaster_card.models.content import Benefit, ComplianceReport, PlatformContent


# ======================================================================
# Fixtures -- reusable content inputs for multiple tests
# ======================================================================


def _compliant_content() -> PlatformContent:
    """Build a PlatformContent that passes all brand compliance checks."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="Nike Air Zoom Pegasus 41",
        description=(
            "Беговые кроссовки Nike Air Zoom Pegasus 41 — отличный выбор "
            "для ежедневных тренировок. Технология Air Zoom обеспечивает "
            "мягкую амортизацию при беге."
        ),
        benefits=[
            Benefit(title="Амортизация", description="Air Zoom обеспечивает комфорт."),
        ],
        seo_title="Nike Беговые кроссовки Pegasus 41",
        seo_meta_description="Купить Nike Pegasus 41 в Спортмастер.",
        seo_keywords=["nike pegasus"],
    )


def _content_with_forbidden_word() -> PlatformContent:
    """Build a PlatformContent containing a forbidden word in the description."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="Nike Air Zoom Pegasus 41",
        description=(
            "Эти кроссовки — самые лучшие на рынке. "
            "Дешёвый вариант для бега."
        ),
        benefits=[
            Benefit(title="Цена", description="Доступная цена."),
        ],
        seo_title="Nike Pegasus 41",
        seo_meta_description="Купить Nike Pegasus 41.",
        seo_keywords=["nike pegasus"],
    )


def _content_with_wrong_brand_casing() -> PlatformContent:
    """Build a PlatformContent with incorrect brand name casing ('nike')."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="nike Air Zoom Pegasus 41",
        description=(
            "Беговые кроссовки nike Pegasus 41 — отличный выбор. "
            "Технология Air Zoom от nike обеспечивает амортизацию."
        ),
        benefits=[
            Benefit(title="Амортизация", description="Air Zoom от nike."),
        ],
        seo_title="nike Pegasus 41",
        seo_meta_description="Купить nike Pegasus 41.",
        seo_keywords=["nike pegasus"],
    )


# ======================================================================
# Tests
# ======================================================================


def test_creation():
    """BrandComplianceAgent can be instantiated without arguments."""
    agent = BrandComplianceAgent()
    assert agent is not None


def test_check_compliant_content():
    """check() returns ComplianceReport with is_compliant=True for clean content."""
    agent = BrandComplianceAgent()
    content = _compliant_content()

    result = agent.check(content, brand_name="Nike")

    assert isinstance(result, ComplianceReport)
    assert result.is_compliant is True
    assert len(result.violations) == 0


def test_check_detects_forbidden_words():
    """check() detects forbidden words and returns is_compliant=False."""
    agent = BrandComplianceAgent()
    content = _content_with_forbidden_word()

    result = agent.check(
        content,
        brand_name="Nike",
        forbidden_words=["дешёвый"],
    )

    assert result.is_compliant is False
    assert len(result.violations) > 0


def test_check_detects_wrong_brand_casing():
    """check() detects wrong brand name casing ('nike' instead of 'Nike')."""
    agent = BrandComplianceAgent()
    content = _content_with_wrong_brand_casing()

    result = agent.check(content, brand_name="Nike")

    assert result.is_compliant is False
    assert len(result.violations) > 0
