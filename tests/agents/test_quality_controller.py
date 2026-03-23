"""Tests for QualityControllerAgent -- multi-dimension content quality scoring.

Tests cover: instantiation, QualityScore return type, dimension score ranges,
high-quality content passing threshold, and low-quality content failing threshold.
Phase 1 uses rule-based scoring heuristics (no LLM calls).
"""

from __future__ import annotations

from sportmaster_card.agents.quality_controller import QualityControllerAgent
from sportmaster_card.models.content import (
    Benefit,
    ComplianceReport,
    FactCheckReport,
    PlatformContent,
    QualityScore,
)


# ======================================================================
# Fixtures -- reusable inputs for multiple tests
# ======================================================================


def _good_content() -> PlatformContent:
    """Build a high-quality PlatformContent that should pass the threshold."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="Nike Air Zoom Pegasus 41",
        description=(
            "Беговые кроссовки Nike Air Zoom Pegasus 41 — отличный выбор "
            "для ежедневных тренировок. Технология Air Zoom обеспечивает "
            "мягкую амортизацию при беге. Верх из текстиля обеспечивает "
            "вентиляцию и комфорт. Подошва из резины даёт надёжное сцепление "
            "с поверхностью. Закажите кроссовки Nike в Спортмастер с доставкой."
        ),
        benefits=[
            Benefit(title="Амортизация", description="Air Zoom обеспечивает комфорт."),
            Benefit(title="Вентиляция", description="Текстильный верх дышит."),
        ],
        seo_title="Nike Беговые кроссовки Pegasus 41",
        seo_meta_description="Купить Nike Pegasus 41 в Спортмастер.",
        seo_keywords=["nike pegasus", "беговые кроссовки"],
    )


def _compliant_report() -> ComplianceReport:
    """Build a compliant ComplianceReport (no violations)."""
    return ComplianceReport(
        mcm_id="MCM-001-BLK-42",
        is_compliant=True,
        violations=[],
        suggestions=[],
    )


def _accurate_fact_check() -> FactCheckReport:
    """Build an accurate FactCheckReport (no inaccuracies)."""
    return FactCheckReport(
        mcm_id="MCM-001-BLK-42",
        is_accurate=True,
        inaccuracies=[],
        unverifiable_claims=[],
    )


def _non_compliant_report() -> ComplianceReport:
    """Build a non-compliant ComplianceReport with violations."""
    return ComplianceReport(
        mcm_id="MCM-001-BLK-42",
        is_compliant=False,
        violations=[
            "Запрещённое слово найдено",
            "Бренд в неправильном регистре",
        ],
        suggestions=["Удалить запрещённое слово", "Исправить регистр"],
    )


def _inaccurate_fact_check() -> FactCheckReport:
    """Build an inaccurate FactCheckReport with issues."""
    return FactCheckReport(
        mcm_id="MCM-001-BLK-42",
        is_accurate=False,
        inaccuracies=["Неизвестная технология 'Boost'"],
        unverifiable_claims=[],
    )


# ======================================================================
# Tests
# ======================================================================


def test_creation():
    """QualityControllerAgent can be instantiated without arguments."""
    agent = QualityControllerAgent()
    assert agent is not None


def test_evaluate_returns_quality_score():
    """evaluate() returns an instance of QualityScore."""
    agent = QualityControllerAgent()
    content = _good_content()
    compliance = _compliant_report()
    fact_check = _accurate_fact_check()

    result = agent.evaluate(content, compliance, fact_check)

    assert isinstance(result, QualityScore)


def test_score_dimensions():
    """All dimension scores are between 0 and 1 (inclusive)."""
    agent = QualityControllerAgent()
    content = _good_content()
    compliance = _compliant_report()
    fact_check = _accurate_fact_check()

    result = agent.evaluate(content, compliance, fact_check)

    assert 0.0 <= result.readability_score <= 1.0
    assert 0.0 <= result.seo_score <= 1.0
    assert 0.0 <= result.factual_accuracy_score <= 1.0
    assert 0.0 <= result.brand_compliance_score <= 1.0
    assert 0.0 <= result.uniqueness_score <= 1.0
    assert 0.0 <= result.overall_score <= 1.0


def test_high_quality_passes_threshold():
    """Good content with no violations passes the quality threshold."""
    agent = QualityControllerAgent()
    content = _good_content()
    compliance = _compliant_report()
    fact_check = _accurate_fact_check()

    result = agent.evaluate(content, compliance, fact_check)

    assert result.passes_threshold is True


def test_low_quality_fails_threshold():
    """Content with compliance violations produces a lower overall score."""
    agent = QualityControllerAgent()
    content = _good_content()
    compliance = _non_compliant_report()
    fact_check = _inaccurate_fact_check()

    result = agent.evaluate(content, compliance, fact_check)

    # With both compliance violations and fact-check inaccuracies,
    # the overall score should be noticeably lower
    assert result.brand_compliance_score < 1.0
    assert result.factual_accuracy_score < 1.0
