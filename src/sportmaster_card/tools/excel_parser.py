"""Excel Parser Tool -- converts Excel template rows into ProductInput.

Reads the Sportmaster 209-column Excel template and maps relevant columns
to ProductInput fields. Column mapping is defined in COLUMN_MAP.

Architecture::

    +---------------------------+
    |   Excel Template          |
    |  (209 cols, 13 blocks)    |
    +------------+--------------+
                 | pandas row / dict
                 v
    +---------------------------+
    |   ExcelParserTool         |
    |   .parse_row(dict)        |
    +------------+--------------+
                 | ProductInput
                 v
    +---------------------------+
    |   Router Agent            |
    +---------------------------+

The tool accepts a plain Python dict (or pandas Series converted to dict)
representing one row from the Excel template. It maps Russian column names
to English ProductInput field names, handles type conversions for list
fields (comma-separated strings to lists), and defaults missing optional
columns to None.

Usage::

    from sportmaster_card.tools.excel_parser import ExcelParserTool

    parser = ExcelParserTool()
    row = {"Код МЦМ": "MCM-001-BLK-42", "Бренд": "Nike", ...}
    product = parser.parse_row(row)
"""

from __future__ import annotations

from sportmaster_card.models.product_input import ProductInput

# ---------------------------------------------------------------------------
# Column mapping: Excel column name (Russian) -> ProductInput field name.
#
# Keys are the exact header strings from the Sportmaster MCM Excel template.
# Values are the corresponding attribute names on ProductInput.
# Only Phase 1 pilot columns are mapped; the full 209 will be added later.
# ---------------------------------------------------------------------------
COLUMN_MAP: dict[str, str] = {
    "Код МЦМ": "mcm_id",
    "Бренд": "brand",
    "Категория": "category",
    "Группа товаров": "product_group",
    "Товарная группа": "product_subgroup",
    "Наименование товара": "product_name",
    "Описание": "description",
    "Пол": "gender",
    "Сезон": "season",
    "Цвет": "color",
    "Ассортиментный сегмент": "assortment_segment",
    "Тип ассортимента": "assortment_type",
    "Уровень ассортимента": "assortment_level",
    "Технологии": "technologies",
    "Фото": "photo_urls",
}

# Fields whose Excel values are comma-separated strings that must be
# converted into Python lists. Each entry here triggers split-and-strip
# logic in parse_row().
_COMMA_LIST_FIELDS: frozenset[str] = frozenset({"technologies", "photo_urls"})


class ExcelParserTool:
    """Parses Excel template rows into ProductInput models.

    Stateless tool that converts a single row dictionary (as produced by
    ``pandas.DataFrame.to_dict(orient='records')`` or manual construction)
    into a validated ProductInput instance.

    The parser handles three concerns:
        1. **Column renaming** -- Russian Excel headers to English field names.
        2. **Type coercion** -- comma-separated strings to ``list[str]``.
        3. **Missing data** -- absent columns default to ``None``.
    """

    def parse_row(self, row: dict) -> ProductInput:
        """Convert a single Excel row (as dict) into a ProductInput.

        Handles column name mapping (Russian to English field names),
        type conversions (comma-separated strings to lists), and
        missing optional fields (defaulted to None).

        Args:
            row: Dictionary whose keys are Russian Excel column headers
                and whose values are the cell contents for one product row.

        Returns:
            A validated ProductInput instance with all mapped fields set.

        Raises:
            pydantic.ValidationError: If required fields (mcm_id, brand,
                category, product_group, product_subgroup, product_name)
                are missing from the row.
        """
        # Build a dict of {english_field: value} from the incoming row,
        # skipping any Excel columns not present in COLUMN_MAP.
        mapped: dict[str, object] = {}

        for excel_col, field_name in COLUMN_MAP.items():
            # Look up the Russian column name in the row dict.
            value = row.get(excel_col)

            if value is None:
                # Column not present or explicitly None -- leave it out
                # so ProductInput applies its own defaults.
                continue

            # Comma-separated fields need splitting into lists.
            if field_name in _COMMA_LIST_FIELDS and isinstance(value, str):
                mapped[field_name] = [
                    item.strip() for item in value.split(",") if item.strip()
                ]
            else:
                mapped[field_name] = value

        return ProductInput(**mapped)
