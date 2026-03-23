"""Wildberries Search Tool — парсинг карточек товаров с WB.

Использует открытый (неофициальный) поисковый API Wildberries
для поиска конкурентных карточек товаров по текстовому запросу.

API endpoint:
    https://search.wb.ru/exactmatch/ru/common/v9/search

Этот endpoint — внутренний API фронтенда wildberries.ru.
Он не документирован официально и может изменяться без уведомления.
Версия endpoint (v9) может устареть — при ошибках попробуйте v7, v5 или v4.

Формат цен:
    Цены в JSON приходят умноженными на 100.
    salePriceU = 1299000 означает 12990 руб.

Формат URL карточки:
    https://www.wildberries.ru/catalog/{product_id}/detail.aspx

Rate Limiting:
    WB применяет token bucket rate limiting.
    Рекомендуется делать 1 запрос в 2-3 секунды.
    При 429 — ждать X-Ratelimit-Retry секунд.

Architecture:
    ┌──────────────────────────┐
    │     wb_search()          │
    │  query → list[WBProduct] │
    └──────────┬───────────────┘
               │ HTTP GET
    ┌──────────▼───────────────┐
    │  search.wb.ru/...search  │
    │  → JSON {data.products}  │
    └──────────────────────────┘

Example:
    >>> from sportmaster_card.tools.wb_search import wb_search
    >>> results = wb_search("Nike Pegasus кроссовки")
    >>> results[0].brand
    'Nike'
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# WB Search API versions — try in order if one fails
WB_SEARCH_VERSIONS = ["v5", "v9", "v7", "v4"]

# Base URL template for WB search
WB_SEARCH_URL = "https://search.wb.ru/exactmatch/ru/common/{version}/search"

# Default region (Moscow) — affects product availability and prices
WB_DEFAULT_DEST = "-1257786"

# Headers mimicking a real browser request
WB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Origin": "https://www.wildberries.ru",
}

# Rate limiting: seconds between requests
WB_REQUEST_DELAY = 2.0

# Timeout for HTTP requests
WB_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class WBProduct:
    """Parsed product from Wildberries search results.

    Attributes:
        product_id: WB article number (nmId). Used to construct product URL.
        name: Product name as shown on WB.
        brand: Brand name.
        price: Sale price in rubles (after discount).
        original_price: Original price before discount, in rubles.
        rating: Product rating (0.0 — 5.0 scale).
        feedbacks: Number of customer reviews.
        url: Direct URL to the product card on WB.
        pics: Number of product images.
        sale_percent: Discount percentage.
        description: Full product description from card detail endpoint.
        composition: Product composition/materials.
        characteristics: List of {name, value} characteristic dicts.
        image_urls: List of direct CDN image URLs.

    Example:
        >>> p = WBProduct(product_id=12345, name="Nike Pegasus 41", ...)
        >>> p.url
        'https://www.wildberries.ru/catalog/12345/detail.aspx'
    """

    product_id: int
    name: str
    brand: str
    price: int
    original_price: int
    rating: float
    feedbacks: int
    url: str
    pics: int = 0
    sale_percent: int = 0
    description: str = ""
    composition: str = ""
    characteristics: list[dict] = None
    image_urls: list[str] = None

    def __post_init__(self):
        if self.characteristics is None:
            self.characteristics = []
        if self.image_urls is None:
            self.image_urls = []


# ---------------------------------------------------------------------------
# Search function
# ---------------------------------------------------------------------------

def wb_search(
    query: str,
    max_results: int = 10,
    min_rating: float = 0.0,
    sort: str = "popular",
    page: int = 1,
    retry_delay: float = WB_REQUEST_DELAY,
    max_versions: int = 4,
) -> list[WBProduct]:
    """Search Wildberries for products matching the query.

    Tries multiple API versions (v9, v7, v5, v4) in sequence until
    one returns results. Applies rate limiting between retries.

    Args:
        query: Search query in Russian (e.g., "Nike Pegasus кроссовки беговые").
            Should include brand, product type, and key characteristics.
        max_results: Maximum number of products to return (default 10).
            WB typically returns 100 products per page.
        min_rating: Minimum product rating filter (0.0-5.0).
            Set to 4.0+ for quality filtering.
        sort: Sort order. Options: "popular", "rate", "priceup", "pricedown", "newly".
        page: Page number (1-based). Each page has ~100 products.
        retry_delay: Seconds to wait between API version retries.

    Returns:
        List of WBProduct objects, sorted by relevance.
        Empty list if all API versions fail or return no results.

    Example:
        >>> products = wb_search("Nike Pegasus кроссовки беговые", max_results=5)
        >>> for p in products:
        ...     print(f"{p.brand} {p.name} — {p.price}₽ ★{p.rating}")
        Nike Кроссовки беговые Pegasus 41 — 12990₽ ★4.7

    Raises:
        No exceptions — returns empty list on any error.
    """
    params = {
        "appType": 1,
        "curr": "rub",
        "dest": WB_DEFAULT_DEST,
        "lang": "ru",
        "page": page,
        "query": query,
        "resultset": "catalog",
        "sort": sort,
        "spp": 30,
    }

    for version in WB_SEARCH_VERSIONS[:max_versions]:
        url = WB_SEARCH_URL.format(version=version)
        try:
            response = requests.get(
                url,
                params=params,
                headers=WB_HEADERS,
                timeout=WB_TIMEOUT,
            )

            if response.status_code == 429:
                # Rate limited — wait and try next version
                retry_after = int(response.headers.get("X-Ratelimit-Retry", retry_delay))
                logger.warning("WB rate limited on %s, waiting %ds", version, retry_after)
                time.sleep(retry_after)
                continue

            if response.status_code != 200:
                logger.warning("WB %s returned status %d", version, response.status_code)
                continue

            data = response.json()
            raw_products = data.get("data", {}).get("products", [])

            if not raw_products:
                logger.info("WB %s returned 0 products for '%s'", version, query)
                time.sleep(retry_delay)
                continue

            # Parse and filter products
            products = []
            for raw in raw_products:
                product = _parse_product(raw)
                if product and product.rating >= min_rating:
                    products.append(product)
                if len(products) >= max_results:
                    break

            logger.info(
                "WB %s: found %d products for '%s' (filtered from %d)",
                version, len(products), query, len(raw_products),
            )
            return products

        except requests.RequestException as e:
            logger.warning("WB %s request failed: %s", version, e)
            time.sleep(retry_delay)
            continue
        except (ValueError, KeyError) as e:
            logger.warning("WB %s JSON parse error: %s", version, e)
            continue

    logger.error("All WB API versions failed for query '%s'", query)
    return []


def build_search_queries(
    brand: str,
    product_name: str,
    category: str,
    product_subgroup: str,
    technologies: list[str] | None = None,
) -> list[str]:
    """Build multiple search queries for Wildberries.

    Generates 3-4 search queries with different specificity levels
    to maximize chances of finding relevant products.

    Args:
        brand: Brand name (e.g., "Nike").
        product_name: Full product name (e.g., "Nike Air Zoom Pegasus 41").
        category: Product category (e.g., "Обувь").
        product_subgroup: Specific type (e.g., "Беговые кроссовки").
        technologies: Optional list of technologies for query enrichment.

    Returns:
        List of 3-4 search query strings, from most specific to most general.

    Example:
        >>> queries = build_search_queries("Nike", "Nike Air Zoom Pegasus 41",
        ...     "Обувь", "Беговые кроссовки", ["Air Zoom"])
        >>> queries
        ['Nike Air Zoom Pegasus 41',
         'Nike Беговые кроссовки Air Zoom',
         'Беговые кроссовки Nike мужские',
         'кроссовки Nike беговые']
    """
    queries = []

    # Query 1: exact product name (most specific)
    queries.append(product_name)

    # Query 2: brand + subgroup + key technology
    q2 = f"{brand} {product_subgroup}"
    if technologies:
        q2 += f" {technologies[0]}"
    queries.append(q2)

    # Query 3: subgroup + brand (broader)
    queries.append(f"{product_subgroup} {brand}")

    # Query 4: generic category search
    queries.append(f"{category} {brand} {product_subgroup.split()[0] if product_subgroup else ''}")

    return queries


# ---------------------------------------------------------------------------
# Card detail & image URL
# ---------------------------------------------------------------------------

def wb_get_card_detail(product_id: int, retry_delay: float = 2.0) -> Optional[dict]:
    """Fetch detailed product card from WB by product ID.

    Uses card.wb.ru API to get full product details including
    description, composition, characteristics, and photos.

    Endpoint: https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&nm={id}

    Args:
        product_id: WB product article number (nmId).
        retry_delay: Seconds to wait on rate limit.

    Returns:
        Dict with product details or None on failure.
        Keys: description, composition, options (characteristics), pics.

    Example:
        >>> detail = wb_get_card_detail(123456789)
        >>> detail['description']
        'Беговые кроссовки Nike с технологией Air Zoom...'
    """
    url = "https://card.wb.ru/cards/v2/detail"
    params = {
        "appType": 1,
        "curr": "rub",
        "dest": WB_DEFAULT_DEST,
        "nm": product_id,
    }

    try:
        response = requests.get(url, params=params, headers=WB_HEADERS, timeout=WB_TIMEOUT)

        if response.status_code == 429:
            time.sleep(retry_delay)
            response = requests.get(url, params=params, headers=WB_HEADERS, timeout=WB_TIMEOUT)

        if response.status_code != 200:
            return None

        data = response.json()
        products = data.get("data", {}).get("products", [])
        if not products:
            return None

        product = products[0]
        return {
            "description": product.get("description", ""),
            "composition": product.get("compositions", ""),
            "options": product.get("options", []),  # list of {name, value} characteristic dicts
            "pics": product.get("pics", 0),
            "colors": [c.get("name", "") for c in product.get("colors", [])],
        }

    except Exception as e:
        logger.warning("WB card detail failed for %d: %s", product_id, e)
        return None


def wb_get_image_url(product_id: int, photo_index: int = 1) -> str:
    """Construct WB product image URL from product ID.

    WB uses a CDN with numbered baskets. The basket number is determined
    by the product ID range (vol = id // 100000).

    Args:
        product_id: WB product article number.
        photo_index: Image index (1-based).

    Returns:
        Direct URL to the product image on WB CDN.
    """
    vol = product_id // 100000
    part = product_id // 1000

    # Basket routing by vol ranges (from Duff89/wildberries_parser)
    basket_ranges = [
        (143, "01"), (287, "02"), (431, "03"), (719, "04"), (1007, "05"),
        (1061, "06"), (1115, "07"), (1169, "08"), (1313, "09"), (1601, "10"),
        (1655, "11"), (1919, "12"), (2045, "13"), (2189, "14"), (2405, "15"),
    ]
    basket = "16"
    for threshold, basket_num in basket_ranges:
        if vol <= threshold:
            basket = basket_num
            break

    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{product_id}/images/big/{photo_index}.webp"


# ---------------------------------------------------------------------------
# Enriched search (search + card details)
# ---------------------------------------------------------------------------

def wb_search_enriched(
    query: str,
    max_results: int = 5,
    min_rating: float = 4.0,
    fetch_details: bool = True,
) -> list[WBProduct]:
    """Search WB and optionally fetch detailed card data for each result.

    Combines wb_search() + wb_get_card_detail() for each product.
    Adds description, characteristics, and image URLs.
    Respects rate limiting with delays between detail requests.

    Args:
        query: Search query in Russian.
        max_results: Maximum number of products to return.
        min_rating: Minimum rating filter.
        fetch_details: Whether to fetch card details for each result.

    Returns:
        List of WBProduct objects with enriched detail fields.
    """
    products = wb_search(query, max_results=max_results, min_rating=min_rating)

    if not fetch_details or not products:
        return products

    for i, p in enumerate(products):
        if i > 0:
            time.sleep(WB_REQUEST_DELAY)  # Rate limit between detail requests

        detail = wb_get_card_detail(p.product_id)
        if detail:
            p.description = detail.get("description", "")
            p.composition = detail.get("composition", "")
            p.characteristics = detail.get("options", [])
            # Build image URLs
            pics_count = min(detail.get("pics", 0), 5)  # Max 5 images
            p.image_urls = [wb_get_image_url(p.product_id, i + 1) for i in range(pics_count)]

    return products


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_product(raw: dict) -> Optional[WBProduct]:
    """Parse a raw WB API product JSON into WBProduct.

    Args:
        raw: Raw product dict from WB search API response.

    Returns:
        WBProduct if parsing succeeds, None if critical fields are missing.
    """
    try:
        product_id = raw.get("id", 0)
        if not product_id:
            return None

        # Prices come multiplied by 100
        sale_price = raw.get("salePriceU", 0) // 100
        original_price = raw.get("priceU", 0) // 100

        return WBProduct(
            product_id=product_id,
            name=raw.get("name", ""),
            brand=raw.get("brand", ""),
            price=sale_price,
            original_price=original_price,
            rating=raw.get("rating", 0.0),
            feedbacks=raw.get("feedbacks", 0),
            url=f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx",
            pics=raw.get("pics", 0),
            sale_percent=raw.get("sale", 0),
        )
    except (TypeError, ValueError) as e:
        logger.warning("Failed to parse WB product: %s", e)
        return None
