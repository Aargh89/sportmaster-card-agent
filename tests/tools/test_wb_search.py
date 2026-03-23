"""Tests for Wildberries Search Tool.

Tests cover:
    - build_search_queries: generates multiple search queries
    - _parse_product: parses raw WB API JSON into WBProduct
    - wb_search: integration test (mocked HTTP, not real API calls)
"""
import pytest


def test_build_search_queries():
    """build_search_queries returns 3+ queries from most to least specific."""
    from sportmaster_card.tools.wb_search import build_search_queries

    queries = build_search_queries(
        brand="Nike",
        product_name="Nike Air Zoom Pegasus 41",
        category="Обувь",
        product_subgroup="Беговые кроссовки",
        technologies=["Air Zoom", "React"],
    )

    assert len(queries) >= 3
    # First query should be exact product name
    assert queries[0] == "Nike Air Zoom Pegasus 41"
    # Second should include brand + subgroup
    assert "Nike" in queries[1]
    assert "Беговые кроссовки" in queries[1]


def test_build_search_queries_no_technologies():
    """Queries work without technologies."""
    from sportmaster_card.tools.wb_search import build_search_queries

    queries = build_search_queries(
        brand="Adidas",
        product_name="Adidas Superstar",
        category="Обувь",
        product_subgroup="Повседневные кроссовки",
    )

    assert len(queries) >= 3
    assert "Adidas Superstar" in queries[0]


def test_parse_product_valid():
    """_parse_product correctly parses WB API JSON."""
    from sportmaster_card.tools.wb_search import _parse_product

    raw = {
        "id": 123456789,
        "name": "Кроссовки беговые",
        "brand": "Nike",
        "salePriceU": 1299000,  # 12990 руб
        "priceU": 1599000,  # 15990 руб
        "rating": 4.7,
        "feedbacks": 1523,
        "pics": 8,
        "sale": 19,
    }

    product = _parse_product(raw)

    assert product is not None
    assert product.product_id == 123456789
    assert product.brand == "Nike"
    assert product.price == 12990
    assert product.original_price == 15990
    assert product.rating == 4.7
    assert product.feedbacks == 1523
    assert "123456789" in product.url


def test_parse_product_missing_id():
    """_parse_product returns None when ID is missing."""
    from sportmaster_card.tools.wb_search import _parse_product

    result = _parse_product({"name": "Test", "brand": "Test"})
    assert result is None


def test_wb_product_url_format():
    """WBProduct URL follows WB format."""
    from sportmaster_card.tools.wb_search import WBProduct

    p = WBProduct(
        product_id=12345,
        name="Test",
        brand="Test",
        price=1000,
        original_price=1500,
        rating=4.5,
        feedbacks=100,
        url="https://www.wildberries.ru/catalog/12345/detail.aspx",
    )

    assert p.url == "https://www.wildberries.ru/catalog/12345/detail.aspx"


def test_wb_search_returns_empty_on_network_error(monkeypatch):
    """wb_search returns empty list on network errors (no crash)."""
    import requests
    from sportmaster_card.tools.wb_search import wb_search

    def mock_get(*args, **kwargs):
        raise requests.ConnectionError("Mocked network error")

    monkeypatch.setattr(requests, "get", mock_get)

    results = wb_search("test query")
    assert results == []
