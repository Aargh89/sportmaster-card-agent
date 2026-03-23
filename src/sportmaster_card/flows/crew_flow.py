"""CrewAI Flow for production pipeline with real LLM execution.

Uses CrewAI Flow decorators (@start, @listen) for event-driven orchestration.
This flow is used in production with OPENROUTER_API_KEY set.
For testing without API keys, use PilotFlow from pilot_flow.py.

Architecture::

    @start --> route_product
      @listen(route_product) --> enrich_data (UC1: validate -> interpret ->
          research -> enrich -> curate)
        @listen(enrich_data) --> generate_content (UC2: seo -> plan ->
            generate -> check -> edit -> score)
          @listen(generate_content) --> finalize

The flow delegates to the same agent classes used in PilotFlow, so all
business logic (routing rules, enrichment heuristics, content templates)
is shared between stub-mode and production-mode pipelines.
"""

from __future__ import annotations

from typing import Any, Optional

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from sportmaster_card.agents.brand_compliance import BrandComplianceAgent
from sportmaster_card.agents.content_generator import ContentGeneratorAgent
from sportmaster_card.agents.copy_editor import CopyEditorAgent
from sportmaster_card.agents.data_curator import DataCuratorAgent
from sportmaster_card.agents.data_enricher import DataEnricherAgent
from sportmaster_card.agents.data_validator import DataValidatorAgent
from sportmaster_card.agents.external_researcher import ExternalResearcherAgent
from sportmaster_card.agents.fact_checker import FactCheckerAgent
from sportmaster_card.agents.internal_researcher import InternalResearcherAgent
from sportmaster_card.agents.quality_controller import QualityControllerAgent
from sportmaster_card.agents.router import RouterAgent
from sportmaster_card.agents.seo_analyst import SEOAnalystAgent
from sportmaster_card.agents.structure_planner import StructurePlannerAgent
from sportmaster_card.agents.synectics_agent import SynecticsAgent
from sportmaster_card.agents.visual_interpreter import VisualInterpreterAgent
from sportmaster_card.models.content import ContentBrief
from sportmaster_card.models.product_input import ProductInput


class FlowState(BaseModel):
    """State passed between flow steps.

    Holds the product input, flow type, and all intermediate results
    produced by each pipeline stage. Each step reads what it needs from
    the state and writes its output back.

    Attributes:
        product_dict: Serialized ProductInput (dict) for Pydantic compat.
        flow_type: "1P" (first-party) or "3P" (third-party).
        mcm_id: Product identifier carried through all steps.
        routing_result: Router agent output (dict).
        enrichment_result: Combined UC1 enrichment outputs (dict).
        content_result: Combined UC2 content generation outputs (dict).
        final_result: Assembled PipelineResult (dict).
    """

    product_dict: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized ProductInput for cross-step access.",
    )
    flow_type: str = Field(
        default="1P",
        description="Pipeline flow type: '1P' or '3P'.",
    )
    mcm_id: str = Field(
        default="",
        description="Product MCM identifier.",
    )
    routing_result: dict[str, Any] = Field(
        default_factory=dict,
        description="Router agent output.",
    )
    enrichment_result: dict[str, Any] = Field(
        default_factory=dict,
        description="Combined UC1 enrichment outputs.",
    )
    content_result: dict[str, Any] = Field(
        default_factory=dict,
        description="Combined UC2 content generation outputs.",
    )
    final_result: dict[str, Any] = Field(
        default_factory=dict,
        description="Assembled PipelineResult.",
    )


