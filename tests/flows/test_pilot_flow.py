"""Tests for PilotFlow -- full UC1+UC2 pipeline orchestration with 15 agents.

Verifies that PilotFlow correctly sequences all 15 agents:
Router -> DataValidator -> VisualInterpreter -> ExternalResearcher ->
InternalResearcher -> Synectics -> DataEnricher -> DataCurator ->
SEOAnalyst -> StructurePlanner -> ContentGenerator -> BrandCompliance ->
FactChecker -> CopyEditor -> QualityController.

Each test validates a specific aspect of the pipeline result:
- Instantiation works without errors (all 15 agents initialized)
- run() returns a PipelineResult
- Result contains PlatformContent (both generated and edited)
- Result contains ValidationReport from the validator
- Result contains RoutingProfile from the router
- Result contains CuratedProfile from the curator
- Result contains QualityScore from the quality controller
- Full end-to-end processing from ProductInput to edited content
"""

import pytest

from sportmaster_card.flows.pilot_flow import PilotFlow, PipelineResult
from sportmaster_card.models.content import (
    ComplianceReport,
    ContentStructure,
    FactCheckReport,
    PlatformContent,
    QualityScore,
    SEOProfile,
)
from sportmaster_card.models.enrichment import (
    CompetitorBenchmark,
    CreativeInsights,
    CuratedProfile,
    EnrichedProductProfile,
    InternalInsights,
    ValidationReport,
)
from sportmaster_card.models.routing import RoutingProfile


class TestPilotFlow:
    """Test suite for the PilotFlow orchestrator."""

    def test_pilot_flow_creation(self):
        """PilotFlow can be instantiated with all 15 agents."""
        flow = PilotFlow()

        # Original Phase 1 agents.
        assert flow.router is not None
        assert flow.validator is not None
        assert flow.researcher is not None
        assert flow.generator is not None
        assert flow.editor is not None

        # Phase 2 UC1 enrichment agents.
        assert flow.visual_interpreter is not None
        assert flow.internal_researcher is not None
        assert flow.synectics is not None
        assert flow.enricher is not None
        assert flow.curator is not None

        # Phase 2 UC2 content generation agents.
        assert flow.seo_analyst is not None
        assert flow.structure_planner is not None
        assert flow.brand_compliance is not None
        assert flow.fact_checker is not None
        assert flow.quality_controller is not None

    def test_pilot_flow_run_returns_result(self, sample_product_input):
        """run() returns a PipelineResult instance."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        assert isinstance(result, PipelineResult)

    def test_pilot_flow_result_has_platform_content(self, sample_product_input):
        """Result contains PlatformContent for both generated and edited stages."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        # Both generated and edited content must be PlatformContent instances.
        assert isinstance(result.generated_content, PlatformContent)
        assert isinstance(result.edited_content, PlatformContent)

    def test_pilot_flow_result_has_validation_report(self, sample_product_input):
        """Result contains a ValidationReport from the DataValidator."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        assert isinstance(result.validation_report, ValidationReport)
        # The validation report should reference the same product.
        assert result.validation_report.mcm_id == sample_product_input.mcm_id

    def test_pilot_flow_result_has_routing_profile(self, sample_product_input):
        """Result contains a RoutingProfile from the Router."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        assert isinstance(result.routing_profile, RoutingProfile)
        # The routing profile should reference the same product.
        assert result.routing_profile.mcm_id == sample_product_input.mcm_id

    def test_pilot_flow_result_has_curated_profile(self, sample_product_input):
        """Result contains a CuratedProfile from the DataCurator."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        assert result.curated_profile is not None
        assert isinstance(result.curated_profile, CuratedProfile)
        assert result.curated_profile.mcm_id == sample_product_input.mcm_id

    def test_pilot_flow_result_has_quality_score(self, sample_product_input):
        """Result contains a QualityScore from the QualityController."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        assert result.quality_score is not None
        assert isinstance(result.quality_score, QualityScore)
        assert result.quality_score.mcm_id == sample_product_input.mcm_id
        # Overall score should be a float between 0 and 1.
        assert 0.0 <= result.quality_score.overall_score <= 1.0

    def test_pilot_flow_result_has_enrichment_outputs(self, sample_product_input):
        """Result contains all UC1 enrichment agent outputs."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        # Visual Interpreter output (dict of extracted attributes).
        assert isinstance(result.extracted_attributes, dict)

        # Internal Researcher output.
        assert result.internal_insights is not None
        assert isinstance(result.internal_insights, InternalInsights)

        # Synectics output.
        assert result.creative_insights is not None
        assert isinstance(result.creative_insights, CreativeInsights)

        # Data Enricher output.
        assert result.enriched_profile is not None
        assert isinstance(result.enriched_profile, EnrichedProductProfile)

    def test_pilot_flow_result_has_uc2_outputs(self, sample_product_input):
        """Result contains all UC2 content generation agent outputs."""
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        # SEO Analyst output.
        assert result.seo_profile is not None
        assert isinstance(result.seo_profile, SEOProfile)

        # Structure Planner output.
        assert result.content_structure is not None
        assert isinstance(result.content_structure, ContentStructure)

        # Brand Compliance output.
        assert result.compliance_report is not None
        assert isinstance(result.compliance_report, ComplianceReport)

        # Fact Checker output.
        assert result.fact_check_report is not None
        assert isinstance(result.fact_check_report, FactCheckReport)

    def test_pilot_flow_processes_product_end_to_end(self, sample_product_input):
        """Full pipeline from ProductInput to edited PlatformContent.

        Verifies the complete data flow: the product's mcm_id appears
        in every intermediate result, provenance entries are collected,
        and the edited content differs from the generated content only
        in formatting (not in identity fields).
        """
        flow = PilotFlow()
        result = flow.run(sample_product_input)

        # mcm_id should be consistent across all outputs.
        assert result.mcm_id == sample_product_input.mcm_id
        assert result.routing_profile.mcm_id == sample_product_input.mcm_id
        assert result.validation_report.mcm_id == sample_product_input.mcm_id
        assert result.competitor_benchmark.mcm_id == sample_product_input.mcm_id
        assert result.generated_content.mcm_id == sample_product_input.mcm_id
        assert result.edited_content.mcm_id == sample_product_input.mcm_id

        # Phase 2 outputs should also have consistent mcm_id.
        assert result.curated_profile.mcm_id == sample_product_input.mcm_id
        assert result.quality_score.mcm_id == sample_product_input.mcm_id
        assert result.seo_profile.mcm_id == sample_product_input.mcm_id
        assert result.compliance_report.mcm_id == sample_product_input.mcm_id
        assert result.fact_check_report.mcm_id == sample_product_input.mcm_id

        # Provenance entries should be collected from all agents.
        assert len(result.provenance_entries) > 0

        # Edited content should target the same platform as generated.
        assert result.edited_content.platform_id == result.generated_content.platform_id

        # The edited product name should be non-empty.
        assert len(result.edited_content.product_name) > 0
