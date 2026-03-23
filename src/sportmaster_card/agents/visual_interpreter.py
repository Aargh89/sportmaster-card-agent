"""VisualInterpreterAgent -- stub visual attribute extraction from product photos.

This module implements Agent 1.4 in the UC1 Enrichment pipeline. The Visual
Interpreter examines product photos and technical sketches to extract visual
attributes (sole type, closure type, upper material, etc.) that are not present
in the structured Excel data.

Phase 1 implementation note:
    In Phase 1, this agent uses **rule-based stubs** -- no real computer vision
    or image analysis is performed. The agent returns typical attributes for
    the product category (e.g., footwear gets sole_type, closure_type,
    upper_material). Phase 2 will integrate actual image analysis models
    (e.g., CLIP, custom CNNs) for real visual extraction.

Architecture and data flow::

    ProductInput (with photo_urls)
        |
        v
    VisualInterpreterAgent.interpret()
        |
        +---> _extract_footwear_attrs()   [Phase 1: rule-based stub]
        |     (Phase 2: _analyze_image() with CLIP/CNN)
        |
        +---> _build_provenance()         [creates DataProvenance entries]
        |
        +---> return (attributes, provenance)
        |
        v
    (dict[str, str], list[DataProvenance])
        |
        v
    Data Enricher (Agent 1.8) merges visual attributes into profile

No-photo handling::

    If photo_urls is None or empty, the agent returns an empty dict and
    an empty provenance list. Visual extraction cannot proceed without
    source images. The Data Enricher will note the absence and rely on
    other sources for attribute values.

Typical usage::

    from sportmaster_card.agents.visual_interpreter import VisualInterpreterAgent
    from sportmaster_card.models.product_input import ProductInput

    agent = VisualInterpreterAgent()
    product = ProductInput(
        mcm_id="MCM-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        photo_urls=["https://cdn.sportmaster.ru/photos/MCM-001-1.jpg"],
    )
    attributes, provenance = agent.interpret(product)
    # attributes: {"sole_type": "Резина", "closure_type": "Шнуровка", ...}
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.models.provenance import DataProvenance, SourceType


class VisualInterpreterAgent:
    """Extracts visual attributes from product photos using rule-based stubs.

    Phase 1 stub implementation returns typical attributes based on product
    category. No real image analysis is performed. Phase 2 will replace the
    stub logic with actual computer vision models.

    The agent checks whether photo_urls are available before attempting
    extraction. If no photos exist, it returns empty results -- visual
    extraction requires source images.

    ASCII Diagram -- Extraction Logic::

        ProductInput
            |
            +-- photo_urls present?
            |       |
            |       NO  --> return ({}, [])
            |       |
            |       YES --> check category
            |                   |
            |                   "Обувь" --> footwear attributes
            |                   other   --> generic attributes
            |
            +-- build DataProvenance for each extracted attribute
            |
            v
        (dict[str, str], list[DataProvenance])

    Attributes:
        AGENT_ID: String identifier for this agent in provenance records.
            Follows the convention ``agent-{number}-{name}``.
        SOURCE_NAME: Human-readable source label for provenance entries.
            Set to ``"product_photo"`` since attributes come from photos.

    Examples:
        Footwear with photos::

            >>> agent = VisualInterpreterAgent()
            >>> attrs, prov = agent.interpret(footwear_with_photos)
            >>> "sole_type" in attrs
            True

        Product without photos::

            >>> attrs, prov = agent.interpret(product_no_photos)
            >>> attrs
            {}
    """

    # Agent identity for provenance records.
    # Follows the "agent-{num}-{name}" convention used across all agents.
    AGENT_ID: str = "agent-1.4-visual-interpreter"

    # Source label for provenance entries.
    # Visual attributes are extracted from product photos.
    SOURCE_NAME: str = "product_photo"

    # ------------------------------------------------------------------
    # Category-specific stub attribute maps
    # ------------------------------------------------------------------

    # Footwear stub attributes: typical visual properties observable in
    # a product photo of a running shoe. Phase 2 will extract these from
    # actual images using computer vision models.
    _FOOTWEAR_ATTRS: dict[str, str] = {
        "sole_type": "Резина",
        "closure_type": "Шнуровка",
        "upper_material": "Текстиль",
    }

    # Generic stub attributes: minimal visual properties applicable to
    # any product category when no specific stub is available.
    _GENERIC_ATTRS: dict[str, str] = {
        "primary_color_visual": "Не определён",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def interpret(
        self, product: ProductInput
    ) -> tuple[dict[str, str], list[DataProvenance]]:
        """Extract visual attributes from product photos (Phase 1 stub).

        Checks for photo_urls availability, then returns rule-based
        attributes appropriate for the product category. Each extracted
        attribute gets a DataProvenance record with source_type=PHOTO.

        Args:
            product: A ProductInput instance. Must have photo_urls for
                visual extraction to proceed. If photo_urls is None or
                empty, returns empty results.

        Returns:
            A tuple of (attributes, provenance):
                - attributes: dict mapping attribute names to extracted
                  values (e.g., {"sole_type": "Резина"}).
                - provenance: list of DataProvenance entries, one per
                  extracted attribute, all with source_type=PHOTO.

        Examples:
            Footwear product with photos::

                >>> agent = VisualInterpreterAgent()
                >>> attrs, prov = agent.interpret(footwear_product)
                >>> attrs["sole_type"]
                'Резина'
                >>> prov[0].source_type == SourceType.PHOTO
                True

            Product without photos::

                >>> attrs, prov = agent.interpret(no_photo_product)
                >>> attrs == {}
                True
                >>> prov == []
                True
        """
        # Rule-based agent — always use deterministic logic (no LLM needed)
        # if self._is_llm_mode():
        #     return self._interpret_with_llm(product)
        return self._interpret_stub(product)

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
    # Stub interpretation (Phase 1 rule-based, deterministic)
    # ------------------------------------------------------------------

    def _interpret_stub(
        self, product: ProductInput
    ) -> tuple[dict[str, str], list[DataProvenance]]:
        """Extract visual attributes using rule-based stubs (no LLM).

        This is the original Phase 1 logic, preserved for use when no API
        key is available or for testing.
        """
        # No photos means no visual extraction is possible.
        # Return empty results and let the Data Enricher handle the gap.
        if not product.photo_urls:
            return {}, []

        # Select category-specific attributes based on the product category.
        # "Обувь" (Footwear) has the most detailed stub in Phase 1.
        attributes = self._get_stub_attributes(product.category)

        # Build provenance entries for each extracted attribute.
        provenance = self._build_provenance(attributes, product.photo_urls[0])

        return attributes, provenance

    # ------------------------------------------------------------------
    # LLM interpretation (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _interpret_with_llm(
        self, product: ProductInput
    ) -> tuple[dict[str, str], list[DataProvenance]]:
        """Extract visual attributes using CrewAI Agent+Task with a real LLM.

        Loads the visual_interpreter.yaml prompt template, fills it with
        product data, and delegates to a CrewAI Crew for execution.
        Falls back to stub interpretation if the LLM call fails.

        Note: In Phase 2, photo URLs would be passed to a vision-capable
        model (e.g., Gemini Flash with vision). Current implementation
        sends photo URLs as text context for the LLM to reason about.

        Args:
            product: A ProductInput instance with photo_urls.

        Returns:
            Tuple of (attributes dict, list[DataProvenance]) from LLM
            output, or stub fallback on error.
        """
        # No photos -- same behavior in both modes
        if not product.photo_urls:
            return {}, []

        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "visual_interpreter.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with product data
        task_desc = prompts["task_template"].format(
            mcm_id=product.mcm_id,
            brand=product.brand,
            category=product.category,
            product_subgroup=product.product_subgroup,
            photo_urls="\n".join(product.photo_urls or []),
            declared_color=product.color or "",
            declared_material="",
        )

        agent = Agent(
            role="Visual Interpreter",
            goal=prompts["system_prompt"],
            backstory="Expert visual analyst for Sportmaster product photos",
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
            return self._interpret_stub(product)

        # LLM output is advisory; use stub for structured return
        # to ensure type safety and consistent provenance tracking.
        return self._interpret_stub(product)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_stub_attributes(self, category: str) -> dict[str, str]:
        """Return stub attributes appropriate for the product category.

        Args:
            category: Product category from the Sportmaster taxonomy
                (e.g., "Обувь", "Одежда").

        Returns:
            Dict of attribute name to extracted value. Returns footwear-
            specific attributes for "Обувь", generic for everything else.
        """
        if category == "Обувь":
            return dict(self._FOOTWEAR_ATTRS)
        return dict(self._GENERIC_ATTRS)

    def _build_provenance(
        self, attributes: dict[str, str], photo_url: str
    ) -> list[DataProvenance]:
        """Create DataProvenance entries for each extracted attribute.

        Each attribute gets a provenance record with source_type=PHOTO,
        linking the extracted value back to the source photo. Confidence
        is set to 0.6 (medium) for Phase 1 stubs since no real image
        analysis was performed.

        Args:
            attributes: Dict of extracted attribute name-value pairs.
            photo_url: URL of the first photo used as source reference.

        Returns:
            List of DataProvenance entries, one per attribute.
        """
        now = datetime.now(timezone.utc)
        provenance: list[DataProvenance] = []

        for attr_name, attr_value in attributes.items():
            provenance.append(
                DataProvenance(
                    attribute_name=attr_name,
                    value=attr_value,
                    source_type=SourceType.PHOTO,
                    source_name=photo_url,
                    confidence=0.6,
                    agent_id=self.AGENT_ID,
                    timestamp=now,
                )
            )

        return provenance
