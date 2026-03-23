"""UC2 content output models -- the MAIN output of the content generation pipeline.

This module defines the three core data models that represent the output of the
UC2 (Content Generation) use case in the Sportmaster multi-agent product card
system. Together, these models capture:

1. **What to write** (ContentBrief) -- instructions for content generation
2. **The written content** (PlatformContent) -- generated text per platform
3. **How good it is** (QualityScore) -- multi-dimensional quality assessment

UC2 Pipeline Flow::

    CuratedProfile (UC1 output)
        |
        v
    Brief Selector (Agent 2.3)
        |
        v
    ContentBrief -----> Content Generator (Agent 2.7)
        |                       |
        |                       v
        |               PlatformContent (one per platform)
        |                       |
        |                       v
        |               Quality Controller (Agent 2.9)
        |                       |
        |                       v
        +-------------> QualityScore
                            |
                            v
                        passes_threshold >= 0.7?
                            |           |
                           YES          NO
                            |           |
                            v           v
                        UC3 Publish   Regenerate

Module-level design decisions:
    - Benefit is a small value object extracted as a separate model because
      benefits appear as a list inside PlatformContent and may be reused.
    - PlatformContent includes change-tracking hashes (content_hash,
      source_curated_profile_hash) for incremental updates.
    - QualityScore uses a computed property (passes_threshold) rather than
      a stored field to ensure the threshold check is always current.
    - All score fields are float 0-1 (not percentage) for consistency.

Typical usage::

    from sportmaster_card.models.content import (
        Benefit,
        ContentBrief,
        PlatformContent,
        QualityScore,
    )

    brief = ContentBrief(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        brief_type="standard",
        tone_of_voice="professional",
        required_sections=["description", "benefits"],
        max_description_length=2000,
        max_title_length=120,
    )
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Benefit(BaseModel):
    """A single product benefit bullet: short title plus explanatory sentence.

    Benefits are the core value-communication element of product content.
    Each benefit highlights one specific advantage of the product in a format
    optimized for scannable reading on marketplace product pages.

    Typical rendering on a product page::

        +-------------------------------------------+
        | Benefit Card                              |
        | +---------+  Амортизация                  |
        | | [icon]  |  Технология Air Zoom           |
        | |         |  обеспечивает мягкую           |
        | +---------+  амортизацию при беге.         |
        +-------------------------------------------+

    Attributes:
        title: Short benefit title (1-3 words). Used as a headline in the
            benefit card or bullet point. Should be concise and scannable.
            Examples: "Амортизация", "Вентиляция", "Сцепление".
        description: Benefit description (1-2 sentences). Explains the
            benefit in terms of the specific technology or feature that
            delivers it. Should reference brand technologies where possible.

    Examples:
        Running shoe cushioning benefit::

            >>> benefit = Benefit(
            ...     title="Амортизация",
            ...     description="Технология Air Zoom обеспечивает мягкую амортизацию.",
            ... )
            >>> benefit.title
            'Амортизация'
    """

    # Short headline for the benefit card (1-3 words, scannable)
    title: str = Field(
        ...,
        description=(
            "Short benefit title used as a headline (1-3 words). "
            "Must be scannable and immediately convey the advantage."
        ),
        examples=["Амортизация", "Вентиляция", "Сцепление", "Поддержка стопы"],
    )

    # Explanatory sentence linking the benefit to a product feature or technology
    description: str = Field(
        ...,
        description=(
            "Benefit description in 1-2 sentences. Explains the specific "
            "technology or feature that delivers this benefit to the user."
        ),
        examples=[
            "Технология Air Zoom обеспечивает мягкую амортизацию при беге.",
            "Mesh-верх обеспечивает свободную циркуляцию воздуха.",
        ],
    )


class ContentBrief(BaseModel):
    """Brief Selector output: instructions controlling content generation.

    ContentBrief is produced by the Brief Selector agent (Agent 2.3) and
    consumed by the Content Generator (Agent 2.7). It specifies HOW content
    should be written for a specific product on a specific platform.

    The brief captures platform-specific constraints (character limits),
    content structure requirements (which sections to include), and tone
    guidelines -- everything the Content Generator needs to produce
    on-brand, on-spec content without further lookups.

    ASCII Schema Diagram::

        +---------------------------------------------------------------+
        |                       ContentBrief                            |
        +---------------------------------------------------------------+
        | Field                  | Type       | Example                 |
        +------------------------+------------+-------------------------|
        | mcm_id                 | str        | "MCM-001-BLK-42"       |
        | platform_id            | str        | "sm_site"              |
        | brief_type             | str        | "standard"             |
        | tone_of_voice          | str        | "professional"         |
        | required_sections      | list[str]  | ["description", ...]   |
        | max_description_length | int        | 2000                   |
        | max_title_length       | int        | 120                    |
        +---------------------------------------------------------------+

        Data Flow::

            RoutingProfile.target_platforms
                |
                v  (one brief per platform)
            Brief Selector
                |
                v
            ContentBrief ---> Content Generator ---> PlatformContent

    Attributes:
        mcm_id: MCM identifier linking this brief to the product. Correlation
            ID used across the entire agent pipeline for traceability.
        platform_id: Target platform identifier. Determines character limits,
            required fields, and formatting rules. Common values: "sm_site",
            "wb", "ozon", "lamoda", "megamarket".
        brief_type: Content brief template type. Controls the overall content
            strategy: "standard" for regular products, "premium" for high-value
            products with richer content, "seo_category" for category pages.
        tone_of_voice: Writing style directive for the Content Generator.
            Common values: "professional" (neutral expert tone), "casual"
            (friendly conversational), "sporty" (energetic motivational).
        required_sections: Ordered list of content sections that MUST be
            present in the generated PlatformContent. The Content Generator
            will produce content for each section in this order.
        max_description_length: Maximum character count for the main product
            description field on this platform. Sourced from PlatformProfile.
        max_title_length: Maximum character count for the product title/name
            on this platform. Sourced from PlatformProfile.

    Examples:
        Standard brief for SM website::

            >>> brief = ContentBrief(
            ...     mcm_id="MCM-001-BLK-42",
            ...     platform_id="sm_site",
            ...     brief_type="standard",
            ...     tone_of_voice="professional",
            ...     required_sections=["description", "benefits", "technologies"],
            ...     max_description_length=2000,
            ...     max_title_length=120,
            ... )
            >>> brief.brief_type
            'standard'
    """

    # ------------------------------------------------------------------
    # Identity fields -- link brief to product and platform
    # ------------------------------------------------------------------

    # MCM identifier: the universal correlation key tying this brief
    # back to the ProductInput and forward to PlatformContent / QualityScore.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this brief to the original product. "
            "Used as correlation ID across all pipeline agents."
        ),
        examples=["MCM-001-BLK-42", "MCM-003-RED-38"],
    )

    # Platform identifier: determines all platform-specific constraints.
    # One ContentBrief is generated per target platform from RoutingProfile.
    platform_id: str = Field(
        ...,
        description=(
            "Target platform identifier. Each platform has different "
            "character limits, required fields, and formatting rules."
        ),
        examples=["sm_site", "wb", "ozon", "lamoda", "megamarket"],
    )

    # ------------------------------------------------------------------
    # Content strategy fields -- control HOW content is generated
    # ------------------------------------------------------------------

    # Brief type selects the content template/strategy.
    # "standard" covers ~80% of products; "premium" triggers richer content.
    brief_type: str = Field(
        ...,
        description=(
            "Content brief template type controlling overall strategy. "
            "'standard' for regular products, 'premium' for rich content, "
            "'seo_category' for category landing pages."
        ),
        examples=["standard", "premium", "seo_category"],
    )

    # Tone of voice guides the Content Generator's writing style.
    # Must match the brand guidelines for the target platform + segment.
    tone_of_voice: str = Field(
        ...,
        description=(
            "Writing style directive: 'professional' (neutral expert), "
            "'casual' (friendly conversational), 'sporty' (energetic)."
        ),
        examples=["professional", "casual", "sporty"],
    )

    # Required sections define the structure of the generated content.
    # The Content Generator MUST produce content for each listed section.
    required_sections: list[str] = Field(
        ...,
        description=(
            "Ordered list of content sections the Content Generator must "
            "produce. Sections are platform-specific and may include: "
            "'description', 'benefits', 'technologies', 'composition'."
        ),
        examples=[
            ["description", "benefits", "technologies"],
            ["description", "benefits"],
        ],
    )

    # ------------------------------------------------------------------
    # Platform constraint fields -- character limits from PlatformProfile
    # ------------------------------------------------------------------

    # Maximum character count for the main description text block.
    # Exceeding this limit causes content truncation or rejection.
    max_description_length: int = Field(
        ...,
        description=(
            "Maximum character count for the main product description. "
            "Sourced from PlatformProfile. Exceeding causes rejection."
        ),
        examples=[2000, 5000, 1000],
    )

    # Maximum character count for the product title / name line.
    # Marketplace titles have strict limits for search result display.
    max_title_length: int = Field(
        ...,
        description=(
            "Maximum character count for the product title. "
            "Marketplace titles have strict limits for search display."
        ),
        examples=[120, 60, 200],
    )


class PlatformContent(BaseModel):
    """Content Generator output: all generated text for one product on one platform.

    PlatformContent is the primary deliverable of the UC2 pipeline. It contains
    every text element needed to populate a product card on a specific marketplace
    or website. One PlatformContent instance is generated per (product, platform)
    pair.

    The model includes both human-facing content (product_name, description,
    benefits) and machine-facing SEO fields (seo_title, seo_meta_description,
    seo_keywords). Change-tracking hashes enable incremental updates when the
    source CuratedProfile is modified.

    ASCII Schema Diagram::

        +---------------------------------------------------------------+
        |                     PlatformContent                           |
        +---------------------------------------------------------------+
        | CONTENT FIELDS (human-facing)                                 |
        |   Field         | Type           | Example                    |
        |   --------------+----------------+----------------------------|
        |   product_name  | str            | "Nike Pegasus 41 Муж..."   |
        |   description   | str            | "Беговые кроссовки..."     |
        |   benefits      | list[Benefit]  | [{title, description},...] |
        +---------------------------------------------------------------+
        | SEO FIELDS (search-engine-facing)                             |
        |   Field                | Type       | Example                 |
        |   ---------------------+------------+-------------------------|
        |   seo_title            | str        | "Купить Nike Pegasus.."  |
        |   seo_meta_description | str        | "Nike Pegasus 41 —..."   |
        |   seo_keywords         | list[str]  | ["nike pegasus", ...]    |
        +---------------------------------------------------------------+
        | TRACKING FIELDS (change detection)                            |
        |   content_hash                | str  | "a1b2c3..."            |
        |   source_curated_profile_hash | str  | "d4e5f6..."            |
        +---------------------------------------------------------------+

        Data Flow::

            ContentBrief + CuratedProfile
                |
                v
            Content Generator (Agent 2.7)
                |
                v
            PlatformContent ---> Quality Controller ---> QualityScore
                |                                            |
                v                                            v
            UC3 Publication (if passes_threshold)     Regenerate (if not)

    Attributes:
        mcm_id: MCM identifier for this product card content.
        platform_id: Target platform (e.g., "sm_site", "wb", "ozon").
        product_name: SEO-optimized product name tailored for this platform.
            May differ from the original ProductInput.product_name.
        description: Main product description text. Length must respect the
            max_description_length from the ContentBrief.
        benefits: List of 1-8 product benefit bullets. Each benefit has a
            short title and explanatory description.
        seo_title: HTML <title> tag content optimized for search engines.
            Typically includes brand + product + call-to-action.
        seo_meta_description: HTML <meta name="description"> content.
            Summarizes the product for search result snippets (150-160 chars).
        seo_keywords: Target keyword list for SEO optimization. Used for
            keyword density checks and internal linking strategies.
        content_hash: SHA-256 hash of all content fields. Used for change
            detection -- if hash unchanged, content was not regenerated.
        source_curated_profile_hash: Hash of the CuratedProfile version
            that was used to generate this content. Enables traceability
            from content back to the source data.

    Examples:
        SM site content for a running shoe::

            >>> from sportmaster_card.models.content import Benefit
            >>> content = PlatformContent(
            ...     mcm_id="MCM-001-BLK-42",
            ...     platform_id="sm_site",
            ...     product_name="Nike Air Zoom Pegasus 41",
            ...     description="Беговые кроссовки с амортизацией.",
            ...     benefits=[Benefit(title="Амортизация", description="Air Zoom.")],
            ...     seo_title="Купить Nike Pegasus | Sportmaster",
            ...     seo_meta_description="Nike Pegasus 41 — кроссовки для бега.",
            ...     seo_keywords=["nike pegasus"],
            ... )
            >>> content.platform_id
            'sm_site'
    """

    # ------------------------------------------------------------------
    # Identity fields -- link content to product and platform
    # ------------------------------------------------------------------

    # MCM identifier: correlates this content with the product across the pipeline.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this content to the original product. "
            "Correlation ID used across all pipeline agents."
        ),
        examples=["MCM-001-BLK-42", "MCM-003-RED-38"],
    )

    # Platform identifier: which marketplace or site this content targets.
    # Content is tailored per-platform (different lengths, tone, SEO strategy).
    platform_id: str = Field(
        ...,
        description=(
            "Target platform this content was generated for. "
            "Content is tailored to each platform's requirements."
        ),
        examples=["sm_site", "wb", "ozon", "lamoda", "megamarket"],
    )

    # ------------------------------------------------------------------
    # Content fields -- human-facing text elements
    # ------------------------------------------------------------------

    # SEO-optimized product name, potentially different per platform.
    # WB may want "Кроссовки Nike Pegasus 41 мужские беговые",
    # while SM site uses "Nike Air Zoom Pegasus 41".
    product_name: str = Field(
        ...,
        description=(
            "SEO-optimized product name tailored for this platform. "
            "May differ from the original ProductInput.product_name."
        ),
        examples=[
            "Nike Air Zoom Pegasus 41 Мужские беговые кроссовки",
            "Кроссовки Nike Pegasus 41 мужские для бега",
        ],
    )

    # Main product description -- the largest text block on the card.
    # Must respect max_description_length from the ContentBrief.
    description: str = Field(
        ...,
        description=(
            "Main product description text. Must respect character limits "
            "from the ContentBrief. Contains the core product narrative."
        ),
        examples=["Беговые кроссовки Nike Air Zoom Pegasus 41 с технологией амортизации."],
    )

    # Product benefit bullets (1-8 items).
    # Each benefit has a short title for scannability and a description
    # that connects the feature to a user-relevant advantage.
    benefits: list[Benefit] = Field(
        ...,
        description=(
            "List of 1-8 product benefit bullets. Each benefit highlights "
            "one specific advantage with a short title and description."
        ),
        examples=[[{"title": "Амортизация", "description": "Air Zoom для мягкого бега."}]],
    )

    # ------------------------------------------------------------------
    # SEO fields -- search-engine-facing metadata
    # ------------------------------------------------------------------

    # HTML <title> tag content for the product page.
    # Optimized for search engine display (typically brand + product + CTA).
    seo_title: str = Field(
        ...,
        description=(
            "HTML <title> tag content optimized for search engines. "
            "Typically: brand + product name + call-to-action or store name."
        ),
        examples=["Купить Nike Air Zoom Pegasus 41 | Sportmaster"],
    )

    # HTML <meta name="description"> content for search result snippets.
    # Should be 150-160 characters for optimal display in search results.
    seo_meta_description: str = Field(
        ...,
        description=(
            "HTML meta description for search result snippets. "
            "Optimal length: 150-160 characters for full display."
        ),
        examples=["Nike Air Zoom Pegasus 41 — беговые кроссовки с амортизацией Air Zoom."],
    )

    # Target keywords for SEO optimization and keyword density analysis.
    # Used by the Quality Controller to verify keyword coverage.
    seo_keywords: list[str] = Field(
        ...,
        description=(
            "Target keyword list for SEO optimization. Used for "
            "keyword density checks and internal linking strategies."
        ),
        examples=[["nike pegasus", "беговые кроссовки", "air zoom"]],
    )

    # ------------------------------------------------------------------
    # Change-tracking fields -- enable incremental content updates
    # ------------------------------------------------------------------

    # Hash of all content fields for change detection.
    # If content_hash is unchanged between runs, content was not modified.
    content_hash: str = Field(
        default="",
        description=(
            "SHA-256 hash of all content fields for change detection. "
            "Empty string means hash has not been computed yet."
        ),
        examples=["a1b2c3d4e5f6", ""],
    )

    # Hash of the CuratedProfile that was used as input for generation.
    # Enables traceability: "this content was generated from THAT data version."
    source_curated_profile_hash: str = Field(
        default="",
        description=(
            "Hash of the CuratedProfile version used to generate this content. "
            "Enables traceability from content back to source data."
        ),
        examples=["d4e5f6a1b2c3", ""],
    )


class QualityScore(BaseModel):
    """Quality Controller output: multi-dimensional quality assessment of content.

    QualityScore is produced by the Quality Controller agent (Agent 2.9) after
    evaluating a PlatformContent instance. It provides both an overall score
    and per-dimension breakdowns, enabling targeted improvements when content
    fails the quality gate.

    The quality gate threshold is 0.7 (70%). Content scoring below this
    threshold is sent back for regeneration. The ``passes_threshold`` property
    provides a convenient boolean check for this gate.

    Score Dimensions::

        +-------------------------------------------------------------------+
        |                    QualityScore Dimensions                        |
        +-------------------------------------------------------------------+
        | Dimension            | What it measures                           |
        +----------------------+--------------------------------------------|
        | readability_score    | Text clarity, sentence structure, grammar  |
        | seo_score            | Keyword coverage, meta tag quality         |
        | factual_accuracy     | Claims match CuratedProfile source data   |
        | brand_compliance     | Tone, terminology, brand guidelines match  |
        | uniqueness_score     | Distinctiveness vs. competitor/template    |
        +-------------------------------------------------------------------+
        | overall_score        | Weighted combination of all dimensions     |
        +-------------------------------------------------------------------+

        Quality Gate Decision::

            overall_score >= 0.7  --->  PASS  --->  UC3 Publication
            overall_score <  0.7  --->  FAIL  --->  Content Regeneration
                                                    (with issues as feedback)

    Attributes:
        mcm_id: MCM identifier for the evaluated product content.
        platform_id: Platform identifier for the evaluated content.
        overall_score: Weighted aggregate score (0.0-1.0). This is the
            primary decision metric for the quality gate.
        readability_score: Text readability assessment (0.0-1.0). Evaluates
            sentence length, paragraph structure, and grammar correctness.
        seo_score: SEO quality assessment (0.0-1.0). Checks keyword density,
            title tag optimization, and meta description quality.
        factual_accuracy_score: Factual correctness (0.0-1.0). Verifies that
            all claims in the content are supported by CuratedProfile data.
        brand_compliance_score: Brand guideline compliance (0.0-1.0). Checks
            tone of voice, prohibited terms, and terminology consistency.
        uniqueness_score: Content uniqueness (0.0-1.0). Measures how
            distinct the content is from templates and competitor content.
        issues: List of specific quality issues found during evaluation.
            Passed back to the Content Generator as feedback for regeneration.

    Examples:
        High-quality content passing the gate::

            >>> score = QualityScore(
            ...     mcm_id="MCM-001-BLK-42",
            ...     platform_id="sm_site",
            ...     overall_score=0.85,
            ...     readability_score=0.9,
            ...     seo_score=0.8,
            ...     factual_accuracy_score=0.95,
            ...     brand_compliance_score=0.75,
            ...     uniqueness_score=0.88,
            ... )
            >>> score.passes_threshold
            True

        Content failing the gate with issues::

            >>> score = QualityScore(
            ...     mcm_id="MCM-002-WHT-40",
            ...     platform_id="wb",
            ...     overall_score=0.55,
            ...     readability_score=0.4,
            ...     seo_score=0.6,
            ...     factual_accuracy_score=0.7,
            ...     brand_compliance_score=0.5,
            ...     uniqueness_score=0.6,
            ...     issues=["Слишком длинные предложения", "Нет ключевых слов"],
            ... )
            >>> score.passes_threshold
            False
    """

    # ------------------------------------------------------------------
    # Identity fields
    # ------------------------------------------------------------------

    # MCM identifier: links this quality assessment to the product.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier for the evaluated product content. "
            "Correlation ID linking score to product and content."
        ),
        examples=["MCM-001-BLK-42", "MCM-003-RED-38"],
    )

    # Platform identifier: links this score to the specific platform content.
    platform_id: str = Field(
        ...,
        description=(
            "Platform identifier for the evaluated content instance. "
            "Scores are platform-specific (SM site vs WB may differ)."
        ),
        examples=["sm_site", "wb", "ozon"],
    )

    # ------------------------------------------------------------------
    # Score fields -- all float 0.0-1.0
    # ------------------------------------------------------------------

    # Overall weighted score: the PRIMARY metric for the quality gate.
    # This is a weighted combination of all dimension scores.
    # The weighting formula is configured per platform in PlatformProfile.
    overall_score: float = Field(
        ...,
        description=(
            "Weighted aggregate quality score (0.0-1.0). Primary metric "
            "for the quality gate. Content >= 0.7 passes to publication."
        ),
        examples=[0.85, 0.55, 0.7],
    )

    # Readability: evaluates sentence structure, paragraph length, grammar.
    # Low scores indicate overly complex or poorly structured text.
    readability_score: float = Field(
        ...,
        description=(
            "Text readability assessment (0.0-1.0). Evaluates sentence "
            "length, paragraph structure, grammar, and clarity."
        ),
        examples=[0.9, 0.4],
    )

    # SEO quality: checks keyword density, title optimization, meta tags.
    # Low scores indicate missing keywords or poor meta descriptions.
    seo_score: float = Field(
        ...,
        description=(
            "SEO quality assessment (0.0-1.0). Checks keyword density, "
            "title tag optimization, and meta description quality."
        ),
        examples=[0.8, 0.6],
    )

    # Factual accuracy: verifies claims against CuratedProfile data.
    # Low scores mean the content contains unsupported or wrong claims.
    factual_accuracy_score: float = Field(
        ...,
        description=(
            "Factual correctness (0.0-1.0). Verifies all content claims "
            "are supported by the source CuratedProfile data."
        ),
        examples=[0.95, 0.7],
    )

    # Brand compliance: checks tone, terminology, prohibited terms.
    # Low scores indicate off-brand language or guideline violations.
    brand_compliance_score: float = Field(
        ...,
        description=(
            "Brand guideline compliance (0.0-1.0). Checks tone of voice, "
            "prohibited terms, and terminology consistency."
        ),
        examples=[0.75, 0.5],
    )

    # Uniqueness: measures distinctiveness from templates and competitors.
    # Low scores indicate generic or duplicated content.
    uniqueness_score: float = Field(
        ...,
        description=(
            "Content uniqueness (0.0-1.0). Measures distinctiveness "
            "from templates, competitor text, and other product cards."
        ),
        examples=[0.88, 0.6],
    )

    # ------------------------------------------------------------------
    # Issues list -- feedback for content regeneration
    # ------------------------------------------------------------------

    # Specific quality issues found during evaluation.
    # When content fails the gate, these issues are passed back to the
    # Content Generator as structured feedback for targeted improvements.
    issues: list[str] = Field(
        default=[],
        description=(
            "List of specific quality issues found. Passed to Content "
            "Generator as feedback when content fails the quality gate."
        ),
        examples=[
            ["Слишком длинное описание", "Нет ключевых слов в заголовке"],
            [],
        ],
    )

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def passes_threshold(self) -> bool:
        """Check whether this content passes the quality gate for publication.

        The quality gate threshold is 0.7 (70%). Content with an overall_score
        at or above this value is approved for UC3 publication. Content below
        the threshold is returned to the Content Generator for regeneration,
        with the ``issues`` list providing specific feedback.

        Returns:
            True if overall_score >= 0.7 (content approved for publication).
            False if overall_score < 0.7 (content needs regeneration).

        Examples::

            >>> score = QualityScore(
            ...     mcm_id="MCM-001", platform_id="sm_site",
            ...     overall_score=0.85, readability_score=0.9,
            ...     seo_score=0.8, factual_accuracy_score=0.9,
            ...     brand_compliance_score=0.8, uniqueness_score=0.8,
            ... )
            >>> score.passes_threshold
            True
        """
        # The 0.7 threshold is defined in the v0.3 architecture specification.
        # It represents the minimum acceptable quality for customer-facing content.
        return self.overall_score >= 0.7


# ======================================================================
# UC2 Quality & SEO models
# ======================================================================
#
# The four models below support the quality-assurance side of the UC2
# pipeline.  While the models above (ContentBrief, PlatformContent,
# QualityScore) cover the *generation* path, the models here cover the
# *evaluation* path:
#
#   SEOProfile          -- keyword & meta-tag recommendations per platform
#   ContentStructure    -- section layout and word-count guidelines
#   ComplianceReport    -- brand-guideline compliance check results
#   FactCheckReport     -- factual accuracy verification results
#
# Together they feed into the Quality Controller (Agent 2.9) and provide
# structured, actionable feedback to the Content Generator (Agent 2.7)
# when content fails the quality gate.


class SEOProfile(BaseModel):
    """SEO keyword and meta-tag recommendations for a product on a platform.

    SEOProfile is produced by the SEO Analyst sub-step of the Quality
    Controller (Agent 2.9).  It captures the primary and secondary
    keywords that the Content Generator should target, plus recommended
    title and meta-description text optimized for search engines.

    The profile is platform-specific because keyword strategies differ
    across marketplaces (e.g., Wildberries favours long-tail queries
    while the SM website targets branded terms).

    Data Flow::

        CuratedProfile + PlatformProfile
            |
            v
        SEO Analyst (Agent 2.9 sub-step)
            |
            v
        SEOProfile ---> Content Generator (keyword targets)
                   +--> Quality Controller  (keyword coverage check)

    Attributes:
        mcm_id: MCM identifier linking this SEO profile to the product.
            Correlation ID used across all pipeline agents for traceability.
        platform_id: Target platform for these SEO recommendations.
            Keyword strategy is platform-specific (SM site vs WB vs Ozon).
        primary_keywords: High-priority keywords that MUST appear in the
            generated content.  Typically 2-5 phrases combining brand name,
            product type, and model.  Ordered by search volume descending.
        secondary_keywords: Supporting keywords to improve topical coverage.
            These SHOULD appear in the content when space allows but are not
            mandatory.  Ordered by relevance descending.
        title_recommendation: Suggested product title optimized for search.
            Includes primary keyword, brand name, and key product attributes.
            Must fit within the platform's max_title_length constraint.
        meta_description_recommendation: Suggested HTML meta description
            optimized for search result click-through rate (CTR).  Should
            be 150-160 characters and include a call-to-action.

    Examples:
        SEO profile for Nike running shoes on SM site::

            >>> seo = SEOProfile(
            ...     mcm_id="MCM-001",
            ...     platform_id="sm_site",
            ...     primary_keywords=["беговые кроссовки nike"],
            ...     secondary_keywords=["кроссовки для бега"],
            ...     title_recommendation="Nike Pegasus 41",
            ...     meta_description_recommendation="Купить Nike Pegasus 41",
            ... )
            >>> seo.primary_keywords[0]
            'беговые кроссовки nike'
    """

    # ------------------------------------------------------------------
    # Identity fields -- link SEO profile to product and platform
    # ------------------------------------------------------------------

    # MCM identifier: the universal correlation key tying this SEO profile
    # back to the ProductInput and forward to PlatformContent / QualityScore.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this SEO profile to the product. "
            "Correlation ID used across all pipeline agents."
        ),
        examples=["MCM-001", "MCM-003-RED-38"],
    )

    # Platform identifier: SEO strategies differ per marketplace.
    # WB favours long-tail queries; SM site targets branded search terms.
    platform_id: str = Field(
        ...,
        description=(
            "Target platform for these SEO recommendations. "
            "Keyword strategy differs across marketplaces."
        ),
        examples=["sm_site", "wb", "ozon", "lamoda"],
    )

    # ------------------------------------------------------------------
    # Keyword fields -- search terms the content should target
    # ------------------------------------------------------------------

    # Primary keywords: MUST appear in the generated content.
    # Ordered by estimated search volume (highest first).
    primary_keywords: list[str] = Field(
        ...,
        description=(
            "High-priority keywords that MUST appear in content. "
            "Typically 2-5 phrases: brand + product type + model. "
            "Ordered by search volume descending."
        ),
        examples=[["беговые кроссовки nike", "nike pegasus"]],
    )

    # Secondary keywords: SHOULD appear when space allows.
    # Improve topical coverage without being mandatory.
    secondary_keywords: list[str] = Field(
        default=[],
        description=(
            "Supporting keywords to improve topical coverage. "
            "Should appear when space allows, not mandatory. "
            "Ordered by relevance descending."
        ),
        examples=[["кроссовки для бега", "air zoom"]],
    )

    # ------------------------------------------------------------------
    # Recommendation fields -- suggested meta-tag text
    # ------------------------------------------------------------------

    # Suggested product title with primary keyword placement.
    # Must respect platform max_title_length from PlatformProfile.
    title_recommendation: str = Field(
        ...,
        description=(
            "Suggested product title optimized for search engines. "
            "Includes primary keyword, brand, and key attributes. "
            "Must fit within the platform's max_title_length."
        ),
        examples=["Nike Беговые кроссовки Pegasus 41"],
    )

    # Suggested meta description for search result snippets.
    # Optimal length: 150-160 characters with a call-to-action.
    meta_description_recommendation: str = Field(
        ...,
        description=(
            "Suggested HTML meta description for search snippets. "
            "Optimal length: 150-160 chars with call-to-action. "
            "Improves click-through rate in search results."
        ),
        examples=["Купить Nike Pegasus 41 в Спортмастер — бесплатная доставка."],
    )


class ContentStructure(BaseModel):
    """Section layout and word-count guidelines for content generation.

    ContentStructure is produced by the Brief Selector (Agent 2.3) as a
    companion to ContentBrief.  While ContentBrief specifies WHAT to write
    and the tone, ContentStructure specifies HOW the content should be
    organized: which sections, in what order, and with what guidelines.

    The Content Generator uses ContentStructure to produce consistently
    formatted product cards across thousands of SKUs, ensuring that every
    card follows the same logical flow (e.g., intro -> benefits ->
    technologies -> composition).

    Data Flow::

        PlatformProfile.content_template
            |
            v
        Brief Selector (Agent 2.3)
            |
            v
        ContentStructure ---> Content Generator (section layout)

    Attributes:
        mcm_id: MCM identifier linking this structure to the product.
            Correlation ID used across all pipeline agents.
        platform_id: Target platform for this content structure.
            Different platforms may require different section layouts
            (e.g., Ozon requires a "characteristics" section).
        sections: Ordered list of section identifiers that define the
            content layout.  The Content Generator produces text for each
            section in this exact order.  Common sections: "intro",
            "benefits", "technologies", "composition", "care".
        section_guidelines: Per-section writing guidelines as a mapping
            from section identifier to instruction text.  Not every
            section needs a guideline; missing keys use defaults.
        target_word_count: Target total word count for all sections
            combined.  Used by the Quality Controller to flag content
            that is too short or too long.

    Examples:
        Structure for a running shoe on SM site::

            >>> cs = ContentStructure(
            ...     mcm_id="MCM-001",
            ...     platform_id="sm_site",
            ...     sections=["intro", "benefits"],
            ...     section_guidelines={"intro": "2-3 sentences"},
            ...     target_word_count=400,
            ... )
            >>> cs.sections[0]
            'intro'
    """

    # ------------------------------------------------------------------
    # Identity fields
    # ------------------------------------------------------------------

    # MCM identifier: correlates this structure with the product.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this content structure to the product. "
            "Correlation ID used across all pipeline agents."
        ),
        examples=["MCM-001", "MCM-003-RED-38"],
    )

    # Platform identifier: section layouts differ per marketplace.
    # Ozon may require "characteristics"; WB may skip "technologies".
    platform_id: str = Field(
        ...,
        description=(
            "Target platform for this content structure. "
            "Different platforms require different section layouts."
        ),
        examples=["sm_site", "wb", "ozon"],
    )

    # ------------------------------------------------------------------
    # Structure fields -- section layout and guidelines
    # ------------------------------------------------------------------

    # Ordered section identifiers defining the content layout.
    # Content Generator produces text for each section in this order.
    sections: list[str] = Field(
        ...,
        description=(
            "Ordered list of section identifiers defining content layout. "
            "Content Generator produces text for each section in order. "
            "Common: 'intro', 'benefits', 'technologies', 'composition'."
        ),
        examples=[["intro", "benefits", "technologies", "composition"]],
    )

    # Per-section writing instructions (section_id -> guideline text).
    # Not all sections need guidelines; missing keys use platform defaults.
    section_guidelines: dict[str, str] = Field(
        default={},
        description=(
            "Per-section writing guidelines mapping section identifier "
            "to instruction text. Missing keys use platform defaults."
        ),
        examples=[{"intro": "2-3 предложения, ключевые преимущества"}],
    )

    # Target total word count across all sections combined.
    # Quality Controller flags content that deviates significantly.
    target_word_count: int = Field(
        default=500,
        description=(
            "Target total word count for all sections combined. "
            "Quality Controller flags content deviating significantly."
        ),
        examples=[300, 500, 800],
    )


class ComplianceReport(BaseModel):
    """Brand-guideline compliance check results for generated content.

    ComplianceReport is produced by the Compliance Checker sub-step of the
    Quality Controller (Agent 2.9).  It verifies that generated content
    adheres to brand guidelines: correct brand name casing, approved
    terminology, prohibited phrases, and tone-of-voice consistency.

    When ``is_compliant`` is False, the ``violations`` list contains
    specific issues and ``suggestions`` provides recommended fixes.  This
    structured feedback enables the Content Generator to make targeted
    corrections rather than regenerating from scratch.

    Data Flow::

        PlatformContent + BrandGuidelines
            |
            v
        Compliance Checker (Agent 2.9 sub-step)
            |
            v
        ComplianceReport
            |
            +---> is_compliant=True  ---> continue to publication
            +---> is_compliant=False ---> Content Generator (feedback)

    Attributes:
        mcm_id: MCM identifier linking this report to the product.
            Correlation ID used across all pipeline agents.
        is_compliant: Whether the content passes all brand guideline
            checks.  True means no violations found; False means at
            least one violation was detected.
        violations: List of specific brand guideline violations found.
            Each entry describes what rule was broken and where.
            Empty list when ``is_compliant`` is True.
        suggestions: List of recommended fixes corresponding to the
            violations.  Provides actionable guidance for the Content
            Generator to correct issues without full regeneration.

    Examples:
        Compliant content::

            >>> cr = ComplianceReport(mcm_id="MCM-001", is_compliant=True)
            >>> cr.violations
            []

        Non-compliant content::

            >>> cr = ComplianceReport(
            ...     mcm_id="MCM-001",
            ...     is_compliant=False,
            ...     violations=["Brand name lowercase"],
            ...     suggestions=["Use 'Nike' not 'nike'"],
            ... )
            >>> cr.is_compliant
            False
    """

    # ------------------------------------------------------------------
    # Identity field
    # ------------------------------------------------------------------

    # MCM identifier: correlates this compliance report with the product.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this compliance report to the product. "
            "Correlation ID used across all pipeline agents."
        ),
        examples=["MCM-001", "MCM-003-RED-38"],
    )

    # ------------------------------------------------------------------
    # Compliance result fields
    # ------------------------------------------------------------------

    # Overall compliance verdict: True if all checks pass, False otherwise.
    is_compliant: bool = Field(
        ...,
        description=(
            "Whether the content passes all brand guideline checks. "
            "True = no violations; False = at least one violation found."
        ),
        examples=[True, False],
    )

    # Specific guideline violations found during the compliance check.
    # Empty list when is_compliant is True.
    violations: list[str] = Field(
        default=[],
        description=(
            "List of specific brand guideline violations found. "
            "Each entry describes what rule was broken and where. "
            "Empty when is_compliant is True."
        ),
        examples=[
            ["Название бренда в нижнем регистре", "Использован запрещённый термин"],
            [],
        ],
    )

    # Recommended fixes for each violation -- actionable feedback.
    # Enables targeted corrections without full content regeneration.
    suggestions: list[str] = Field(
        default=[],
        description=(
            "Recommended fixes for violations. Provides actionable "
            "guidance for the Content Generator to correct issues "
            "without full regeneration."
        ),
        examples=[
            ["Использовать 'Nike' вместо 'nike'"],
            [],
        ],
    )


class FactCheckReport(BaseModel):
    """Factual accuracy verification results for generated content.

    FactCheckReport is produced by the Fact Checker sub-step of the
    Quality Controller (Agent 2.9).  It verifies that every factual claim
    in the generated PlatformContent is supported by the source
    CuratedProfile data (materials, technologies, measurements, etc.).

    The report distinguishes between *inaccuracies* (claims that
    contradict the source data) and *unverifiable claims* (claims that
    cannot be confirmed or denied from available data).  Both types
    require attention before publication.

    Data Flow::

        PlatformContent + CuratedProfile
            |
            v
        Fact Checker (Agent 2.9 sub-step)
            |
            v
        FactCheckReport
            |
            +---> is_accurate=True   ---> continue to publication
            +---> is_accurate=False  ---> Content Generator (feedback)

    Attributes:
        mcm_id: MCM identifier linking this report to the product.
            Correlation ID used across all pipeline agents.
        is_accurate: Whether all factual claims in the content are
            verified against the CuratedProfile.  True means no
            inaccuracies or unverifiable claims found.
        inaccuracies: List of factual errors found -- claims that
            directly contradict the CuratedProfile source data.
            Each entry describes the incorrect claim and the correct
            value from the source.  Empty when ``is_accurate`` is True.
        unverifiable_claims: List of claims that cannot be confirmed
            or denied from the available CuratedProfile data.  These
            may be marketing superlatives or comparative claims lacking
            supporting data.

    Examples:
        Accurate content::

            >>> fcr = FactCheckReport(mcm_id="MCM-001", is_accurate=True)
            >>> fcr.inaccuracies
            []

        Content with factual issues::

            >>> fcr = FactCheckReport(
            ...     mcm_id="MCM-001",
            ...     is_accurate=False,
            ...     inaccuracies=["Wrong material listed"],
            ...     unverifiable_claims=["'lightest model' — no data"],
            ... )
            >>> fcr.is_accurate
            False
    """

    # ------------------------------------------------------------------
    # Identity field
    # ------------------------------------------------------------------

    # MCM identifier: correlates this fact-check report with the product.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this fact-check report to the product. "
            "Correlation ID used across all pipeline agents."
        ),
        examples=["MCM-001", "MCM-003-RED-38"],
    )

    # ------------------------------------------------------------------
    # Accuracy result fields
    # ------------------------------------------------------------------

    # Overall accuracy verdict: True if all claims verified, False otherwise.
    is_accurate: bool = Field(
        ...,
        description=(
            "Whether all factual claims are verified against CuratedProfile. "
            "True = no issues; False = inaccuracies or unverifiable claims."
        ),
        examples=[True, False],
    )

    # Factual errors: claims that contradict the CuratedProfile source data.
    # Each entry describes the wrong claim and the correct source value.
    inaccuracies: list[str] = Field(
        default=[],
        description=(
            "Factual errors: claims contradicting CuratedProfile data. "
            "Each entry describes the incorrect claim and correct value. "
            "Empty when is_accurate is True."
        ),
        examples=[
            ["Указан материал 'кожа', в CuratedProfile — 'текстиль'"],
            [],
        ],
    )

    # Claims that cannot be confirmed or denied from available data.
    # Marketing superlatives and comparative claims often fall here.
    unverifiable_claims: list[str] = Field(
        default=[],
        description=(
            "Claims that cannot be confirmed from CuratedProfile data. "
            "Often marketing superlatives or comparative claims lacking "
            "supporting data for verification."
        ),
        examples=[
            ["'самая лёгкая модель' — нет данных для сравнения"],
            [],
        ],
    )


# ---------------------------------------------------------------------------
# PlatformContentSet — aggregated content across all target platforms
# ---------------------------------------------------------------------------


class PlatformContentSet(BaseModel):
    """Aggregated content across all target platforms for one MCM.

    This is the MAIN OUTPUT of the parallel generation pipeline.
    Contains one PlatformContent per target platform, all generated
    from the same CuratedProfile but with different PlatformProfile configs.

    Architecture (v0.3 -- parallel generation from source)::

        +------------------+
        |  CuratedProfile  | (single source of truth)
        +--------+---------+
                 | fan-out
        +--------+--------+----------+
        v        v        v          v
       SM       WB      Ozon     Lamoda  ...
        |        |        |          |
        v        v        v          v
      PlatformContent per platform
        |        |        |          |
        +--------+--------+----------+
                 v
          PlatformContentSet

    Attributes:
        mcm_id: Master catalog model identifier. Links back to the source
            product across all platforms.
        contents: Mapping of platform_id to PlatformContent. Each entry
            holds the fully generated content for that platform.
        quality_scores: Mapping of platform_id to QualityScore. Populated
            after the quality evaluation step runs for each platform.
        target_platforms: Ordered list of platform_ids that should be
            generated. Defines the scope of the fan-out.
        all_passed_quality: Convenience flag indicating whether every
            platform in quality_scores meets the passing threshold.
    """

    mcm_id: str = Field(
        ...,
        description="Master catalog model ID for the product.",
    )
    contents: dict[str, PlatformContent] = Field(
        default={},
        description="platform_id -> PlatformContent mapping.",
    )
    quality_scores: dict[str, QualityScore] = Field(
        default={},
        description="platform_id -> QualityScore mapping.",
    )
    target_platforms: list[str] = Field(
        default=[],
        description="Ordered list of platform_ids to generate content for.",
    )
    all_passed_quality: bool = Field(
        default=False,
        description=(
            "True when every platform in quality_scores meets the "
            "passing threshold (>= 0.7)."
        ),
    )
