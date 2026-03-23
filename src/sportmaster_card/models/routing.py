"""RoutingProfile model -- Router Agent output determining pipeline configuration.

This module defines the routing decision model that the Router Agent produces
after analyzing a ProductInput. The RoutingProfile controls three key aspects
of the downstream processing pipeline:

1. **Flow Type (1P vs 3P):**
   - 1P (First Party) products go through the full 30+ agent pipeline:
     enrichment, content generation for SM site + external VMPs, publication.
   - 3P (Third Party) products take the lightweight path: agents 2.11-2.16
     for validation and minimal content adjustment only.

2. **Processing Profile (depth of processing):**
   - minimal: Basic/Low products -- quick enrichment, template content
   - standard: Mid-tier products -- standard enrichment, decent content
   - premium: High/Premium products -- deep enrichment, polished content
   - complex: Products requiring special handling (multi-sport, technical)

3. **Target Platforms (where content goes):**
   - sm_site: Sportmaster's own website (always included for 1P)
   - wb, ozon, lamoda, etc.: External VMPs (marketplaces) for 1P products
   - 3P products typically target sm_site only

The routing logic from the v0.3 architecture specification:
    - If product type = 3P -> lightweight pipeline (agents 2.11-2.16)
    - If product type = 1P -> full pipeline + parallel VMP generation
    - Processing depth is derived from assortment_type + assortment_level:
        Basic + Low   -> minimal
        any   + Mid   -> standard
        any   + High  -> premium
        any   + Premium -> premium
        complex flag  -> complex

Typical usage::

    from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile

    routing = RoutingProfile(
        mcm_id="MCM-001-BLK-42",
        flow_type=FlowType.FIRST_PARTY,
        processing_profile=ProcessingProfile.STANDARD,
        target_platforms=["sm_site", "wb", "ozon"],
        attribute_class="footwear.running",
    )
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class FlowType(str, Enum):
    """Pipeline flow type: determines 1P (full) vs 3P (lightweight) processing.

    The flow type is the primary routing decision. It splits the product card
    lifecycle into two fundamentally different paths:

    - FIRST_PARTY ("1P"): The product belongs to Sportmaster's own assortment.
      It goes through the complete multi-agent pipeline including enrichment
      (UC1), content generation for all target platforms (UC2), and publication
      to both SM site and external VMPs (UC3).

    - THIRD_PARTY ("3P"): The product comes from an external seller on the
      Sportmaster marketplace. It follows a lightweight validation path using
      only agents 2.11-2.16 (data validation, minimal content checks, and
      publication to SM site only).

    Values:
        FIRST_PARTY: "1P" -- full pipeline processing
        THIRD_PARTY: "3P" -- lightweight validation only

    Examples::

        >>> FlowType.FIRST_PARTY.value
        '1P'
        >>> FlowType.THIRD_PARTY.value
        '3P'
    """

    # 1P = first-party product owned by Sportmaster
    # Full pipeline: enrichment -> content generation -> publication to all VMPs
    FIRST_PARTY = "1P"

    # 3P = third-party seller product on Sportmaster marketplace
    # Lightweight path: validation -> minimal adjustment -> SM site only
    THIRD_PARTY = "3P"


class ProcessingProfile(str, Enum):
    """Processing depth profile controlling agent effort and content quality.

    The processing profile determines how much computational effort and
    agent attention each product receives. This is derived from the product's
    assortment_type and assortment_level fields in the ProductInput:

    Routing matrix (assortment_type x assortment_level -> profile):

        +------------------+-------+---------+---------+---------+
        | assortment_type  | Low   | Mid     | High    | Premium |
        +------------------+-------+---------+---------+---------+
        | Basic            | MIN   | STD     | PREM    | PREM    |
        | Fashion          | STD   | STD     | PREM    | PREM    |
        | Seasonal         | MIN   | STD     | PREM    | PREM    |
        +------------------+-------+---------+---------+---------+
        | Complex products (multi-sport, technical) -> COMPLEX   |
        +--------------------------------------------------------+

    Values:
        MINIMAL:  "minimal"  -- template content, basic enrichment
        STANDARD: "standard" -- balanced enrichment and content quality
        PREMIUM:  "premium"  -- deep enrichment, polished marketing content
        COMPLEX:  "complex"  -- special handling for multi-category products

    Examples::

        >>> ProcessingProfile.MINIMAL.value
        'minimal'
        >>> ProcessingProfile.PREMIUM.value
        'premium'
    """

    # Minimal processing: Basic/Low products get template-driven content
    # with only essential attribute enrichment. Fastest throughput.
    MINIMAL = "minimal"

    # Standard processing: Mid-tier products receive balanced enrichment
    # and decent content quality. The default for most products.
    STANDARD = "standard"

    # Premium processing: High-value products get deep enrichment from
    # multiple sources, polished marketing copy, and detailed SEO.
    PREMIUM = "premium"

    # Complex processing: Products that span multiple categories or have
    # unusual technical requirements. Triggers additional specialist agents.
    COMPLEX = "complex"


class RoutingProfile(BaseModel):
    """Router Agent output: the routing decision for a single product card.

    RoutingProfile is produced by the Router Agent (Agent 1.2) after analyzing
    the ProductInput. It encapsulates all decisions needed to configure the
    downstream processing pipeline for this specific product.

    ASCII Schema Diagram::

        +---------------------------------------------------------------+
        |                     RoutingProfile                            |
        +---------------------------------------------------------------+
        | Field              | Type               | Example             |
        +--------------------+--------------------+---------------------|
        | mcm_id             | str                | "MCM-001-BLK-42"   |
        | flow_type          | FlowType           | FlowType.FIRST_PARTY|
        | processing_profile | ProcessingProfile  | ProcessingProfile.STD|
        | target_platforms   | list[str] (>=1)    | ["sm_site", "wb"]   |
        | attribute_class    | str                | "footwear.running"  |
        +---------------------------------------------------------------+

        Data Flow::

            ProductInput
                |
                v
            Router Agent (1.2)
                |
                v
            RoutingProfile ----+----> UC1 Enrichment Pipeline
                               |       (depth = processing_profile)
                               +----> UC2 Content Pipeline
                               |       (platforms = target_platforms)
                               +----> UC3 Publication Pipeline
                                       (flow = flow_type)

    Attributes:
        mcm_id: The MCM identifier linking this routing decision back to
            the original ProductInput. Used as correlation ID across all
            agents in the pipeline.
        flow_type: Whether this is a 1P (full pipeline) or 3P (lightweight)
            product. Determines which agent set processes the card.
        processing_profile: How deeply the agents should process this
            product. Controls enrichment thoroughness and content quality.
        target_platforms: List of platform identifiers where content will
            be generated and published. Must contain at least one entry.
            Common values: "sm_site", "wb", "ozon", "lamoda", "megamarket".
        attribute_class: Dot-notation product classification used to select
            category-specific agent configurations and prompt templates.
            Example: "footwear.running", "apparel.outerwear.jackets".

    Examples:
        Basic 1P product for SM site only::

            >>> routing = RoutingProfile(
            ...     mcm_id="MCM-001-BLK-42",
            ...     flow_type=FlowType.FIRST_PARTY,
            ...     processing_profile=ProcessingProfile.MINIMAL,
            ...     target_platforms=["sm_site"],
            ...     attribute_class="footwear.running",
            ... )
            >>> routing.flow_type
            <FlowType.FIRST_PARTY: '1P'>

        Premium 1P product targeting multiple VMPs::

            >>> routing = RoutingProfile(
            ...     mcm_id="MCM-003-RED-38",
            ...     flow_type=FlowType.FIRST_PARTY,
            ...     processing_profile=ProcessingProfile.PREMIUM,
            ...     target_platforms=["sm_site", "wb", "ozon", "lamoda"],
            ...     attribute_class="footwear.running",
            ... )
            >>> len(routing.target_platforms)
            4
    """

    # ------------------------------------------------------------------
    # MCM identifier -- links routing decision to the original product
    # ------------------------------------------------------------------

    # The MCM ID is the correlation key that ties this routing decision
    # back to the ProductInput and forward to all downstream agent outputs.
    # Every agent in the pipeline uses this ID for logging and traceability.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this routing decision to the original "
            "ProductInput. Used as correlation ID across all pipeline agents."
        ),
        examples=["MCM-001-BLK-42", "MCM-3P-001"],
    )

    # ------------------------------------------------------------------
    # Flow type -- the primary 1P vs 3P routing decision
    # ------------------------------------------------------------------

    # Flow type is the single most important routing decision.
    # It determines whether the product enters the full 30+ agent pipeline
    # (1P) or the lightweight 6-agent validation path (3P).
    flow_type: FlowType = Field(
        ...,
        description=(
            "Pipeline flow type: FIRST_PARTY (1P) for full processing "
            "or THIRD_PARTY (3P) for lightweight validation only."
        ),
        examples=[FlowType.FIRST_PARTY, FlowType.THIRD_PARTY],
    )

    # ------------------------------------------------------------------
    # Processing profile -- controls agent effort and content depth
    # ------------------------------------------------------------------

    # The processing profile tells each agent how much effort to invest.
    # A MINIMAL product gets template content; a PREMIUM product gets
    # deep research, polished copy, and detailed SEO optimization.
    processing_profile: ProcessingProfile = Field(
        ...,
        description=(
            "Processing depth level determining how thoroughly agents "
            "enrich data and generate content for this product."
        ),
        examples=[ProcessingProfile.STANDARD, ProcessingProfile.PREMIUM],
    )

    # ------------------------------------------------------------------
    # Target platforms -- where content will be published
    # ------------------------------------------------------------------

    # Target platforms is a list of marketplace/site identifiers.
    # For 1P products, this typically includes sm_site plus any external
    # VMPs (wb, ozon, lamoda, megamarket). For 3P products, usually
    # just sm_site. Must contain at least one platform.
    target_platforms: list[str] = Field(
        ...,
        description=(
            "List of platform identifiers for content generation and "
            "publication. Must contain at least one entry. "
            "Common: 'sm_site', 'wb', 'ozon', 'lamoda', 'megamarket'."
        ),
        examples=[["sm_site"], ["sm_site", "wb", "ozon", "lamoda"]],
    )

    # ------------------------------------------------------------------
    # Attribute class -- product classification for agent configuration
    # ------------------------------------------------------------------

    # The attribute class is a dot-notation string that identifies which
    # category-specific prompts, templates, and validation rules to use.
    # Examples: "footwear.running", "apparel.outerwear.jackets".
    # Agents use this to load the correct configuration for the product type.
    attribute_class: str = Field(
        ...,
        description=(
            "Dot-notation product classification for selecting category-specific "
            "agent configurations, prompt templates, and validation rules. "
            "Derived from category + product_group + product_subgroup."
        ),
        examples=["footwear.running", "footwear.casual", "apparel.outerwear.jackets"],
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("target_platforms")
    @classmethod
    def target_platforms_must_not_be_empty(
        cls, value: list[str],
    ) -> list[str]:
        """Ensure at least one target platform is specified.

        A RoutingProfile without any target platforms is meaningless -- there
        would be nowhere to publish the generated content. This validator
        catches the edge case of an empty list being passed.

        Args:
            value: The list of platform identifier strings to validate.

        Returns:
            The validated list, unchanged if it passes.

        Raises:
            ValueError: If the list is empty.
        """
        # Every product must target at least one platform for publication
        if len(value) == 0:
            raise ValueError(
                "target_platforms must contain at least one platform; "
                "a routing decision with no target is invalid"
            )
        # Return the validated list unchanged
        return value
