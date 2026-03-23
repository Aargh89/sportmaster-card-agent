"""Tests for PilotFlow -- Phase 1 end-to-end pipeline orchestration.

Verifies that PilotFlow correctly sequences all five Phase 1 agents:
Router -> DataValidator -> ExternalResearcher -> ContentGenerator -> CopyEditor.

Each test validates a specific aspect of the pipeline result:
- Instantiation works without errors
- run() returns a PipelineResult
- Result contains PlatformContent (both generated and edited)
- Result contains ValidationReport from the validator
- Result contains RoutingProfile from the router
- Full end-to-end processing from ProductInput to edited content
"""

import pytest

from sportmaster_card.flows.pilot_flow import PilotFlow, PipelineResult
from sportmaster_card.models.content import PlatformContent
from sportmaster_card.models.enrichment import CompetitorBenchmark, ValidationReport
from sportmaster_card.models.routing import RoutingProfile


class TestPilotFlow:
    """Test suite for the PilotFlow orchestrator."""

    def test_pilot_flow_creation(self):
        """PilotFlow can be instantiated with all five agents."""
        flow = PilotFlow()

        # All five agents should be initialized as attributes.
        assert flow.router is not None
        assert flow.validator is not None
        assert flow.researcher is not None
        assert flow.generator is not None
        assert flow.editor is not None

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

        # Provenance entries should be collected from validator + researcher.
        assert len(result.provenance_entries) > 0

        # Edited content should target the same platform as generated.
        assert result.edited_content.platform_id == result.generated_content.platform_id

        # The edited product name should be non-empty.
        assert len(result.edited_content.product_name) > 0
