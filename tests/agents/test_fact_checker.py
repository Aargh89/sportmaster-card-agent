"""Tests for FactCheckerAgent -- factual accuracy verification against CuratedProfile.

Tests cover: instantiation, accurate content detection, unknown technology
detection, and wrong material (composition mismatch) detection.
Phase 1 uses rule-based comparison (no LLM calls).
"""

from __future__ import annotations

from sportmaster_card.agents.fact_checker import FactCheckerAgent
from sportmaster_card.models.content import Benefit, FactCheckReport, PlatformContent
from sportmaster_card.models.enrichment import CuratedProfile
from sportmaster_card.models.provenance import DataProvenanceLog


# ======================================================================
# Fixtures -- reusable inputs for multiple tests
# ======================================================================


def _sample_profile() -> CuratedProfile:
    """Build a CuratedProfile with known technologies and composition."""
    return CuratedProfile(
        mcm_id="MCM-001-BLK-42",
        product_name="Nike Air Zoom Pegasus 41",
        brand="Nike",
        category="Обувь",
        description="Беговые кроссовки с технологией Air Zoom.",
        key_features=["Air Zoom", "Flywire"],
        technologies=["Air Zoom", "React"],
        composition={"Верх": "Текстиль 80%", "Подошва": "Резина"},
        benefits_data=["Отличная амортизация"],
        seo_material=["беговые кроссовки nike"],
        provenance_log=DataProvenanceLog(mcm_id="MCM-001-BLK-42"),
    )


def _accurate_content() -> PlatformContent:
    """Build a PlatformContent with claims matching the CuratedProfile."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="Nike Air Zoom Pegasus 41",
        description=(
            "Беговые кроссовки Nike с технологией Air Zoom и React. "
            "Верх из текстиля обеспечивает вентиляцию."
        ),
        benefits=[
            Benefit(title="Амортизация", description="Технология Air Zoom."),
        ],
        seo_title="Nike Pegasus 41",
        seo_meta_description="Купить Nike Pegasus 41.",
        seo_keywords=["nike pegasus"],
    )


def _content_with_unknown_technology() -> PlatformContent:
    """Build content mentioning a technology NOT in CuratedProfile."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="Nike Air Zoom Pegasus 41",
        description=(
            "Беговые кроссовки Nike с технологией Boost и Air Zoom. "
            "Технология Boost обеспечивает энергию."
        ),
        benefits=[
            Benefit(title="Энергия", description="Технология Boost."),
        ],
        seo_title="Nike Pegasus 41",
        seo_meta_description="Купить Nike Pegasus 41.",
        seo_keywords=["nike pegasus"],
    )


def _content_with_wrong_material() -> PlatformContent:
    """Build content claiming wrong material (leather instead of textile)."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="Nike Air Zoom Pegasus 41",
        description=(
            "Беговые кроссовки Nike из натуральной кожи. "
            "Кожаный верх обеспечивает прочность."
        ),
        benefits=[
            Benefit(title="Прочность", description="Натуральная кожа."),
        ],
        seo_title="Nike Pegasus 41",
        seo_meta_description="Купить Nike Pegasus 41.",
        seo_keywords=["nike pegasus"],
    )


# ======================================================================
# Tests
# ======================================================================


def test_creation():
    """FactCheckerAgent can be instantiated without arguments."""
    agent = FactCheckerAgent()
    assert agent is not None


def test_check_accurate_content():
    """check() returns FactCheckReport with is_accurate=True for correct content."""
    agent = FactCheckerAgent()
    content = _accurate_content()
    profile = _sample_profile()

    result = agent.check(content, profile)

    assert isinstance(result, FactCheckReport)
    assert result.is_accurate is True
    assert len(result.inaccuracies) == 0


def test_check_detects_unknown_technology():
    """check() detects a technology mentioned in content but not in CuratedProfile."""
    agent = FactCheckerAgent()
    content = _content_with_unknown_technology()
    profile = _sample_profile()

    result = agent.check(content, profile)

    assert result.is_accurate is False
    assert len(result.inaccuracies) > 0


def test_check_detects_wrong_material():
    """check() detects material composition mismatch with CuratedProfile."""
    agent = FactCheckerAgent()
    content = _content_with_wrong_material()
    profile = _sample_profile()

    result = agent.check(content, profile)

    assert result.is_accurate is False
    assert len(result.inaccuracies) > 0
