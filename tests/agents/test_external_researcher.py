"""Tests for ExternalResearcherAgent -- competitor product card research.

Validates that the ExternalResearcherAgent can research competitor product
cards on external marketplaces and produce a CompetitorBenchmark with
DataProvenance entries. Phase 1 uses stub data; real scraping comes later.

Test strategy:
    Each test creates a ProductInput fixture and calls the agent's
    research() method. We verify the returned CompetitorBenchmark
    structure and DataProvenance entries without any external calls.
"""

import pytest

from sportmaster_card.agents.external_researcher import ExternalResearcherAgent
from sportmaster_card.models.enrichment import CompetitorBenchmark, CompetitorCard
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance, SourceType


@pytest.fixture
def sample_product() -> ProductInput:
    """Create a minimal ProductInput for testing the external researcher.

    Returns a footwear product with technologies filled in, so the
    stub competitor data can mirror them in key_features.
    """
    return ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Air Zoom Pegasus 41",
        technologies=["Air Zoom", "React"],
    )


@pytest.fixture
def empty_product() -> ProductInput:
    """Create a ProductInput with no technologies for empty-result testing.

    Used to verify that the agent handles products with no technologies
    gracefully (stub competitors will have empty key_features).
    """
    return ProductInput(
        mcm_id="MCM-EMPTY-001",
        brand="NoName",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Generic Shoe",
    )


@pytest.fixture
def agent() -> ExternalResearcherAgent:
    """Create an ExternalResearcherAgent instance for testing."""
    return ExternalResearcherAgent()


class TestExternalResearcherCreation:
    """Tests for ExternalResearcherAgent instantiation."""

    def test_external_researcher_creation(self):
        """ExternalResearcherAgent can be instantiated without arguments.

        The agent requires no configuration for Phase 1 (stub mode).
        In Phase 2, it will accept tool configurations for scraping.
        """
        agent = ExternalResearcherAgent()
        assert agent is not None


class TestExternalResearcherResearch:
    """Tests for the research() method output structure."""

    def test_research_returns_benchmark(self, agent, sample_product):
        """research() returns a CompetitorBenchmark as the first element.

        The benchmark must contain the same mcm_id as the input product
        and have at least one competitor card in Phase 1 stub mode.
        """
        benchmark, provenance = agent.research(sample_product)

        assert isinstance(benchmark, CompetitorBenchmark)
        assert benchmark.mcm_id == sample_product.mcm_id
        assert len(benchmark.competitors) >= 1

    def test_research_produces_provenance(self, agent, sample_product):
        """research() produces DataProvenance entries with source_type=EXTERNAL.

        Every provenance entry from the external researcher must be tagged
        as EXTERNAL source, since the data comes from competitor marketplaces.
        """
        benchmark, provenance = agent.research(sample_product)

        assert len(provenance) >= 1
        for entry in provenance:
            assert isinstance(entry, DataProvenance)
            assert entry.source_type == SourceType.EXTERNAL

    def test_research_with_no_results(self, agent):
        """research() returns empty benchmark when product has no stub matches.

        When _get_stub_competitors returns an empty list (simulating no
        competitors found), the benchmark should still be valid with
        empty competitors, None average_price, and empty common_features.
        """
        product = ProductInput(
            mcm_id="MCM-NICHE-999",
            brand="UnknownBrand",
            category="Обувь",
            product_group="Кроссовки",
            product_subgroup="Специальные кроссовки",
            product_name="Ultra Rare Shoe",
        )
        # Patch the stub to return empty
        agent._get_stub_competitors = lambda p: []

        benchmark, provenance = agent.research(product)

        assert isinstance(benchmark, CompetitorBenchmark)
        assert benchmark.mcm_id == product.mcm_id
        assert len(benchmark.competitors) == 0
        assert benchmark.average_price is None
        assert benchmark.common_features == []

    def test_benchmark_summary_not_empty(self, agent, sample_product):
        """benchmark_summary is populated with a non-empty description.

        The summary should contain meaningful text about the competitor
        research results, not be left blank or None.
        """
        benchmark, _ = agent.research(sample_product)

        assert benchmark.benchmark_summary
        assert len(benchmark.benchmark_summary) > 0


class TestExternalResearcherStubFallback:
    """Tests for stub fallback when no API keys are available."""

    def test_research_uses_stub_without_api_key(self, sample_product, monkeypatch):
        """Without API keys, research() uses stub mode."""
        monkeypatch.delenv("NEVEL_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        agent = ExternalResearcherAgent()
        benchmark, prov = agent.research(sample_product)
        assert benchmark.mcm_id == sample_product.mcm_id
        assert len(benchmark.competitors) >= 1  # Stub returns at least 1
