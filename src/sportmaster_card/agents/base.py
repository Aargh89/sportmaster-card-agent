"""Base agent factory for creating CrewAI agents from YAML configuration.

All agents in the system are created through this factory. Agent definitions
(role, goal, backstory, model assignment) live in agents.yaml -- not in code.
This separation allows non-developers to adjust agent behavior.

Architecture:
    +---------------+     +----------------+     +---------------+
    | agents.yaml   | --> | AgentFactory   | --> | CrewAI Agent  |
    | (config)      |     | .create()      |     | (runtime)     |
    +---------------+     +----------------+     +---------------+
"""

import yaml
from crewai import Agent
from pathlib import Path
from typing import Any


class BaseAgentFactory:
    """Factory for creating CrewAI agents from YAML configuration.

    Loads agent definitions from a YAML file and creates configured
    Agent instances. Each agent definition includes:
    - role: the agent's role description
    - goal: what the agent aims to achieve
    - backstory: context and expertise background
    - model: which LLM to use (mapped via llm_config)
    - verbose: whether to log agent actions

    Example:
        >>> factory = BaseAgentFactory("config/agents.yaml")
        >>> router = factory.create("router")
        >>> router.role
        'Product Router'
    """

    def __init__(self, config_path: str | Path):
        """Initialize factory with path to agents YAML config.

        Args:
            config_path: Path to agents.yaml file.

        Raises:
            FileNotFoundError: If config file doesn't exist.
        """
        self._config_path = Path(config_path)
        with open(self._config_path, "r", encoding="utf-8") as f:
            self._configs: dict[str, Any] = yaml.safe_load(f)

    def create(
        self,
        agent_name: str,
        tools: list | None = None,
        llm: Any | None = None,
    ) -> Agent:
        """Create a CrewAI Agent from YAML configuration.

        Args:
            agent_name: Key in agents.yaml (e.g., "router", "data_validator").
            tools: Optional list of CrewAI tools to attach.
            llm: Optional LLM instance. If None, uses default.

        Returns:
            Configured CrewAI Agent instance.

        Raises:
            KeyError: If agent_name not found in config.

        Example:
            >>> agent = factory.create("router")
            >>> agent.role
            'Product Router'
        """
        if agent_name not in self._configs:
            raise KeyError(
                f"Agent '{agent_name}' not found in {self._config_path}. "
                f"Available: {list(self._configs.keys())}"
            )

        config = self._configs[agent_name]

        agent_kwargs = {
            "role": config["role"],
            "goal": config["goal"],
            "backstory": config["backstory"],
            "verbose": config.get("verbose", True),
            "allow_delegation": config.get("allow_delegation", False),
        }

        if tools:
            agent_kwargs["tools"] = tools
        if llm:
            agent_kwargs["llm"] = llm

        return Agent(**agent_kwargs)
