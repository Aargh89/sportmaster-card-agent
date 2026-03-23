"""Tests for ExcelParserTool — verifies Excel row dict to ProductInput conversion.

Tests cover column mapping, optional field handling, comma-separated list parsing,
and edge cases with minimal data rows.
"""

from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.tools.excel_parser import ExcelParserTool


class TestExcelParserTool:
    """Test suite for ExcelParserTool.parse_row()."""

    def setup_method(self):
        """Create a fresh parser instance for each test."""
        self.parser = ExcelParserTool()

    def test_parse_excel_row_dict(self):
        """parse_row() accepts a dict (simulating a pandas row) and returns ProductInput."""
        row = {
            "Код МЦМ": "MCM-001-BLK-42",
            "Бренд": "Nike",
            "Категория": "Обувь",
            "Группа товаров": "Кроссовки",
            "Товарная группа": "Беговые кроссовки",
            "Наименование товара": "Nike Air Zoom Pegasus 41",
        }
        result = self.parser.parse_row(row)
        assert isinstance(result, ProductInput)
        assert result.mcm_id == "MCM-001-BLK-42"

    def test_parse_maps_columns_correctly(self):
        """Russian column names map to the correct ProductInput fields."""
        row = {
            "Код МЦМ": "MCM-007-WHT-40",
            "Бренд": "Adidas",
            "Категория": "Обувь",
            "Группа товаров": "Кроссовки",
            "Товарная группа": "Баскетбольные кроссовки",
            "Наименование товара": "Adidas Ultraboost Light",
            "Описание": "Лёгкие кроссовки для бега",
            "Пол": "Мужской",
            "Сезон": "Весна-Лето 2026",
            "Цвет": "Белый",
            "Ассортиментный сегмент": "TRD",
            "Тип ассортимента": "Basic",
            "Уровень ассортимента": "Mid",
        }
        result = self.parser.parse_row(row)
        assert result.brand == "Adidas"
        assert result.category == "Обувь"
        assert result.product_group == "Кроссовки"
        assert result.product_subgroup == "Баскетбольные кроссовки"
        assert result.product_name == "Adidas Ultraboost Light"
        assert result.description == "Лёгкие кроссовки для бега"
        assert result.gender == "Мужской"
        assert result.season == "Весна-Лето 2026"
        assert result.color == "Белый"
        assert result.assortment_segment == "TRD"
        assert result.assortment_type == "Basic"
        assert result.assortment_level == "Mid"

    def test_parse_handles_missing_optional_columns(self):
        """Missing optional columns result in None fields on ProductInput."""
        row = {
            "Код МЦМ": "MCM-010-GRN-44",
            "Бренд": "Puma",
            "Категория": "Обувь",
            "Группа товаров": "Кроссовки",
            "Товарная группа": "Повседневные кроссовки",
            "Наименование товара": "Puma RS-X",
        }
        result = self.parser.parse_row(row)
        assert result.description is None
        assert result.gender is None
        assert result.season is None
        assert result.color is None
        assert result.technologies is None
        assert result.photo_urls is None

    def test_parse_handles_technologies_as_comma_string(self):
        """Comma-separated technology string is split into a list."""
        row = {
            "Код МЦМ": "MCM-020-BLU-41",
            "Бренд": "Nike",
            "Категория": "Обувь",
            "Группа товаров": "Кроссовки",
            "Товарная группа": "Беговые кроссовки",
            "Наименование товара": "Nike Pegasus 41",
            "Технологии": "Air Zoom, React",
        }
        result = self.parser.parse_row(row)
        assert result.technologies == ["Air Zoom", "React"]

    def test_parse_handles_empty_row(self):
        """Row with only mcm_id and brand plus required fields yields Nones for optional."""
        row = {
            "Код МЦМ": "MCM-099-BLK-38",
            "Бренд": "New Balance",
            "Категория": "Обувь",
            "Группа товаров": "Кроссовки",
            "Товарная группа": "Беговые кроссовки",
            "Наименование товара": "NB 574",
        }
        result = self.parser.parse_row(row)
        assert result.mcm_id == "MCM-099-BLK-38"
        assert result.brand == "New Balance"
        assert result.description is None
        assert result.gender is None
        assert result.season is None
        assert result.color is None
        assert result.assortment_segment is None
        assert result.assortment_type is None
        assert result.assortment_level is None
        assert result.technologies is None
        assert result.photo_urls is None
