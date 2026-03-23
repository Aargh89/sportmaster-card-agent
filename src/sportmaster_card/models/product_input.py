"""ProductInput model -- raw Excel row from the Sportmaster 209-column template.

This module defines the entry-point data model for the multi-agent product card
system. Every product card lifecycle begins with a ProductInput instance parsed
from one row of the Sportmaster MCM Excel template.

MCM = Merchandising Color Model (мерчендайзинговая цветомодель) -- the atomic
unit of product identity at Sportmaster. One MCM represents a single product
in a specific color, mapped to a unique article/barcode set.

Module-level design decisions:
    - Only Phase 1 pilot fields are modeled (footwear subset).
    - The full 209-column template will be added incrementally.
    - All optional fields default to None for sparse Excel rows.
    - Field descriptions use Russian terminology matching the Excel headers.

Typical usage::

    from sportmaster_card.models.product_input import ProductInput

    row = {"mcm_id": "MCM-001-BLK-42", "brand": "Nike", ...}
    product = ProductInput(**row)
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProductInput(BaseModel):
    """Raw product data from one row of the Sportmaster 209-column Excel template.

    ProductInput is the entry point for all 30+ downstream agents. It captures
    the essential subset of columns needed for the Phase 1 pilot (footwear
    category). Fields map directly to Excel column headers from the MCM
    template provided by the Sportmaster merchandising team.

    ASCII Schema Diagram -- Phase 1 Pilot Fields::

        +---------------------------------------------------------------+
        |                      ProductInput (MCM Row)                   |
        +---------------------------------------------------------------+
        | REQUIRED FIELDS (Identity Block)                              |
        |   Excel Col  | Field            | Type   | Example            |
        |   -----------+------------------+--------+--------------------|
        |   A (ID МЦМ) | mcm_id           | str    | "MCM-001-BLK-42"  |
        |   B (Бренд)  | brand            | str    | "Nike"             |
        |   C (Кат.)   | category         | str    | "Обувь"            |
        |   D (Группа) | product_group    | str    | "Кроссовки"        |
        |   E (Подгр.) | product_subgroup | str    | "Беговые кросс."   |
        |   F (Назв.)  | product_name     | str    | "Air Zoom Peg. 41" |
        +---------------------------------------------------------------+
        | OPTIONAL FIELDS (Attribute Blocks)                            |
        |   Excel Col  | Field              | Type          | Default   |
        |   -----------+--------------------+---------------+-----------|
        |   G (Описан.)| description        | str | None    | None      |
        |   H (Пол)   | gender             | str | None    | None      |
        |   I (Сезон)  | season             | str | None    | None      |
        |   J (Цвет)   | color              | str | None    | None      |
        |   K (Сегм.)  | assortment_segment | str | None    | None      |
        |   L (Тип)    | assortment_type    | str | None    | None      |
        |   M (Уров.)  | assortment_level   | str | None    | None      |
        +---------------------------------------------------------------+
        | OPTIONAL COMPLEX FIELDS (Extended Blocks)                     |
        |   Excel Col  | Field         | Type              | Default    |
        |   -----------+---------------+-------------------+------------|
        |   N-P (Техн.)| technologies  | list[str] | None  | None       |
        |   Q-R (Сост.)| composition   | dict[str,str]|None| None       |
        |   S-T (Фото) | photo_urls    | list[str] | None  | None       |
        +---------------------------------------------------------------+

        Data Flow::

            Excel File (.xlsx)
                |
                v
            ProductInput  -->  RoutingProfile  -->  UC1 Enrichment Agents
                                                    UC2 Content Agents
                                                    UC3 Publication Agents

    Attributes:
        mcm_id: Unique MCM identifier, serves as the primary key across
            the entire agent pipeline. Format varies by category.
        brand: Brand name exactly as it appears in the Sportmaster catalog.
        category: Top-level product category from the Sportmaster taxonomy
            (e.g., "Обувь", "Одежда", "Аксессуары").
        product_group: Product type group within the category
            (e.g., "Кроссовки", "Ботинки").
        product_subgroup: Specific product type within the group
            (e.g., "Беговые кроссовки", "Зимние ботинки").
        product_name: Original product name from the brand/supplier.
        description: Free-text product description from the supplier.
        gender: Target gender segment ("Мужской", "Женский", "Унисекс").
        season: Season designation (e.g., "Весна-Лето 2026").
        color: Primary color name in Russian.
        assortment_segment: Sportmaster assortment segment code
            (TRD = Trade, PRO = Professional, KIDS = Children).
        assortment_type: Product lifecycle type
            (Basic = permanent, Fashion = trend, Seasonal = one-season).
        assortment_level: Price/quality tier
            (Low, Mid, High, Premium).
        technologies: List of brand technologies used in the product
            (e.g., ["Air Zoom", "Flywire", "React"]).
        composition: Material composition as a mapping of component to
            material description (e.g., {"Верх": "Текстиль 80%"}).
        photo_urls: List of product photo URLs from the supplier.

    Examples:
        Minimal required fields only::

            >>> product = ProductInput(
            ...     mcm_id="MCM-001-BLK-42",
            ...     brand="Nike",
            ...     category="Обувь",
            ...     product_group="Кроссовки",
            ...     product_subgroup="Беговые кроссовки",
            ...     product_name="Nike Air Zoom Pegasus 41",
            ... )
            >>> product.mcm_id
            'MCM-001-BLK-42'

        With all pilot fields::

            >>> product = ProductInput(
            ...     mcm_id="MCM-003-RED-38",
            ...     brand="Nike",
            ...     category="Обувь",
            ...     product_group="Кроссовки",
            ...     product_subgroup="Беговые кроссовки",
            ...     product_name="Nike Pegasus 41",
            ...     technologies=["Air Zoom", "React"],
            ...     composition={"Верх": "Текстиль"},
            ... )
            >>> len(product.technologies)
            2
    """

    # ------------------------------------------------------------------
    # Required fields -- Identity Block
    # ------------------------------------------------------------------

    mcm_id: str = Field(
        ...,
        description=(
            "Unique MCM (merchandising color model) identifier. "
            "Primary key across the entire agent pipeline. "
            "Format varies by category but is always a non-empty string."
        ),
        examples=["MCM-001-BLK-42", "MCM-100-WHT-39", "MCM-2024-NIKE-RUN-001"],
    )

    brand: str = Field(
        ...,
        description=(
            "Brand name exactly as it appears in the Sportmaster product catalog. "
            "Must match the official brand registry for downstream matching."
        ),
        examples=["Nike", "Adidas", "Puma", "New Balance"],
    )

    category: str = Field(
        ...,
        description=(
            "Top-level product category from the Sportmaster taxonomy tree. "
            "Used for routing to category-specific processing pipelines."
        ),
        examples=["Обувь", "Одежда", "Аксессуары", "Спортивное оборудование"],
    )

    product_group: str = Field(
        ...,
        description=(
            "Product type group within the category. "
            "Second level of the Sportmaster taxonomy hierarchy."
        ),
        examples=["Кроссовки", "Ботинки", "Сандалии", "Шлёпанцы"],
    )

    product_subgroup: str = Field(
        ...,
        description=(
            "Specific product type within the product group. "
            "Third and most granular level of the taxonomy."
        ),
        examples=["Беговые кроссовки", "Баскетбольные кроссовки", "Повседневные кроссовки"],
    )

    product_name: str = Field(
        ...,
        description=(
            "Original product name as provided by the brand or supplier. "
            "Used as the base for content generation and SEO optimization."
        ),
        examples=["Nike Air Zoom Pegasus 41", "Adidas Ultraboost Light", "Puma RS-X"],
    )

    # ------------------------------------------------------------------
    # Optional fields -- Attribute Blocks
    # ------------------------------------------------------------------

    description: Optional[str] = Field(
        default=None,
        description=(
            "Free-text product description from the supplier or brand. "
            "May be empty for new products; enrichment agents will generate it."
        ),
        examples=["Беговые кроссовки с технологией Air Zoom для ежедневных тренировок"],
    )

    gender: Optional[str] = Field(
        default=None,
        description=(
            "Target gender segment for the product. "
            "Used for content tone and marketplace attribute mapping."
        ),
        examples=["Мужской", "Женский", "Унисекс", "Детский"],
    )

    season: Optional[str] = Field(
        default=None,
        description=(
            "Season designation for the product collection. "
            "Determines seasonal content strategies and publication timing."
        ),
        examples=["Весна-Лето 2026", "Осень-Зима 2025", "Всесезонный"],
    )

    color: Optional[str] = Field(
        default=None,
        description=(
            "Primary color name in Russian as specified in the MCM template. "
            "May differ from the marketing color name used in content."
        ),
        examples=["Красный", "Чёрный", "Белый", "Мультиколор"],
    )

    assortment_segment: Optional[str] = Field(
        default=None,
        description=(
            "Sportmaster assortment segment code determining the target audience. "
            "TRD = mainstream trade, PRO = professional athletes, KIDS = children."
        ),
        examples=["TRD", "PRO", "KIDS"],
    )

    assortment_type: Optional[str] = Field(
        default=None,
        description=(
            "Product lifecycle type in the Sportmaster assortment matrix. "
            "Basic = permanent range, Fashion = trend-driven, Seasonal = one season."
        ),
        examples=["Basic", "Fashion", "Seasonal"],
    )

    assortment_level: Optional[str] = Field(
        default=None,
        description=(
            "Price and quality tier within the assortment segment. "
            "Affects content tone, competitive positioning, and target platforms."
        ),
        examples=["Low", "Mid", "High", "Premium"],
    )

    # ------------------------------------------------------------------
    # Optional complex fields -- Extended Blocks
    # ------------------------------------------------------------------

    technologies: Optional[list[str]] = Field(
        default=None,
        description=(
            "List of brand-specific technologies used in the product. "
            "Extracted from supplier data or enriched by the Technology Agent. "
            "Each entry is a technology name as recognized by the brand."
        ),
        examples=[["Air Zoom", "Flywire", "React"], ["Boost", "Primeknit", "Continental"]],
    )

    composition: Optional[dict[str, str]] = Field(
        default=None,
        description=(
            "Material composition as a mapping of product component to its "
            "material description. Keys are component names (e.g., 'Верх', "
            "'Подошва'), values are material specs with percentages."
        ),
        examples=[
            {"Верх": "Текстиль 80%, синтетика 20%", "Подошва": "Резина"},
            {"Верх": "Натуральная кожа", "Подкладка": "Текстиль", "Подошва": "ЭВА"},
        ],
    )

    photo_urls: Optional[list[str]] = Field(
        default=None,
        description=(
            "List of product photo URLs provided by the supplier or brand. "
            "Used by the Visual Interpreter agent for attribute extraction. "
            "URLs must be publicly accessible or within the Sportmaster CDN."
        ),
        examples=[
            ["https://cdn.sportmaster.ru/photos/MCM-001-1.jpg"],
            [
                "https://example.com/photo1.jpg",
                "https://example.com/photo2.jpg",
            ],
        ],
    )
