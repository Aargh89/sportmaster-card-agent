"""StructurePlannerAgent -- plans content section layout from a ContentBrief.

This agent takes a ContentBrief (produced by the Brief Selector) and
generates a ContentStructure that defines the ordered section layout and
per-section writing guidelines for the Content Generator to follow.

Phase 1 uses a deterministic section mapping: each required section from
the brief is placed in a logical order with predefined writing guidelines.
Phase 2 will use LLM-based analysis of the product category and platform
to produce adaptive, context-sensitive section structures.

Architecture::

    ContentBrief
        |
        v
    StructurePlannerAgent.plan(brief)
        |
        +-- _order_sections()        -> logical ordering
        +-- _generate_guidelines()   -> per-section writing tips
        |
        v
    ContentStructure (section layout + guidelines)

Section ordering strategy (Phase 1):
    Sections are ordered by a predefined priority map that reflects
    natural reading flow: introduction first, then benefits, then
    technical details (technologies, composition), then care instructions.
    Sections not in the priority map are appended at the end.

Typical usage::

    from sportmaster_card.agents.structure_planner import StructurePlannerAgent
    from sportmaster_card.models.content import ContentBrief

    agent = StructurePlannerAgent()
    brief = ContentBrief(
        mcm_id="MCM-001", platform_id="sm_site",
        brief_type="standard", tone_of_voice="professional",
        required_sections=["description", "benefits"],
        max_description_length=2000, max_title_length=120,
    )
    structure = agent.plan(brief)
    print(structure.sections)  # ["description", "benefits"]
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from sportmaster_card.models.content import ContentBrief, ContentStructure


class StructurePlannerAgent:
    """Plans content section structure from a ContentBrief.

    Maps the brief's required_sections into an ordered ContentStructure
    with per-section writing guidelines.  The ordering follows a natural
    reading flow optimized for product card consumption on marketplaces.

    Phase 1: deterministic ordering with predefined guidelines.
    Phase 2: LLM-based adaptive structure for complex products.

    Attributes:
        _SECTION_ORDER: Priority map controlling section display order.
            Lower numbers appear first.  Sections not in this map get
            a high default priority and appear at the end.
        _SECTION_GUIDELINES: Default writing guideline for each known
            section.  Guidelines help the Content Generator produce
            consistent, on-brand content across thousands of SKUs.

    Example::

        >>> agent = StructurePlannerAgent()
        >>> brief = ContentBrief(
        ...     mcm_id="MCM-001", platform_id="sm_site",
        ...     brief_type="standard", tone_of_voice="professional",
        ...     required_sections=["description", "benefits"],
        ...     max_description_length=2000, max_title_length=120,
        ... )
        >>> structure = agent.plan(brief)
        >>> "description" in structure.sections
        True
    """

    # Priority map: lower value = earlier in the content layout.
    # Reflects natural reading flow for product card consumers.
    _SECTION_ORDER: dict[str, int] = {
        "intro": 0,
        "description": 1,
        "benefits": 2,
        "technologies": 3,
        "composition": 4,
        "care": 5,
        "characteristics": 6,
    }

    # Default writing guidelines per section.
    # Each guideline provides a concise instruction for content generators.
    _SECTION_GUIDELINES: dict[str, str] = {
        "intro": "2-3 предложения, ключевые преимущества продукта.",
        "description": "Основное описание, 3-5 абзацев, включить ключевые особенности.",
        "benefits": "Список преимуществ, 3-6 пунктов, каждый с заголовком.",
        "technologies": "Перечислить технологии бренда с кратким описанием каждой.",
        "composition": "Указать состав материалов по компонентам (верх, подошва и т.д.).",
        "care": "Инструкция по уходу за изделием, 2-3 пункта.",
        "characteristics": "Таблица характеристик: размер, вес, цвет, сезон.",
    }

    def plan(self, brief: ContentBrief) -> ContentStructure:
        """Plan content section structure from a ContentBrief.

        Takes the brief's required_sections, orders them by reading
        flow priority, and attaches per-section writing guidelines.

        Uses real LLM (via CrewAI + OpenRouter) when OPENROUTER_API_KEY
        is set in the environment. Falls back to deterministic section
        planning otherwise.

        Args:
            brief: ContentBrief specifying required sections, platform,
                and content constraints from the Brief Selector agent.

        Returns:
            ContentStructure with ordered sections and guidelines,
            ready for the Content Generator to produce section content.
        """
        if self._is_llm_mode():
            return self._plan_with_llm(brief)
        return self._plan_stub(brief)

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    def _is_llm_mode(self) -> bool:
        """Check if real LLM is available via OPENROUTER_API_KEY."""
        key = os.environ.get("OPENROUTER_API_KEY", "")
        return bool(key.strip())

    # ------------------------------------------------------------------
    # Stub planning (Phase 1 deterministic, no LLM)
    # ------------------------------------------------------------------

    def _plan_stub(self, brief: ContentBrief) -> ContentStructure:
        """Plan using deterministic section ordering (no LLM).

        This is the original Phase 1 planning logic, preserved for use
        when no API key is available or for testing.
        """
        # Step 1: Order sections by priority (natural reading flow)
        ordered = self._order_sections(brief.required_sections)

        # Step 2: Generate per-section writing guidelines
        guidelines = self._generate_guidelines(ordered)

        return ContentStructure(
            mcm_id=brief.mcm_id,
            platform_id=brief.platform_id,
            sections=ordered,
            section_guidelines=guidelines,
        )

    # ------------------------------------------------------------------
    # LLM planning (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _plan_with_llm(self, brief: ContentBrief) -> ContentStructure:
        """Plan using CrewAI Agent+Task with a real LLM.

        Loads the structure_planner.yaml prompt template, fills it with
        brief data, and delegates to a CrewAI Crew for execution.
        Falls back to stub planning if the LLM call fails or returns
        unparseable output.

        Args:
            brief: ContentBrief with required sections and constraints.

        Returns:
            ContentStructure from LLM output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "structure_planner.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with brief data
        task_desc = prompts["task_template"].format(
            mcm_id=brief.mcm_id,
            brand="",
            category="",
            product_subgroup="",
            platform_id=brief.platform_id,
            tone_of_voice=brief.tone_of_voice,
            technologies="",
            key_features="",
            composition="",
            benefits_data="",
            seo_keywords="",
            max_description_length=brief.max_description_length,
            required_sections=", ".join(brief.required_sections),
            html_support="true",
        )

        agent = Agent(
            role="Structure Planner",
            goal=prompts["system_prompt"],
            backstory="Information architecture specialist for Sportmaster product cards",
            llm=get_llm("claude_haiku"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
            output_pydantic=ContentStructure,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
        except Exception:
            return self._plan_stub(brief)

        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic

        # Fallback: could not parse LLM output into ContentStructure
        return self._plan_stub(brief)

    # ------------------------------------------------------------------
    # Private helpers -- deterministic section planning (Phase 1)
    # ------------------------------------------------------------------

    def _order_sections(self, sections: list[str]) -> list[str]:
        """Order sections by the predefined reading-flow priority.

        Sections present in _SECTION_ORDER are sorted by their priority
        value.  Unknown sections receive a high default priority (999)
        and appear at the end in their original order.

        Args:
            sections: Unordered list of section identifiers from the brief.

        Returns:
            Sections sorted by reading-flow priority.
        """
        return sorted(
            sections,
            key=lambda s: self._SECTION_ORDER.get(s, 999),
        )

    def _generate_guidelines(self, sections: list[str]) -> dict[str, str]:
        """Generate writing guidelines for each section.

        Looks up each section in the predefined guidelines map.
        Sections without a predefined guideline receive a generic
        instruction to keep content professional and concise.

        Args:
            sections: Ordered list of section identifiers.

        Returns:
            Mapping of section identifier to guideline text.
        """
        guidelines: dict[str, str] = {}
        for section in sections:
            if section in self._SECTION_GUIDELINES:
                guidelines[section] = self._SECTION_GUIDELINES[section]
            else:
                # Generic guideline for unknown section types
                guidelines[section] = (
                    "Профессиональный стиль, краткое содержание по теме раздела."
                )
        return guidelines
