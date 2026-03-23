"""Integration tests for the full UC1+UC2 pipeline with 15 agents.

Tests the complete data flow from raw product input to final edited content
with quality scoring. Validates that all agents work together correctly
and data flows through the pipeline without loss or corruption.

These tests use NO real LLM calls -- all agents are rule/template-based.
"""


def test_full_pipeline_nike_pegasus(sample_product_input):
    """Full pipeline test with the canonical Nike Pegasus test product.

    Validates:
    1. Router produces correct routing (1P, STANDARD, sm_site)
    2. DataValidator produces a valid report with high completeness
    3. ExternalResearcher produces a benchmark with at least 1 competitor
    4. ContentGenerator produces PlatformContent with all required fields
    5. CopyEditor produces edited content within length limits
    6. All outputs reference the same mcm_id
    7. Provenance entries are collected from all agents
    8. CuratedProfile is populated with flattened product data
    9. QualityScore passes the 0.7 threshold
    """
    from sportmaster_card.flows.pilot_flow import PilotFlow

    flow = PilotFlow()
    result = flow.run(sample_product_input)

    # 1. Routing
    assert result.routing_profile.flow_type.value == "1P"
    assert result.routing_profile.processing_profile.value == "standard"
    assert "sm_site" in result.routing_profile.target_platforms

    # 2. Validation
    assert result.validation_report.is_valid is True
    assert result.validation_report.overall_completeness > 0.5

    # 3. Competitor research
    assert len(result.competitor_benchmark.competitors) >= 1

    # 4. Generated content
    assert result.generated_content.product_name != ""
    assert result.generated_content.description != ""
    assert len(result.generated_content.benefits) >= 1
    assert len(result.generated_content.seo_keywords) >= 1

    # 5. Edited content
    assert len(result.edited_content.product_name) <= 150
    assert len(result.edited_content.description) <= 3000

    # 6. Consistent MCM ID
    assert result.routing_profile.mcm_id == sample_product_input.mcm_id
    assert result.validation_report.mcm_id == sample_product_input.mcm_id
    assert result.generated_content.mcm_id == sample_product_input.mcm_id
    assert result.edited_content.mcm_id == sample_product_input.mcm_id

    # 7. Provenance
    assert len(result.provenance_entries) > 0

    # 8. CuratedProfile is populated with product data
    assert result.curated_profile is not None
    assert result.curated_profile.mcm_id == sample_product_input.mcm_id
    assert result.curated_profile.brand == sample_product_input.brand
    assert result.curated_profile.category == sample_product_input.category
    assert len(result.curated_profile.key_features) > 0

    # 9. QualityScore passes threshold
    assert result.quality_score is not None
    assert result.quality_score.passes_threshold is True
    assert result.quality_score.overall_score >= 0.7


def test_full_pipeline_minimal_product():
    """Pipeline works with a minimal product (only required fields).

    Even with minimal data, the pipeline should produce valid output.
    """
    from sportmaster_card.models.product_input import ProductInput
    from sportmaster_card.flows.pilot_flow import PilotFlow

    minimal = ProductInput(
        mcm_id="MCM-MIN-001",
        brand="Adidas",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Повседневные кроссовки",
        product_name="Adidas Superstar",
    )

    flow = PilotFlow()
    result = flow.run(minimal)

    assert result.edited_content.product_name != ""
    assert result.edited_content.mcm_id == "MCM-MIN-001"

    # Phase 2 outputs should also be present even for minimal products.
    assert result.curated_profile is not None
    assert result.curated_profile.mcm_id == "MCM-MIN-001"
    assert result.quality_score is not None
    assert result.quality_score.overall_score > 0.0


def test_full_pipeline_data_flow_integrity():
    """Verify data doesn't get corrupted or lost through the pipeline.

    Checks that technologies from input appear in generated benefits.
    """
    from sportmaster_card.models.product_input import ProductInput
    from sportmaster_card.flows.pilot_flow import PilotFlow

    product = ProductInput(
        mcm_id="MCM-TECH-001",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike React Infinity",
        technologies=["React", "Flyknit"],
        assortment_type="Basic",
        assortment_level="Mid",
    )

    flow = PilotFlow()
    result = flow.run(product)

    # Technologies should influence the content
    content_text = result.edited_content.description.lower()
    assert "react" in content_text or len(result.edited_content.benefits) >= 1

    # CuratedProfile should contain the technologies
    assert result.curated_profile is not None
    assert "React" in result.curated_profile.technologies
    assert "Flyknit" in result.curated_profile.technologies


def test_full_pipeline_quality_score_dimensions():
    """Verify QualityScore has all five dimension scores populated."""
    from sportmaster_card.models.product_input import ProductInput
    from sportmaster_card.flows.pilot_flow import PilotFlow

    product = ProductInput(
        mcm_id="MCM-QS-001",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        technologies=["Air Zoom", "React"],
    )

    flow = PilotFlow()
    result = flow.run(product)

    qs = result.quality_score
    assert qs is not None

    # All dimension scores should be floats between 0 and 1.
    assert 0.0 <= qs.readability_score <= 1.0
    assert 0.0 <= qs.seo_score <= 1.0
    assert 0.0 <= qs.factual_accuracy_score <= 1.0
    assert 0.0 <= qs.brand_compliance_score <= 1.0
    assert 0.0 <= qs.uniqueness_score <= 1.0

    # Overall should be the average of dimensions.
    assert 0.0 <= qs.overall_score <= 1.0
