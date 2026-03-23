"""ContentGeneratorAgent -- generates platform-specific product content.

This is the MOST IMPORTANT agent in the pipeline. It takes validated,
enriched product data (ProductInput / CuratedProfile) and generates all
text elements for a specific platform: product name, description, benefits,
and SEO metadata.

For Phase 1 pilot, uses TEMPLATE-BASED generation (no LLM calls).
When a real LLM (Claude Sonnet) is connected in Phase 2, only the
generation methods (_generate_product_name, _generate_description, etc.)
need to change -- the public interface remains identical.

Architecture::

    ProductInput (enriched)
        |
        v
    ContentGeneratorAgent.generate(product, platform_id, limits)
        |
        +-- _generate_product_name()   -> SEO-optimized title
        +-- _generate_description()    -> main text block
        +-- _generate_benefits()       -> list[Benefit]
        +-- _extract_seo_keywords()    -> keyword list
        |
        v
    PlatformContent (one per platform)

Template strategy (Phase 1):
    Each helper method constructs content from product attributes using
    Russian-language templates. The templates are intentionally simple --
    they produce structurally correct content that passes quality checks
    but lacks the stylistic polish of LLM-generated text.

Typical usage::

    from sportmaster_card.agents.content_generator import ContentGeneratorAgent
    from sportmaster_card.models.product_input import ProductInput

    agent = ContentGeneratorAgent()
    product = ProductInput(mcm_id="MCM-001", brand="Nike", ...)
    content = agent.generate(product, platform_id="sm_site")
    print(content.product_name)   # "Nike Беговые кроссовки Air Zoom Pegasus 41"
    print(len(content.benefits))  # 3 (one per technology)
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from sportmaster_card.models.content import Benefit, PlatformContent
from sportmaster_card.models.product_input import ProductInput


class ContentGeneratorAgent:
    """Generates platform-specific product content from enriched data.

    This is the CORE agent of the UC2 content pipeline. It receives a
    ProductInput (enriched by UC1 agents) and produces a PlatformContent
    instance containing all text elements needed for a product card on
    the target platform.

    Phase 1: template-based generation (deterministic, no LLM).
    Phase 2: LLM-based generation via Claude Sonnet (swap internals only).

    The public API (generate method) is stable across phases. Only the
    private helper methods change when switching from templates to LLM.

    Attributes:
        No instance attributes in Phase 1. The agent is stateless --
        all inputs are passed via the generate() method. Phase 2 will
        add an LLM client attribute.

    Example::

        >>> agent = ContentGeneratorAgent()
        >>> product = ProductInput(
        ...     mcm_id="MCM-001-BLK-42", brand="Nike",
        ...     category="Обувь", product_group="Кроссовки",
        ...     product_subgroup="Беговые кроссовки",
        ...     product_name="Nike Air Zoom Pegasus 41",
        ...     technologies=["Air Zoom", "React"],
        ... )
        >>> content = agent.generate(product)
        >>> content.platform_id
        'sm_site'
    """

    # ------------------------------------------------------------------
    # Default benefit templates -- used when product has no technologies.
    # Each tuple is (title, description_template) where {brand} and
    # {subgroup} are substituted at runtime.
    # ------------------------------------------------------------------
    _DEFAULT_BENEFITS: list[tuple[str, str]] = [
        ("Качество", "Продукция {brand} отвечает высоким стандартам качества."),
        ("Комфорт", "{subgroup} {brand} обеспечивают комфорт при использовании."),
    ]

    # ------------------------------------------------------------------
    # Technology-to-benefit mapping -- translates tech names to user benefits.
    # Keys are lowercased technology names; values are (title, description).
    # ------------------------------------------------------------------
    _TECH_BENEFIT_MAP: dict[str, tuple[str, str]] = {
        "air zoom": ("Амортизация", "Технология Air Zoom обеспечивает мягкую амортизацию при беге."),
        "react": ("Отзывчивость", "Пена React обеспечивает упругую и отзывчивую амортизацию."),
        "flywire": ("Поддержка", "Технология Flywire обеспечивает адаптивную поддержку стопы."),
        "boost": ("Энергия", "Технология Boost возвращает энергию при каждом шаге."),
        "primeknit": ("Вентиляция", "Primeknit обеспечивает дышащий и адаптивный верх."),
        "continental": ("Сцепление", "Подошва Continental обеспечивает надёжное сцепление с поверхностью."),
        "gore-tex": ("Защита от влаги", "Мембрана GORE-TEX обеспечивает водонепроницаемость и дышащие свойства."),
        "vibram": ("Износостойкость", "Подошва Vibram обеспечивает долговечность и надёжное сцепление."),
    }

    def generate(
        self,
        product: ProductInput,
        platform_id: str = "sm_site",
        max_description_length: int = 3000,
        max_title_length: int = 150,
    ) -> PlatformContent:
        """Generate product content for a specific platform.

        This is the main entry point of the Content Generator. It
        orchestrates all helper methods and assembles the final
        PlatformContent instance.

        Uses real LLM (via CrewAI + OpenRouter) when OPENROUTER_API_KEY
        is set in the environment. Falls back to deterministic template-based
        generation otherwise.

        Args:
            product: Enriched product data (ProductInput or CuratedProfile).
                Must have all required fields populated. Optional fields
                (technologies, composition, gender) improve content quality.
            platform_id: Target platform identifier. Controls content style
                and SEO strategy. Defaults to "sm_site" (Sportmaster website).
                Other values: "wb", "ozon", "lamoda", "megamarket".
            max_description_length: Maximum character count for the description
                field. Content will be truncated to fit. Default: 3000 chars.
            max_title_length: Maximum character count for the product name.
                Default: 150 chars (generous for most platforms).

        Returns:
            PlatformContent instance with all text elements populated:
            product_name, description, benefits, seo_title,
            seo_meta_description, seo_keywords.

        Example::

            >>> agent = ContentGeneratorAgent()
            >>> product = ProductInput(
            ...     mcm_id="MCM-001", brand="Nike", category="Обувь",
            ...     product_group="Кроссовки",
            ...     product_subgroup="Беговые кроссовки",
            ...     product_name="Pegasus 41",
            ... )
            >>> result = agent.generate(product, platform_id="wb")
            >>> result.platform_id
            'wb'
        """
        if self._is_llm_mode():
            return self._generate_with_llm(
                product, platform_id, max_description_length, max_title_length,
            )
        return self._generate_stub(
            product, platform_id, max_description_length, max_title_length,
        )

    # ------------------------------------------------------------------
    # Mode detection
    # ------------------------------------------------------------------

    def _is_llm_mode(self) -> bool:
        """Check if real LLM is available via OPENROUTER_API_KEY."""
        key = os.environ.get("OPENROUTER_API_KEY", "")
        return bool(key.strip())

    # ------------------------------------------------------------------
    # Stub generation (Phase 1 template-based, deterministic)
    # ------------------------------------------------------------------

    def _generate_stub(
        self,
        product: ProductInput,
        platform_id: str,
        max_description_length: int,
        max_title_length: int,
    ) -> PlatformContent:
        """Generate content using deterministic templates (no LLM).

        This is the original Phase 1 generation logic, preserved for use
        when no API key is available or for testing.
        """
        # Step 1: Generate SEO-optimized product name
        product_name = self._generate_product_name(product, max_title_length)

        # Step 2: Generate main description text block
        description = self._generate_description(product, max_description_length)

        # Step 3: Generate benefit bullets from technologies
        benefits = self._generate_benefits(product)

        # Step 4: Generate SEO metadata fields
        seo_title = self._generate_seo_title(product, max_title_length)
        seo_keywords = self._extract_seo_keywords(product)
        seo_meta = self._generate_seo_meta(product)

        return PlatformContent(
            mcm_id=product.mcm_id,
            platform_id=platform_id,
            product_name=product_name,
            description=description,
            benefits=benefits,
            seo_title=seo_title,
            seo_meta_description=seo_meta,
            seo_keywords=seo_keywords,
        )

    # ------------------------------------------------------------------
    # LLM generation (Phase 2 -- CrewAI + OpenRouter)
    # ------------------------------------------------------------------

    def _generate_with_llm(
        self,
        product: ProductInput,
        platform_id: str,
        max_description_length: int,
        max_title_length: int,
    ) -> PlatformContent:
        """Generate content using CrewAI Agent+Task with a real LLM.

        Loads the content_generator.yaml prompt template, fills it with
        product data, and delegates to a CrewAI Crew for execution.
        Falls back to stub generation if the LLM call fails or returns
        unparseable output.

        Args:
            product: Enriched product data.
            platform_id: Target platform identifier.
            max_description_length: Maximum description length.
            max_title_length: Maximum title length.

        Returns:
            PlatformContent from LLM output, or stub fallback on error.
        """
        from crewai import Agent, Crew, Task

        from sportmaster_card.utils.llm_config import get_llm

        # Load prompt template from YAML config
        prompt_path = (
            Path(__file__).parent.parent / "config" / "prompts" / "content_generator.yaml"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)

        # Fill task template with product data
        task_desc = prompts["task_template"].format(
            platform_id=platform_id,
            product_name=product.product_name,
            brand=product.brand,
            category=product.category,
            description=product.description or "",
            technologies=", ".join(product.technologies or []),
            composition=str(product.composition or {}),
            key_features=", ".join(product.technologies or []),
            benefits_data="",
            seo_keywords="",
            title_recommendation="",
            max_title_length=max_title_length,
            max_description_length=max_description_length,
            required_sections="description, benefits, technologies",
            tone_of_voice="professional",
            content_structure="standard",
            creative_hooks="",
            emotional_hooks="",
        )

        agent = Agent(
            role="Content Generator",
            goal=prompts["system_prompt"],
            backstory="Expert e-commerce copywriter for Sportmaster",
            llm=get_llm("claude_sonnet"),
            verbose=False,
        )

        task = Task(
            description=task_desc,
            agent=agent,
            expected_output=prompts["expected_output"],
            output_pydantic=PlatformContent,
        )

        crew = Crew(agents=[agent], tasks=[task], verbose=False)

        try:
            result = crew.kickoff()
        except Exception:
            # LLM call failed -- fall back to stub
            return self._generate_stub(
                product, platform_id, max_description_length, max_title_length,
            )

        if hasattr(result, "pydantic") and result.pydantic:
            return result.pydantic

        # Fallback: could not parse LLM output into PlatformContent
        return self._generate_stub(
            product, platform_id, max_description_length, max_title_length,
        )

    # ------------------------------------------------------------------
    # Private helper methods -- template-based generation (Phase 1).
    # In Phase 2, these will be replaced with LLM prompt calls.
    # ------------------------------------------------------------------

    def _generate_product_name(
        self,
        product: ProductInput,
        max_length: int,
    ) -> str:
        """Generate an SEO-optimized product name for the platform.

        Template: "{brand} {product_subgroup} {product_name}".
        Truncated to max_length if necessary.

        Args:
            product: Source product data.
            max_length: Maximum character count for the name.

        Returns:
            SEO-optimized product name string, truncated to max_length.
        """
        # Combine brand, subgroup, and original name for SEO density.
        # The subgroup keyword (e.g., "Беговые кроссовки") improves search.
        name = f"{product.brand} {product.product_subgroup} {product.product_name}"
        return name[:max_length]

    def _generate_description(
        self,
        product: ProductInput,
        max_length: int,
    ) -> str:
        """Generate the main product description text block.

        Builds a multi-paragraph description from product attributes:
        1. Opening sentence with brand, subgroup, and product name.
        2. Technology paragraph (if technologies are available).
        3. Composition paragraph (if composition is available).
        4. Closing call-to-action sentence.

        Args:
            product: Source product data.
            max_length: Maximum character count for the description.

        Returns:
            Description text, truncated to max_length.
        """
        # Paragraph 1: opening sentence introducing the product
        parts: list[str] = []
        opening = (
            f"{product.product_subgroup} {product.brand} {product.product_name} — "
            f"отличный выбор для спорта и активного образа жизни."
        )
        parts.append(opening)

        # Paragraph 2: gender and season context (if available)
        if product.gender or product.season:
            context_parts = []
            if product.gender:
                context_parts.append(f"Предназначены для: {product.gender.lower()}")
            if product.season:
                context_parts.append(f"Сезон: {product.season}")
            parts.append(". ".join(context_parts) + ".")

        # Paragraph 3: technologies (if available)
        if product.technologies:
            tech_str = ", ".join(product.technologies)
            parts.append(
                f"Модель оснащена технологиями: {tech_str}. "
                f"Каждая технология вносит вклад в общий комфорт и "
                f"производительность обуви."
            )

        # Paragraph 4: composition (if available)
        if product.composition:
            comp_items = [f"{k}: {v}" for k, v in product.composition.items()]
            comp_str = "; ".join(comp_items)
            parts.append(f"Состав: {comp_str}.")

        # Closing sentence: call to action
        parts.append(
            f"Закажите {product.product_name} в Спортмастер с доставкой по всей России."
        )

        # Join paragraphs and truncate to max_length
        full_text = "\n\n".join(parts)
        return full_text[:max_length]

    def _generate_benefits(self, product: ProductInput) -> list[Benefit]:
        """Generate product benefit bullets from technologies.

        If the product has technologies, each known technology is mapped
        to a user-facing benefit using _TECH_BENEFIT_MAP. Unknown
        technologies get a generic benefit. If no technologies exist,
        default benefits are used.

        Args:
            product: Source product data.

        Returns:
            List of Benefit objects (always non-empty, at least 1 item).
        """
        benefits: list[Benefit] = []

        if product.technologies:
            for tech in product.technologies:
                tech_lower = tech.lower()
                if tech_lower in self._TECH_BENEFIT_MAP:
                    title, desc = self._TECH_BENEFIT_MAP[tech_lower]
                else:
                    # Generic benefit for unknown technologies
                    title = tech
                    desc = f"Технология {tech} повышает характеристики модели."
                benefits.append(Benefit(title=title, description=desc))
        else:
            # No technologies -- use default benefits
            for title, desc_template in self._DEFAULT_BENEFITS:
                desc = desc_template.format(
                    brand=product.brand,
                    subgroup=product.product_subgroup,
                )
                benefits.append(Benefit(title=title, description=desc))

        return benefits

    def _generate_seo_title(
        self,
        product: ProductInput,
        max_length: int,
    ) -> str:
        """Generate the SEO title (HTML <title> tag content).

        Template: "{brand} {product_subgroup} {product_name}".
        Truncated to max_length.

        Args:
            product: Source product data.
            max_length: Maximum character count.

        Returns:
            SEO title string.
        """
        seo_title = (
            f"{product.brand} {product.product_subgroup} {product.product_name}"
        )
        return seo_title[:max_length]

    def _extract_seo_keywords(self, product: ProductInput) -> list[str]:
        """Extract SEO keywords from product attributes.

        Combines brand, product group, subgroup, product name, and
        technologies (if available) into a flat keyword list. All
        keywords are lowercased for consistency.

        Args:
            product: Source product data.

        Returns:
            List of lowercase keyword strings (always non-empty).
        """
        keywords: list[str] = [
            product.brand.lower(),
            product.product_group.lower(),
            product.product_subgroup.lower(),
            product.product_name.lower(),
        ]

        # Add technology names as keywords (high SEO value)
        if product.technologies:
            for tech in product.technologies:
                keywords.append(tech.lower())

        return keywords

    def _generate_seo_meta(self, product: ProductInput) -> str:
        """Generate the SEO meta description (HTML <meta> tag).

        Template: "Купить {product_name} в Спортмастер. {subgroup} {brand}."
        Kept under 160 characters for optimal search snippet display.

        Args:
            product: Source product data.

        Returns:
            Meta description string (under 160 characters).
        """
        meta = (
            f"Купить {product.product_name} в Спортмастер. "
            f"{product.product_subgroup} {product.brand}."
        )
        # Truncate to 160 chars for search engine snippet optimization
        return meta[:160]
