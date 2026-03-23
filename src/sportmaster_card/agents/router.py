"""Router Agent -- classifies products and selects processing pipeline.

The Router is the ENTRY POINT of the multi-agent pipeline. It receives
a ProductInput and produces a RoutingProfile that determines:
- Which flow to use (1P full pipeline vs 3P lightweight validation)
- Which processing depth (minimal/standard/premium/complex)
- Which platforms to generate content for

Routing logic from v0.3 architecture:

    +---------------------------------------------+
    | Step 1: Determine flow type                 |
    |   type = 3P -> FlowType.THIRD_PARTY        |
    |   type = 1P -> FlowType.FIRST_PARTY        |
    +---------------------------------------------+
    | Step 2: Determine processing profile        |
    |   Basic + Low  -> MINIMAL                   |
    |   Mid          -> STANDARD                  |
    |   High/Premium -> PREMIUM                   |
    |   Complex      -> COMPLEX                   |
    +---------------------------------------------+
    | Step 3: Determine attribute class            |
    |   category.product_group                    |
    |   (e.g., footwear.running)                  |
    +---------------------------------------------+

For Phase 1 pilot, all routing is DETERMINISTIC (rule-based).
No LLM calls are made -- classification uses explicit field values
from the Excel template. The LLM is reserved for future edge cases
where classification is ambiguous.

Typical usage::

    from sportmaster_card.agents.router import RouterAgent

    router = RouterAgent()
    profile = router.route(product_input)
    print(profile.processing_profile)  # e.g., ProcessingProfile.STANDARD
"""

from __future__ import annotations

from typing import Any, Optional

from crewai import Agent, Task

from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile


