"""Pilot Flow -- Phase 1 end-to-end pipeline orchestration.

Sequences all Phase 1 agents in the correct order:

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
    +-- ExternalResearcherAgent -----+
    |  -> CompetitorBenchmark        |
    |  -> DataProvenance[]           |
    +----------------+---------------+
                     |
    +-- ContentGeneratorAgent -------+
    |  -> PlatformContent            |
    +----------------+---------------+
                     |
    +-- CopyEditorAgent -------------+
    |  -> PlatformContent (edited)   |
    +----------------+---------------+
                     |
                     v
               PipelineResult

This is a PLAIN Python class (not a CrewAI Flow). It sequences agents
in order, passing each agent's output as the next agent's input.
CrewAI Flow with @start/@listen decorators will be added when we
integrate real LLM calls in Phase 2.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sportmaster_card.agents.content_generator import ContentGeneratorAgent
from sportmaster_card.agents.copy_editor import CopyEditorAgent
from sportmaster_card.agents.data_validator import DataValidatorAgent
from sportmaster_card.agents.external_researcher import ExternalResearcherAgent
from sportmaster_card.agents.router import RouterAgent
from sportmaster_card.models.content import PlatformContent
from sportmaster_card.models.enrichment import CompetitorBenchmark, ValidationReport
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance
from sportmaster_card.models.routing import RoutingProfile


class PipelineResult(BaseModel):
    """Result of the full Phase 1 pipeline execution.

    Contains all intermediate and final outputs from each agent in the
    pipeline. Downstream consumers can inspect any stage's output for
    debugging, auditing, or selective re-processing.

    Attributes:
        mcm_id: Product identifier correlating all outputs.
        routing_profile: Router's classification and pipeline config.
        validation_report: Data Validator's completeness assessment.
        competitor_benchmark: External Researcher's competitive intel.
        generated_content: Content Generator's raw platform content.
        edited_content: Copy Editor's polished platform content.
        provenance_entries: Combined provenance from validator + researcher.
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

    # External Researcher output -- competitor intelligence.
    competitor_benchmark: CompetitorBenchmark = Field(
        ...,
        description="Competitor benchmark from the External Researcher agent.",
    )

    # Content Generator output -- raw content before editing.
    generated_content: PlatformContent = Field(
        ...,
        description="Raw platform content from the Content Generator agent.",
    )

    # Copy Editor output -- polished content after editing.
    edited_content: PlatformContent = Field(
        ...,
        description="Edited platform content from the Copy Editor agent.",
    )

    # Combined provenance entries from validator and researcher.
    provenance_entries: list[DataProvenance] = Field(
        default_factory=list,
        description="Data provenance entries from validator and researcher.",
    )


class PilotFlow:
    """Orchestrates the Phase 1 pilot pipeline.

    Sequences agents: Router -> Validator -> Researcher -> Generator -> Editor.
    Each agent's output feeds into the next agent's input. The flow is
    synchronous and deterministic in Phase 1 (no LLM calls).

    This is a plain Python class, not a CrewAI Flow. The CrewAI Flow
    version with @start/@listen decorators will replace this when
    real LLM integration happens in Phase 2.

    Attributes:
        router: RouterAgent instance for product classification.
        validator: DataValidatorAgent instance for completeness checking.
        researcher: ExternalResearcherAgent for competitor intelligence.
        generator: ContentGeneratorAgent for platform content creation.
        editor: CopyEditorAgent for content polishing.

    Example::

        >>> flow = PilotFlow()
        >>> result = flow.run(product_input)
        >>> result.edited_content.product_name
        'Nike Беговые кроссовки Air Zoom Pegasus 41'
    """

    def __init__(self) -> None:
        """Initialize PilotFlow with all five Phase 1 agents.

        Each agent is instantiated in standalone mode (no CrewAI agent
        backing). All processing is deterministic and rule-based.
        """
        # Step 1 agent: classifies product and determines pipeline config.
        self.router = RouterAgent()

        # Step 2 agent: validates data completeness from the Excel template.
        self.validator = DataValidatorAgent()

        # Step 3 agent: researches competitor product cards (stub in Phase 1).
        self.researcher = ExternalResearcherAgent()

        # Step 4 agent: generates platform-specific product content.
        self.generator = ContentGeneratorAgent()

        # Step 5 agent: polishes and enforces formatting on generated content.
        self.editor = CopyEditorAgent()

    def run(self, product: ProductInput, flow_type: str = "1P") -> PipelineResult:
        """Execute the full Phase 1 pipeline for one product.

        Runs all five agents in sequence, passing each agent's output
        as input to the next. Returns a PipelineResult containing every
        intermediate and final output for full traceability.

        Args:
            product: Raw product data from the Excel template. Must have
                all required fields populated (mcm_id, brand, category,
                product_group, product_subgroup, product_name).
            flow_type: "1P" (first-party, full pipeline) or "3P"
                (third-party, lightweight). Defaults to "1P".

        Returns:
            PipelineResult with routing, validation, benchmark,
            generated content, edited content, and provenance entries.

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
        # Step 1: Route -- classify product and determine pipeline config.
        routing = self.router.route(product, flow_type)

        # Step 2: Validate -- check data completeness and produce provenance.
        validation, val_provenance = self.validator.validate(product)

        # Step 3: Research -- gather competitor intelligence (stub in Phase 1).
        benchmark, res_provenance = self.researcher.research(product)

        # Step 4: Generate -- create platform content for the first target.
        # Phase 1 targets a single platform (the first in the routing list).
        platform_id = routing.target_platforms[0]
        generated = self.generator.generate(product, platform_id=platform_id)

        # Step 5: Edit -- polish the generated content (enforce limits, cleanup).
        edited = self.editor.edit(generated)

        # Combine provenance entries from validator and researcher.
        all_provenance = val_provenance + res_provenance

        return PipelineResult(
            mcm_id=product.mcm_id,
            routing_profile=routing,
            validation_report=validation,
            competitor_benchmark=benchmark,
            generated_content=generated,
            edited_content=edited,
            provenance_entries=all_provenance,
        )
