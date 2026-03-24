"""Crawl4AI-based marketplace search — headless browser parsing.

Uses Crawl4AI (headless Chromium) to load marketplace search pages,
wait for JS rendering, and extract product data from the rendered HTML.

This approach is specified in the v0.3 architecture document:
    "Парсинг конкурентов: Crawl4AI / Playwright + BeautifulSoup"

Advantages over direct API:
    - Bypasses API rate limiting (search.wb.ru 429 errors)
    - Bypasses anti-bot protections (Ozon 403)
    - Gets fully rendered pages with all product data
    - Works like a real browser

Supported marketplaces:
    - Wildberries (wildberries.ru)
    - Ozon (ozon.ru)
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CrawledProduct:
    """Product data extracted from a marketplace page via Crawl4AI."""
    platform: str
    product_id: str = ""
    name: str = ""
    brand: str = ""
    price: int = 0
    old_price: int = 0
    discount: str = ""
    rating: float = 0.0
    url: str = ""
    image_url: str = ""


def crawl_wb_search(query: str, max_results: int = 10) -> list[CrawledProduct]:
    """Search Wildberries using headless browser via Crawl4AI.

    Opens WB search page, waits for JS rendering, extracts product data
    from the rendered markdown.

    Args:
        query: Search query in Russian.
        max_results: Maximum products to return.

    Returns:
        List of CrawledProduct from WB search results.
    """
    try:
        return asyncio.run(_crawl_wb_async(query, max_results))
    except RuntimeError:
        # Already in async context — use nest_asyncio or thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(lambda: asyncio.run(_crawl_wb_async(query, max_results)))
            return future.result(timeout=60)


async def _crawl_wb_async(query: str, max_results: int) -> list[CrawledProduct]:
    """Async implementation of WB search crawl."""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        wait_until="networkidle",
        delay_before_return_html=6.0,
    )

    url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={query.replace(' ', '+')}"

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        md = result.markdown.raw_markdown if result.markdown else ""
        logger.info("WB crawl: %d chars markdown for '%s'", len(md), query)
        return _parse_wb_markdown(md, max_results)


def _parse_wb_markdown(md: str, max_results: int) -> list[CrawledProduct]:
    """Parse WB search results from Crawl4AI markdown output.

    Real WB markdown format (from Crawl4AI):
        [](https://www.wildberries.ru/catalog/494934114/detail.aspx)
        ![Беговая дорожка T-165 Shape Torneo](https://basket-27.wbbasket.ru/.../494934114/images/...)
        −40%
        22 948 ₽0~~38 847 ₽~~ −40%
        ##  Torneo / Беговая дорожка T-165 Shape
        51 оценка
    """
    products = []

    # Pattern 1: detail link with product ID
    detail_pattern = re.compile(r'wildberries\.ru/catalog/(\d{6,12})/detail')

    # Pattern 2: product image with alt text and ID in URL
    image_pattern = re.compile(
        r'!\[([^\]]+)\]\(https://basket[^)]*?/(\d{6,12})/images/[^)]+\)'
    )

    # Price: "22 948 ₽" — first price on a line (current price)
    price_pattern = re.compile(r'(\d[\d\s\xa0]*)\s*₽')

    # Old price: ~~38 847 ₽~~
    old_price_pattern = re.compile(r'~~(\d[\d\s\xa0]*)\s*₽~~')

    # Brand/name: "## Torneo / Беговая дорожка T-165 Shape"
    brand_pattern = re.compile(r'##\s+([^/\n]+?)\s*/\s*(.+?)$', re.MULTILINE)

    # Discount: "−40%" or "-40%"
    discount_pattern = re.compile(r'[−\-](\d+)%')

    # Reviews: "51 оценка" or "123 оценки"
    reviews_pattern = re.compile(r'(\d+)\s+оценк')

    lines = md.split('\n')
    current_product = None

    for line in lines:
        # Check for detail link (starts a new product block)
        detail_match = detail_pattern.search(line)
        if detail_match and '![' not in line:
            # Save previous product
            if current_product and current_product.name:
                products.append(current_product)
                if len(products) >= max_results:
                    break

            pid = detail_match.group(1)
            current_product = CrawledProduct(
                platform="wb",
                product_id=pid,
                url=f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
            )
            continue

        # Check for product image (also contains product ID and name)
        img_match = image_pattern.search(line)
        if img_match:
            alt_text = img_match.group(1)
            pid = img_match.group(2)
            if current_product and current_product.product_id == pid:
                current_product.name = alt_text
                current_product.image_url = line.split('(')[1].rstrip(')') if '(' in line else ''
            elif not current_product or current_product.product_id != pid:
                if current_product and current_product.name:
                    products.append(current_product)
                    if len(products) >= max_results:
                        break
                current_product = CrawledProduct(
                    platform="wb",
                    product_id=pid,
                    name=alt_text,
                    url=f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
                )
            continue

        if not current_product:
            continue

        # Price line
        price_match = price_pattern.search(line)
        if price_match and current_product.price == 0:
            price_str = price_match.group(1).replace(' ', '').replace('\xa0', '')
            try:
                current_product.price = int(price_str)
            except ValueError:
                pass

            old_match = old_price_pattern.search(line)
            if old_match:
                old_str = old_match.group(1).replace(' ', '').replace('\xa0', '')
                try:
                    current_product.old_price = int(old_str)
                except ValueError:
                    pass

            disc = discount_pattern.search(line)
            if disc:
                current_product.discount = f"-{disc.group(1)}%"

        # Brand / Name line
        brand_match = brand_pattern.search(line)
        if brand_match:
            current_product.brand = brand_match.group(1).strip()
            current_product.name = brand_match.group(2).strip()

        # Reviews
        rev_match = reviews_pattern.search(line)
        if rev_match:
            try:
                current_product.rating = float(rev_match.group(1))  # store review count in rating temporarily
            except ValueError:
                pass

    # Last product
    if current_product and current_product.name:
        products.append(current_product)

    logger.info("WB crawl parsed %d products", len(products))
    return products[:max_results]


def crawl_ozon_search(query: str, max_results: int = 10) -> list[CrawledProduct]:
    """Search Ozon using headless browser via Crawl4AI."""
    try:
        return asyncio.run(_crawl_ozon_async(query, max_results))
    except RuntimeError:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(lambda: asyncio.run(_crawl_ozon_async(query, max_results)))
            return future.result(timeout=60)


async def _crawl_ozon_async(query: str, max_results: int) -> list[CrawledProduct]:
    """Async Ozon search crawl."""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        wait_until="networkidle",
        delay_before_return_html=6.0,
    )

    encoded = query.replace(' ', '+')
    url = f"https://www.ozon.ru/search/?text={encoded}&from_global=true"

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        md = result.markdown.raw_markdown if result.markdown else ""
        logger.info("Ozon crawl: %d chars markdown for '%s'", len(md), query)
        return _parse_ozon_markdown(md, max_results)


def _parse_ozon_markdown(md: str, max_results: int) -> list[CrawledProduct]:
    """Parse Ozon search results from markdown."""
    products = []

    # Ozon product links: [Product Name](https://www.ozon.ru/product/slug-PRODUCT_ID/)
    link_pattern = re.compile(
        r'\[([^\]]{10,200})\]\(https://www\.ozon\.ru/product/[^)]*?(\d{6,12})[^)]*\)'
    )

    price_pattern = re.compile(r'(\d[\d\s]*)\s*₽')

    for match in link_pattern.finditer(md):
        name = match.group(1).strip()
        product_id = match.group(2)

        # Skip navigation links
        if len(name) < 15 or name.startswith('Ещё') or name.startswith('Показать'):
            continue

        product = CrawledProduct(
            platform="ozon",
            product_id=product_id,
            name=name,
            url=f"https://www.ozon.ru/product/{product_id}/",
        )

        # Try to find price near this match
        context = md[match.start():match.start() + 500]
        price_match = price_pattern.search(context)
        if price_match:
            price_str = price_match.group(1).replace(' ', '').replace('\xa0', '')
            try:
                product.price = int(price_str)
            except ValueError:
                pass

        products.append(product)
        if len(products) >= max_results:
            break

    logger.info("Ozon crawl parsed %d products", len(products))
    return products