class RouterAgent:
    """Classifies products and produces routing decisions.

    For Phase 1 pilot, routing is DETERMINISTIC (rule-based).
    No LLM calls are needed -- classification is based on
    explicit field values from the Excel template.

    The RouterAgent can operate in two modes:

    1. **Standalone** (no CrewAI agent): Pure routing logic via ``route()``.
       Used when no LLM is needed (Phase 1 deterministic routing).

    2. **With CrewAI agent**: Wraps a CrewAI Agent for integration into
       a Crew pipeline via ``create_task()``. The agent is created by
       BaseAgentFactory from agents.yaml configuration.

    Attributes:
        agent: Optional CrewAI Agent instance for pipeline integration.
            None when used in standalone mode.

    Example:
        Standalone routing (no LLM)::

            >>> router = RouterAgent()
            >>> profile = router.route(product_input)
            >>> profile.processing_profile
            ProcessingProfile.STANDARD

        With CrewAI agent (pipeline mode)::

            >>> factory = BaseAgentFactory("config/agents.yaml")
            >>> crewai_agent = factory.create("router")
            >>> router = RouterAgent(agent=crewai_agent)
            >>> task = router.create_task(product_input)
    """

    def __init__(self, agent: Optional[Agent] = None) -> None:
        """Initialize RouterAgent with an optional CrewAI Agent.

        Args:
            agent: A CrewAI Agent instance created by BaseAgentFactory.
                If None, the router operates in standalone mode (pure
                deterministic routing without LLM capabilities).
        """
        self.agent = agent

    def route(self, product: ProductInput, flow_type: str = "1P") -> RoutingProfile:
        """Classify a product and produce a RoutingProfile.

        Applies the deterministic routing matrix to determine flow type,
        processing depth, target platforms, and attribute class. No LLM
        calls are made -- all decisions are rule-based.

        Args:
            product: Raw product data from the Excel template.
            flow_type: "1P" (first-party, full pipeline) or "3P"
                (third-party, lightweight validation). Provided by
                the task initiator or inferred from the data source.

        Returns:
            RoutingProfile containing all pipeline configuration
            decisions for this product.

        Example::

            >>> router = RouterAgent()
            >>> product = ProductInput(
            ...     mcm_id="MCM-001", brand="Nike",
            ...     category="Обувь", product_group="Кроссовки",
            ...     product_subgroup="Беговые", product_name="Pegasus",
            ...     assortment_type="Basic", assortment_level="Low",
            ... )
            >>> profile = router.route(product)
            >>> profile.processing_profile
            ProcessingProfile.MINIMAL
        """
        # Step 1: Determine flow type from the provided string flag.
        # "3P" -> third-party lightweight path; everything else -> first-party full pipeline.
        ft = FlowType.THIRD_PARTY if flow_type == "3P" else FlowType.FIRST_PARTY

        # Step 2: Determine processing profile using the rule-based routing matrix.
        profile = self._determine_processing_profile(product)

        # Step 3: Target platforms -- Phase 1 pilot targets SM site only.
        platforms = ["sm_site"]

        # Step 4: Derive attribute class from product taxonomy fields.
        attr_class = self._determine_attribute_class(product)

        return RoutingProfile(
            mcm_id=product.mcm_id,
            flow_type=ft,
            processing_profile=profile,
            target_platforms=platforms,
            attribute_class=attr_class,
        )

    def create_task(self, product: ProductInput) -> Task:
        """Create a CrewAI Task for routing this product within a Crew.

        Builds a Task with a description that includes the MCM ID and
        key product fields. The task is assigned to this router's
        underlying CrewAI agent.

        Args:
            product: The product to be routed.

        Returns:
            A CrewAI Task configured for product routing.

        Raises:
            ValueError: If no CrewAI agent was provided at init time.

        Example::

            >>> task = router.create_task(product)
            >>> task.description
            'Classify product MCM-001-BLK-42 ...'
        """
        if self.agent is None:
            raise ValueError(
                "Cannot create a CrewAI Task without an agent. "
                "Pass a CrewAI Agent to RouterAgent(agent=...) first."
            )

        # Build a description with enough context for the agent to route.
        description = (
            f"Classify product {product.mcm_id} and determine the routing profile.\n"
            f"Brand: {product.brand}\n"
            f"Category: {product.category}\n"
            f"Product group: {product.product_group}\n"
            f"Assortment type: {product.assortment_type}\n"
            f"Assortment level: {product.assortment_level}\n"
        )

        return Task(
            description=description,
            agent=self.agent,
            expected_output="RoutingProfile with flow_type, processing_profile, target_platforms, attribute_class",
        )

    def _determine_processing_profile(self, product: ProductInput) -> ProcessingProfile:
        """Map assortment_type + assortment_level to a processing profile.

        Implements the routing matrix from the v0.3 architecture spec:
            Basic + Low   -> MINIMAL
            any   + Mid   -> STANDARD
            any   + High  -> PREMIUM
            any   + Premium -> PREMIUM
            default       -> STANDARD

        Args:
            product: Product with assortment_type and assortment_level fields.

        Returns:
            The appropriate ProcessingProfile enum value.
        """
        # Normalize to lowercase for case-insensitive matching.
        level = (product.assortment_level or "").lower()
        atype = (product.assortment_type or "").lower()

        # Basic + Low is the only combination that yields MINIMAL.
        if level == "low" and atype == "basic":
            return ProcessingProfile.MINIMAL

        # High or Premium level always yields PREMIUM regardless of type.
        if level in ("high", "premium"):
            return ProcessingProfile.PREMIUM

        # Mid level yields STANDARD regardless of type.
        if level == "mid":
            return ProcessingProfile.STANDARD

        # Default fallback: STANDARD for unrecognized combinations.
        return ProcessingProfile.STANDARD

    def _determine_attribute_class(self, product: ProductInput) -> str:
        """Derive attribute class from category and product group.

        Produces a dot-notation string used by downstream agents to
        select category-specific prompts and validation rules.

        Args:
            product: Product with category and product_group fields.

        Returns:
            Dot-notation attribute class string, e.g. "обувь.кроссовки".

        Example::

            >>> product.category = "Обувь"
            >>> product.product_group = "Кроссовки"
            >>> router._determine_attribute_class(product)
            'обувь.кроссовки'
        """
        # Normalize: lowercase and replace spaces with underscores.
        category = (product.category or "").lower().replace(" ", "_")
        group = (product.product_group or "").lower().replace(" ", "_")
        return f"{category}.{group}"
