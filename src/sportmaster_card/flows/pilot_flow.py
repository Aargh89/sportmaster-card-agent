"""Pilot Flow -- full UC1+UC2 pipeline orchestration with 15 agents.

Sequences all 15 agents in the correct order:

    ProductInput
        |
        v
    +-- RouterAgent -----------------+
    |  -> RoutingProfile             |
    +----------------+---------------+
                     |
    +-- DataValidatorAgent ----------+
    |  -> ValidationReport           |
    |  -> DataProvenance[]           |
    +----------------+---------------+
                     |
    +-- VisualInterpreterAgent ------+
    |  -> extracted_attributes       |
    |  -> DataProvenance[]           |
    +----------------+---------------+
                     |
    +-- ExternalResearcherAgent -----+
    |  -> CompetitorBenchmark        |
    |  -> DataProvenance[]           |
    +----------------+---------------+
                     |
    +-- InternalResearcherAgent -----+
    |  -> InternalInsights           |
    |  -> DataProvenance[]           |
    +----------------+---------------+
                     |
    +-- SynecticsAgent --------------+
    |  -> CreativeInsights           |
    +----------------+---------------+
                     |
    +-- DataEnricherAgent -----------+
    |  -> EnrichedProductProfile     |
    +----------------+---------------+
                     |
    +-- DataCuratorAgent ------------+
    |  -> CuratedProfile             |
    +----------------+---------------+
                     |
    +-- SEOAnalystAgent -------------+
    |  -> SEOProfile                 |
    +----------------+---------------+
                     |
    +-- StructurePlannerAgent -------+
    |  -> ContentStructure           |
    +----------------+---------------+
                     |
    +-- ContentGeneratorAgent -------+
    |  -> PlatformContent            |
    +----------------+---------------+
                     |
    +-- BrandComplianceAgent --------+
    |  -> ComplianceReport           |
    +----------------+---------------+
                     |
    +-- FactCheckerAgent ------------+
    |  -> FactCheckReport            |
    +----------------+---------------+
                     |
    +-- CopyEditorAgent -------------+
    |  -> PlatformContent (edited)   |
    +----------------+---------------+
                     |
    +-- QualityControllerAgent ------+
    |  -> QualityScore               |
    +----------------+---------------+
                     |
                     v
               PipelineResult

This is a PLAIN Python class (not a CrewAI Flow). It sequences agents
in order, passing each agent's output as the next agent's input.
CrewAI Flow with @start/@listen decorators will be added when we
integrate real LLM calls in a future phase.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Phase 1 agents (original 5)
from sportmaster_card.agents.content_generator import ContentGeneratorAgent
from sportmaster_card.agents.copy_editor import CopyEditorAgent
from sportmaster_card.agents.data_validator import DataValidatorAgent
from sportmaster_card.agents.external_researcher import ExternalResearcherAgent
from sportmaster_card.agents.router import RouterAgent

# Phase 2 agents (10 new)
from sportmaster_card.agents.brand_compliance import BrandComplianceAgent
from sportmaster_card.agents.data_curator import DataCuratorAgent
from sportmaster_card.agents.data_enricher import DataEnricherAgent
from sportmaster_card.agents.fact_checker import FactCheckerAgent
from sportmaster_card.agents.internal_researcher import InternalResearcherAgent
from sportmaster_card.agents.quality_controller import QualityControllerAgent
from sportmaster_card.agents.seo_analyst import SEOAnalystAgent
from sportmaster_card.agents.structure_planner import StructurePlannerAgent
from sportmaster_card.agents.synectics_agent import SynecticsAgent
from sportmaster_card.agents.visual_interpreter import VisualInterpreterAgent

# Models
from sportmaster_card.models.content import (
    ComplianceReport,
    ContentBrief,
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
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance
from sportmaster_card.models.routing import RoutingProfile


class PipelineResult(BaseModel):
    """Result of the full UC1+UC2 pipeline execution.

    Contains all intermediate and final outputs from each agent in the
    15-agent pipeline. Downstream consumers can inspect any stage's output
    for debugging, auditing, or selective re-processing.

    Attributes:
        mcm_id: Product identifier correlating all outputs.
        routing_profile: Router's classification and pipeline config.
        validation_report: Data Validator's completeness assessment.
        extracted_attributes: Visual Interpreter's photo-extracted attributes.
        competitor_benchmark: External Researcher's competitive intel.
        internal_insights: Internal Researcher's customer insights.
        creative_insights: Synectics Agent's metaphors and associations.
        enriched_profile: Data Enricher's aggregated profile.
        curated_profile: Data Curator's flattened profile for content gen.
        seo_profile: SEO Analyst's keyword profile.
        content_structure: Structure Planner's section layout.
        generated_content: Content Generator's raw platform content.
        compliance_report: Brand Compliance check results.
        fact_check_report: Fact Checker verification results.
        edited_content: Copy Editor's polished platform content.
        quality_score: Quality Controller's multi-dimension score.
        provenance_entries: Combined provenance from all agents.
    """

    # Product identifier -- ties all pipeline outputs together.
    mcm_id: str = Field(
        ...,
        description="MCM identifier correlating all pipeline outputs.",
    )

    # Router output -- determines pipeline configuration.
    routing_profile: RoutingProfile = Field(
        ...,
        description="Routing decision from the Router agent.",
    )

    # Data Validator output -- completeness and validity assessment.
    validation_report: ValidationReport = Field(
        ...,
        description="Validation report from the Data Validator agent.",
    )

    # Visual Interpreter output -- extracted visual attributes from photos.
    extracted_attributes: dict = Field(
        default_factory=dict,
        description="Visual attributes extracted from product photos.",
    )

    # External Researcher output -- competitor intelligence.
    competitor_benchmark: CompetitorBenchmark = Field(
        ...,
        description="Competitor benchmark from the External Researcher agent.",
    )

    # Internal Researcher output -- customer insights from internal docs.
    internal_insights: Optional[InternalInsights] = Field(
        default=None,
        description="Customer insights from the Internal Researcher agent.",
    )

    # Synectics Agent output -- creative metaphors and associations.
    creative_insights: Optional[CreativeInsights] = Field(
        default=None,
        description="Creative insights from the Synectics agent.",
    )

    # Data Enricher output -- aggregated enrichment profile.
    enriched_profile: Optional[EnrichedProductProfile] = Field(
        default=None,
        description="Enriched product profile from the Data Enricher agent.",
    )

    # Data Curator output -- flat profile ready for content generation.
    curated_profile: Optional[CuratedProfile] = Field(
        default=None,
        description="Curated profile from the Data Curator agent.",
    )

    # SEO Analyst output -- keyword profile for target platform.
    seo_profile: Optional[SEOProfile] = Field(
        default=None,
        description="SEO keyword profile from the SEO Analyst agent.",
    )

    # Structure Planner output -- content section layout.
    content_structure: Optional[ContentStructure] = Field(
        default=None,
        description="Content structure from the Structure Planner agent.",
    )

    # Content Generator output -- raw content before editing.
    generated_content: PlatformContent = Field(
        ...,
        description="Raw platform content from the Content Generator agent.",
    )

    # Brand Compliance output -- guideline check results.
    compliance_report: Optional[ComplianceReport] = Field(
        default=None,
        description="Compliance report from the Brand Compliance agent.",
    )

    # Fact Checker output -- factual accuracy verification.
    fact_check_report: Optional[FactCheckReport] = Field(
        default=None,
        description="Fact check report from the Fact Checker agent.",
    )

    # Copy Editor output -- polished content after editing.
    edited_content: PlatformContent = Field(
        ...,
        description="Edited platform content from the Copy Editor agent.",
    )

    # Quality Controller output -- multi-dimension quality score.
    quality_score: Optional[QualityScore] = Field(
        default=None,
        description="Quality score from the Quality Controller agent.",
    )

    # Combined provenance entries from all agents.
    provenance_entries: list[DataProvenance] = Field(
        default_factory=list,
        description="Data provenance entries from all pipeline agents.",
    )


class PilotFlow:
    """Orchestrates the full UC1+UC2 pipeline with 15 agents.

    Sequences agents in the correct order:
        Router -> DataValidator -> VisualInterpreter -> ExternalResearcher
        -> InternalResearcher -> Synectics -> DataEnricher -> DataCurator
        -> SEOAnalyst -> StructurePlanner -> ContentGenerator -> BrandCompliance
        -> FactChecker -> CopyEditor -> QualityController

    Each agent's output feeds into the next agent's input. The flow is
    synchronous and deterministic (no LLM calls in stub mode).

    Attributes:
        router: RouterAgent instance for product classification.
        validator: DataValidatorAgent instance for completeness checking.
        visual_interpreter: VisualInterpreterAgent for photo analysis.
        researcher: ExternalResearcherAgent for competitor intelligence.
        internal_researcher: InternalResearcherAgent for customer insights.
        synectics: SynecticsAgent for creative metaphors.
        enricher: DataEnricherAgent for data aggregation.
        curator: DataCuratorAgent for profile flattening.
        seo_analyst: SEOAnalystAgent for keyword profiles.
        structure_planner: StructurePlannerAgent for content layout.
        generator: ContentGeneratorAgent for platform content creation.
        brand_compliance: BrandComplianceAgent for guideline checking.
        fact_checker: FactCheckerAgent for accuracy verification.
        editor: CopyEditorAgent for content polishing.
        quality_controller: QualityControllerAgent for quality scoring.

    Example::

        >>> flow = PilotFlow()
        >>> result = flow.run(product_input)
        >>> result.edited_content.product_name
        'Nike Беговые кроссовки Air Zoom Pegasus 41'
        >>> result.quality_score.passes_threshold
        True
    """

    def __init__(self) -> None:
        """Initialize PilotFlow with all 15 agents.

        Each agent is instantiated in standalone mode (no CrewAI agent
        backing). All processing is deterministic and rule-based.
        """
        # UC1 Enrichment agents (agents 1-8)
        self.router = RouterAgent()
        self.validator = DataValidatorAgent()
        self.visual_interpreter = VisualInterpreterAgent()
        self.researcher = ExternalResearcherAgent()
        self.internal_researcher = InternalResearcherAgent()
        self.synectics = SynecticsAgent()
        self.enricher = DataEnricherAgent()
        self.curator = DataCuratorAgent()

        # UC2 Content Generation agents (agents 9-15)
        self.seo_analyst = SEOAnalystAgent()
        self.structure_planner = StructurePlannerAgent()
        self.generator = ContentGeneratorAgent()
        self.brand_compliance = BrandComplianceAgent()
        self.fact_checker = FactCheckerAgent()
        self.editor = CopyEditorAgent()
        self.quality_controller = QualityControllerAgent()

    def run(self, product: ProductInput, flow_type: str = "1P") -> PipelineResult:
        """Execute the full 15-agent pipeline for one product.

        Runs all agents in sequence, passing each agent's output as input
        to the next. Returns a PipelineResult containing every intermediate
        and final output for full traceability.

        Args:
            product: Raw product data from the Excel template. Must have
                all required fields populated (mcm_id, brand, category,
                product_group, product_subgroup, product_name).
            flow_type: "1P" (first-party, full pipeline) or "3P"
                (third-party, lightweight). Defaults to "1P".

        Returns:
            PipelineResult with all 15 agent outputs and provenance entries.

        Example::

            >>> flow = PilotFlow()
            >>> product = ProductInput(
            ...     mcm_id="MCM-001", brand="Nike",
            ...     category="Обувь", product_group="Кроссовки",
            ...     product_subgroup="Беговые", product_name="Pegasus",
            ... )
            >>> result = flow.run(product)
            >>> result.mcm_id
            'MCM-001'
        """
        # ---- UC1 Enrichment Pipeline ----

        # Step 1: Route -- classify product and determine pipeline config.
        routing = self.router.route(product, flow_type)

        # Step 2: Validate -- check data completeness and produce provenance.
        validation, val_provenance = self.validator.validate(product)

        # Step 3: Visual Interpret -- extract attributes from product photos.
        extracted_attrs, vis_provenance = self.visual_interpreter.interpret(product)

        # Step 4: External Research -- gather competitor intelligence.
        benchmark, res_provenance = self.researcher.research(product)

        # Step 5: Internal Research -- mine internal knowledge bases.
        internal_insights, int_provenance = self.internal_researcher.research(product)

        # Step 6: Synectics -- generate creative metaphors and associations.
        creative_insights = self.synectics.generate(product)

        # Combine all provenance entries from UC1 agents.
        all_provenance = (
            val_provenance + vis_provenance + res_provenance + int_provenance
        )

        # Step 7: Data Enricher -- merge all upstream outputs.
        enriched_profile = self.enricher.enrich(
            product=product,
            validation_report=validation,
            competitor_benchmark=benchmark,
            provenance_entries=all_provenance,
            internal_insights=internal_insights,
            creative_insights=creative_insights,
        )

        # Step 8: Data Curator -- flatten into CuratedProfile.
        curated_profile = self.curator.curate(enriched_profile)

        # ---- UC2 Content Generation Pipeline ----

        # Step 9: SEO Analyst -- generate keyword profile.
        platform_id = routing.target_platforms[0]
        seo_profile = self.seo_analyst.analyze(product, platform_id=platform_id)

        # Step 10: Structure Planner -- plan content section layout.
        brief = ContentBrief(
            mcm_id=product.mcm_id,
            platform_id=platform_id,
            brief_type="standard",
            tone_of_voice="professional",
            required_sections=["description", "benefits", "technologies", "composition"],
            max_description_length=3000,
            max_title_length=150,
        )
        content_structure = self.structure_planner.plan(brief)

        # Step 11: Content Generator -- create platform content.
        generated = self.generator.generate(product, platform_id=platform_id)

        # Step 12: Brand Compliance -- check against brand guidelines.
        compliance_report = self.brand_compliance.check(
            generated, brand_name=product.brand
        )

        # Step 13: Fact Checker -- verify factual accuracy.
        fact_check_report = self.fact_checker.check(generated, curated_profile)

        # Step 14: Copy Editor -- polish the generated content.
        edited = self.editor.edit(generated)

        # Step 15: Quality Controller -- final quality scoring.
        quality_score = self.quality_controller.evaluate(
            edited, compliance_report, fact_check_report
        )

        return PipelineResult(
            mcm_id=product.mcm_id,
            routing_profile=routing,
            validation_report=validation,
            extracted_attributes=extracted_attrs,
            competitor_benchmark=benchmark,
            internal_insights=internal_insights,
            creative_insights=creative_insights,
            enriched_profile=enriched_profile,
            curated_profile=curated_profile,
            seo_profile=seo_profile,
            content_structure=content_structure,
            generated_content=generated,
            compliance_report=compliance_report,
            fact_check_report=fact_check_report,
            edited_content=edited,
            quality_score=quality_score,
            provenance_entries=all_provenance,
        )