class ProductCardFlow(Flow[FlowState]):
    """Production CrewAI Flow for product card generation.

    Orchestrates the same 15 agents as PilotFlow but uses CrewAI Flow
    decorators for event-driven execution. Each decorated method represents
    a pipeline stage that runs when its upstream dependency completes.

    The flow is initialized with a ProductInput and flow_type, stored in
    the FlowState. Call ``kickoff()`` to execute the full pipeline.

    Attributes:
        router: RouterAgent for product classification.
        validator: DataValidatorAgent for completeness checking.
        visual_interpreter: VisualInterpreterAgent for photo analysis.
        researcher: ExternalResearcherAgent for competitor intel.
        internal_researcher: InternalResearcherAgent for customer insights.
        synectics: SynecticsAgent for creative metaphors.
        enricher: DataEnricherAgent for data aggregation.
        curator: DataCuratorAgent for profile flattening.
        seo_analyst: SEOAnalystAgent for keyword profiles.
        structure_planner: StructurePlannerAgent for content layout.
        generator: ContentGeneratorAgent for platform content.
        brand_compliance: BrandComplianceAgent for guideline checking.
        fact_checker: FactCheckerAgent for accuracy verification.
        editor: CopyEditorAgent for content polishing.
        quality_controller: QualityControllerAgent for quality scoring.

    Example::

        >>> product = ProductInput(mcm_id="MCM-001", brand="Nike", ...)
        >>> flow = ProductCardFlow(product=product)
        >>> result = flow.kickoff()
    """

    def __init__(
        self,
        product: Optional[ProductInput] = None,
        flow_type: str = "1P",
        **kwargs: Any,
    ) -> None:
        """Initialize ProductCardFlow with agents and optional product input.

        Args:
            product: ProductInput to process. If provided, it is serialized
                into the FlowState so all steps can access it.
            flow_type: "1P" (full pipeline) or "3P" (lightweight).
            **kwargs: Passed through to the CrewAI Flow base class.
        """
        super().__init__(**kwargs)

        # Store product in state if provided.
        if product is not None:
            self.state.product_dict = product.model_dump()
            self.state.mcm_id = product.mcm_id
            self.state.flow_type = flow_type

        # UC1 Enrichment agents.
        self.router = RouterAgent()
        self.validator = DataValidatorAgent()
        self.visual_interpreter = VisualInterpreterAgent()
        self.researcher = ExternalResearcherAgent()
        self.internal_researcher = InternalResearcherAgent()
        self.synectics = SynecticsAgent()
        self.enricher = DataEnricherAgent()
        self.curator = DataCuratorAgent()

        # UC2 Content Generation agents.
        self.seo_analyst = SEOAnalystAgent()
        self.structure_planner = StructurePlannerAgent()
        self.generator = ContentGeneratorAgent()
        self.brand_compliance = BrandComplianceAgent()
        self.fact_checker = FactCheckerAgent()
        self.editor = CopyEditorAgent()
        self.quality_controller = QualityControllerAgent()

    def _get_product(self) -> ProductInput:
        """Reconstruct ProductInput from the flow state.

        Returns:
            ProductInput instance rebuilt from the serialized dict.
        """
        return ProductInput(**self.state.product_dict)

    @start()
    def route_product(self) -> dict[str, Any]:
        """Step 1: Route the product -- classify and determine pipeline config.

        Reads the ProductInput from flow state, runs the RouterAgent,
        and stores the RoutingProfile in state for downstream steps.

        Returns:
            Dict with routing_profile data for the @listen chain.
        """
        product = self._get_product()
        routing = self.router.route(product, self.state.flow_type)
        self.state.routing_result = routing.model_dump()
        return self.state.routing_result

    @listen(route_product)
    def enrich_data(self) -> dict[str, Any]:
        """Step 2: UC1 enrichment pipeline.

        Runs all enrichment agents in sequence: DataValidator,
        VisualInterpreter, ExternalResearcher, InternalResearcher,
        Synectics, DataEnricher, DataCurator.

        Stores combined enrichment outputs in state.

        Returns:
            Dict with all enrichment outputs for the @listen chain.
        """
        product = self._get_product()

        # Validate.
        validation, val_provenance = self.validator.validate(product)

        # Visual Interpret.
        extracted_attrs, vis_provenance = self.visual_interpreter.interpret(product)

        # External Research.
        benchmark, res_provenance = self.researcher.research(product)

        # Internal Research.
        internal_insights, int_provenance = self.internal_researcher.research(product)

        # Synectics.
        creative_insights = self.synectics.generate(product)

        # Combine provenance.
        all_provenance = (
            val_provenance + vis_provenance + res_provenance + int_provenance
        )

        # Data Enricher.
        enriched_profile = self.enricher.enrich(
            product=product,
            validation_report=validation,
            competitor_benchmark=benchmark,
            provenance_entries=all_provenance,
            internal_insights=internal_insights,
            creative_insights=creative_insights,
        )

        # Data Curator.
        curated_profile = self.curator.curate(enriched_profile)

        self.state.enrichment_result = {
            "validation_report": validation.model_dump(),
            "extracted_attributes": extracted_attrs,
            "competitor_benchmark": benchmark.model_dump(),
            "internal_insights": internal_insights.model_dump(),
            "creative_insights": creative_insights.model_dump(),
            "enriched_profile": enriched_profile.model_dump(),
            "curated_profile": curated_profile.model_dump(),
            "provenance_entries": [p.model_dump() for p in all_provenance],
        }
        return self.state.enrichment_result

    @listen(enrich_data)
    def generate_content(self) -> dict[str, Any]:
        """Step 3: UC2 content generation pipeline.

        Runs all content generation agents: SEOAnalyst, StructurePlanner,
        ContentGenerator, BrandCompliance, FactChecker, CopyEditor,
        QualityController.

        Stores combined content outputs in state.

        Returns:
            Dict with all content generation outputs for the @listen chain.
        """
        product = self._get_product()
        routing_data = self.state.routing_result
        target_platforms = routing_data.get("target_platforms", ["sm_site"])
        platform_id = target_platforms[0]

        # SEO Analyst.
        seo_profile = self.seo_analyst.analyze(product, platform_id=platform_id)

        # Structure Planner.
        brief = ContentBrief(
            mcm_id=product.mcm_id,
            platform_id=platform_id,
            brief_type="standard",
            tone_of_voice="professional",
            required_sections=[
                "description",
                "benefits",
                "technologies",
                "composition",
            ],
            max_description_length=3000,
            max_title_length=150,
        )
        content_structure = self.structure_planner.plan(brief)

        # Content Generator.
        generated = self.generator.generate(product, platform_id=platform_id)

        # Brand Compliance.
        compliance_report = self.brand_compliance.check(
            generated, brand_name=product.brand
        )

        # Fact Checker.
        from sportmaster_card.models.enrichment import CuratedProfile

        curated_profile = CuratedProfile(
            **self.state.enrichment_result["curated_profile"]
        )
        fact_check_report = self.fact_checker.check(generated, curated_profile)

        # Copy Editor.
        edited = self.editor.edit(generated)

        # Quality Controller.
        quality_score = self.quality_controller.evaluate(
            edited, compliance_report, fact_check_report
        )

        self.state.content_result = {
            "seo_profile": seo_profile.model_dump(),
            "content_structure": content_structure.model_dump(),
            "generated_content": generated.model_dump(),
            "compliance_report": compliance_report.model_dump(),
            "fact_check_report": fact_check_report.model_dump(),
            "edited_content": edited.model_dump(),
            "quality_score": quality_score.model_dump(),
        }
        return self.state.content_result

    @listen(generate_content)
    def finalize(self) -> dict[str, Any]:
        """Step 4: Final assembly -- combine all outputs into PipelineResult.

        Merges routing, enrichment, and content results into a single
        dict matching the PipelineResult schema. This is the terminal
        node of the flow graph.

        Returns:
            Dict with the complete pipeline result.
        """
        self.state.final_result = {
            "mcm_id": self.state.mcm_id,
            "routing_profile": self.state.routing_result,
            **self.state.enrichment_result,
            **self.state.content_result,
        }
        return self.state.final_result
