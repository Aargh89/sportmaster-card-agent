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
