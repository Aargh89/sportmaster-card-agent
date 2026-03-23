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

from sportmaster_card.models.content import SEOProfile
from sportmaster_card.models.product_input import ProductInput


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

        Args:
            product: Product data containing brand, category, product
                group, subgroup, name, and optionally technologies.
            platform_id: Target platform identifier. Keyword strategy
                varies per platform. Defaults to "sm_site".

        Returns:
            SEOProfile with primary/secondary keywords and meta-tag
            recommendations for the specified platform.
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
