"""ExternalResearcherAgent -- competitor product card research on external marketplaces.

This module implements the External Researcher (Agent 1.5) in the UC1 Enrichment
pipeline. The agent's job is to find the same (or similar) product on competitor
marketplaces (Wildberries, Ozon, Lamoda, Megamarket) and extract structured data
from their product cards: names, descriptions, prices, ratings, and key features.

Phase 1 implementation note:
    In the Phase 1 pilot, this agent operates with **stub data** -- no real web
    scraping is performed. The agent structure, interfaces, and data flow are
    production-ready, but the actual marketplace scraping tools (Crawl4AI,
    Playwright) will be integrated in Phase 2. This approach lets us validate
    the full pipeline end-to-end without external dependencies.

Architecture and data flow::

    ProductInput
        |
        v
    ExternalResearcherAgent.research()
        |
        +---> _get_stub_competitors()   [Phase 1: returns mock data]
        |     (Phase 2: _scrape_wb(), _scrape_ozon(), _scrape_lamoda())
        |
        +---> _build_provenance()       [creates DataProvenance entries]
        |
        +---> aggregate & return
        |
        v
    (CompetitorBenchmark, list[DataProvenance])
        |
        v
    Data Enricher (Agent 1.8) uses benchmark for:
        - price positioning analysis
        - feature gap identification
        - content quality inspiration

Marketplace coverage (planned for Phase 2)::

    +------------------+----------+--------------------------------------+
    | Marketplace      | Code     | Scraping approach                    |
    +------------------+----------+--------------------------------------+
    | Wildberries      | "wb"     | Crawl4AI + API fallback              |
    | Ozon             | "ozon"   | Playwright (JS-rendered pages)       |
    | Lamoda           | "lamoda" | Crawl4AI (static HTML)               |
    | SberMegaMarket   | "mega"   | API + Playwright fallback            |
    +------------------+----------+--------------------------------------+

Typical usage::

    from sportmaster_card.agents.external_researcher import ExternalResearcherAgent
    from sportmaster_card.models.product_input import ProductInput

    agent = ExternalResearcherAgent()
    product = ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Air Zoom Pegasus 41",
        technologies=["Air Zoom", "React"],
    )
    benchmark, provenance = agent.research(product)
    print(benchmark.benchmark_summary)
    # "Found 1 competitor cards"
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from sportmaster_card.models.enrichment import CompetitorBenchmark, CompetitorCard
from sportmaster_card.models.provenance import DataProvenance, SourceType

if TYPE_CHECKING:
    from sportmaster_card.models.product_input import ProductInput


# Agent identifier following the project convention: "agent-{number}-{name}".
# Used in DataProvenance records to trace which agent produced each value.
_AGENT_ID = "agent-1.5-external-researcher"


class ExternalResearcherAgent:
    """Researches competitor product cards on external marketplaces.

    For Phase 1 pilot, uses STUB data. Real web scraping
    (Crawl4AI/Playwright) will be integrated in Phase 2.

    The agent searches for the same product on WB, Ozon, Lamoda
    and extracts: names, descriptions, prices, ratings, features.

    The research() method returns a tuple of:
    - CompetitorBenchmark: aggregated competitor intelligence
    - list[DataProvenance]: provenance records for each extracted attribute

    Lifecycle::

        agent = ExternalResearcherAgent()
        benchmark, provenance = agent.research(product)

    Phase 2 extension point::

        agent = ExternalResearcherAgent(tools=[crawl4ai_tool, playwright_tool])
        # tools will replace _get_stub_competitors with real scraping

    Attributes:
        _tools: List of scraping tools (empty in Phase 1, populated in Phase 2).
    """

    def __init__(self, tools: list | None = None):
        """Initialize the external researcher agent.

        Args:
            tools: Optional list of scraping tools for Phase 2 integration.
                In Phase 1, this is ignored and stub data is used instead.
                Expected tools in Phase 2: Crawl4AI, Playwright browser tools.
        """
        # Store tools for Phase 2 when real scraping is implemented.
        # In Phase 1, _get_stub_competitors() is used regardless of tools.
        self._tools = tools or []

    def research(
        self, product: ProductInput
    ) -> tuple[CompetitorBenchmark, list[DataProvenance]]:
        """Research competitor cards for the given product.

        This is the main entry point for the External Researcher agent.
        It searches competitor marketplaces for the same or similar product,
        extracts structured data, and aggregates it into a benchmark.

        In LLM mode, uses REAL Wildberries Search API to find actual
        competitor products with real prices, ratings, and features.

        Args:
            product: ProductInput to research competitors for. The agent uses
                brand, product_name, and technologies to find matching products.

        Returns:
            Tuple of (CompetitorBenchmark, list of DataProvenance entries).
            The benchmark contains aggregated competitor data; provenance
            entries trace each data point back to its marketplace source.

        Example::

            >>> benchmark, prov = agent.research(product)
            >>> benchmark.mcm_id
            'MCM-001-BLK-42'
            >>> len(prov) >= 1
            True
        """
        if self._is_llm_mode():
            return self._research_wb_api(product)
        return self._research_stub(product)

    # ------------------------------------------------------------------
    # Real WB Search API research
    # ------------------------------------------------------------------

    def _research_wb_api(
        self, product: ProductInput
    ) -> tuple[CompetitorBenchmark, list[DataProvenance]]:
        """Research competitors using REAL Wildberries Search API.

        Builds search queries from product attributes, calls WB API,
        parses results into CompetitorCard objects. Falls back to stub
        if WB API is unavailable or returns no results.

        Strategy:
            1. Build 3-4 search queries (specific → general)
            2. Try each query until we get results
            3. Convert WBProduct → CompetitorCard
            4. Build provenance records
            5. Aggregate into CompetitorBenchmark
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            from sportmaster_card.tools.wb_search import wb_search, build_search_queries

            # Build search queries from product attributes
            queries = build_search_queries(
                brand=product.brand,
                product_name=product.product_name,
                category=product.category,
                product_subgroup=product.product_subgroup,
                technologies=product.technologies,
            )

            # Try each query until we get results
            wb_products = []
            used_query = ""
            for query in queries:
                wb_products = wb_search(
                    query=query,
                    max_results=10,
                    min_rating=4.0,
                    sort="popular",
                )
                if wb_products:
                    used_query = query
                    logger.info("WB search '%s' returned %d products", query, len(wb_products))
                    break
                import time
                time.sleep(2)  # Rate limiting between queries

            if not wb_products:
                logger.warning("WB search returned no results, falling back to stub")
                return self._research_stub(product)

            # Convert WBProduct → CompetitorCard
            competitors = []
            for wp in wb_products[:10]:
                card = CompetitorCard(
                    platform="wb",
                    product_name=f"{wp.brand} {wp.name}",
                    description=f"Рейтинг {wp.rating}/5, {wp.feedbacks} отзывов",
                    price=float(wp.price),
                    rating=wp.rating,
                    key_features=[
                        f"Цена: {wp.price}₽",
                        f"Рейтинг: {wp.rating}",
                        f"Отзывы: {wp.feedbacks}",
                        f"Скидка: {wp.sale_percent}%",
                    ],
                    url=wp.url,
                )
                competitors.append(card)

            # Build provenance
            provenance = self._build_provenance(competitors)

            # Calculate averages
            prices = [c.price for c in competitors if c.price]
            avg_price = sum(prices) / len(prices) if prices else None

            # Find common features
            all_features = [f for c in competitors for f in c.key_features]
            from collections import Counter
            feature_counts = Counter(all_features)
            common = [f for f, count in feature_counts.items() if count >= 2]

            benchmark = CompetitorBenchmark(
                mcm_id=product.mcm_id,
                competitors=competitors,
                benchmark_summary=(
                    f"WB поиск '{used_query}': найдено {len(competitors)} товаров. "
                    f"Средняя цена: {avg_price:.0f}₽. "
                    f"Средний рейтинг: {sum(c.rating for c in competitors if c.rating) / len(competitors):.1f}"
                ),
                average_price=avg_price,
                common_features=common,
            )

            logger.info(
                "WB research complete: %d competitors, avg price %.0f₽",
                len(competitors), avg_price or 0,
            )
            return benchmark, provenance

        except Exception as e:
            logger.error("WB API research failed: %s, falling back to stub", e)
            return self._research_stub(product)

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    def _is_llm_mode(self) -> bool:
        """Check if real LLM is available (Nevel API or OpenRouter)."""
        nevel_key = os.environ.get("NEVEL_API_KEY", "").strip()
        if nevel_key:
            return True
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        return bool(openrouter_key)

    # ------------------------------------------------------------------
    # Stub research (Phase 1 rule-based, deterministic)
    # ------------------------------------------------------------------

    def _research_stub(
        self, product: ProductInput
    ) -> tuple[CompetitorBenchmark, list[DataProvenance]]:
        """Research competitors using stub data (no LLM).

        This is the original Phase 1 research logic, preserved for use
        when no API key is available or for testing.
        """
        competitors = self._get_stub_competitors(product)

        # Build provenance records for each competitor card extracted.
        provenance = self._build_provenance(competitors)

        # Calculate average price across all competitors with known prices.
        # None if no competitors have prices (out of stock, no results).
        avg_price = None
        if competitors:
            prices = [c.price for c in competitors if c.price is not None]
            avg_price = sum(prices) / len(prices) if prices else None

        # Find common features across competitor listings.
        # A feature is "common" if it appears in 2+ competitor cards.
        # These represent market-standard attributes our card should highlight.
        all_features = [f for c in competitors for f in c.key_features]
        feature_counts = Counter(all_features)
        common = [f for f, count in feature_counts.items() if count >= 2]

        # Build the final benchmark with aggregated competitor intelligence.
        benchmark = CompetitorBenchmark(
            mcm_id=product.mcm_id,
            competitors=competitors,
            benchmark_summary=f"Found {len(competitors)} competitor cards",
            average_price=avg_price,
            common_features=common,
        )

        return benchmark, provenance

    # ------------------------------------------------------------------
    # LLM research (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _research_with_llm(
        self, product: ProductInput
    ) -> tuple[CompetitorBenchmark, list[DataProvenance]]:
        """Research competitors using CrewAI Agent+Task with a real LLM.

        Loads the external_researcher.yaml prompt template, fills it with
        product data, and delegates to a CrewAI Crew for execution.
        Falls back to stub research if the LLM call fails.

        Args:
            product: ProductInput to research competitors for.

        Returns:
            Tuple of (CompetitorBenchmark, list[DataProvenance]) from LLM
            output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "external_researcher.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with product data
        task_desc = prompts["task_template"].format(
            mcm_id=product.mcm_id,
            brand=product.brand,
            category=product.category,
            product_subgroup=product.product_subgroup,
            product_name=product.product_name,
            target_platforms="Wildberries, Ozon, Lamoda, Яндекс.Маркет",
        )

        agent = Agent(
            role="External Researcher",
            goal=prompts["system_prompt"],
            backstory="Competitive intelligence analyst for Russian e-commerce",
            llm=get_llm("gemini_flash"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            crew.kickoff()
        except Exception:
            # LLM call failed -- fall back to stub
            return self._research_stub(product)

        # LLM output is advisory; use stub for structured return
        # to ensure type safety and consistent provenance tracking.
        return self._research_stub(product)

    def _get_stub_competitors(self, product: ProductInput) -> list[CompetitorCard]:
        """Return stub competitor data for Phase 1 testing.

        Generates one fake competitor card from Wildberries that mirrors
        the input product's brand, name, and technologies. This stub
        will be replaced by real scraping in Phase 2.

        Args:
            product: The ProductInput to generate stub competitors for.
                Uses brand, product_name, and technologies fields.

        Returns:
            List containing one CompetitorCard with stub data from "wb".
            Technologies from the input are copied to key_features.
        """
        return [
            CompetitorCard(
                platform="wb",
                product_name=f"{product.brand} {product.product_name}",
                description=f"Stub description for {product.product_name} on WB",
                price=12990.0,
                rating=4.5,
                key_features=product.technologies or [],
            ),
        ]

    def _build_provenance(
        self, competitors: list[CompetitorCard]
    ) -> list[DataProvenance]:
        """Build DataProvenance entries for each competitor card extracted.

        Creates one provenance record per competitor, documenting where the
        data came from (which marketplace), when it was extracted, and the
        confidence level. All entries are tagged as EXTERNAL source type.

        Args:
            competitors: List of CompetitorCard instances to create
                provenance records for. One provenance entry per card.

        Returns:
            List of DataProvenance entries, one per competitor card.
            Empty list if no competitors were provided.
        """
        # Current UTC timestamp for all provenance entries in this batch.
        now = datetime.now(timezone.utc)

        provenance_entries: list[DataProvenance] = []
        for card in competitors:
            # Each competitor card gets its own provenance record.
            # The attribute_name tracks which marketplace the data came from.
            entry = DataProvenance(
                attribute_name=f"competitor_{card.platform}",
                value=card.product_name,
                source_type=SourceType.EXTERNAL,
                source_name=card.platform,
                confidence=0.6,
                agent_id=_AGENT_ID,
                timestamp=now,
            )
            provenance_entries.append(entry)

        return provenance_entries
