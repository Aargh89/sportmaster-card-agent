"""UC1 Enrichment output models -- full pipeline from validation to curated profile.

This module defines data models for all key agents in the UC1 Enrichment pipeline:

1. **Data Validator (Agent 1.3)** produces a ``ValidationReport`` after checking
   each field in the ProductInput for presence, correctness, and completeness.
   The report lists per-field validation results, identifies missing required
   fields, and computes an overall completeness score.

2. **External Researcher (Agent 1.5)** produces a ``CompetitorBenchmark`` after
   scraping competitor product cards from external marketplaces (Wildberries,
   Ozon, Lamoda, etc.). The benchmark aggregates competitor data to provide
   pricing intelligence, feature analysis, and content inspiration.

3. **Internal Researcher (Agent 1.6)** produces ``InternalInsights`` by mining
   Sportmaster's internal knowledge bases -- UX research, return-reason logs,
   customer reviews, and category-manager notes -- to surface purchase drivers,
   pain points, and customer insights that external sources cannot provide.

4. **Creative Strategist (Agent 1.7 / ГПТК)** produces ``CreativeInsights``
   containing brand-safe metaphors, emotional hooks, and word associations
   that content generators can weave into product card copy. All creative
   output requires explicit GPTK approval before use (``approved=False`` by
   default).

5. **Data Enricher (Agent 1.8)** aggregates all upstream outputs into an
   ``EnrichedProductProfile`` -- the single canonical record that content
   generators consume. It bundles the base product, validation report,
   competitor benchmark, and provenance log into one object.

6. **Data Curator (Agent 1.10)** reviews the enriched profile, resolves
   disputes, and produces the final ``CuratedProfile`` -- a flat, ready-to-use
   data object with all fields needed for content generation across all
   marketplace platforms.

Module-level design decisions:
    - FieldValidation is a fine-grained per-field result; ValidationReport
      aggregates these into a single report per MCM product.
    - CompetitorCard captures one competitor listing; CompetitorBenchmark
      aggregates multiple listings into actionable insights.
    - InternalInsights and CreativeInsights carry list-of-string fields for
      flexible, open-ended agent output; no rigid schema for creative content.
    - EnrichedProductProfile composes upstream models by reference (not copy),
      keeping a single source of truth for each data element.
    - CuratedProfile is intentionally flat (no nested models except
      provenance_log) so that content generators can access fields directly
      without navigating a deep object tree.
    - All collection fields default to empty (not None) for safe iteration.
    - overall_completeness is a float in [0, 1] representing the fraction
      of fields that are present and filled in the source Excel row.

Data flow in the UC1 pipeline::

    ProductInput
        |
        v
    Data Validator (1.3) --------> ValidationReport
        |                              |
        v                              v
    Visual Interpreter (1.4)      (feeds into Data Enricher)
        |
        v
    External Researcher (1.5) ---> CompetitorBenchmark
        |                              |
        v                              v
    Internal Researcher (1.6) ---> InternalInsights
        |                              |
        v                              v
    Creative Strategist (1.7) ---> CreativeInsights
        |                              |
        v                              v
    Data Enricher (1.8) ---------> EnrichedProductProfile
        |                              |
        v                              v
    Data Curator (1.10) ---------> CuratedProfile
                                       |
                                       v
                                  UC2 Content Generators

Typical usage::

    from sportmaster_card.models.enrichment import (
        CompetitorBenchmark,
        CompetitorCard,
        CreativeInsights,
        CuratedProfile,
        EnrichedProductProfile,
        FieldValidation,
        InternalInsights,
        ValidationReport,
    )

    # Build a validation report
    report = ValidationReport(
        mcm_id="MCM-001-BLK-42",
        field_validations=[
            FieldValidation(field_name="brand", is_present=True, is_valid=True),
        ],
        missing_required=[],
        overall_completeness=1.0,
        is_valid=True,
    )

    # Build a competitor benchmark
    benchmark = CompetitorBenchmark(
        mcm_id="MCM-001-BLK-42",
        competitors=[
            CompetitorCard(platform="wb", product_name="Nike Pegasus 41"),
        ],
        benchmark_summary="Competitor priced at 12990 RUB.",
        average_price=12990.0,
    )
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenanceLog


class FieldValidation(BaseModel):
    """Result of validating a single field from the ProductInput Excel row.

    Each field in the MCM template is checked for two properties:
    - **Presence**: Was the cell filled at all in the Excel row?
    - **Validity**: Does the value pass basic format/content checks?

    A field can be present but invalid (e.g., a description that is too short),
    or absent and therefore automatically invalid.

    ASCII Schema::

        +---------------------------------------------------+
        |              FieldValidation                      |
        +---------------------------------------------------+
        | field_name  | str           | "brand"             |
        | is_present  | bool          | True                |
        | is_valid    | bool          | True                |
        | issue       | str | None    | None (no problem)   |
        +---------------------------------------------------+

        Example for a missing required field::

            FieldValidation(
                field_name="color",
                is_present=False,      # <-- cell was empty
                is_valid=False,        # <-- missing = invalid
                issue="Required field missing",
            )

    Attributes:
        field_name: Name of the field that was checked, matching the
            ProductInput attribute name (e.g., "brand", "description").
        is_present: Whether the field had a non-empty value in the
            source Excel row. False means the cell was blank or missing.
        is_valid: Whether the field's value passes basic validation rules.
            A missing field is always invalid. A present field may still
            be invalid if the value doesn't meet format requirements.
        issue: Human-readable description of the validation problem, if any.
            None when the field is present and valid. Examples:
            "Required field missing", "Description too short (< 10 chars)".

    Examples:
        Valid field with no issues::

            >>> v = FieldValidation(
            ...     field_name="brand", is_present=True, is_valid=True
            ... )
            >>> v.issue is None
            True

        Invalid field with an issue description::

            >>> v = FieldValidation(
            ...     field_name="description",
            ...     is_present=True,
            ...     is_valid=False,
            ...     issue="Description too short (< 10 chars)",
            ... )
            >>> v.issue
            'Description too short (< 10 chars)'
    """

    # The field name must match a ProductInput attribute name exactly.
    # This enables downstream agents to look up which fields need attention.
    field_name: str = Field(
        ...,
        description=(
            "Name of the ProductInput field that was validated. "
            "Must match the attribute name exactly (e.g., 'brand', 'description')."
        ),
        examples=["brand", "description", "color", "technologies"],
    )

    # Presence check: was there any value in the Excel cell?
    # An empty string or whitespace-only value counts as not present.
    is_present: bool = Field(
        ...,
        description=(
            "Whether the field contained a non-empty value in the source "
            "Excel row. False means the cell was blank, empty, or whitespace-only."
        ),
    )

    # Validity check: does the value meet basic quality requirements?
    # A field that is not present is automatically not valid.
    is_valid: bool = Field(
        ...,
        description=(
            "Whether the field value passes basic validation rules. "
            "A missing field (is_present=False) is always invalid. "
            "A present field may be invalid if it fails format checks."
        ),
    )

    # Human-readable issue description, only populated when something is wrong.
    # Downstream agents and human reviewers use this to understand what to fix.
    issue: Optional[str] = Field(
        default=None,
        description=(
            "Human-readable description of the validation issue, if any. "
            "None when the field passes all checks. Examples: "
            "'Required field missing', 'Description too short (< 10 chars)'."
        ),
        examples=["Required field missing", "Description too short (< 10 chars)"],
    )


class ValidationReport(BaseModel):
    """Data Validator output: comprehensive validation results for one MCM product.

    The Data Validator agent (1.3) checks every field of a ProductInput against
    the requirements defined by the Sportmaster MCM template. The ValidationReport
    aggregates per-field results into an actionable summary that tells downstream
    agents which data is missing, which is invalid, and how complete the input is.

    ASCII Schema::

        +---------------------------------------------------------------+
        |                    ValidationReport                           |
        +---------------------------------------------------------------+
        | mcm_id               | str                | "MCM-001-BLK-42" |
        | field_validations    | list[FieldValid.]  | [v1, v2, v3]     |
        | missing_required     | list[str]          | ["color"]         |
        | overall_completeness | float (0-1)        | 0.67              |
        | is_valid             | bool               | False             |
        | notes                | list[str]          | ["Color missing"] |
        +---------------------------------------------------------------+

        Downstream usage::

            ValidationReport
                |
                +--> Data Enricher: knows which fields to fill
                |
                +--> Data Curator: knows which validations passed
                |
                +--> Quality Controller: checks improvement over baseline

    Attributes:
        mcm_id: MCM identifier linking this report to the original product.
            Used as the correlation key across all pipeline stages.
        field_validations: List of per-field validation results. Each entry
            describes whether one ProductInput field was present and valid.
            Order matches the ProductInput field declaration order.
        missing_required: Names of required fields that were not present in
            the Excel row. These are the fields that MUST be filled by the
            enrichment pipeline before content generation can proceed.
        overall_completeness: Fraction of all checked fields that are present,
            expressed as a float in [0.0, 1.0]. Calculated as:
            ``count(is_present=True) / len(field_validations)``.
            A value of 1.0 means every checked field had a value.
        is_valid: True if no critical validation issues were found. A report
            is invalid if any required field is missing or any field has a
            critical validation failure. Used as a gate for pipeline progression.
        notes: Human-readable notes summarizing key findings for human reviewers
            or logging. Defaults to an empty list when there are no special notes.

    Examples:
        Fully valid product (all fields present)::

            >>> report = ValidationReport(
            ...     mcm_id="MCM-001-BLK-42",
            ...     field_validations=[
            ...         FieldValidation(
            ...             field_name="brand", is_present=True, is_valid=True
            ...         ),
            ...     ],
            ...     missing_required=[],
            ...     overall_completeness=1.0,
            ...     is_valid=True,
            ... )
            >>> report.is_valid
            True

        Product with missing required fields::

            >>> report = ValidationReport(
            ...     mcm_id="MCM-002-WHT-40",
            ...     field_validations=[],
            ...     missing_required=["brand", "category"],
            ...     overall_completeness=0.0,
            ...     is_valid=False,
            ...     notes=["2 required fields missing"],
            ... )
            >>> len(report.missing_required)
            2
    """

    # ------------------------------------------------------------------
    # MCM identifier -- links validation results to the source product
    # ------------------------------------------------------------------

    # Every agent output in the pipeline carries the mcm_id for traceability.
    # This connects the validation report back to the ProductInput it checked.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this validation report to the original "
            "ProductInput. Used as the correlation key across all pipeline agents."
        ),
        examples=["MCM-001-BLK-42", "MCM-002-WHT-40"],
    )

    # ------------------------------------------------------------------
    # Per-field validation results
    # ------------------------------------------------------------------

    # Each FieldValidation entry corresponds to one field that was checked.
    # The list provides a complete, ordered audit trail of what was validated.
    field_validations: list[FieldValidation] = Field(
        ...,
        description=(
            "List of per-field validation results. Each entry describes "
            "whether one ProductInput field was present and passed validation. "
            "Provides a complete audit trail for downstream agents."
        ),
    )

    # ------------------------------------------------------------------
    # Missing required fields -- the most critical finding
    # ------------------------------------------------------------------

    # This is the most actionable part of the report: which required fields
    # must be filled before the product can proceed through the pipeline.
    # The Data Enricher uses this list to prioritize its work.
    missing_required: list[str] = Field(
        ...,
        description=(
            "Names of required fields that were not present in the Excel row. "
            "These fields MUST be filled by enrichment agents before content "
            "generation can proceed. Empty list means all required fields present."
        ),
        examples=[[], ["color", "description"], ["brand", "category", "product_name"]],
    )

    # ------------------------------------------------------------------
    # Overall completeness score
    # ------------------------------------------------------------------

    # A single number summarizing how complete the input data is.
    # Ranges from 0.0 (no fields filled) to 1.0 (all fields filled).
    # Used for prioritization: products with lower completeness need more work.
    overall_completeness: float = Field(
        ...,
        description=(
            "Fraction of checked fields that are present, as a float in [0.0, 1.0]. "
            "Calculated as count(is_present=True) / total_fields_checked. "
            "A value of 1.0 means every field had a value in the Excel row."
        ),
        examples=[0.0, 0.33, 0.67, 1.0],
    )

    # ------------------------------------------------------------------
    # Overall validity flag
    # ------------------------------------------------------------------

    # A quick boolean gate: can this product proceed as-is, or does it need
    # enrichment before content generation? False triggers mandatory enrichment.
    is_valid: bool = Field(
        ...,
        description=(
            "True if no critical validation issues were found. False if any "
            "required field is missing or any field has a critical failure. "
            "Used as a gate to determine if enrichment is mandatory."
        ),
    )

    # ------------------------------------------------------------------
    # Human-readable notes
    # ------------------------------------------------------------------

    # Free-text notes for human reviewers and logging. These provide context
    # beyond what the structured fields capture. Defaults to empty list.
    notes: list[str] = Field(
        default=[],
        description=(
            "Human-readable notes summarizing key findings for reviewers. "
            "May include warnings, suggestions, or context about validation. "
            "Defaults to an empty list when there are no special observations."
        ),
        examples=[
            ["Description needs expansion", "Color field is missing"],
            ["All fields valid -- product ready for content generation"],
        ],
    )


class CompetitorCard(BaseModel):
    """Data about a single competitor product listing from an external marketplace.

    The External Researcher agent (1.5) scrapes competitor product pages from
    marketplaces like Wildberries (wb), Ozon, Lamoda, and Megamarket. Each
    CompetitorCard captures the key data points from one competitor listing
    that are useful for benchmarking and content inspiration.

    ASCII Schema::

        +---------------------------------------------------------------+
        |                     CompetitorCard                            |
        +---------------------------------------------------------------+
        | platform      | str           | "wb"                          |
        | product_name  | str           | "Nike Air Zoom Pegasus 41"    |
        | description   | str | None    | "Легкие беговые кроссовки"    |
        | price         | float | None  | 12990.0                       |
        | rating        | float | None  | 4.7                           |
        | key_features  | list[str]     | ["Air Zoom", "легкие"]        |
        | url           | str | None    | "https://wb.ru/catalog/123"   |
        +---------------------------------------------------------------+

        Data source mapping::

            Wildberries page
                |
                +---> product_name  = page title
                +---> description   = product description block
                +---> price         = current selling price (RUB)
                +---> rating        = star rating (1-5 scale)
                +---> key_features  = extracted from bullet points
                +---> url           = page URL for reference

    Attributes:
        platform: Marketplace identifier where this competitor listing was found.
            Uses short codes: "wb" (Wildberries), "ozon" (Ozon), "lamoda" (Lamoda),
            "megamarket" (SberMegaMarket), "detmir" (Детский мир).
        product_name: Product title as displayed on the marketplace page.
            May differ from the official brand name due to seller optimization.
        description: Product description text from the listing, if available.
            None if the listing has no description or it couldn't be extracted.
        price: Current selling price in Russian Rubles (RUB). None if the
            price couldn't be determined (out of stock, price on request).
        rating: Customer rating on a 1-5 star scale. None if the product
            has no ratings yet or the rating couldn't be extracted.
        key_features: List of notable product features extracted from the
            listing. Used for feature gap analysis and content inspiration.
            Defaults to an empty list if no features could be identified.
        url: Direct URL to the competitor product page for manual verification.
            None if the URL is not available or the data came from an API.

    Examples:
        Full competitor listing from Wildberries::

            >>> card = CompetitorCard(
            ...     platform="wb",
            ...     product_name="Nike Air Zoom Pegasus 41",
            ...     description="Легкие беговые кроссовки",
            ...     price=12990.0,
            ...     rating=4.7,
            ...     key_features=["Air Zoom", "легкие", "дышащие"],
            ...     url="https://www.wildberries.ru/catalog/12345",
            ... )
            >>> card.platform
            'wb'

        Minimal listing (name only)::

            >>> card = CompetitorCard(platform="ozon", product_name="Nike Pegasus")
            >>> card.price is None
            True
    """

    # ------------------------------------------------------------------
    # Platform identifier -- which marketplace this listing came from
    # ------------------------------------------------------------------

    # Short marketplace codes are used throughout the pipeline for consistency.
    # The same codes appear in RoutingProfile.target_platforms.
    platform: str = Field(
        ...,
        description=(
            "Marketplace identifier where this competitor listing was found. "
            "Uses short codes: 'wb', 'ozon', 'lamoda', 'megamarket', 'detmir'."
        ),
        examples=["wb", "ozon", "lamoda", "megamarket"],
    )

    # ------------------------------------------------------------------
    # Product title from the marketplace page
    # ------------------------------------------------------------------

    # The product name as sellers display it on the marketplace.
    # Often includes SEO keywords that differ from the official brand name.
    product_name: str = Field(
        ...,
        description=(
            "Product title as displayed on the marketplace listing page. "
            "May include SEO keywords added by the seller beyond the brand name."
        ),
        examples=["Nike Air Zoom Pegasus 41", "Кроссовки Nike Pegasus беговые мужские"],
    )

    # ------------------------------------------------------------------
    # Optional fields -- may not be available for all listings
    # ------------------------------------------------------------------

    # Product description text, if the listing includes one.
    # Many marketplace listings have minimal or no descriptions.
    description: Optional[str] = Field(
        default=None,
        description=(
            "Product description text from the marketplace listing. "
            "None if the listing lacks a description or extraction failed."
        ),
    )

    # Current price in RUB. None for out-of-stock or price-on-request items.
    # Used for competitive pricing analysis in the benchmark summary.
    price: Optional[float] = Field(
        default=None,
        description=(
            "Current selling price in Russian Rubles (RUB). "
            "None if the product is out of stock or price is not available."
        ),
        examples=[12990.0, 8499.0, 15990.0],
    )

    # Customer star rating (1-5 scale). None if no ratings exist yet.
    # Helps assess product quality perception in the market.
    rating: Optional[float] = Field(
        default=None,
        description=(
            "Customer rating on a 1.0-5.0 star scale from the marketplace. "
            "None if the product has no ratings or extraction failed."
        ),
        examples=[4.7, 4.2, 3.9],
    )

    # Key features extracted from bullet points or description.
    # Used for feature gap analysis: which features do competitors highlight
    # that we might be missing in our product card?
    key_features: list[str] = Field(
        default=[],
        description=(
            "Notable product features extracted from the listing. "
            "Used for feature gap analysis and content inspiration. "
            "Defaults to empty list if no features could be identified."
        ),
        examples=[["Air Zoom", "легкие", "дышащие"], ["Boost", "Primeknit"]],
    )

    # Direct URL to the competitor page for manual verification.
    # Stored for audit trail and human review purposes.
    url: Optional[str] = Field(
        default=None,
        description=(
            "Direct URL to the competitor product page for manual verification. "
            "None if the URL is unavailable or data came from an API source."
        ),
        examples=["https://www.wildberries.ru/catalog/12345"],
    )


class CompetitorBenchmark(BaseModel):
    """External Researcher output: competitor intelligence for one MCM product.

    The External Researcher agent (1.5) gathers competitor product listings from
    external marketplaces, analyzes them, and produces a CompetitorBenchmark that
    the Data Enricher uses to fill gaps and improve product card quality.

    The benchmark answers three questions for the Data Enricher:
    1. **Price positioning**: How does our price compare to competitors?
    2. **Feature coverage**: Which features do competitors highlight that we miss?
    3. **Content quality**: What content patterns work well on each marketplace?

    ASCII Schema::

        +---------------------------------------------------------------+
        |                   CompetitorBenchmark                         |
        +---------------------------------------------------------------+
        | mcm_id            | str               | "MCM-001-BLK-42"     |
        | competitors       | list[Competitor.]  | [card1, card2]       |
        | benchmark_summary | str               | "Avg price 13K RUB"  |
        | average_price     | float | None      | 13240.0              |
        | common_features   | list[str]         | ["Air Zoom"]         |
        +---------------------------------------------------------------+

        Data flow::

            External Researcher (1.5)
                |
                +--> scrapes WB, Ozon, Lamoda, Megamarket
                |
                +--> builds CompetitorCard for each listing
                |
                +--> aggregates into CompetitorBenchmark
                        |
                        v
                    Data Enricher (1.8)
                        uses benchmark for:
                        - price positioning
                        - feature gap analysis
                        - content inspiration

    Attributes:
        mcm_id: MCM identifier linking this benchmark to the original product.
            Used as the correlation key across all pipeline agents.
        competitors: List of competitor product cards found across marketplaces.
            May be empty if no comparable products were found (niche product).
            Defaults to an empty list for safe iteration.
        benchmark_summary: Human-readable summary of key competitive insights.
            Written by the External Researcher after analyzing all competitor
            listings. Defaults to empty string when no competitors were found.
        average_price: Mean price across all competitor listings that had a
            price available, in Russian Rubles. None if no prices were found
            (all competitors out of stock or no competitors at all).
        common_features: Features that appear across multiple competitor listings.
            These represent market-standard attributes that our product card
            should also highlight. Defaults to an empty list.

    Examples:
        Benchmark with competitor data::

            >>> benchmark = CompetitorBenchmark(
            ...     mcm_id="MCM-001-BLK-42",
            ...     competitors=[
            ...         CompetitorCard(platform="wb", product_name="Nike Pegasus"),
            ...     ],
            ...     benchmark_summary="One competitor found at 12990 RUB.",
            ...     average_price=12990.0,
            ...     common_features=["Air Zoom"],
            ... )
            >>> len(benchmark.competitors)
            1

        No competitors found (niche or new product)::

            >>> benchmark = CompetitorBenchmark(mcm_id="MCM-RARE-001")
            >>> benchmark.competitors
            []
            >>> benchmark.average_price is None
            True
    """

    # ------------------------------------------------------------------
    # MCM identifier -- links benchmark to the source product
    # ------------------------------------------------------------------

    # Correlation key tying this competitive analysis back to the product.
    # The Data Enricher joins on mcm_id to merge benchmark data with
    # other enrichment sources (validation, visual, internal research).
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking this competitor benchmark to the original "
            "ProductInput. Used as the correlation key across all pipeline agents."
        ),
        examples=["MCM-001-BLK-42", "MCM-RARE-001"],
    )

    # ------------------------------------------------------------------
    # Competitor listings -- raw data from external marketplaces
    # ------------------------------------------------------------------

    # A list of competitor product cards scraped from WB, Ozon, Lamoda, etc.
    # May be empty for niche products where no comparable listings exist.
    # Defaults to empty list so downstream code can safely iterate.
    competitors: list[CompetitorCard] = Field(
        default=[],
        description=(
            "List of competitor product cards found on external marketplaces. "
            "Empty if no comparable products were found (niche or new product). "
            "Defaults to empty list for safe iteration in downstream agents."
        ),
    )

    # ------------------------------------------------------------------
    # Benchmark summary -- key insights in natural language
    # ------------------------------------------------------------------

    # A concise text summary of competitive findings written by the agent.
    # Used by the Data Enricher and human reviewers for quick understanding.
    benchmark_summary: str = Field(
        default="",
        description=(
            "Human-readable summary of key competitive insights from the "
            "External Researcher. Covers pricing, feature gaps, and content "
            "patterns. Empty string when no competitors were found."
        ),
        examples=[
            "Средняя цена конкурентов ~13240 руб. Ключевые фичи: Air Zoom.",
            "",
        ],
    )

    # ------------------------------------------------------------------
    # Aggregated metrics
    # ------------------------------------------------------------------

    # Mean price across all competitor listings with available prices.
    # None when no prices could be extracted or no competitors were found.
    average_price: Optional[float] = Field(
        default=None,
        description=(
            "Mean price across competitor listings with available prices, "
            "in Russian Rubles. None if no prices were found or no competitors "
            "exist. Used for competitive price positioning analysis."
        ),
        examples=[13240.0, 8990.0, None],
    )

    # Features that appeared in multiple competitor listings.
    # These represent "table stakes" features that the market expects.
    # Our product card should highlight these if applicable.
    common_features: list[str] = Field(
        default=[],
        description=(
            "Features appearing across multiple competitor listings, representing "
            "market-standard attributes. Our product card should highlight these "
            "if applicable. Empty list if no common features were identified."
        ),
        examples=[["Air Zoom", "амортизация"], ["Boost", "Primeknit", "Continental"]],
    )


class InternalInsights(BaseModel):
    """Internal Researcher output: insights mined from Sportmaster knowledge bases.

    The Internal Researcher agent (1.6) analyses Sportmaster's proprietary data
    sources -- UX research reports, product-return logs, customer reviews from
    sportmaster.ru, and category-manager notes -- to surface actionable insights
    that are invisible to external research.

    These insights fill a critical gap: competitor benchmarks tell us what the
    *market* says, but InternalInsights tells us what *our customers* actually
    experience, complain about, and value when buying this type of product.

    ASCII Schema::

        +---------------------------------------------------------------+
        |                    InternalInsights                           |
        +---------------------------------------------------------------+
        | Field             | Type        | Example                     |
        +-------------------+-------------+-----------------------------|
        | mcm_id            | str         | "MCM-001"                   |
        | insights          | list[str]   | ["Покупатели ценят..."]     |
        | pain_points       | list[str]   | ["Узкая колодка"]           |
        | purchase_drivers  | list[str]   | ["Технология бренда"]       |
        | source_documents  | list[str]   | ["UX Report Q1 2026"]       |
        +---------------------------------------------------------------+

        Data sources mined by the Internal Researcher::

            Sportmaster Internal Systems
                |
                +---> UX research reports  --> insights, pain_points
                +---> Return-reason logs   --> pain_points
                +---> Customer reviews     --> insights, purchase_drivers
                +---> Category-mgr notes   --> purchase_drivers
                |
                v
            InternalInsights(mcm_id="MCM-...")
                |
                v
            Data Enricher (1.8) uses these to fill description gaps

    Attributes:
        mcm_id: MCM identifier linking these insights to the product being
            enriched. Serves as the correlation key across all pipeline agents.
        insights: General customer insights extracted from internal sources.
            Free-form observations about how customers perceive, use, or
            evaluate this type of product. Each string is one insight.
        pain_points: Known customer complaints and frustrations related to
            this product type. Extracted from return reasons, negative reviews,
            and UX research findings. Content generators use these to craft
            preemptive reassurance copy.
        purchase_drivers: Factors that motivate customers to buy this product
            type. Extracted from positive reviews, purchase-funnel analytics,
            and category-manager domain knowledge.
        source_documents: List of internal document identifiers or titles that
            were consulted to produce these insights. Provides an audit trail
            for the Data Curator to verify claims.

    Examples:
        Insights from UX research::

            >>> ins = InternalInsights(
            ...     mcm_id="MCM-001",
            ...     insights=["Покупатели ценят амортизацию"],
            ...     pain_points=["Узкая колодка"],
            ...     purchase_drivers=["Технология бренда"],
            ...     source_documents=["UX Report Q1 2026"],
            ... )
            >>> len(ins.insights)
            1

        Empty insights (no internal data found)::

            >>> ins = InternalInsights(mcm_id="MCM-NEW-001")
            >>> ins.insights
            []
    """

    # ------------------------------------------------------------------
    # MCM identifier -- links insights to the product being enriched
    # ------------------------------------------------------------------

    # Correlation key tying internal research back to the product.
    # The Data Enricher joins on mcm_id to merge internal insights
    # with competitor benchmarks and validation results.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking these internal insights to the product "
            "being enriched. Correlation key across all pipeline agents."
        ),
        examples=["MCM-001", "MCM-001-BLK-42"],
    )

    # ------------------------------------------------------------------
    # Insight categories -- structured output from internal research
    # ------------------------------------------------------------------

    # General insights: observations about customer perception and usage.
    # Each entry is a self-contained insight sentence in Russian.
    insights: list[str] = Field(
        default=[],
        description=(
            "General customer insights from internal sources: how customers "
            "perceive, use, or evaluate this product type. Each string is "
            "one self-contained insight in Russian."
        ),
        examples=[
            ["Покупатели ценят амортизацию", "Часто покупают для марафонов"],
        ],
    )

    # Pain points: specific complaints and frustrations.
    # Content generators use these to write preemptive reassurance copy
    # (e.g., "Обновлённая колодка стала шире на 3 мм").
    pain_points: list[str] = Field(
        default=[],
        description=(
            "Known customer complaints and frustrations for this product type. "
            "Extracted from returns, negative reviews, and UX research. "
            "Used by content generators for preemptive reassurance copy."
        ),
        examples=[["Узкая колодка", "Быстрый износ подошвы"]],
    )

    # Purchase drivers: what makes customers click "buy".
    # Used to prioritize which features to highlight in the product card.
    purchase_drivers: list[str] = Field(
        default=[],
        description=(
            "Factors motivating purchase of this product type. Extracted from "
            "positive reviews, purchase analytics, and category-manager notes. "
            "Guides content generators on which features to emphasize."
        ),
        examples=[["Технология бренда", "Соотношение цена/качество"]],
    )

    # Source documents: audit trail for the Data Curator.
    # Each entry identifies a document that was consulted.
    source_documents: list[str] = Field(
        default=[],
        description=(
            "Internal document identifiers or titles consulted to produce "
            "these insights. Provides an audit trail for the Data Curator "
            "to verify claims and trace data lineage."
        ),
        examples=[["UX Report Q1 2026", "Returns Analysis FW25"]],
    )


class CreativeInsights(BaseModel):
    """Creative Strategist output: brand-safe metaphors, hooks, and associations.

    The Creative Strategist agent (1.7 / GPTK -- Группа Подготовки Текстового
    Контента) generates creative language elements that content generators can
    weave into product card copy. Unlike factual data (InternalInsights,
    CompetitorBenchmark), creative output is subjective and requires explicit
    human approval before use in published content.

    The ``approved`` flag defaults to False. Only after a GPTK team member
    reviews and approves the creative output does it become usable by
    downstream content generation agents.

    ASCII Schema::

        +---------------------------------------------------------------+
        |                    CreativeInsights                           |
        +---------------------------------------------------------------+
        | Field           | Type        | Example                       |
        +-----------------+-------------+-------------------------------|
        | mcm_id          | str         | "MCM-001"                     |
        | metaphors       | list[str]   | ["Облако для ваших ног"]      |
        | associations    | list[str]   | ["лёгкость", "свобода"]       |
        | emotional_hooks | list[str]   | ["почувствуйте разницу"]      |
        | approved        | bool        | False (until ГПТК approves)   |
        +---------------------------------------------------------------+

        Approval workflow::

            Creative Strategist (1.7)
                |
                v
            CreativeInsights(approved=False)
                |
                v
            ГПТК Human Review
                |
                +--> approved=True  --> Content Generators may use
                |
                +--> approved=False --> Content Generators must skip

    Attributes:
        mcm_id: MCM identifier linking creative insights to the product.
            Correlation key across the pipeline.
        metaphors: Brand-safe metaphors and figurative language suggested
            for this product. Each string is one metaphor or simile in
            Russian. Must be reviewed for brand safety before use.
        associations: Word associations and conceptual links that evoke
            the desired emotional response. Used to enrich product
            descriptions with sensory and lifestyle language.
        emotional_hooks: Short phrases designed to trigger an emotional
            buying response. Used in headlines, bullet points, and call-
            to-action elements of the product card.
        approved: Whether GPTK has approved this creative output for use
            in published content. Defaults to False. Content generators
            MUST check this flag and skip unapproved creative material.

    Examples:
        Pending approval (default state)::

            >>> ci = CreativeInsights(
            ...     mcm_id="MCM-001",
            ...     metaphors=["Облако для ваших ног"],
            ...     associations=["лёгкость", "свобода"],
            ...     emotional_hooks=["почувствуйте разницу"],
            ... )
            >>> ci.approved
            False

        After GPTK approval::

            >>> ci = CreativeInsights(
            ...     mcm_id="MCM-001",
            ...     metaphors=["Облако для ваших ног"],
            ...     approved=True,
            ... )
            >>> ci.approved
            True
    """

    # ------------------------------------------------------------------
    # MCM identifier -- links creative output to the product
    # ------------------------------------------------------------------

    # Every creative output is tied to a specific product via mcm_id.
    # The Data Enricher and Content Generators join on this key.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier linking creative insights to the product. "
            "Correlation key across all pipeline agents."
        ),
        examples=["MCM-001", "MCM-001-BLK-42"],
    )

    # ------------------------------------------------------------------
    # Creative language elements
    # ------------------------------------------------------------------

    # Metaphors: figurative language for enriching product descriptions.
    # Each entry is one metaphor or simile in Russian.
    metaphors: list[str] = Field(
        default=[],
        description=(
            "Brand-safe metaphors and figurative language for this product. "
            "Each string is one metaphor or simile in Russian. Must be "
            "reviewed by ГПТК for brand safety before use in content."
        ),
        examples=[["Облако для ваших ног", "Второе дыхание для ваших стоп"]],
    )

    # Associations: evocative words linked to the product experience.
    # Content generators sprinkle these into descriptions for richness.
    associations: list[str] = Field(
        default=[],
        description=(
            "Word associations evoking the desired emotional response. "
            "Used to enrich product descriptions with sensory and lifestyle "
            "language. Each string is one word or short phrase in Russian."
        ),
        examples=[["лёгкость", "свобода", "энергия"]],
    )

    # Emotional hooks: short, punchy phrases for headlines and CTAs.
    # Designed to trigger an emotional buying impulse.
    emotional_hooks: list[str] = Field(
        default=[],
        description=(
            "Short phrases designed to trigger an emotional buying response. "
            "Used in headlines, bullet points, and call-to-action elements. "
            "Each string is one hook phrase in Russian."
        ),
        examples=[["почувствуйте разницу", "бегите дальше, чем вчера"]],
    )

    # ------------------------------------------------------------------
    # Approval gate -- GPTK must approve before content use
    # ------------------------------------------------------------------

    # Defaults to False. Content generators MUST check this flag.
    # Only after a human GPTK reviewer sets approved=True can these
    # creative elements appear in published product card content.
    approved: bool = Field(
        default=False,
        description=(
            "Whether ГПТК (Creative Content Team) has approved this output "
            "for use in published content. Defaults to False. Content "
            "generators MUST skip unapproved creative material."
        ),
    )


class EnrichedProductProfile(BaseModel):
    """Data Enricher output: aggregated enrichment data for one MCM product.

    The Data Enricher agent (1.8) is the convergence point of the UC1 pipeline.
    It collects outputs from all upstream agents -- the original ProductInput,
    the ValidationReport, the CompetitorBenchmark, and the DataProvenanceLog --
    and bundles them into a single EnrichedProductProfile.

    This profile is the canonical input for the Data Curator (1.10), which
    reviews it, resolves disputes, and produces the final CuratedProfile.

    ASCII Schema::

        +---------------------------------------------------------------+
        |                 EnrichedProductProfile                        |
        +---------------------------------------------------------------+
        | Field                | Type                  | Source Agent    |
        +----------------------+-----------------------+----------------|
        | mcm_id               | str                   | (identity)     |
        | base_product         | ProductInput          | Excel import   |
        | validation_report    | ValidationReport      | Agent 1.3      |
        | competitor_benchmark | CompetitorBenchmark   | Agent 1.5      |
        | internal_insights    | InternalInsights|None | Agent 1.6      |
        | creative_insights    | CreativeInsights|None | Agent 1.7      |
        | provenance_log       | DataProvenanceLog     | All agents     |
        +---------------------------------------------------------------+

        Aggregation flow::

            ProductInput --------+
            ValidationReport ----+
            CompetitorBenchmark -+----> EnrichedProductProfile
            InternalInsights ----+           |
            CreativeInsights ----+           v
            DataProvenanceLog ---+     Data Curator (1.10)
                                             |
                                             v
                                       CuratedProfile

    Attributes:
        mcm_id: MCM identifier for this enriched profile. Must match the
            mcm_id of all nested models for data consistency.
        base_product: The original ProductInput parsed from the Excel row.
            Carries all raw fields as received from the supplier.
        validation_report: Data Validator output describing field completeness
            and validity of the base product.
        competitor_benchmark: External Researcher output with competitive
            intelligence from marketplace scraping.
        internal_insights: Internal Researcher output with customer insights
            from Sportmaster knowledge bases. None if internal research was
            not performed (e.g., new category with no historical data).
        creative_insights: Creative Strategist output with metaphors and
            emotional hooks. None if creative generation was skipped.
        provenance_log: Aggregated provenance log tracking the origin of
            every attribute value across all enrichment agents.

    Examples:
        Full enrichment profile::

            >>> profile = EnrichedProductProfile(
            ...     mcm_id="MCM-001",
            ...     base_product=ProductInput(
            ...         mcm_id="MCM-001", brand="Nike", category="Обувь",
            ...         product_group="Кроссовки", product_subgroup="Беговые",
            ...         product_name="Pegasus",
            ...     ),
            ...     validation_report=ValidationReport(
            ...         mcm_id="MCM-001", field_validations=[],
            ...         missing_required=[], overall_completeness=0.9,
            ...         is_valid=True,
            ...     ),
            ...     competitor_benchmark=CompetitorBenchmark(mcm_id="MCM-001"),
            ...     provenance_log=DataProvenanceLog(mcm_id="MCM-001"),
            ... )
            >>> profile.base_product.brand
            'Nike'
    """

    # ------------------------------------------------------------------
    # MCM identifier -- must match all nested models
    # ------------------------------------------------------------------

    # The mcm_id here acts as the top-level correlation key. All nested
    # models (base_product, validation_report, etc.) should carry the
    # same mcm_id for data integrity.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier for this enriched profile. Must match the "
            "mcm_id of all nested models for data consistency."
        ),
        examples=["MCM-001", "MCM-001-BLK-42"],
    )

    # ------------------------------------------------------------------
    # Upstream agent outputs -- composed by reference
    # ------------------------------------------------------------------

    # The original product data from the Excel import.
    # This is the raw input that all enrichment agents worked on.
    base_product: ProductInput = Field(
        ...,
        description=(
            "Original ProductInput from the Excel row. Carries all raw "
            "fields as received from the supplier before enrichment."
        ),
    )

    # Validation results from the Data Validator (Agent 1.3).
    # Tells the Data Curator which fields passed and which need attention.
    validation_report: ValidationReport = Field(
        ...,
        description=(
            "Data Validator output: field completeness and validity checks. "
            "Used by the Data Curator to assess data quality."
        ),
    )

    # Competitive intelligence from the External Researcher (Agent 1.5).
    # Provides market context for pricing and feature gap analysis.
    competitor_benchmark: CompetitorBenchmark = Field(
        ...,
        description=(
            "External Researcher output: competitor pricing, features, and "
            "content patterns from marketplace scraping."
        ),
    )

    # Internal insights from the Internal Researcher (Agent 1.6).
    # None when no internal data is available for this product type.
    internal_insights: Optional[InternalInsights] = Field(
        default=None,
        description=(
            "Internal Researcher output: customer insights from Sportmaster "
            "knowledge bases. None if internal research was not performed."
        ),
    )

    # Creative language elements from the Creative Strategist (Agent 1.7).
    # None when creative generation was skipped or not yet run.
    creative_insights: Optional[CreativeInsights] = Field(
        default=None,
        description=(
            "Creative Strategist output: metaphors, associations, and "
            "emotional hooks. None if creative generation was skipped."
        ),
    )

    # Aggregated provenance log covering all attribute extractions.
    # The Data Curator reviews this to resolve disputed values.
    provenance_log: DataProvenanceLog = Field(
        ...,
        description=(
            "Aggregated provenance log tracking the origin of every "
            "attribute value across all enrichment agents."
        ),
    )


class CuratedProfile(BaseModel):
    """Data Curator output: final flat profile ready for content generation.

    The Data Curator agent (1.10) reviews the EnrichedProductProfile, resolves
    any disputed attribute values, and produces a CuratedProfile -- a flat,
    ready-to-use data object containing all fields that content generators
    need to create product card copy for every target marketplace.

    The CuratedProfile is intentionally denormalized: instead of nesting
    ProductInput, ValidationReport, etc., it extracts the final resolved
    values into top-level fields. This design lets content generators access
    any field with a single attribute lookup (``cp.brand``) instead of
    navigating a deep object tree (``profile.base_product.brand``).

    ASCII Schema::

        +---------------------------------------------------------------+
        |                      CuratedProfile                           |
        +---------------------------------------------------------------+
        | Field           | Type              | Example                 |
        +-----------------+-------------------+-------------------------|
        | mcm_id          | str               | "MCM-001"               |
        | product_name    | str               | "Nike Pegasus 41"       |
        | brand           | str               | "Nike"                  |
        | category        | str               | "Обувь"                 |
        | description     | str               | "Беговые кроссовки"     |
        | key_features    | list[str]         | ["Air Zoom"]            |
        | technologies    | list[str]         | ["React"]               |
        | composition     | dict[str,str]     | {"Верх": "Текстиль"}    |
        | benefits_data   | list[str]         | ["Отличная амортиз."]   |
        | seo_material    | list[str]         | ["кроссовки nike"]      |
        | provenance_log  | DataProvenanceLog | log                     |
        +---------------------------------------------------------------+

        Consumption by UC2 Content Generators::

            CuratedProfile
                |
                +---> UC2 Copywriter: uses description, benefits_data
                +---> UC2 SEO Agent: uses seo_material, key_features
                +---> UC2 Platform Adapter: uses all fields per platform
                |
                v
            Platform-specific product cards (WB, Ozon, Lamoda, ...)

    Attributes:
        mcm_id: MCM identifier for this curated profile.
        product_name: Final resolved product name after curation. May differ
            from the original Excel value if the Curator improved it.
        brand: Brand name, verified and normalized by the Curator.
        category: Product category from the Sportmaster taxonomy.
        description: Curated product description, enriched and validated.
            This is the base text that content generators will adapt for
            each marketplace platform.
        key_features: Curated list of key product features to highlight.
            Merged from supplier data, competitor analysis, and internal
            insights. Ordered by importance for content generators.
        technologies: List of brand technologies used in the product.
            Verified against known technology databases by the Curator.
        composition: Material composition as component-to-material mapping.
            Verified and normalized by the Curator.
        benefits_data: Customer-facing benefit statements derived from
            features, internal insights, and competitive positioning.
            Ready to be inserted into product card copy.
        seo_material: SEO keywords and phrases for search optimization.
            Derived from competitor analysis, search trends, and category
            keyword databases. Used by the SEO Agent in UC2.
        provenance_log: Full provenance log carried through from the
            EnrichedProductProfile. Preserved for audit trail and
            quality control purposes.

    Examples:
        Complete curated profile::

            >>> cp = CuratedProfile(
            ...     mcm_id="MCM-001",
            ...     product_name="Nike Pegasus 41",
            ...     brand="Nike",
            ...     category="Обувь",
            ...     description="Беговые кроссовки",
            ...     key_features=["Air Zoom"],
            ...     technologies=["React"],
            ...     composition={"Верх": "Текстиль"},
            ...     benefits_data=["Отличная амортизация"],
            ...     seo_material=["беговые кроссовки nike"],
            ...     provenance_log=DataProvenanceLog(mcm_id="MCM-001"),
            ... )
            >>> cp.brand
            'Nike'
    """

    # ------------------------------------------------------------------
    # Product identity -- flat fields resolved by the Data Curator
    # ------------------------------------------------------------------

    # MCM identifier: same key used throughout the entire pipeline.
    # Links this curated output back to the original ProductInput.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM identifier for this curated profile. Links back to the "
            "original ProductInput and all upstream enrichment outputs."
        ),
        examples=["MCM-001", "MCM-001-BLK-42"],
    )

    # Product name: may be improved by the Curator (e.g., adding model year).
    # Content generators use this as the base product title.
    product_name: str = Field(
        ...,
        description=(
            "Final resolved product name after curation. May differ from "
            "the original Excel value if the Curator improved it."
        ),
        examples=["Nike Pegasus 41", "Adidas Ultraboost Light"],
    )

    # Brand name: verified against the Sportmaster brand registry.
    # Normalized to the official spelling (e.g., "Nike" not "NIKE").
    brand: str = Field(
        ...,
        description=(
            "Brand name verified and normalized by the Curator. "
            "Matches the official Sportmaster brand registry spelling."
        ),
        examples=["Nike", "Adidas", "Puma"],
    )

    # Category: top-level taxonomy node, carried through from ProductInput.
    # Used by platform adapters for category mapping on each marketplace.
    category: str = Field(
        ...,
        description=(
            "Product category from the Sportmaster taxonomy. Used by "
            "platform adapters for marketplace category mapping."
        ),
        examples=["Обувь", "Одежда", "Аксессуары"],
    )

    # ------------------------------------------------------------------
    # Content-ready fields -- used directly by UC2 content generators
    # ------------------------------------------------------------------

    # Description: enriched and validated base text for content generation.
    # Content generators adapt this for each marketplace's tone and format.
    description: str = Field(
        ...,
        description=(
            "Curated product description, enriched and validated. Base text "
            "that content generators adapt for each marketplace platform."
        ),
    )

    # Key features: ordered by importance for content prioritization.
    # Merged from supplier data, competitor analysis, and internal insights.
    key_features: list[str] = Field(
        default=[],
        description=(
            "Curated list of key product features ordered by importance. "
            "Merged from supplier data, competitor analysis, and internal "
            "insights. Content generators highlight these in bullet points."
        ),
        examples=[["Air Zoom", "React", "Flywire"]],
    )

    # Technologies: verified brand technology names.
    # Used in technical specs and feature callouts.
    technologies: list[str] = Field(
        default=[],
        description=(
            "Brand technologies used in the product, verified against known "
            "technology databases. Used in technical specs and feature callouts."
        ),
        examples=[["React", "Air Zoom", "Flyknit"]],
    )

    # Composition: normalized material specs for regulatory compliance.
    # Required by Russian marketplace regulations for certain categories.
    composition: dict[str, str] = Field(
        default={},
        description=(
            "Material composition as component-to-material mapping. "
            "Verified and normalized by the Curator. Required by "
            "marketplace regulations for certain product categories."
        ),
        examples=[{"Верх": "Текстиль", "Подошва": "Резина"}],
    )

    # Benefits: customer-facing benefit statements ready for copy.
    # Derived from features + internal insights + competitive positioning.
    benefits_data: list[str] = Field(
        default=[],
        description=(
            "Customer-facing benefit statements derived from features, "
            "internal insights, and competitive positioning. Ready for "
            "direct insertion into product card copy."
        ),
        examples=[["Отличная амортизация", "Дышащий верх"]],
    )

    # SEO material: keywords and phrases for search optimization.
    # The SEO Agent in UC2 uses these to optimize titles and descriptions.
    seo_material: list[str] = Field(
        default=[],
        description=(
            "SEO keywords and phrases for search optimization on marketplaces. "
            "Derived from competitor analysis, search trends, and category "
            "keyword databases. Used by the UC2 SEO Agent."
        ),
        examples=[["беговые кроссовки nike", "кроссовки для бега мужские"]],
    )

    # ------------------------------------------------------------------
    # Audit trail -- provenance preserved for quality control
    # ------------------------------------------------------------------

    # Full provenance log from the EnrichedProductProfile.
    # Preserved so that quality controllers can trace every field value
    # back to its original source and extraction agent.
    provenance_log: DataProvenanceLog = Field(
        ...,
        description=(
            "Full provenance log from the EnrichedProductProfile. Preserved "
            "for audit trail, dispute resolution, and quality control."
        ),
    )
