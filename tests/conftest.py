"""Shared pytest fixtures for the Sportmaster Card Agent test suite.

Provides reusable test data and mock objects:
- sample_product_input: valid Nike running shoe ProductInput
- sample_routing_profile: 1P Basic routing to SM site
- sample_platform_profile_sm: SM website PlatformProfile
- sample_validation_report: valid ValidationReport
- sample_competitor_benchmark: CompetitorBenchmark with 2 competitors
- sample_content_brief: ContentBrief for SM site
- mock_llm_response: fixture that patches CrewAI LLM to return canned responses
"""

import os

import pytest


@pytest.fixture
def sample_product_input():
    """A valid Nike running shoe -- the canonical test product.

    Returns a ProductInput representing Nike Air Zoom Pegasus 41,
    a mid-tier running shoe in the TRD segment. This product is
    used as the baseline across all agent tests.
    """
    from sportmaster_card.models.product_input import ProductInput

    return ProductInput(
        mcm_id="MCM-TEST-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        description="Беговые кроссовки с технологией Air Zoom для ежедневных тренировок",
        gender="Мужской",
        season="Весна-Лето 2026",
        color="Чёрный",
        assortment_segment="TRD",
        assortment_type="Basic",
        assortment_level="Mid",
        technologies=["Air Zoom", "Flywire", "React"],
        composition={"Верх": "Текстиль 80%, синтетика 20%", "Подошва": "Резина"},
        photo_urls=["https://example.com/pegasus41_1.jpg"],
    )


@pytest.fixture
def sample_routing_profile():
    """1P Basic routing targeting only SM site.

    Represents the simplest routing decision: a Basic product
    going through the full 1P pipeline for the SM website only.
    """
    from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile

    return RoutingProfile(
        mcm_id="MCM-TEST-001-BLK-42",
        flow_type=FlowType.FIRST_PARTY,
        processing_profile=ProcessingProfile.STANDARD,
        target_platforms=["sm_site"],
        attribute_class="footwear.running",
    )


@pytest.fixture
def sample_platform_profile_sm():
    """SM website PlatformProfile loaded from YAML config.

    Uses the actual sm_site.yaml config file to ensure
    test fixtures match real configuration.
    """
    from sportmaster_card.models.platform_profile import PlatformProfile

    yaml_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
        "sportmaster_card",
        "config",
        "platforms",
        "sm_site.yaml",
    )
    return PlatformProfile.from_yaml(yaml_path)


@pytest.fixture
def sample_validation_report():
    """Valid ValidationReport for the test product.

    Shows a product with 80% completeness -- description present
    but composition details need enrichment.
    """
    from sportmaster_card.models.enrichment import FieldValidation, ValidationReport

    return ValidationReport(
        mcm_id="MCM-TEST-001-BLK-42",
        field_validations=[
            FieldValidation(field_name="mcm_id", is_present=True, is_valid=True),
            FieldValidation(field_name="brand", is_present=True, is_valid=True),
            FieldValidation(field_name="category", is_present=True, is_valid=True),
            FieldValidation(field_name="description", is_present=True, is_valid=True),
            FieldValidation(
                field_name="composition",
                is_present=True,
                is_valid=False,
                issue="Неполный состав",
            ),
        ],
        missing_required=[],
        overall_completeness=0.8,
        is_valid=True,
        notes=["Состав материалов требует дополнения"],
    )


@pytest.fixture
def sample_competitor_benchmark():
    """CompetitorBenchmark with 2 competitor cards from WB and Ozon.

    Provides realistic competitor data for testing enrichment agents
    that rely on competitive intelligence for gap analysis and
    content inspiration.
    """
    from sportmaster_card.models.enrichment import CompetitorBenchmark, CompetitorCard

    return CompetitorBenchmark(
        mcm_id="MCM-TEST-001-BLK-42",
        competitors=[
            CompetitorCard(
                platform="wb",
                product_name="Nike Air Zoom Pegasus 41 Мужские",
                description="Беговые кроссовки Nike с амортизацией Air Zoom",
                price=12990.0,
                rating=4.7,
                key_features=["Air Zoom", "Дышащий верх", "Гибкая подошва"],
            ),
            CompetitorCard(
                platform="ozon",
                product_name="Кроссовки Nike Pegasus 41",
                description="Универсальные беговые кроссовки для ежедневных тренировок",
                price=11990.0,
                rating=4.5,
                key_features=["React пена", "Flywire", "Подошва Waffle"],
            ),
        ],
        benchmark_summary="Средняя цена ~12500₽, акцент на амортизацию и дышащий верх",
        average_price=12490.0,
        common_features=["Air Zoom", "Дышащий верх"],
    )


@pytest.fixture
def sample_content_brief():
    """ContentBrief for SM site -- standard footwear brief.

    Represents a typical content generation brief for a running shoe
    on the Sportmaster website, with professional tone and all
    standard sections required.
    """
    from sportmaster_card.models.content import ContentBrief

    return ContentBrief(
        mcm_id="MCM-TEST-001-BLK-42",
        platform_id="sm_site",
        brief_type="standard",
        tone_of_voice="professional",
        required_sections=["description", "benefits", "technologies", "composition"],
        max_description_length=3000,
        max_title_length=150,
    )


@pytest.fixture
def mock_llm_response(monkeypatch):
    """Patches CrewAI to avoid real LLM API calls in unit tests.

    Returns a helper function that sets the canned response text.
    Usage in tests::

        def test_something(mock_llm_response):
            mock_llm_response("Expected agent output text")
            # ... run agent ...

    The fixture sets two environment variables that test-aware code
    can check to short-circuit real API calls:
    - CREWAI_TEST_MODE: set to "true" to signal test mode
    - CREWAI_TEST_RESPONSE: the canned response text to return
    """

    def _set_response(text: str):
        """Configure the mock to return the given text.

        Args:
            text: The canned response string that the mocked LLM
                should return when called by any CrewAI agent.
        """
        monkeypatch.setenv("CREWAI_TEST_MODE", "true")
        monkeypatch.setenv("CREWAI_TEST_RESPONSE", text)

    return _set_response
