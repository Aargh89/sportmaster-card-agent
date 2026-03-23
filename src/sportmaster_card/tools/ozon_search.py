"""Ozon Search Tool — product card parsing from Ozon marketplace.

Uses Ozon's internal composer-api endpoint to search for products.
This is an undocumented internal API used by the Ozon frontend.

API endpoint:
    https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/search/?text={query}

The response contains widgetStates with searchResultsV2 data.
Product data is in cellTrackingInfo.product within each search result item.

Rate Limiting:
    Ozon has aggressive anti-bot protection.
    Use delays of 3-5 seconds between requests.
    Rotate User-Agents if making many requests.

Example:
    >>> from sportmaster_card.tools.ozon_search import ozon_search
    >>> results = ozon_search("Nike Pegasus кроссовки")
    >>> results[0].brand
    'Nike'
"""

import json
import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OZON_SEARCH_URL = "https://www.ozon.ru/api/composer-api.bx/page/json/v2"
OZON_TIMEOUT = 20
OZON_REQUEST_DELAY = 3.0

OZON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


@dataclass
class OzonProduct:
    """Parsed product from Ozon search results.

    Attributes:
        product_id: Ozon product ID.
        name: Product name as shown on Ozon.
        brand: Brand name.
        price: Current price in rubles.
        original_price: Price before discount, in rubles.
        rating: Product rating (0.0-5.0).
        reviews_count: Number of customer reviews.
        url: Direct URL to the product page on Ozon.
        image_url: URL to the main product image.
        delivery_info: Delivery estimate text.
    """

    product_id: int
    name: str
    brand: str = ""
    price: int = 0
    original_price: int = 0
    rating: float = 0.0
    reviews_count: int = 0
    url: str = ""
    image_url: str = ""
    delivery_info: str = ""

    def __post_init__(self):
        if not self.url and self.product_id:
            self.url = f"https://www.ozon.ru/product/{self.product_id}/"


def ozon_search(
    query: str,
    max_results: int = 10,
    min_rating: float = 0.0,
) -> list[OzonProduct]:
    """Search Ozon for products matching the query.

    Uses the composer-api.bx endpoint which returns the full page
    state as JSON, including search results in widgetStates.

    Args:
        query: Search query in Russian.
        max_results: Maximum number of products to return.
        min_rating: Minimum rating filter.

    Returns:
        List of OzonProduct objects. Empty list on failure.
    """
    encoded_query = urllib.parse.quote(query)
    params = {"url": f"/search/?text={encoded_query}&from_global=true"}

    try:
        response = requests.get(
            OZON_SEARCH_URL,
            params=params,
            headers=OZON_HEADERS,
            timeout=OZON_TIMEOUT,
        )

        if response.status_code == 403:
            logger.warning("Ozon returned 403 Forbidden (anti-bot). Try with different headers/proxy.")
            return []

        if response.status_code != 200:
            logger.warning("Ozon returned status %d", response.status_code)
            return []

        data = response.json()
        widget_states = data.get("widgetStates", {})

        # Find search results widget
        products = []
        for key, value in widget_states.items():
            if "searchResultsV2" in key:
                try:
                    parsed = json.loads(value) if isinstance(value, str) else value
                    items = parsed.get("items", [])
                    for item in items:
                        product = _parse_ozon_item(item)
                        if product and product.rating >= min_rating:
                            products.append(product)
                        if len(products) >= max_results:
                            break
                except (json.JSONDecodeError, TypeError):
                    continue
                if products:
                    break

        logger.info("Ozon search '%s': found %d products", query, len(products))
        return products

    except requests.RequestException as e:
        logger.warning("Ozon request failed: %s", e)
        return []
    except (ValueError, KeyError) as e:
        logger.warning("Ozon JSON parse error: %s", e)
        return []


def _parse_ozon_item(item: dict) -> Optional[OzonProduct]:
    """Parse a single Ozon search result item into OzonProduct.

    Extracts product data from the cellTrackingInfo.product structure
    used by the Ozon composer-api response format.

    Args:
        item: Raw item dict from Ozon search results widget.

    Returns:
        OzonProduct if parsing succeeds, None if product ID is missing.
    """
    try:
        # Main product info from mainState
        main = item.get("mainState", [])
        title = ""
        for atom in main:
            if atom.get("atom", {}).get("type") == "action":
                title = atom.get("atom", {}).get("textAtom", {}).get("text", "")
            # The title can also be in textAtom directly
            text_atom = atom.get("atom", {}).get("textAtom", {})
            if text_atom.get("maxLines") and not title:
                title = text_atom.get("text", "")

        # Tracking info has structured product data
        tracking = item.get("cellTrackingInfo", {})
        if not tracking:
            # Try from trackingInfo
            tracking_str = item.get("trackingInfo", "")
            if tracking_str:
                try:
                    tracking = json.loads(tracking_str) if isinstance(tracking_str, str) else tracking_str
                except json.JSONDecodeError:
                    pass

        product_data = tracking.get("product", {}) if isinstance(tracking, dict) else {}

        product_id = product_data.get("id", 0)
        if not product_id:
            # Try from item directly
            product_id = item.get("id", 0)
        if not product_id:
            return None

        name = product_data.get("title", title or "")
        brand = product_data.get("brand", "")
        price = product_data.get("finalPrice", 0)
        if isinstance(price, str):
            price = int("".join(c for c in price if c.isdigit()) or "0")

        rating_str = product_data.get("rating", "0")
        rating = float(rating_str) if rating_str else 0.0

        # Image from tileImage
        image_url = ""
        tile_image = item.get("tileImage", {})
        if tile_image:
            image_url = tile_image.get("imageUrl", "") or tile_image.get("link", "")

        return OzonProduct(
            product_id=product_id,
            name=name,
            brand=brand,
            price=price,
            rating=rating,
            url=f"https://www.ozon.ru/product/{product_id}/",
            image_url=image_url,
        )

    except Exception as e:
        logger.warning("Failed to parse Ozon item: %s", e)
        return None
