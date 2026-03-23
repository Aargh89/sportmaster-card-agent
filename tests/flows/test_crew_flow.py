"""Tests for ProductCardFlow -- CrewAI Flow-based production pipeline.

Verifies that:
- FlowState can be created with defaults and custom values.
- ProductCardFlow can be instantiated with and without a product.
- All 15 agents are initialized on the flow instance.
"""

from sportmaster_card.flows.crew_flow import FlowState, ProductCardFlow
from sportmaster_card.models.product_input import ProductInput


class TestFlowState:
    """Tests for the FlowState Pydantic model."""

    def test_flow_state_creation_defaults(self):
        """FlowState can be created with all default values."""
        state = FlowState()

        assert state.product_dict == {}
        assert state.flow_type == "1P"
        assert state.mcm_id == ""
        assert state.routing_result == {}
        assert state.enrichment_result == {}
        assert state.content_result == {}
        assert state.final_result == {}

    def test_flow_state_creation_with_values(self):
        """FlowState accepts custom values for all fields."""
        state = FlowState(
            product_dict={"mcm_id": "MCM-001", "brand": "Nike"},
            flow_type="3P",
            mcm_id="MCM-001",
        )

        assert state.product_dict["mcm_id"] == "MCM-001"
        assert state.flow_type == "3P"
        assert state.mcm_id == "MCM-001"


class TestProductCardFlow:
    """Tests for ProductCardFlow instantiation."""

    def test_flow_instantiation_without_product(self):
        """ProductCardFlow can be created without a product input."""
        flow = ProductCardFlow()

        # All 15 agents should be initialized.
        assert flow.router is not None
        assert flow.validator is not None
        assert flow.visual_interpreter is not None
        assert flow.researcher is not None
        assert flow.internal_researcher is not None
        assert flow.synectics is not None
        assert flow.enricher is not None
        assert flow.curator is not None
        assert flow.seo_analyst is not None
        assert flow.structure_planner is not None
        assert flow.generator is not None
        assert flow.brand_compliance is not None
        assert flow.fact_checker is not None
        assert flow.editor is not None
        assert flow.quality_controller is not None

    def test_flow_instantiation_with_product(self, sample_product_input):
        """ProductCardFlow stores product in state when provided."""
        flow = ProductCardFlow(product=sample_product_input)

        assert flow.state.mcm_id == sample_product_input.mcm_id
        assert flow.state.product_dict["brand"] == "Nike"
        assert flow.state.flow_type == "1P"

    def test_flow_instantiation_with_3p_flow_type(self, sample_product_input):
        """ProductCardFlow accepts custom flow_type."""
        flow = ProductCardFlow(product=sample_product_input, flow_type="3P")

        assert flow.state.flow_type == "3P"

    def test_flow_get_product_reconstructs_input(self, sample_product_input):
        """_get_product() reconstructs a ProductInput from state."""
        flow = ProductCardFlow(product=sample_product_input)
        reconstructed = flow._get_product()

        assert isinstance(reconstructed, ProductInput)
        assert reconstructed.mcm_id == sample_product_input.mcm_id
        assert reconstructed.brand == sample_product_input.brand
        assert reconstructed.product_name == sample_product_input.product_name

    def test_flow_has_start_and_listen_methods(self):
        """Flow has route_product, enrich_data, generate_content, finalize."""
        flow = ProductCardFlow()

        assert callable(getattr(flow, "route_product", None))
        assert callable(getattr(flow, "enrich_data", None))
        assert callable(getattr(flow, "generate_content", None))
        assert callable(getattr(flow, "finalize", None))
