"""Tests for BaseAgentFactory -- YAML-driven agent creation.

Validates that the factory correctly loads agent configuration from
YAML files and creates properly configured CrewAI Agent instances.

Test strategy:
    Each test uses a temporary YAML file (via tmp_path) to isolate
    config loading from the real agents.yaml. This ensures tests
    don't break when production config changes.
"""

import os

import pytest
import yaml
from crewai import Agent

from sportmaster_card.agents.base import BaseAgentFactory


@pytest.fixture(autouse=True)
def _fake_openai_key(monkeypatch):
    """Set a dummy OPENAI_API_KEY so CrewAI Agent can instantiate without a real key.

    CrewAI validates the presence of an API key at Agent creation time.
    We provide a fake one since unit tests never make actual LLM calls.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-test-key-for-unit-tests")


@pytest.fixture
def agent_yaml(tmp_path):
    """Create a temporary agents.yaml with test agent definitions.

    Returns the path to a YAML file containing two agent configs:
    'router' (a product routing agent) and 'validator' (a data
    validation agent). Both have role, goal, backstory, and verbose.
    """
    config = {
        "router": {
            "role": "Product Router",
            "goal": "Route products to correct processing pipelines",
            "backstory": "Expert in product classification and routing logic.",
            "verbose": False,
        },
        "validator": {
            "role": "Data Validator",
            "goal": "Validate product data completeness and correctness",
            "backstory": "Meticulous data quality specialist.",
            "verbose": True,
        },
    }
    yaml_file = tmp_path / "agents.yaml"
    yaml_file.write_text(yaml.dump(config, allow_unicode=True), encoding="utf-8")
    return yaml_file


def test_load_agent_config_from_yaml(agent_yaml):
    """Factory loads all agent config dicts from the YAML file.

    After initialization, the factory's internal config should contain
    both 'router' and 'validator' keys with their full definitions.
    """
    factory = BaseAgentFactory(agent_yaml)
    assert "router" in factory._configs
    assert "validator" in factory._configs
    assert factory._configs["router"]["role"] == "Product Router"


def test_create_agent_with_config(agent_yaml):
    """Factory.create() returns a CrewAI Agent with role, goal, backstory.

    The returned object must be an instance of crewai.Agent and carry
    the configuration values specified in the YAML file.
    """
    factory = BaseAgentFactory(agent_yaml)
    agent = factory.create("router")
    assert isinstance(agent, Agent)
    assert agent.goal == "Route products to correct processing pipelines"
    assert agent.backstory == "Expert in product classification and routing logic."


def test_agent_has_correct_role(agent_yaml):
    """Agent.role matches the role string defined in YAML config.

    Verifies that the role attribute is passed through accurately
    from YAML config to the CrewAI Agent constructor.
    """
    factory = BaseAgentFactory(agent_yaml)
    agent = factory.create("router")
    assert agent.role == "Product Router"


def test_agent_config_not_found(agent_yaml):
    """Factory raises KeyError when asked for a non-existent agent name.

    The error message should include the requested name and available
    agent names to help with debugging configuration issues.
    """
    factory = BaseAgentFactory(agent_yaml)
    with pytest.raises(KeyError, match="nonexistent"):
        factory.create("nonexistent")
