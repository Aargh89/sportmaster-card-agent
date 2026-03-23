"""Tests for Ozon Search Tool.

Tests cover:
    - OzonProduct dataclass: URL generation, defaults
    - _parse_ozon_item: parsing raw Ozon API JSON
    - ozon_search: error handling (mocked HTTP)
"""
import pytest


def test_ozon_product_url():
    """OzonProduct URL is auto-generated from product_id."""
    from sportmaster_card.tools.ozon_search import OzonProduct
    p = OzonProduct(product_id=12345, name="Test")
    assert p.url == "https://www.ozon.ru/product/12345/"


def test_ozon_product_defaults():
    """OzonProduct has sensible defaults."""
    from sportmaster_card.tools.ozon_search import OzonProduct
    p = OzonProduct(product_id=1, name="Test")
    assert p.brand == ""
    assert p.price == 0
    assert p.rating == 0.0


def test_ozon_search_returns_empty_on_network_error(monkeypatch):
    """ozon_search returns empty list on network errors."""
    import requests as req
    from sportmaster_card.tools.ozon_search import ozon_search

    def mock_get(*args, **kwargs):
        raise req.ConnectionError("Mocked")

    monkeypatch.setattr(req, "get", mock_get)
    results = ozon_search("test")
    assert results == []


def test_ozon_search_handles_403(monkeypatch):
    """ozon_search returns empty list on 403 (anti-bot)."""
    import requests as req
    from unittest.mock import MagicMock
    from sportmaster_card.tools.ozon_search import ozon_search

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    monkeypatch.setattr(req, "get", lambda *a, **k: mock_resp)

    results = ozon_search("test")
    assert results == []


def test_parse_ozon_item_minimal():
    """_parse_ozon_item handles minimal item data."""
    from sportmaster_card.tools.ozon_search import _parse_ozon_item
    result = _parse_ozon_item({
        "cellTrackingInfo": {
            "product": {"id": 999, "title": "Test Product", "brand": "Nike", "finalPrice": 5990, "rating": "4.5"}
        }
    })
    assert result is not None
    assert result.product_id == 999
    assert result.name == "Test Product"
    assert result.brand == "Nike"
    assert result.price == 5990
    assert result.rating == 4.5


def test_parse_ozon_item_empty():
    """_parse_ozon_item returns None for empty data."""
    from sportmaster_card.tools.ozon_search import _parse_ozon_item
    assert _parse_ozon_item({}) is None
