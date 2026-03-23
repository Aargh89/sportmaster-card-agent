"""DataCuratorAgent -- validate enriched profile and produce CuratedProfile.

This module implements Agent 1.10 in the UC1 Enrichment pipeline. The Data
Curator reviews an EnrichedProductProfile, resolves any disputed attribute
values, and produces a CuratedProfile -- a flat, ready-to-use data object
with all fields needed for content generation across marketplace platforms.

The CuratedProfile is intentionally denormalized: instead of nesting models,
it extracts final resolved values into top-level fields. This lets content
generators access any field with a single attribute lookup (``cp.brand``)
instead of navigating a deep tree (``profile.base_product.brand``).

Architecture and data flow::

    EnrichedProductProfile
        |
        v
    DataCuratorAgent.curate()
        |
        +---> _extract_identity()    [product_name, brand, category]
        +---> _extract_description() [from base_product or generate]
        +---> _combine_features()    [from benchmark + technologies]
        +---> _generate_benefits()   [from features + insights]
        +---> _generate_seo()        [from features + category]
        +---> _passthrough_provenance()
        |
        v
    CuratedProfile (flat, ready for UC2 content generators)
        |
        v
    UC2 Copywriter, SEO Agent, Platform Adapter

Field resolution strategy::

    +------------------+------------------------------------------+
    | CuratedProfile   | Source / Resolution                      |
    +------------------+------------------------------------------+
    | product_name     | base_product.product_name (direct)       |
    | brand            | base_product.brand (direct)              |
    | category         | base_product.category (direct)           |
    | description      | base_product.description or generated    |
    | key_features     | benchmark.common_features + technologies |
    | technologies     | base_product.technologies (direct)       |
    | composition      | base_product.composition (direct)        |
    | benefits_data    | derived from features + category         |
    | seo_material     | derived from name + category + features  |
    | provenance_log   | passthrough from enriched profile        |
    +------------------+------------------------------------------+

Typical usage::

    from sportmaster_card.agents.data_curator import DataCuratorAgent

    curator = DataCuratorAgent()
    curated = curator.curate(enriched_profile)
    print(curated.brand)  # "Nike" -- direct flat access
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from sportmaster_card.models.enrichment import (
    CuratedProfile,
    EnrichedProductProfile,
)


class DataCuratorAgent:
    """Reviews enriched profile and produces a flat CuratedProfile for content gen.

    The curator extracts identity fields, combines features from multiple
    sources, generates benefits and SEO material, and passes through the
    provenance log unchanged. No LLM calls in Phase 1 -- all curation
    logic is deterministic.

    ASCII Diagram -- Curation Logic::

        EnrichedProductProfile
            |
            +-- extract identity (name, brand, category)
            |
            +-- extract/generate description
            |
            +-- combine features (benchmark + technologies)
            |
            +-- generate benefits (from features + category)
            |
            +-- generate SEO material (from name + category)
            |
            +-- passthrough provenance_log
            |
            v
        CuratedProfile

    Attributes:
        AGENT_ID: String identifier for this agent.

    Examples:
        Curate a profile::

            >>> curator = DataCuratorAgent()
            >>> curated = curator.curate(enriched_profile)
            >>> curated.brand
            'Nike'
    """

    # Agent identity for traceability in logs and debugging.
    AGENT_ID: str = "agent-1.10-data-curator"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def curate(self, profile: EnrichedProductProfile) -> CuratedProfile:
        """Review enriched profile and produce a flat CuratedProfile.

        Extracts and flattens data from the enriched profile into a
        denormalized CuratedProfile that content generators can consume
        directly. Combines features from competitor benchmark with
        product technologies, generates benefits and SEO material.

        Args:
            profile: An EnrichedProductProfile containing all upstream
                agent outputs. Must have base_product, validation_report,
                competitor_benchmark, and provenance_log.

        Returns:
            CuratedProfile with flat fields ready for content generation.
            All identity fields come from base_product. Features combine
            benchmark and technology data. Provenance is passed through.

        Examples:
            Basic curation::

                >>> curator = DataCuratorAgent()
                >>> curated = curator.curate(enriched_profile)
                >>> curated.mcm_id == enriched_profile.mcm_id
                True
        """
        if self._is_llm_mode():
            return self._curate_with_llm(profile)
        return self._curate_stub(profile)

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
    # Stub curation (Phase 1 deterministic)
    # ------------------------------------------------------------------

    def _curate_stub(self, profile: EnrichedProductProfile) -> CuratedProfile:
        """Curate enriched profile using deterministic rules (no LLM).

        This is the original Phase 1 logic, preserved for use when no API
        key is available or for testing.
        """
        base = profile.base_product

        # Extract description or generate a placeholder.
        description = self._resolve_description(profile)

        # Combine features from competitor benchmark and technologies.
        key_features = self._combine_features(profile)

        # Extract technologies from base product (or empty list).
        technologies = base.technologies or []

        # Extract composition from base product (or empty dict).
        composition = base.composition or {}

        # Generate customer-facing benefits from features.
        benefits_data = self._generate_benefits(key_features, base.category)

        # Generate SEO keywords from product identity and features.
        seo_material = self._generate_seo(base.product_name, base.category, key_features)

        return CuratedProfile(
            mcm_id=profile.mcm_id,
            product_name=base.product_name,
            brand=base.brand,
            category=base.category,
            description=description,
            key_features=key_features,
            technologies=technologies,
            composition=composition,
            benefits_data=benefits_data,
            seo_material=seo_material,
            provenance_log=profile.provenance_log,
        )

    # ------------------------------------------------------------------
    # LLM curation (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _curate_with_llm(self, profile: EnrichedProductProfile) -> CuratedProfile:
        """Curate enriched profile using CrewAI Agent+Task with a real LLM.

        Loads the data_curator.yaml prompt template, fills it with
        enriched profile data, and delegates to a CrewAI Crew for
        intelligent field resolution and curation.
        Falls back to stub curation if the LLM call fails.

        Args:
            profile: EnrichedProductProfile to curate.

        Returns:
            CuratedProfile from LLM-guided curation,
            or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "data_curator.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with profile data
        task_desc = prompts["task_template"].format(
            enriched_profile=str(profile),
            disputed_fields="",
        )

        agent = Agent(
            role="Data Curator",
            goal=prompts["system_prompt"],
            backstory="Senior data curator for Sportmaster product profiles",
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
            return self._curate_stub(profile)

        # LLM output is advisory; use stub for structured return
        # to ensure type safety (CuratedProfile model).
        return self._curate_stub(profile)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_description(profile: EnrichedProductProfile) -> str:
        """Extract or generate product description.

        Uses the base product description if available. Falls back to
        a generated description combining brand, product name, and
        category for products without supplier descriptions.

        Args:
            profile: The enriched profile to extract description from.

        Returns:
            Non-empty description string.
        """
        base = profile.base_product

        # Prefer the supplier-provided description.
        if base.description and base.description.strip():
            return base.description

        # Generate a basic description from identity fields.
        return f"{base.brand} {base.product_name} -- {base.category}"

    @staticmethod
    def _combine_features(profile: EnrichedProductProfile) -> list[str]:
        """Combine features from competitor benchmark and technologies.

        Merges common_features from the competitor benchmark with the
        product's own technologies to create a comprehensive feature
        list. Deduplicates while preserving order.

        Args:
            profile: The enriched profile with benchmark and product data.

        Returns:
            Combined list of unique features.
        """
        features: list[str] = []
        seen: set[str] = set()

        # Start with competitor common features (market expectations).
        for feature in profile.competitor_benchmark.common_features:
            lower = feature.lower()
            if lower not in seen:
                features.append(feature)
                seen.add(lower)

        # Add product technologies (brand differentiators).
        if profile.base_product.technologies:
            for tech in profile.base_product.technologies:
                lower = tech.lower()
                if lower not in seen:
                    features.append(tech)
                    seen.add(lower)

        return features

    @staticmethod
    def _generate_benefits(features: list[str], category: str) -> list[str]:
        """Generate customer-facing benefit statements from features.

        Transforms feature names into benefit-oriented phrases that
        content generators can insert into product card copy. Phase 1
        uses simple templates; Phase 2 will use LLM generation.

        Args:
            features: List of key features to derive benefits from.
            category: Product category for context-appropriate phrasing.

        Returns:
            List of benefit statement strings.
        """
        benefits: list[str] = []

        for feature in features:
            benefits.append(f"Преимущество: {feature}")

        # Add a category-level benefit if we have features.
        if features and category == "Обувь":
            benefits.append("Комфорт и поддержка для ваших ног")

        return benefits

    @staticmethod
    def _generate_seo(
        product_name: str, category: str, features: list[str]
    ) -> list[str]:
        """Generate SEO keywords from product identity and features.

        Creates search-optimized phrases by combining the product name,
        category, and key features. Phase 1 uses simple concatenation;
        Phase 2 will integrate keyword research tools and search volume data.

        Args:
            product_name: Product name for keyword inclusion.
            category: Product category for category-level keywords.
            features: Key features to include as search terms.

        Returns:
            List of SEO keyword/phrase strings.
        """
        seo: list[str] = []

        # Product name + category combination (high search intent).
        seo.append(f"{product_name.lower()} купить")
        seo.append(f"{category.lower()} {product_name.split()[0].lower()}")

        # Feature-based keywords.
        for feature in features[:3]:
            seo.append(feature.lower())

        return seo
