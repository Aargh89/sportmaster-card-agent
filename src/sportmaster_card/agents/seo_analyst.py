"""SEOAnalystAgent -- generates SEO keyword profiles for product content.

This agent analyzes a ProductInput and produces an SEOProfile containing
primary and secondary keywords, plus title and meta-description
recommendations optimized for a specific marketplace platform.

Phase 1 uses deterministic keyword extraction from product attributes
(brand, category, product group, technologies). Phase 2 will incorporate
search-volume data from marketplace APIs and LLM-based keyword expansion.

Architecture::

    ProductInput (enriched)
        |
        v
    SEOAnalystAgent.analyze(product, platform_id)
        |
        +-- _extract_primary_keywords()   -> high-priority terms
        +-- _extract_secondary_keywords() -> supporting terms
        +-- _build_title_recommendation() -> SEO title suggestion
        +-- _build_meta_description()     -> meta tag suggestion
        |
        v
    SEOProfile (one per platform)

Keyword strategy (Phase 1):
    Primary keywords combine the brand name with the product subgroup
    and product name -- these are the highest-intent search queries.
    Secondary keywords include technologies, the product group, and
    the category for broader topical coverage.

Typical usage::

    from sportmaster_card.agents.seo_analyst import SEOAnalystAgent
    from sportmaster_card.models.product_input import ProductInput

    agent = SEOAnalystAgent()
    product = ProductInput(mcm_id="MCM-001", brand="Nike", ...)
    seo = agent.analyze(product, platform_id="sm_site")
    print(seo.primary_keywords)   # ["беговые кроссовки nike", ...]
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from sportmaster_card.models.content import SEOProfile
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


class SEOAnalystAgent:
    """Generates SEO keyword profiles from product data for a target platform.

    The SEO Analyst extracts keywords from product attributes (brand,
    category, product group, subgroup, technologies) and assembles them
    into an SEOProfile with primary keywords, secondary keywords, and
    meta-tag recommendations.

    Phase 1: deterministic extraction from ProductInput fields.
    Phase 2: LLM-based expansion with search-volume weighting.

    The public API (analyze method) is stable across phases -- only the
    private extraction methods change when switching to LLM-based analysis.

    Example::

        >>> agent = SEOAnalystAgent()
        >>> product = ProductInput(
        ...     mcm_id="MCM-001", brand="Nike",
        ...     category="Обувь", product_group="Кроссовки",
        ...     product_subgroup="Беговые кроссовки",
        ...     product_name="Nike Air Zoom Pegasus 41",
        ... )
        >>> seo = agent.analyze(product)
        >>> len(seo.primary_keywords) > 0
        True
    """

    def analyze(
        self,
        product: ProductInput,
        platform_id: str = "sm_site",
    ) -> SEOProfile:
        """Analyze product data and generate an SEO keyword profile.

        Extracts keywords from product attributes, builds title and
        meta-description recommendations, and returns a complete
        SEOProfile for the target platform.

        Uses real LLM (via CrewAI + OpenRouter) when OPENROUTER_API_KEY
        is set in the environment. Falls back to deterministic keyword
        extraction otherwise.

        Args:
            product: Product data containing brand, category, product
                group, subgroup, name, and optionally technologies.
            platform_id: Target platform identifier. Keyword strategy
                varies per platform. Defaults to "sm_site".

        Returns:
            SEOProfile with primary/secondary keywords and meta-tag
            recommendations for the specified platform.
        """
        if self._is_llm_mode():
            return self._analyze_with_llm(product, platform_id)
        return self._analyze_stub(product, platform_id)

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
    # Stub analysis (Phase 1 deterministic, no LLM)
    # ------------------------------------------------------------------

    def _analyze_stub(
        self,
        product: ProductInput,
        platform_id: str,
    ) -> SEOProfile:
        """Analyze using deterministic keyword extraction (no LLM).

        This is the original Phase 1 analysis logic, preserved for use
        when no API key is available or for testing.
        """
        # Step 1: Extract high-priority keywords (brand + product type combos)
        primary = self._extract_primary_keywords(product)

        # Step 2: Extract supporting keywords (technologies, category, group)
        secondary = self._extract_secondary_keywords(product)

        # Step 3: Build title and meta-description recommendations
        title = self._build_title_recommendation(product)
        meta = self._build_meta_description(product)

        return SEOProfile(
            mcm_id=product.mcm_id,
            platform_id=platform_id,
            primary_keywords=primary,
            secondary_keywords=secondary,
            title_recommendation=title,
            meta_description_recommendation=meta,
        )

    # ------------------------------------------------------------------
    # LLM analysis (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _analyze_with_llm(
        self,
        product: ProductInput,
        platform_id: str,
    ) -> SEOProfile:
        """Analyze using CrewAI Agent+Task with a real LLM.

        Loads the seo_analyst.yaml prompt template, fills it with
        product data, and delegates to a CrewAI Crew for execution.
        Falls back to stub analysis if the LLM call fails or returns
        unparseable output.

        Args:
            product: Product data for SEO analysis.
            platform_id: Target platform identifier.

        Returns:
            SEOProfile from LLM output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "seo_analyst.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with product data
        task_desc = prompts["task_template"].format(
            platform_id=platform_id,
            mcm_id=product.mcm_id,
            brand=product.brand,
            category=product.category,
            product_subgroup=product.product_subgroup,
            product_name=product.product_name,
            technologies=", ".join(product.technologies or []),
            key_features=", ".join(product.technologies or []),
            competitor_keywords="",
            category_popular_queries="",
            max_title_length=150,
            platform_seo_notes="",
        )

        agent = Agent(
            role="SEO Analyst",
            goal=prompts["system_prompt"],
            backstory="SEO specialist for Sportmaster marketplaces",
            llm=get_llm("gemini_flash"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
            output_pydantic=SEOProfile,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
            raw = result.raw if hasattr(result, 'raw') else str(result)

            # Strip markdown code fences
            raw_clean = _strip_code_fences(raw)

            parsed = json.loads(raw_clean)

            return SEOProfile(
                mcm_id=product.mcm_id,
                platform_id=platform_id,
                primary_keywords=parsed.get('primary_keywords', []),
                secondary_keywords=parsed.get('secondary_keywords', []),
                title_recommendation=parsed.get('title_recommendation', ''),
                meta_description_recommendation=parsed.get('meta_description_recommendation', ''),
            )
        except Exception:
            return self._analyze_stub(product, platform_id)

    # ------------------------------------------------------------------
    # Private helpers -- deterministic keyword extraction (Phase 1)
    # ------------------------------------------------------------------

    def _extract_primary_keywords(self, product: ProductInput) -> list[str]:
        """Extract primary (high-priority) keywords from product data.

        Primary keywords target the highest-intent search queries:
        brand + product subgroup, brand + product name.  These MUST
        appear in generated content for effective SEO.

        Args:
            product: Source product data.

        Returns:
            List of 2-4 primary keyword phrases, lowercased.
        """
        # Combine brand with subgroup for the main category-intent keyword
        # e.g., "беговые кроссовки nike"
        keywords: list[str] = [
            f"{product.product_subgroup} {product.brand}".lower(),
            f"{product.brand} {product.product_name}".lower(),
        ]
        return keywords

    def _extract_secondary_keywords(self, product: ProductInput) -> list[str]:
        """Extract secondary (supporting) keywords for topical coverage.

        Secondary keywords broaden search coverage without being
        mandatory in the content.  Includes technologies, the product
        group, and the top-level category.

        Args:
            product: Source product data.

        Returns:
            List of secondary keyword phrases, lowercased.
        """
        keywords: list[str] = [
            product.product_group.lower(),
            product.category.lower(),
        ]

        # Add technology names as secondary keywords (high SEO value)
        if product.technologies:
            for tech in product.technologies:
                keywords.append(tech.lower())

        return keywords

    def _build_title_recommendation(self, product: ProductInput) -> str:
        """Build an SEO-optimized title recommendation.

        Template: "{brand} {product_subgroup} {product_name}".
        Places brand first for brand-search intent, followed by
        the subgroup keyword and model name.

        Args:
            product: Source product data.

        Returns:
            Recommended product title string.
        """
        return f"{product.brand} {product.product_subgroup} {product.product_name}"

    def _build_meta_description(self, product: ProductInput) -> str:
        """Build a meta-description recommendation for search snippets.

        Template includes a call-to-action ("Купить ... в Спортмастер")
        and the key product attributes.  Kept under 160 characters for
        optimal search snippet display.

        Args:
            product: Source product data.

        Returns:
            Meta description string, truncated to 160 characters.
        """
        meta = (
            f"Купить {product.product_name} {product.brand} в Спортмастер. "
            f"{product.product_subgroup} с доставкой по всей России."
        )
        return meta[:160]
