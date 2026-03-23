"""Live smoke test -- runs full pipeline with real LLM via OpenRouter.

Usage::

    OPENROUTER_API_KEY=your-key python scripts/smoke_test.py

This script:
    1. Creates a sample Nike Pegasus product.
    2. Runs the full PilotFlow pipeline (15 agents).
    3. Prints all outputs at each stage.
    4. Reports total elapsed time.

Requires: OPENROUTER_API_KEY environment variable.
Without it, agents will fall back to stub/rule-based mode.
"""

import os
import sys
import time


def main() -> None:
    """Run the full pipeline smoke test and print results."""
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: Set OPENROUTER_API_KEY environment variable")
        print("Usage: OPENROUTER_API_KEY=sk-xxx python scripts/smoke_test.py")
        sys.exit(1)

    from sportmaster_card.flows.pilot_flow import PilotFlow
    from sportmaster_card.models.product_input import ProductInput

    product = ProductInput(
        mcm_id="MCM-SMOKE-001-BLK-42",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Air Zoom Pegasus 41",
        description="Беговые кроссовки с технологией Air Zoom для ежедневных тренировок",
        gender="Мужской",
        season="Весна-Лето 2026",
        color="Чёрный",
        assortment_segment="TRD",
        assortment_type="Basic",
        assortment_level="Mid",
        technologies=["Air Zoom", "Flywire", "React"],
        composition={"Верх": "Текстиль 80%, синтетика 20%", "Подошва": "Резина"},
        photo_urls=["https://example.com/pegasus41.jpg"],
    )

    print("=" * 60)
    print("SPORTMASTER CARD AGENT -- SMOKE TEST")
    print("=" * 60)
    print(f"Product: {product.brand} {product.product_name}")
    print(f"MCM: {product.mcm_id}")
    print(f"LLM Mode: {'ON' if os.environ.get('OPENROUTER_API_KEY') else 'OFF (stub)'}")
    print("=" * 60)

    start_time = time.time()

    flow = PilotFlow()
    result = flow.run(product)

    elapsed = time.time() - start_time

    print(f"\n--- ROUTING ---")
    print(f"Flow: {result.routing_profile.flow_type.value}")
    print(f"Profile: {result.routing_profile.processing_profile.value}")
    print(f"Platforms: {result.routing_profile.target_platforms}")

    print(f"\n--- VALIDATION ---")
    print(f"Valid: {result.validation_report.is_valid}")
    print(f"Completeness: {result.validation_report.overall_completeness:.0%}")

    print(f"\n--- CURATED PROFILE ---")
    if result.curated_profile:
        print(f"Features: {result.curated_profile.key_features[:5]}")
        print(f"Technologies: {result.curated_profile.technologies}")
    else:
        print("(not available)")

    print(f"\n--- GENERATED CONTENT ---")
    print(f"Title: {result.edited_content.product_name}")
    desc = result.edited_content.description
    print(f"Description ({len(desc)} chars):")
    if len(desc) > 300:
        print(desc[:300] + "...")
    else:
        print(desc)
    print(f"Benefits: {len(result.edited_content.benefits)}")
    for benefit in result.edited_content.benefits[:3]:
        desc_text = benefit.description
        if len(desc_text) > 80:
            desc_text = desc_text[:80] + "..."
        print(f"  * {benefit.title}: {desc_text}")
    print(f"SEO Keywords: {result.edited_content.seo_keywords}")

    print(f"\n--- QUALITY ---")
    if result.quality_score:
        print(f"Overall: {result.quality_score.overall_score:.2f}")
        print(f"Passes threshold: {result.quality_score.passes_threshold}")
    else:
        print("(not available)")

    print(f"\n--- PROVENANCE ---")
    print(f"Total entries: {len(result.provenance_entries)}")

    print(f"\n{'=' * 60}")
    print(f"Pipeline completed in {elapsed:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
