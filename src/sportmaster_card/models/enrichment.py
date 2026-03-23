"""UC1 Enrichment output models -- ValidationReport and CompetitorBenchmark.

This module defines data models for two key agents in the UC1 Enrichment pipeline:

1. **Data Validator (Agent 1.3)** produces a ``ValidationReport`` after checking
   each field in the ProductInput for presence, correctness, and completeness.
   The report lists per-field validation results, identifies missing required
   fields, and computes an overall completeness score.

2. **External Researcher (Agent 1.5)** produces a ``CompetitorBenchmark`` after
   scraping competitor product cards from external marketplaces (Wildberries,
   Ozon, Lamoda, etc.). The benchmark aggregates competitor data to provide
   pricing intelligence, feature analysis, and content inspiration.

Module-level design decisions:
    - FieldValidation is a fine-grained per-field result; ValidationReport
      aggregates these into a single report per MCM product.
    - CompetitorCard captures one competitor listing; CompetitorBenchmark
      aggregates multiple listings into actionable insights.
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
    Internal Researcher (1.6)     (feeds into Data Enricher)
        |
        v
    Data Enricher (1.8) <--- aggregates all upstream outputs

Typical usage::

    from sportmaster_card.models.enrichment import (
        CompetitorBenchmark,
        CompetitorCard,
        FieldValidation,
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
