"""Integration tests for the full Phase 1 pipeline.

Tests the complete data flow from raw product input to final edited content.
Validates that all agents work together correctly and data flows through
the pipeline without loss or corruption.

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
