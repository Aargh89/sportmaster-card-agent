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
        """Curate enriched profile using real LLM for intelligent enrichment.

        Sends product data to the LLM with a detailed prompt asking it to:
        1. Write a compelling product description in Russian
        2. Identify key features and benefits for customers
        3. Generate SEO keywords and material
        4. Resolve any data conflicts

        The LLM response is parsed as JSON into CuratedProfile fields.
        Falls back to stub curation if the LLM call fails.

        Args:
            profile: EnrichedProductProfile to curate.

        Returns:
            CuratedProfile with LLM-enriched data,
            or stub fallback on error.
        """
        import json

        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        base = profile.base_product
        techs = ", ".join(base.technologies or [])
        comp = ", ".join(f"{k}: {v}" for k, v in (base.composition or {}).items())
        competitor_info = ""
        if profile.competitor_benchmark and profile.competitor_benchmark.competitors:
            for c in profile.competitor_benchmark.competitors[:3]:
                competitor_info += f"- {c.platform}: {c.product_name}"
                if c.key_features:
                    competitor_info += f" (особенности: {', '.join(c.key_features[:5])})"
                competitor_info += "\n"
        internal_info = ""
        if profile.internal_insights and profile.internal_insights.insights:
            internal_info = "\n".join(f"- {i}" for i in profile.internal_insights.insights[:5])
        creative_info = ""
        if profile.creative_insights:
            if profile.creative_insights.metaphors:
                creative_info += "Метафоры: " + ", ".join(profile.creative_insights.metaphors[:3]) + "\n"
            if profile.creative_insights.emotional_hooks:
                creative_info += "Эмоциональные крючки: " + ", ".join(profile.creative_insights.emotional_hooks[:3])

        # Build a focused enrichment prompt
        task_desc = f"""Ты — эксперт по товарам Спортмастер. Обогати данные карточки товара.

ВХОДНЫЕ ДАННЫЕ:
- МЦМ: {base.mcm_id}
- Бренд: {base.brand}
- Категория: {base.category}
- Подгруппа: {base.product_subgroup}
- Название: {base.product_name}
- Описание от поставщика: {base.description or 'НЕТ'}
- Пол: {base.gender or 'не указан'}
- Сезон: {base.season or 'не указан'}
- Цвет: {base.color or 'не указан'}
- Технологии: {techs or 'не указаны'}
- Состав: {comp or 'не указан'}

ДАННЫЕ КОНКУРЕНТОВ:
{competitor_info or 'Нет данных'}

ВНУТРЕННИЕ ИНСАЙТЫ:
{internal_info or 'Нет данных'}

КРЕАТИВНЫЕ ИДЕИ:
{creative_info or 'Нет данных'}

ЗАДАЧА — верни ТОЛЬКО JSON (без markdown, без ```):
{{
  "description": "Подробное описание товара на русском (3-5 предложений). Опиши назначение, ключевые технологии, для кого подходит. Не придумывай характеристики, которых нет во входных данных.",
  "key_features": ["список 5-8 ключевых особенностей товара для покупателя, на русском"],
  "benefits_data": ["список 5-8 бенефитов: каждый — короткое предложение о пользе для покупателя"],
  "seo_material": ["список 8-12 поисковых запросов на русском, по которым покупатели ищут этот товар"]
}}"""

        agent = Agent(
            role="Product Data Enrichment Expert",
            goal="Обогати данные карточки товара: описание, ключевые особенности, бенефиты, SEO-запросы",
            backstory="Ты эксперт по спортивным товарам с 10-летним опытом в e-commerce. Знаешь все технологии Nike, Adidas, Puma. Пишешь на русском.",
            llm=get_llm("claude_sonnet"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output="JSON с полями: description, key_features, benefits_data, seo_material",
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
            raw = result.raw if hasattr(result, "raw") else str(result)

            # Parse JSON from LLM response
            # Strip markdown code fences if present
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                raw_clean = raw_clean.split("\n", 1)[1] if "\n" in raw_clean else raw_clean[3:]
                if raw_clean.endswith("```"):
                    raw_clean = raw_clean[:-3]
                raw_clean = raw_clean.strip()

            enriched = json.loads(raw_clean)

            return CuratedProfile(
                mcm_id=profile.mcm_id,
                product_name=base.product_name,
                brand=base.brand,
                category=base.category,
                description=enriched.get("description", base.description or ""),
                key_features=enriched.get("key_features", base.technologies or []),
                technologies=base.technologies or [],
                composition=base.composition or {},
                benefits_data=enriched.get("benefits_data", []),
                seo_material=enriched.get("seo_material", []),
                provenance_log=profile.provenance_log,
            )
        except Exception:
            # LLM call or JSON parse failed -- fall back to stub
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
