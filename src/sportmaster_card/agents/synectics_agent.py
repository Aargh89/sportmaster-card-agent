"""SynecticsAgent -- creative metaphor and association generation for product cards.

This module implements the Creative Strategist (Agent 1.7 / GPTK) in the UC1
Enrichment pipeline. The agent uses synectics methodology -- finding creative
connections between seemingly unrelated concepts -- to generate metaphors,
word associations, and emotional hooks for product card copy.

Phase 1 implementation note:
    In Phase 1, the agent uses **template-based generation** -- no LLM calls
    are made. Technologies are mapped to pre-defined metaphors and associations
    via lookup tables. Phase 2 will integrate LLM-powered creative generation
    with brand-safety guardrails and style-guide compliance.

Synectics methodology::

    Synectics is a creative problem-solving technique that uses analogies
    and metaphors to generate novel ideas. In product card context:

    1. Direct analogy:  "Air Zoom = облако для ваших ног"
    2. Personal analogy: "Почувствуйте себя марафонцем"
    3. Symbolic analogy: "React = пружина" (energy return)

Architecture and data flow::

    ProductInput (with technologies)
        |
        v
    SynecticsAgent.generate()
        |
        +---> _map_technologies()   [tech -> metaphors/associations]
        +---> _add_category_hooks() [category -> emotional hooks]
        |
        +---> CreativeInsights(approved=False)
        |
        v
    CreativeInsights (awaiting GPTK approval)
        |
        v
    GPTK Human Review --> approved=True/False
        |
        v
    Data Enricher (1.8) includes in profile if approved

Approval workflow::

    All creative output starts with approved=False. Only after a human
    from the GPTK team (Группа Подготовки Текстового Контента) reviews
    and approves the output can content generators use it. This protects
    against brand-unsafe metaphors or off-tone associations.

Typical usage::

    from sportmaster_card.agents.synectics_agent import SynecticsAgent
    from sportmaster_card.models.product_input import ProductInput

    agent = SynecticsAgent()
    product = ProductInput(
        mcm_id="MCM-001", brand="Nike", category="Обувь",
        product_group="Кроссовки", product_subgroup="Беговые",
        product_name="Pegasus 41", technologies=["Air Zoom", "React"],
    )
    creative = agent.generate(product)
    # creative.metaphors: ["Облако для ваших ног", "Пружина в каждом шаге"]
    # creative.approved: False (awaiting GPTK review)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from sportmaster_card.models.enrichment import CreativeInsights
from sportmaster_card.models.product_input import ProductInput


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
    return text


class SynecticsAgent:
    """Generates creative metaphors and associations using synectics templates.

    Phase 1 uses lookup tables mapping technologies to creative language
    elements. Each known technology adds metaphors and associations to the
    output. Products without technologies get only category-level creative
    material.

    All output is created with approved=False -- GPTK review is mandatory
    before any creative material appears in published product cards.

    ASCII Diagram -- Generation Logic::

        ProductInput
            |
            +-- technologies present?
            |       |
            |       YES --> map each tech to metaphors + associations
            |       |
            |       NO  --> baseline category metaphors only
            |
            +-- add category emotional hooks
            |
            +-- CreativeInsights(approved=False)
            |
            v
        CreativeInsights (unapproved)

    Attributes:
        AGENT_ID: String identifier for this agent.
        _TECH_METAPHORS: Mapping of technology names to metaphor strings.
        _TECH_ASSOCIATIONS: Mapping of technology names to association words.
        _CATEGORY_HOOKS: Mapping of categories to emotional hook phrases.

    Examples:
        Product with technologies::

            >>> agent = SynecticsAgent()
            >>> ci = agent.generate(product_with_tech)
            >>> len(ci.metaphors) > 0
            True
            >>> ci.approved
            False
    """

    # Agent identity for traceability.
    AGENT_ID: str = "agent-1.7-synectics"

    # ------------------------------------------------------------------
    # Technology-to-creative mappings (Phase 1 templates)
    # ------------------------------------------------------------------

    # Each technology maps to a metaphor that conveys its key benefit
    # in figurative language. These are pre-approved templates that
    # still require GPTK review for context-appropriateness.
    _TECH_METAPHORS: dict[str, str] = {
        "Air Zoom": "Облако для ваших ног",
        "React": "Пружина в каждом шаге",
        "Flywire": "Невидимая поддержка",
        "Boost": "Энергия, которая не заканчивается",
        "Primeknit": "Вторая кожа",
        "Continental": "Сцепление без компромиссов",
        "Flyknit": "Лёгкость паутины",
        "ZoomX": "Скорость без границ",
    }

    # Each technology maps to evocative word associations that content
    # generators weave into descriptions for emotional richness.
    _TECH_ASSOCIATIONS: dict[str, list[str]] = {
        "Air Zoom": ["лёгкость", "воздушность", "невесомость"],
        "React": ["отзывчивость", "энергия", "возврат"],
        "Flywire": ["поддержка", "фиксация", "надёжность"],
        "Boost": ["энергия", "упругость", "бесконечность"],
        "Primeknit": ["адаптивность", "комфорт", "обтекаемость"],
        "Continental": ["надёжность", "сцепление", "контроль"],
        "Flyknit": ["лёгкость", "дышащий", "гибкость"],
        "ZoomX": ["скорость", "рекорд", "прорыв"],
    }

    # Category-level emotional hooks. These are baseline creative
    # elements that apply regardless of specific technologies.
    _CATEGORY_HOOKS: dict[str, list[str]] = {
        "Обувь": [
            "Почувствуйте разницу с первого шага",
            "Ваш путь начинается здесь",
        ],
        "_default": [
            "Качество, которое чувствуется",
        ],
    }

    # Baseline metaphors for products without technologies.
    # Ensures every product gets at least some creative material.
    _BASELINE_METAPHORS: list[str] = [
        "Надёжный спутник для ваших тренировок",
    ]

    # Baseline associations for products without technologies.
    _BASELINE_ASSOCIATIONS: list[str] = [
        "комфорт",
        "стиль",
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, product: ProductInput) -> CreativeInsights:
        """Generate creative metaphors and associations for a product.

        Maps product technologies to pre-defined creative templates and
        adds category-level emotional hooks. Output is always created
        with approved=False -- GPTK review is required.

        Args:
            product: A ProductInput instance. Technologies influence the
                richness of creative output; products without technologies
                get baseline creative material only.

        Returns:
            CreativeInsights with metaphors, associations, emotional_hooks,
            and approved=False. The mcm_id matches the input product.

        Examples:
            Product with Air Zoom technology::

                >>> agent = SynecticsAgent()
                >>> ci = agent.generate(product_with_air_zoom)
                >>> "Облако для ваших ног" in ci.metaphors
                True
        """
        if self._is_llm_mode():
            return self._generate_with_llm(product)
        return self._generate_stub(product)

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
    # Stub generation (Phase 1 template-based, deterministic)
    # ------------------------------------------------------------------

    def _generate_stub(self, product: ProductInput) -> CreativeInsights:
        """Generate creative material using template lookups (no LLM).

        This is the original Phase 1 logic, preserved for use when no API
        key is available or for testing.
        """
        metaphors: list[str] = []
        associations: list[str] = []

        # Map each technology to its creative template.
        if product.technologies:
            for tech in product.technologies:
                # Add technology-specific metaphor if we have one.
                if tech in self._TECH_METAPHORS:
                    metaphors.append(self._TECH_METAPHORS[tech])

                # Add technology-specific associations if we have them.
                if tech in self._TECH_ASSOCIATIONS:
                    associations.extend(self._TECH_ASSOCIATIONS[tech])

        # Ensure at least baseline creative material exists.
        if not metaphors:
            metaphors = list(self._BASELINE_METAPHORS)

        if not associations:
            associations = list(self._BASELINE_ASSOCIATIONS)

        # Add category-level emotional hooks.
        hooks = self._get_category_hooks(product.category)

        return CreativeInsights(
            mcm_id=product.mcm_id,
            metaphors=metaphors,
            associations=associations,
            emotional_hooks=hooks,
            approved=False,
        )

    # ------------------------------------------------------------------
    # LLM generation (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _generate_with_llm(self, product: ProductInput) -> CreativeInsights:
        """Generate creative material using CrewAI Agent+Task with a real LLM.

        Loads the synectics.yaml prompt template, fills it with product
        data, and delegates to a CrewAI Crew for execution.
        Falls back to stub generation if the LLM call fails.

        Args:
            product: ProductInput to generate creative material for.

        Returns:
            CreativeInsights from LLM output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "synectics.yaml"
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
            technologies=", ".join(product.technologies or []),
            key_features=", ".join(product.technologies or []),
            materials=str(product.composition or {}),
            target_audience=product.gender or "",
        )

        agent = Agent(
            role="Synectics Strategist",
            goal=prompts["system_prompt"],
            backstory="Creative copywriting strategist using synectics methodology",
            llm=get_llm("claude_haiku"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
            raw = result.raw if hasattr(result, 'raw') else str(result)

            # Strip markdown code fences
            raw_clean = _strip_code_fences(raw)

            parsed = json.loads(raw_clean)

            return CreativeInsights(
                mcm_id=product.mcm_id,
                metaphors=parsed.get('metaphors', []),
                associations=parsed.get('associations', []),
                emotional_hooks=parsed.get('emotional_hooks', []),
                approved=False,  # Always requires GPTK review
            )
        except Exception:
            # LLM call failed or output unparseable -- fall back to stub
            return self._generate_stub(product)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_category_hooks(self, category: str) -> list[str]:
        """Return emotional hooks appropriate for the product category.

        Args:
            category: Product category from the Sportmaster taxonomy.

        Returns:
            List of emotional hook phrases for the category. Falls back
            to default hooks if category is not in the lookup table.
        """
        if category in self._CATEGORY_HOOKS:
            return list(self._CATEGORY_HOOKS[category])
        return list(self._CATEGORY_HOOKS["_default"])
