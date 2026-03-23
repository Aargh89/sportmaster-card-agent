"""Tests for RouterAgent -- deterministic product routing logic.

Validates that RouterAgent correctly classifies products based on
assortment_type and assortment_level fields, producing the expected
ProcessingProfile for each combination. Also verifies factory
instantiation and CrewAI task creation.

Test strategy:
    All routing logic is deterministic (rule-based). No LLM calls are
    needed or mocked. Tests use ProductInput fixtures with varying
    assortment fields to exercise each routing path.
"""

import os

import pytest
import yaml
from crewai import Agent, Task

from sportmaster_card.agents.base import BaseAgentFactory
from sportmaster_card.agents.router import RouterAgent
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile


@pytest.fixture(autouse=True)
def _fake_openai_key(monkeypatch):
    """Set a dummy OPENAI_API_KEY so CrewAI Agent can instantiate without a real key.

    CrewAI validates the presence of an API key at Agent creation time.
    We provide a fake one since unit tests never make actual LLM calls.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key-for-unit-tests")


@pytest.fixture
def agent_yaml(tmp_path):
    """Create a temporary agents.yaml with a router agent definition.

    Returns the path to a YAML file containing a 'router' config
    matching the production schema (role, goal, backstory, verbose).
    """
    config = {
        "router": {
            "role": "Product Router",
            "goal": "Classify products and select processing pipelines.",
            "backstory": "Expert product classifier at Sportmaster.",
            "verbose": False,
        },
    }
    yaml_file = tmp_path / "agents.yaml"
    yaml_file.write_text(yaml.dump(config, allow_unicode=True), encoding="utf-8")
    return yaml_file


def _make_product(**overrides) -> ProductInput:
    """Build a ProductInput with sensible defaults, overriding as needed.

    Provides required fields so tests only need to specify the fields
    relevant to the routing logic under test (assortment_type, assortment_level).
    """
    defaults = {
        "mcm_id": "MCM-TEST-001",
        "brand": "TestBrand",
        "category": "Обувь",
        "product_group": "Кроссовки",
        "product_subgroup": "Беговые кроссовки",
        "product_name": "Test Runner 5",
    }
    defaults.update(overrides)
    return ProductInput(**defaults)


# ---- Test 1: Factory instantiation ----------------------------------------


def test_router_agent_creation(agent_yaml):
    """RouterAgent can be instantiated from BaseAgentFactory.

    The factory should load the 'router' config from YAML and the
    RouterAgent class should accept the resulting CrewAI Agent instance.
    """
    factory = BaseAgentFactory(agent_yaml)
    crewai_agent = factory.create("router")
    router = RouterAgent(agent=crewai_agent)
    assert router.agent is not None
    assert router.agent.role == "Product Router"


# ---- Test 2: Task creation -------------------------------------------------


def test_router_creates_routing_task(agent_yaml):
    """RouterAgent.create_task() returns a CrewAI Task with correct description.

    The returned Task must reference the MCM ID in its description and
    be assigned to the router's underlying CrewAI agent.
    """
    factory = BaseAgentFactory(agent_yaml)
    crewai_agent = factory.create("router")
    router = RouterAgent(agent=crewai_agent)

    product = _make_product(mcm_id="MCM-TASK-777")
    task = router.create_task(product)

    assert isinstance(task, Task)
    assert "MCM-TASK-777" in task.description


# ---- Test 3: Basic + Low -> MINIMAL ----------------------------------------


def test_routing_logic_basic_1p():
    """Basic assortment_type + Low assortment_level routes to MINIMAL profile.

    This is the lightest processing path: template content, minimal enrichment.
    Per the routing matrix, Basic+Low -> ProcessingProfile.MINIMAL.
    """
    router = RouterAgent()
    product = _make_product(assortment_type="Basic", assortment_level="Low")
    profile = router.route(product)

    assert profile.processing_profile == ProcessingProfile.MINIMAL
    assert profile.flow_type == FlowType.FIRST_PARTY
    assert profile.mcm_id == "MCM-TEST-001"


# ---- Test 4: Premium level -> PREMIUM --------------------------------------


def test_routing_logic_premium_1p():
    """Premium assortment_level routes to PREMIUM profile regardless of type.

    High-value products get deep enrichment and polished content.
    Per the routing matrix, any type + Premium -> ProcessingProfile.PREMIUM.
    """
    router = RouterAgent()
    product = _make_product(assortment_type="Fashion", assortment_level="Premium")
    profile = router.route(product)

    assert profile.processing_profile == ProcessingProfile.PREMIUM
    assert profile.flow_type == FlowType.FIRST_PARTY


# ---- Test 5: Mid level -> STANDARD -----------------------------------------


def test_routing_logic_mid_1p():
    """Mid assortment_level routes to STANDARD profile.

    Standard processing: balanced enrichment and decent content quality.
    Per the routing matrix, any type + Mid -> ProcessingProfile.STANDARD.
    """
    router = RouterAgent()
    product = _make_product(assortment_type="Seasonal", assortment_level="Mid")
    profile = router.route(product)

    assert profile.processing_profile == ProcessingProfile.STANDARD
    assert profile.flow_type == FlowType.FIRST_PARTY
    assert "sm_site" in profile.target_platforms
