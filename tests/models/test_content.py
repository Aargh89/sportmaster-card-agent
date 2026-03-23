"""Tests for UC2 content output models: ContentBrief, PlatformContent, QualityScore.

These models represent the MAIN output of the UC2 content generation pipeline.
The flow is: CuratedProfile -> ContentBrief -> PlatformContent + QualityScore.

Test strategy:
    - ContentBrief captures brief structure, tone, and section requirements
    - Benefit is a small value object for product benefit bullets
    - PlatformContent holds all generated text elements for one platform
    - PlatformContent includes SEO-specific fields (title, meta, keywords)
    - QualityScore tracks per-dimension scores and threshold gating
    - passes_threshold property gates content publication (>= 0.7)
"""

import pytest
from pydantic import ValidationError


def test_content_brief_valid():
    """ContentBrief accepts valid brief with structure, tone, and required sections."""
    from sportmaster_card.models.content import ContentBrief

    brief = ContentBrief(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        brief_type="standard",
        tone_of_voice="professional",
        required_sections=["description", "benefits", "technologies"],
        max_description_length=2000,
        max_title_length=120,
    )
    assert brief.mcm_id == "MCM-001-BLK-42"
    assert brief.platform_id == "sm_site"
    assert brief.brief_type == "standard"
    assert brief.tone_of_voice == "professional"
    assert len(brief.required_sections) == 3
    assert "benefits" in brief.required_sections
    assert brief.max_description_length == 2000
    assert brief.max_title_length == 120


def test_benefit_model():
    """Benefit captures a short title and 1-2 sentence description."""
    from sportmaster_card.models.content import Benefit

    benefit = Benefit(
        title="Амортизация",
        description="Технология Air Zoom обеспечивает мягкую амортизацию при беге.",
    )
    assert benefit.title == "Амортизация"
    assert "Air Zoom" in benefit.description


def test_platform_content_valid():
    """PlatformContent holds all generated text elements for a single platform."""
    from sportmaster_card.models.content import Benefit, PlatformContent

    content = PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name="Nike Air Zoom Pegasus 41 Мужские беговые кроссовки",
        description="Беговые кроссовки Nike Air Zoom Pegasus 41 с амортизацией.",
        benefits=[
            Benefit(title="Амортизация", description="Air Zoom для мягкого бега."),
            Benefit(title="Вентиляция", description="Mesh-верх для воздухообмена."),
        ],
        seo_title="Купить Nike Air Zoom Pegasus 41 | Sportmaster",
        seo_meta_description="Nike Air Zoom Pegasus 41 — беговые кроссовки с амортизацией.",
        seo_keywords=["nike pegasus", "беговые кроссовки", "air zoom"],
    )
    assert content.mcm_id == "MCM-001-BLK-42"
    assert content.platform_id == "sm_site"
    assert len(content.benefits) == 2
    assert content.benefits[0].title == "Амортизация"
    assert content.content_hash == ""
    assert content.source_curated_profile_hash == ""


def test_platform_content_seo_fields():
    """PlatformContent carries SEO-specific fields: seo_title, meta, keywords."""
    from sportmaster_card.models.content import Benefit, PlatformContent

    content = PlatformContent(
        mcm_id="MCM-002-WHT-40",
        platform_id="wb",
        product_name="Adidas Ultraboost Light Кроссовки для бега",
        description="Кроссовки Adidas Ultraboost Light с технологией Boost.",
        benefits=[
            Benefit(title="Энергия возврата", description="Boost для пружинистого бега."),
        ],
        seo_title="Adidas Ultraboost Light — купить на Wildberries",
        seo_meta_description="Кроссовки Adidas Ultraboost Light с бесплатной доставкой.",
        seo_keywords=["adidas ultraboost", "кроссовки для бега", "boost"],
        content_hash="abc123",
        source_curated_profile_hash="def456",
    )
    assert content.seo_title == "Adidas Ultraboost Light — купить на Wildberries"
    assert "бесплатной доставкой" in content.seo_meta_description
    assert len(content.seo_keywords) == 3
    assert "boost" in content.seo_keywords
    assert content.content_hash == "abc123"
    assert content.source_curated_profile_hash == "def456"


