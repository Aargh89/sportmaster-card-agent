"""Parallel Content Flow -- fan-out content generation across platforms.

Runs UC1 enrichment once, then generates content for each target platform
in parallel using concurrent.futures.ThreadPoolExecutor.

This implements the v0.3 architecture change: parallel generation from
CuratedProfile instead of master->rewrite model.

Architecture::

    ProductInput
        |
        v
    UC1 (sequential, runs ONCE):
        Router -> DataValidator -> VisualInterpreter -> ExternalResearcher
        -> InternalResearcher -> Synectics -> DataEnricher -> DataCurator
        -> CuratedProfile (single source of truth)
        |
        | fan-out per platform
        +----------+----------+----------+
        v          v          v          v
    UC2(SM)    UC2(WB)    UC2(Ozon)  UC2(Lamoda)  <- PARALLEL
        |          |          |          |
        v          v          v          v
    PlatformContent per platform
        |          |          |          |
        +----------+----------+----------+
                        v
                PlatformContentSet
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from pydantic import BaseModel, Field

from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.routing import RoutingProfile
from sportmaster_card.models.enrichment import (
    ValidationReport, CompetitorBenchmark, InternalInsights,
    CreativeInsights, EnrichedProductProfile, CuratedProfile,
)
from sportmaster_card.models.content import (
    PlatformContent, QualityScore, PlatformContentSet,
    SEOProfile, ContentStructure, ComplianceReport, FactCheckReport,
    ContentBrief,
)
from sportmaster_card.models.provenance import DataProvenance, DataProvenanceLog
from sportmaster_card.models.platform_profile import PlatformProfile

# Import all agents
from sportmaster_card.agents.router import RouterAgent
from sportmaster_card.agents.data_validator import DataValidatorAgent
from sportmaster_card.agents.visual_interpreter import VisualInterpreterAgent
from sportmaster_card.agents.external_researcher import ExternalResearcherAgent
from sportmaster_card.agents.internal_researcher import InternalResearcherAgent
from sportmaster_card.agents.synectics_agent import SynecticsAgent
from sportmaster_card.agents.data_enricher import DataEnricherAgent
from sportmaster_card.agents.data_curator import DataCuratorAgent
from sportmaster_card.agents.seo_analyst import SEOAnalystAgent
from sportmaster_card.agents.structure_planner import StructurePlannerAgent
from sportmaster_card.agents.content_generator import ContentGeneratorAgent
from sportmaster_card.agents.brand_compliance import BrandComplianceAgent
from sportmaster_card.agents.fact_checker import FactCheckerAgent
from sportmaster_card.agents.copy_editor import CopyEditorAgent
from sportmaster_card.agents.quality_controller import QualityControllerAgent


class ParallelPipelineResult(BaseModel):
    """Result of the parallel content generation pipeline.

    Contains UC1 results (shared) and UC2 results per platform.

    Attributes:
        mcm_id: Product identifier correlating all outputs.
        routing_profile: Router's classification and pipeline config.
        validation_report: Data Validator's completeness assessment.
        curated_profile: Data Curator's flattened profile for content gen.
        content_set: Aggregated content across all target platforms.
        provenance_entries: Combined provenance from all UC1 agents.
        platforms_generated: Number of platforms that received content.
        platforms_passed_quality: Number of platforms passing quality threshold.
    """

    mcm_id: str = Field(
        ...,
        description="MCM identifier correlating all pipeline outputs.",
    )
    routing_profile: RoutingProfile = Field(
        ...,
        description="Routing decision from the Router agent.",
    )
    validation_report: ValidationReport = Field(
        ...,
        description="Validation report from the Data Validator agent.",
    )
    curated_profile: CuratedProfile = Field(
        ...,
        description="Curated profile from the Data Curator agent.",
    )
    content_set: PlatformContentSet = Field(
        ...,
        description="Aggregated content across all target platforms.",
    )
    provenance_entries: list[DataProvenance] = Field(
        default_factory=list,
        description="Data provenance entries from all UC1 pipeline agents.",
    )
    platforms_generated: int = Field(
        default=0,
        description="Number of platforms that received generated content.",
    )
    platforms_passed_quality: int = Field(
        default=0,
        description="Number of platforms passing the quality threshold.",
    )


class ParallelContentFlow:
    """Parallel content generation across multiple platforms.

    UC1 runs once -> CuratedProfile
    UC2 fans out per platform (ThreadPoolExecutor)

    Attributes:
        max_workers: Maximum number of threads for parallel UC2 execution.
        router: RouterAgent instance for product classification.
        validator: DataValidatorAgent instance for completeness checking.
        visual: VisualInterpreterAgent for photo analysis.
        ext_researcher: ExternalResearcherAgent for competitor intelligence.
        int_researcher: InternalResearcherAgent for customer insights.
        synectics: SynecticsAgent for creative metaphors.
        enricher: DataEnricherAgent for data aggregation.
        curator: DataCuratorAgent for profile flattening.
        seo: SEOAnalystAgent for keyword profiles.
        planner: StructurePlannerAgent for content layout.
        generator: ContentGeneratorAgent for platform content creation.
        compliance: BrandComplianceAgent for guideline checking.
        fact_checker: FactCheckerAgent for accuracy verification.
        editor: CopyEditorAgent for content polishing.
        qc: QualityControllerAgent for quality scoring.

    Example::

        >>> flow = ParallelContentFlow()
        >>> result = flow.run(product, target_platforms=["sm_site", "wb", "ozon"])
        >>> len(result.content_set.contents)  # 3 platforms
        3
    """

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize with configurable parallelism.

        Args:
            max_workers: Maximum number of threads for parallel UC2
                execution. Defaults to 4.
        """
        self.max_workers = max_workers

        # UC1 agents (shared, run once)
        self.router = RouterAgent()
        self.validator = DataValidatorAgent()
        self.visual = VisualInterpreterAgent()
        self.ext_researcher = ExternalResearcherAgent()
        self.int_researcher = InternalResearcherAgent()
        self.synectics = SynecticsAgent()
        self.enricher = DataEnricherAgent()
        self.curator = DataCuratorAgent()

        # UC2 agents (shared instances -- they are stateless)
        self.seo = SEOAnalystAgent()
        self.planner = StructurePlannerAgent()
        self.generator = ContentGeneratorAgent()
        self.compliance = BrandComplianceAgent()
        self.fact_checker = FactCheckerAgent()
        self.editor = CopyEditorAgent()
        self.qc = QualityControllerAgent()

    def run(
        self,
        product: ProductInput,
        target_platforms: list[str] | None = None,
        flow_type: str = "1P",
    ) -> ParallelPipelineResult:
        """Execute full pipeline with parallel platform generation.

        Args:
            product: Raw product input.
            target_platforms: List of platform IDs. If None, uses ["sm_site"].
            flow_type: "1P" or "3P".

        Returns:
            ParallelPipelineResult with content per platform.
        """
        if target_platforms is None:
            target_platforms = ["sm_site"]

        # === UC1: Enrichment (runs ONCE) ===
        routing = self.router.route(product, flow_type)
        val_report, val_prov = self.validator.validate(product)
        extracted, vis_prov = self.visual.interpret(product)
        benchmark, ext_prov = self.ext_researcher.research(product)
        insights, int_prov = self.int_researcher.research(product)
        creative = self.synectics.generate(product)

        all_prov = val_prov + vis_prov + ext_prov + int_prov
        enriched = self.enricher.enrich(
            product=product,
            validation_report=val_report,
            competitor_benchmark=benchmark,
            internal_insights=insights,
            creative_insights=creative,
            provenance_entries=all_prov,
        )
        curated = self.curator.curate(enriched)

        # === UC2: Content Generation (fan-out per platform) ===
        contents: dict[str, PlatformContent] = {}
        scores: dict[str, QualityScore] = {}

        if self.max_workers > 1 and len(target_platforms) > 1:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(
                        self._generate_for_platform, product, curated, pid
                    ): pid
                    for pid in target_platforms
                }
                for future in as_completed(futures):
                    pid = futures[future]
                    content, score = future.result()
                    contents[pid] = content
                    scores[pid] = score
        else:
            # Sequential (single platform or max_workers=1)
            for pid in target_platforms:
                content, score = self._generate_for_platform(product, curated, pid)
                contents[pid] = content
                scores[pid] = score

        # Assemble result
        all_passed = all(s.passes_threshold for s in scores.values())

        content_set = PlatformContentSet(
            mcm_id=product.mcm_id,
            contents=contents,
            quality_scores=scores,
            target_platforms=target_platforms,
            all_passed_quality=all_passed,
        )

        return ParallelPipelineResult(
            mcm_id=product.mcm_id,
            routing_profile=routing,
            validation_report=val_report,
            curated_profile=curated,
            content_set=content_set,
            provenance_entries=all_prov,
            platforms_generated=len(contents),
            platforms_passed_quality=sum(
                1 for s in scores.values() if s.passes_threshold
            ),
        )

    def _generate_for_platform(
        self,
        product: ProductInput,
        curated: CuratedProfile,
        platform_id: str,
    ) -> tuple[PlatformContent, QualityScore]:
        """Run the full UC2 cycle for one platform.

        This method is called in parallel for each target platform.

        Args:
            product: Raw product input (for agent calls that need it).
            curated: Shared CuratedProfile from UC1.
            platform_id: Target platform identifier (e.g., "sm_site", "wb").

        Returns:
            Tuple of (edited PlatformContent, QualityScore) for this platform.
        """
        # Load platform profile from YAML config (if available)
        profile = self._load_platform_profile(platform_id)
        max_desc = (
            profile.text_requirements.max_description_length if profile else 3000
        )
        max_title = (
            profile.text_requirements.max_title_length if profile else 150
        )

        # UC2 pipeline for this platform
        seo = self.seo.analyze(product, platform_id)

        brief = ContentBrief(
            mcm_id=product.mcm_id,
            platform_id=platform_id,
            brief_type="standard",
            tone_of_voice=(
                profile.text_requirements.tone_of_voice
                if profile
                else "professional"
            ),
            required_sections=(
                profile.text_requirements.required_sections
                if profile
                else ["description", "benefits"]
            ),
            max_description_length=max_desc,
            max_title_length=max_title,
        )

        structure = self.planner.plan(brief)
        content = self.generator.generate(product, platform_id, max_desc, max_title)
        compliance = self.compliance.check(
            content,
            brand_name=product.brand,
            forbidden_words=(
                profile.text_requirements.forbidden_words if profile else []
            ),
        )
        fact_report = self.fact_checker.check(content, curated)
        edited = self.editor.edit(content, max_desc, max_title)
        score = self.qc.evaluate(edited, compliance, fact_report)

        return edited, score

    def _load_platform_profile(self, platform_id: str) -> Optional[PlatformProfile]:
        """Load PlatformProfile from YAML config.

        Args:
            platform_id: Platform identifier to look up.

        Returns:
            PlatformProfile if the YAML config exists, None otherwise.
        """
        from pathlib import Path

        config_dir = Path(__file__).parent.parent / "config" / "platforms"
        yaml_path = config_dir / f"{platform_id}.yaml"
        if yaml_path.exists():
            return PlatformProfile.from_yaml(str(yaml_path))
        return None
