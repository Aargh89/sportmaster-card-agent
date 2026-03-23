"""DataProvenance and DataProvenanceLog models -- attribute origin tracking.

This module implements the v0.3 data provenance system that records the origin,
confidence, and dispute status of every product attribute extracted or enriched
by agents in the UC1 (Enrichment) pipeline. Provenance tracking is a core v0.3
feature: every enrichment agent must record WHERE each attribute came from, HOW
confident the extraction is, and WHETHER the value is disputed.

Why provenance matters:
    Product cards pass through 30+ agents. Without provenance, it is impossible
    to trace which agent produced which value, debug conflicting attributes, or
    audit data quality. The DataProvenance record solves this by attaching a
    "birth certificate" to every single attribute value.

Module-level design decisions:
    - SourceType uses str+Enum for JSON-serializable enum values.
    - Confidence is bounded [0, 1] using Pydantic Field(ge=0, le=1).
    - DataProvenanceLog auto-computes disputed_count and alert_required via
      a model_validator, so callers never need to calculate these manually.
    - The ``value`` field uses ``Any`` to support strings, numbers, lists, etc.

Data flow in the enrichment pipeline::

    ProductInput
        |
        v
    Agent 1.3 (Data Validator)  ---> DataProvenance(source_type=INTERNAL)
    Agent 1.5 (Visual Interpr.) ---> DataProvenance(source_type=PHOTO)
    Agent 1.6 (Ext. Researcher) ---> DataProvenance(source_type=EXTERNAL)
    Agent 1.7 (Int. Researcher) ---> DataProvenance(source_type=INTERNAL)
        |
        v  (all provenance entries collected)
    DataProvenanceLog(mcm_id="MCM-...")
        |
        v
    Agent 1.10 (Data Curator) reviews disputed entries

Typical usage::

    from sportmaster_card.models.provenance import (
        DataProvenance,
        DataProvenanceLog,
        SourceType,
    )

    entry = DataProvenance(
        attribute_name="brand",
        value="Nike",
        source_type=SourceType.INTERNAL,
        source_name="Excel шаблон",
        confidence=0.99,
        agent_id="agent-1.3-data-validator",
        timestamp=datetime.now(timezone.utc),
    )

    log = DataProvenanceLog(mcm_id="MCM-001-BLK-42", entries=[entry])
    assert log.disputed_count == 0
    assert log.alert_required is False
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ======================================================================
# SourceType enum -- classifies the origin of an attribute value
# ======================================================================


class SourceType(str, Enum):
    """Origin type for an extracted product attribute.

    SourceType classifies WHERE an attribute value was obtained. Each
    enrichment agent tags its outputs with the appropriate source type
    so that downstream agents and human reviewers can assess data quality.

    The six source types cover all data origins in the Sportmaster pipeline:

    ASCII Diagram -- Source Types and Their Typical Agents::

        +------------------+--------------------------------------------+
        | SourceType       | Typical Agent / Origin                     |
        +------------------+--------------------------------------------+
        | INTERNAL         | Excel template, Sportmaster DB, ERP data   |
        | EXTERNAL         | Competitor sites (WB, Ozon), brand APIs    |
        | PHOTO            | Supplier product photos (official)         |
        | SKETCH           | Technical drawings, design sketches        |
        | INTERNET_PHOTO   | Web-scraped product images                 |
        | MANUAL           | Human operator manual entry                |
        +------------------+--------------------------------------------+

    Values:
        INTERNAL: "internal" -- data from Sportmaster's own systems
        EXTERNAL: "external" -- data from external sources (competitors, APIs)
        PHOTO: "photo" -- data extracted from official product photos
        SKETCH: "sketch" -- data extracted from technical drawings
        INTERNET_PHOTO: "internet_photo" -- data from web-scraped images
        MANUAL: "manual" -- data entered manually by a human operator

    Examples::

        >>> SourceType.INTERNAL.value
        'internal'
        >>> SourceType.PHOTO.value
        'photo'
    """

    # Data from Sportmaster's own systems: Excel templates, ERP, internal DB.
    # Highest baseline trust -- this is first-party data.
    INTERNAL = "internal"

    # Data from external sources: competitor marketplaces (WB, Ozon, Lamoda),
    # brand APIs, supplier data feeds. Trust depends on source reputation.
    EXTERNAL = "external"

    # Data extracted from official supplier product photos by the Visual
    # Interpreter agent (1.5). Confidence varies by image quality.
    PHOTO = "photo"

    # Data extracted from technical drawings or design sketches.
    # Typically high-confidence for measurements and materials.
    SKETCH = "sketch"

    # Data extracted from web-scraped product images found online.
    # Lower confidence than official photos -- provenance less certain.
    INTERNET_PHOTO = "internet_photo"

    # Data entered manually by a human operator or merchandiser.
    # High confidence (human-verified) but low throughput.
    MANUAL = "manual"


# ======================================================================
# DataProvenance model -- single attribute provenance record
# ======================================================================


class DataProvenance(BaseModel):
    """Provenance record for a single product attribute value.

    Every time an enrichment agent extracts, infers, or receives an attribute
    value, it creates a DataProvenance record. This record is the "birth
    certificate" of the attribute: it tells downstream agents and reviewers
    exactly where the value came from, how confident the extraction is, and
    whether the value needs human review.

    ASCII Schema Diagram::

        +---------------------------------------------------------------+
        |                      DataProvenance                           |
        +---------------------------------------------------------------+
        | Field            | Type       | Example                       |
        +------------------+------------+-------------------------------|
        | attribute_name   | str        | "brand"                       |
        | value            | Any        | "Nike"                        |
        | source_type      | SourceType | SourceType.INTERNAL           |
        | source_name      | str        | "Excel шаблон"                |
        | confidence       | float      | 0.95 (range: 0.0 to 1.0)     |
        | is_disputed      | bool       | False                         |
        | agent_id         | str        | "agent-1.3-data-validator"    |
        | timestamp        | datetime   | 2026-03-23T12:00:00Z          |
        +---------------------------------------------------------------+

        Confidence Scale::

            0.0 -------- 0.3 -------- 0.6 -------- 0.8 -------- 1.0
            |  very low  |    low     |   medium   |    high    |
            |  (guess)   | (inferred) | (extracted)| (verified) |

    Attributes:
        attribute_name: Name of the product attribute this provenance tracks.
            Must match a field name from ProductInput or enrichment output
            (e.g., "brand", "color", "description", "technologies").
        value: The actual attribute value extracted by the agent. Can be any
            type: str, int, float, list, dict -- depends on the attribute.
        source_type: Classification of the data origin. See SourceType enum
            for the six possible values and their meanings.
        source_name: Human-readable identifier of the specific source within
            the source type. Examples: "Excel шаблон" (for INTERNAL),
            "WB" (for EXTERNAL), "supplier_photo_01.jpg" (for PHOTO).
        confidence: Extraction confidence score in the range [0.0, 1.0].
            0.0 = pure guess, 1.0 = verified fact. Enforced by Pydantic
            Field validators (ge=0, le=1).
        is_disputed: Flag indicating the attribute value conflicts with
            another source or fails validation rules. When True, the Data
            Curator (Agent 1.10) must review this entry before the value
            can be used in content generation. Defaults to False.
        agent_id: Identifier of the agent that produced this provenance
            record. Format: "agent-{number}-{name}" by convention.
        timestamp: UTC timestamp of when the attribute was extracted.
            Used for ordering and audit trail purposes.

    Examples:
        Agent extracting brand from Excel template::

            >>> from datetime import datetime, timezone
            >>> prov = DataProvenance(
            ...     attribute_name="brand",
            ...     value="Nike",
            ...     source_type=SourceType.INTERNAL,
            ...     source_name="Excel шаблон",
            ...     confidence=0.99,
            ...     agent_id="agent-1.3-data-validator",
            ...     timestamp=datetime(2026, 3, 23, tzinfo=timezone.utc),
            ... )
            >>> prov.confidence
            0.99

        Disputed color from photo analysis::

            >>> prov = DataProvenance(
            ...     attribute_name="color",
            ...     value="Красный",
            ...     source_type=SourceType.PHOTO,
            ...     source_name="supplier_photo_01.jpg",
            ...     confidence=0.55,
            ...     is_disputed=True,
            ...     agent_id="agent-1.5-visual-interpreter",
            ...     timestamp=datetime(2026, 3, 23, tzinfo=timezone.utc),
            ... )
            >>> prov.is_disputed
            True
    """

    # ------------------------------------------------------------------
    # Attribute identity -- what attribute this provenance is about
    # ------------------------------------------------------------------

    # The attribute name must match a known product attribute from the
    # ProductInput model or from an enrichment agent's output schema.
    # This is the key that links provenance to the actual data field.
    attribute_name: str = Field(
        ...,
        description=(
            "Name of the product attribute this provenance record tracks. "
            "Must match a field from ProductInput or enrichment output."
        ),
        examples=["brand", "color", "description", "technologies"],
    )

    # The actual value extracted by the agent. Using Any type because
    # different attributes have different types: brand is str, technologies
    # is list[str], composition is dict[str,str], etc.
    value: Any = Field(
        ...,
        description=(
            "The actual attribute value extracted or inferred by the agent. "
            "Type varies by attribute: str, int, float, list, or dict."
        ),
        examples=["Nike", ["Air Zoom", "React"], {"Верх": "Текстиль"}],
    )

    # ------------------------------------------------------------------
    # Source identification -- where the value came from
    # ------------------------------------------------------------------

    # Source type classifies the broad category of data origin.
    # Combined with source_name, it gives full traceability.
    source_type: SourceType = Field(
        ...,
        description=(
            "Classification of the data origin. Determines the baseline "
            "trust level and appropriate validation strategy."
        ),
        examples=[SourceType.INTERNAL, SourceType.PHOTO, SourceType.EXTERNAL],
    )

    # Source name is the specific source within the source type category.
    # For INTERNAL: "Excel шаблон", "ERP system", "product database".
    # For EXTERNAL: "WB", "Ozon", "brand API".
    # For PHOTO: "supplier_photo_01.jpg", "product_main.png".
    source_name: str = Field(
        ...,
        description=(
            "Human-readable name of the specific source within the source "
            "type. Used in audit trails and dispute resolution."
        ),
        examples=["Excel шаблон", "WB", "supplier_photo_01.jpg", "operator input"],
    )

    # ------------------------------------------------------------------
    # Quality indicators -- how trustworthy the extraction is
    # ------------------------------------------------------------------

    # Confidence score bounded to [0.0, 1.0] by Pydantic Field validators.
    # ge=0 ensures >= 0.0, le=1 ensures <= 1.0. Values outside this range
    # will raise a ValidationError at model construction time.
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description=(
            "Extraction confidence score in range [0.0, 1.0]. "
            "0.0 = pure guess, 1.0 = verified fact. "
            "Enforced by ge=0, le=1 validators."
        ),
        examples=[0.95, 0.7, 0.5, 0.3],
    )

    # The disputed flag is set when the attribute value conflicts with
    # another source or fails a validation check. Disputed entries
    # require human review by the Data Curator before they can be trusted.
    is_disputed: bool = Field(
        default=False,
        description=(
            "Whether this attribute value is disputed (conflicts with "
            "another source or fails validation). Disputed entries require "
            "human review by the Data Curator (Agent 1.10)."
        ),
    )

    # ------------------------------------------------------------------
    # Audit trail -- who extracted it and when
    # ------------------------------------------------------------------

    # Agent ID follows the convention "agent-{number}-{name}".
    # This links every provenance record to the specific agent instance
    # that produced it, enabling per-agent quality tracking.
    agent_id: str = Field(
        ...,
        description=(
            "Identifier of the agent that produced this provenance record. "
            "Convention: 'agent-{number}-{name}' (e.g., 'agent-1.3-data-validator')."
        ),
        examples=["agent-1.3-data-validator", "agent-1.5-visual-interpreter"],
    )

    # Extraction timestamp in UTC. Used for ordering provenance entries
    # chronologically and for audit trail compliance.
    timestamp: datetime = Field(
        ...,
        description=(
            "UTC timestamp of when the attribute was extracted or inferred. "
            "Used for chronological ordering and audit trails."
        ),
        examples=["2026-03-23T12:00:00Z"],
    )


# ======================================================================
# DataProvenanceLog model -- aggregated provenance for one product
# ======================================================================


class DataProvenanceLog(BaseModel):
    """Aggregated provenance log for all attributes of a single product.

    DataProvenanceLog collects all DataProvenance entries for one MCM product
    and computes summary statistics. The key computed fields are disputed_count
    (how many entries are disputed) and alert_required (whether any disputes
    exist that need human attention).

    The model_validator(mode="after") automatically computes these fields from
    the entries list, so callers never need to calculate them manually. Any
    manually provided values for disputed_count and alert_required will be
    overwritten by the validator.

    ASCII Schema Diagram::

        +---------------------------------------------------------------+
        |                    DataProvenanceLog                          |
        +---------------------------------------------------------------+
        | Field            | Type                | Computed?             |
        +------------------+---------------------+-----------------------|
        | mcm_id           | str                 | No (required input)   |
        | entries          | list[DataProvenance] | No (default: [])      |
        | disputed_count   | int                 | Yes (from entries)    |
        | alert_required   | bool                | Yes (from disputed)   |
        | summary          | str                 | No (default: "")      |
        +---------------------------------------------------------------+

        Computation Flow::

            entries: [prov1, prov2, prov3, ...]
                |
                v
            disputed_count = sum(1 for e in entries if e.is_disputed)
                |
                v
            alert_required = (disputed_count > 0)

    Attributes:
        mcm_id: The MCM product identifier that this provenance log belongs
            to. Links back to the ProductInput and all downstream outputs.
        entries: List of individual DataProvenance records, one per attribute
            extraction event. Multiple agents may produce entries for the
            same attribute (which may lead to disputes).
        disputed_count: Number of entries with is_disputed=True. Auto-computed
            by the model validator from the entries list.
        alert_required: Whether any disputed entries exist. True when
            disputed_count > 0. Auto-computed by the model validator.
        summary: Optional brief summary text for human reviewers. Can be
            populated by the Data Curator with a summary of dispute reasons.

    Examples:
        Log with no disputes::

            >>> log = DataProvenanceLog(
            ...     mcm_id="MCM-001-BLK-42",
            ...     entries=[...],  # all entries have is_disputed=False
            ... )
            >>> log.alert_required
            False

        Log with disputes triggering alert::

            >>> log = DataProvenanceLog(
            ...     mcm_id="MCM-002-WHT-40",
            ...     entries=[...],  # some entries have is_disputed=True
            ... )
            >>> log.alert_required
            True
    """

    # ------------------------------------------------------------------
    # Product identity -- which product this log belongs to
    # ------------------------------------------------------------------

    # The MCM ID ties this provenance log to a specific product card.
    # One product = one provenance log = many provenance entries.
    mcm_id: str = Field(
        ...,
        description=(
            "MCM product identifier this provenance log belongs to. "
            "Links to ProductInput and all downstream pipeline outputs."
        ),
        examples=["MCM-001-BLK-42", "MCM-003-RED-38"],
    )

    # ------------------------------------------------------------------
    # Provenance entries -- individual attribute records
    # ------------------------------------------------------------------

    # The entries list holds one DataProvenance per attribute extraction.
    # Multiple entries may exist for the same attribute_name when different
    # agents extract conflicting values (leading to disputes).
    entries: list[DataProvenance] = Field(
        default_factory=list,
        description=(
            "List of individual DataProvenance records for this product. "
            "One entry per attribute extraction event across all agents."
        ),
    )

    # ------------------------------------------------------------------
    # Computed summary fields -- auto-calculated by model_validator
    # ------------------------------------------------------------------

    # Number of disputed entries. Computed automatically from entries.
    # Callers should NOT set this manually -- the validator overwrites it.
    disputed_count: int = Field(
        default=0,
        description=(
            "Count of entries with is_disputed=True. Auto-computed by "
            "the model validator from the entries list."
        ),
    )

    # Alert flag derived from disputed_count. True when any disputes exist.
    # Signals to the Data Curator that human review is needed.
    alert_required: bool = Field(
        default=False,
        description=(
            "Whether human review is required. True when disputed_count > 0. "
            "Auto-computed by the model validator."
        ),
    )

    # Optional summary text for human reviewers. Populated by the Data
    # Curator with context about disputes and recommended resolutions.
    summary: str = Field(
        default="",
        description=(
            "Brief summary text for human reviewers. Can describe dispute "
            "reasons, recommended resolutions, or overall data quality."
        ),
    )

    # ------------------------------------------------------------------
    # Model validator -- auto-compute disputed_count and alert_required
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def compute_dispute_stats(self) -> DataProvenanceLog:
        """Auto-compute disputed_count and alert_required from entries.

        This validator runs after all fields are set. It scans the entries
        list, counts how many have is_disputed=True, and sets the
        alert_required flag accordingly.

        Returns:
            The model instance with updated disputed_count and alert_required.

        Example::

            >>> log = DataProvenanceLog(mcm_id="MCM-001", entries=[...])
            >>> # disputed_count and alert_required are now auto-set
        """
        # Count entries where the value is disputed and needs review
        self.disputed_count = sum(1 for entry in self.entries if entry.is_disputed)

        # Alert is required whenever there is at least one disputed entry
        self.alert_required = self.disputed_count > 0

        return self