def test_quality_score_valid():
    """QualityScore carries overall and per-dimension scores (0-1 range)."""
    from sportmaster_card.models.content import QualityScore

    score = QualityScore(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        overall_score=0.85,
        readability_score=0.9,
        seo_score=0.8,
        factual_accuracy_score=0.95,
        brand_compliance_score=0.75,
        uniqueness_score=0.88,
        issues=["Слишком длинное описание (превышен лимит на 50 символов)"],
    )
    assert score.mcm_id == "MCM-001-BLK-42"
    assert score.overall_score == 0.85
    assert score.readability_score == 0.9
    assert score.seo_score == 0.8
    assert score.factual_accuracy_score == 0.95
    assert score.brand_compliance_score == 0.75
    assert score.uniqueness_score == 0.88
    assert len(score.issues) == 1


def test_quality_score_passes_threshold():
    """passes_threshold returns True when overall_score >= 0.7, False otherwise."""
    from sportmaster_card.models.content import QualityScore

    base = dict(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        readability_score=0.8,
        seo_score=0.8,
        factual_accuracy_score=0.8,
        brand_compliance_score=0.8,
        uniqueness_score=0.8,
    )

    # Above threshold
    high = QualityScore(overall_score=0.85, **base)
    assert high.passes_threshold is True

    # Exactly at threshold
    edge = QualityScore(overall_score=0.7, **base)
    assert edge.passes_threshold is True

    # Below threshold
    low = QualityScore(overall_score=0.69, **base)
    assert low.passes_threshold is False

    # Zero score
    zero = QualityScore(overall_score=0.0, **base)
    assert zero.passes_threshold is False


# ---------------------------------------------------------------------------
# UC2 quality models: SEOProfile, ContentStructure, ComplianceReport, FactCheckReport
# ---------------------------------------------------------------------------


def test_seo_profile_valid():
    """SEOProfile captures keyword recommendations for a product on a platform."""
    from sportmaster_card.models.content import SEOProfile

    seo = SEOProfile(
        mcm_id="MCM-001",
        platform_id="sm_site",
        primary_keywords=["беговые кроссовки nike", "nike pegasus"],
        secondary_keywords=["кроссовки для бега", "air zoom"],
        title_recommendation="Nike Беговые кроссовки Pegasus 41",
        meta_description_recommendation="Купить Nike Pegasus 41 в Спортмастер",
    )
    assert len(seo.primary_keywords) == 2


def test_content_structure_valid():
    """ContentStructure defines section layout and guidelines for content generation."""
    from sportmaster_card.models.content import ContentStructure

    cs = ContentStructure(
        mcm_id="MCM-001",
        platform_id="sm_site",
        sections=["intro", "benefits", "technologies", "composition"],
        section_guidelines={"intro": "2-3 предложения, ключевые преимущества"},
        target_word_count=500,
    )
    assert len(cs.sections) == 4


def test_compliance_report_valid():
    """ComplianceReport defaults to empty violations when compliant."""
    from sportmaster_card.models.content import ComplianceReport

    cr = ComplianceReport(mcm_id="MCM-001", is_compliant=True)
    assert cr.violations == []


def test_compliance_report_with_violations():
    """ComplianceReport captures brand guideline violations and suggestions."""
    from sportmaster_card.models.content import ComplianceReport

    cr = ComplianceReport(
        mcm_id="MCM-001",
        is_compliant=False,
        violations=["Название бренда в нижнем регистре"],
        suggestions=["Использовать 'Nike' вместо 'nike'"],
    )
    assert not cr.is_compliant


def test_fact_check_report_valid():
    """FactCheckReport defaults to empty inaccuracies when accurate."""
    from sportmaster_card.models.content import FactCheckReport

    fcr = FactCheckReport(mcm_id="MCM-001", is_accurate=True)
    assert fcr.inaccuracies == []


def test_fact_check_report_with_issues():
    """FactCheckReport captures inaccuracies and unverifiable claims."""
    from sportmaster_card.models.content import FactCheckReport

    fcr = FactCheckReport(
        mcm_id="MCM-001",
        is_accurate=False,
        inaccuracies=["Указан материал 'кожа', в CuratedProfile — 'текстиль'"],
        unverifiable_claims=["'самая лёгкая модель' — нет данных для сравнения"],
    )
    assert len(fcr.inaccuracies) == 1
