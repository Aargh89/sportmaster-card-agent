# Phase 1: Pilot Pipeline (v0.1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal end-to-end pipeline: Router → Data Validator → External Researcher → Content Generator → Copy Editor for SM (1P), processing one MCM from an Excel row into a PlatformContent for the SM website.

**Architecture:** CrewAI Flow orchestrates a sequential Crew of 5 agents. Each agent receives typed Pydantic input and produces typed Pydantic output. The Router agent classifies the product and selects a processing profile. The remaining 4 agents execute sequentially: validate → research → generate → edit. OpenRouter provides LLM access.

**Tech Stack:** Python 3.12, CrewAI 1.5+, Pydantic v2, OpenRouter (LLM), pytest, YAML configs

**Documentation standard:** Every function/class must have Google-style docstrings with Args, Returns, Raises, Examples sections. Target: ~3 lines of documentation per 1 line of code.

---

## File Structure

```
src/sportmaster_card/
├── __init__.py                     # Package root, version
├── models/
│   ├── __init__.py                 # Model index
│   ├── product_input.py            # ProductInput — raw Excel row
│   ├── routing.py                  # RoutingProfile — routing decision
│   ├── provenance.py               # DataProvenance, DataProvenanceLog
│   ├── enrichment.py               # ValidationReport, CompetitorBenchmark
│   ├── content.py                  # ContentBrief, PlatformContent, QualityScore
│   └── platform_profile.py         # PlatformProfile — platform config
├── agents/
│   ├── __init__.py                 # Agent index
│   ├── base.py                     # BaseAgentFactory — shared agent creation logic
│   ├── router.py                   # RouterAgent — classifies MCM, selects pipeline
│   ├── data_validator.py           # DataValidatorAgent — checks Excel data completeness
│   ├── external_researcher.py      # ExternalResearcherAgent — parses competitor cards
│   ├── content_generator.py        # ContentGeneratorAgent — generates PlatformContent
│   └── copy_editor.py              # CopyEditorAgent — grammar, length, formatting
├── tools/
│   ├── __init__.py                 # Tool index
│   └── excel_parser.py             # ExcelParserTool — reads Excel row into ProductInput
├── config/
│   ├── __init__.py                 # Config loader
│   ├── agents.yaml                 # Agent definitions (role, goal, backstory, model)
│   └── platforms/
│       └── sm_site.yaml            # PlatformProfile for SM website
├── flows/
│   ├── __init__.py                 # Flow index
│   └── pilot_flow.py              # PilotFlow — Phase 1 end-to-end flow
└── utils/
    ├── __init__.py
    └── llm_config.py               # OpenRouter LLM configuration helper

tests/
├── models/
│   ├── test_product_input.py       # ProductInput validation tests
│   ├── test_routing.py             # RoutingProfile tests
│   ├── test_provenance.py          # DataProvenance tests
│   ├── test_enrichment.py          # ValidationReport, CompetitorBenchmark tests
│   ├── test_content.py             # ContentBrief, PlatformContent tests
│   └── test_platform_profile.py    # PlatformProfile tests
├── agents/
│   ├── test_router.py              # RouterAgent tests
│   ├── test_data_validator.py      # DataValidatorAgent tests
│   ├── test_external_researcher.py # ExternalResearcherAgent tests
│   ├── test_content_generator.py   # ContentGeneratorAgent tests
│   └── test_copy_editor.py         # CopyEditorAgent tests
├── tools/
│   └── test_excel_parser.py        # ExcelParserTool tests
├── flows/
│   └── test_pilot_flow.py          # PilotFlow integration tests
└── conftest.py                     # Shared fixtures (sample products, mock LLM)
```

---

## Task 1: Core Pydantic Models — ProductInput

**Files:**
- Create: `src/sportmaster_card/models/product_input.py`
- Test: `tests/models/test_product_input.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for ProductInput model.

Validates that raw Excel row data is correctly parsed into a structured
ProductInput with all required fields from the 209-column template.
Phase 1 focuses on the essential subset of columns needed for the pilot.

Test strategy:
    - Valid minimal input → successful creation
    - Missing required fields → ValidationError
    - Type coercion (string MCM ID must be preserved as-is)
    - Empty optional fields → None defaults
"""
import pytest
from pydantic import ValidationError


def test_product_input_valid_minimal():
    """ProductInput accepts valid minimal data with all required fields.

    The minimal set for Phase 1 pilot includes:
    - mcm_id (col ~1): unique product identifier
    - brand (col 8/18): brand name
    - category (col 12): top-level category
    - product_group (col 9): product type group
    - product_subgroup (col 10): specific product type
    - product_name (col ~5): original product name
    """
    from sportmaster_card.models.product_input import ProductInput

    data = {
        "mcm_id": "MCM-001-BLK-42",
        "brand": "Nike",
        "category": "Обувь",
        "product_group": "Кроссовки",
        "product_subgroup": "Беговые кроссовки",
        "product_name": "Nike Air Zoom Pegasus 41",
    }
    product = ProductInput(**data)

    assert product.mcm_id == "MCM-001-BLK-42"
    assert product.brand == "Nike"
    assert product.category == "Обувь"


def test_product_input_missing_required_field():
    """ProductInput raises ValidationError when mcm_id is missing.

    mcm_id is the primary identifier — every product MUST have one.
    """
    from sportmaster_card.models.product_input import ProductInput

    with pytest.raises(ValidationError, match="mcm_id"):
        ProductInput(
            brand="Nike",
            category="Обувь",
            product_group="Кроссовки",
            product_subgroup="Беговые кроссовки",
            product_name="Nike Air Zoom Pegasus 41",
        )


def test_product_input_optional_fields_default_to_none():
    """Optional fields (description, composition, photos) default to None.

    Many columns in the Excel template are optional — agents will
    enrich these during the UC1 pipeline.
    """
    from sportmaster_card.models.product_input import ProductInput

    product = ProductInput(
        mcm_id="MCM-002-WHT-40",
        brand="Adidas",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Повседневные кроссовки",
        product_name="Adidas Ultraboost Light",
    )

    assert product.description is None
    assert product.composition is None
    assert product.photo_urls is None


def test_product_input_with_all_pilot_fields():
    """ProductInput with all fields relevant to Phase 1 pilot (footwear).

    Includes extended attributes available in the Excel template:
    - assortment_segment (col 83): TRD / PRO / KIDS
    - assortment_type (col 85): Basic / Fashion / Seasonal
    - assortment_level (col 86): Low / Mid / High / Premium
    - gender, season, color, technologies
    """
    from sportmaster_card.models.product_input import ProductInput

    product = ProductInput(
        mcm_id="MCM-003-RED-38",
        brand="Nike",
        category="Обувь",
        product_group="Кроссовки",
        product_subgroup="Беговые кроссовки",
        product_name="Nike Pegasus 41",
        description="Беговые кроссовки с технологией Air Zoom",
        gender="Мужской",
        season="Весна-Лето 2026",
        color="Красный",
        assortment_segment="TRD",
        assortment_type="Basic",
        assortment_level="Mid",
        technologies=["Air Zoom", "Flywire", "React"],
        composition={"Верх": "Текстиль 80%, синтетика 20%", "Подошва": "Резина"},
        photo_urls=["https://example.com/photo1.jpg"],
    )

    assert product.assortment_level == "Mid"
    assert len(product.technologies) == 3
    assert "Верх" in product.composition
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Projects/Sportmaster_card && python -m pytest tests/models/test_product_input.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sportmaster_card.models.product_input'`

- [ ] **Step 3: Write minimal implementation**

```python
"""ProductInput model — structured representation of a raw Excel row.

This model captures the essential subset of the 209-column Excel template
used by Sportmaster for product data. Each field maps to one or more
columns in the template.

Architecture context:
    ProductInput is the ENTRY POINT of the entire pipeline. It is created
    by the ExcelParserTool and consumed by the Router Agent to determine
    the processing flow.

Schema diagram:
    ┌─────────────────────────────────────────┐
    │             ProductInput                │
    ├─────────────────────────────────────────┤
    │ mcm_id: str          ← col ~1          │
    │ brand: str           ← col 8/18        │
    │ category: str        ← col 12          │
    │ product_group: str   ← col 9           │
    │ product_subgroup: str← col 10          │
    │ product_name: str    ← col ~5          │
    │ description: str?    ← col ~6          │
    │ gender: str?         ← col ~20         │
    │ season: str?         ← col ~30         │
    │ color: str?          ← col ~25         │
    │ assortment_segment: str? ← col 83      │
    │ assortment_type: str?    ← col 85      │
    │ assortment_level: str?   ← col 86      │
    │ technologies: list[str]? ← col ~50+    │
    │ composition: dict?   ← col ~60+        │
    │ photo_urls: list[str]? ← col ~100+     │
    └─────────────────────────────────────────┘

Example:
    >>> from sportmaster_card.models.product_input import ProductInput
    >>> product = ProductInput(
    ...     mcm_id="MCM-001-BLK-42",
    ...     brand="Nike",
    ...     category="Обувь",
    ...     product_group="Кроссовки",
    ...     product_subgroup="Беговые кроссовки",
    ...     product_name="Nike Air Zoom Pegasus 41",
    ... )
    >>> product.mcm_id
    'MCM-001-BLK-42'
"""

from typing import Optional

from pydantic import BaseModel, Field


class ProductInput(BaseModel):
    """Raw product data extracted from the Sportmaster Excel template.

    This is the atomic input unit for the entire multi-agent pipeline.
    One ProductInput = one MCM (мерчендайзинговая цветомодель).
    All downstream agents receive data derived from this input.

    Attributes:
        mcm_id: Unique MCM identifier (e.g., "MCM-001-BLK-42").
            This is the primary key for all operations in the system.
            Maps to the first column group in the Excel template.
        brand: Brand name (e.g., "Nike", "Adidas").
            Used by Router for brand-guideline selection and by
            External Researcher for competitor card parsing.
        category: Top-level product category (e.g., "Обувь", "Одежда").
            Primary routing dimension — determines attribute class.
        product_group: Product type group (e.g., "Кроссовки").
            Second-level routing dimension.
        product_subgroup: Specific product type (e.g., "Беговые кроссовки").
            Third-level routing — affects brief selection.
        product_name: Original product name from supplier/brand.
            Basis for SEO-optimized naming per platform.
        description: Supplier-provided description text, if available.
            Often incomplete — enriched by UC1 agents.
        gender: Target gender (e.g., "Мужской", "Женский", "Унисекс").
        season: Season designation (e.g., "Весна-Лето 2026").
        color: Primary color name in Russian.
        assortment_segment: TRD (trend) / PRO (professional) / KIDS.
            Affects tone of voice and content depth.
        assortment_type: Basic / Fashion / Seasonal.
            Determines processing profile (minimal/standard/premium).
        assortment_level: Low / Mid / High / Premium.
            Key routing field — Premium gets mandatory human review.
        technologies: List of product technologies (e.g., ["Air Zoom", "React"]).
            Used for benefit generation and infographics.
        composition: Material composition as key-value pairs.
            Keys are component names, values are material descriptions.
        photo_urls: URLs of product photos, if available.
            Visual Interpreter will analyze these in UC1.

    Example:
        >>> product = ProductInput(
        ...     mcm_id="MCM-001-BLK-42",
        ...     brand="Nike",
        ...     category="Обувь",
        ...     product_group="Кроссовки",
        ...     product_subgroup="Беговые кроссовки",
        ...     product_name="Nike Air Zoom Pegasus 41",
        ...     assortment_level="Mid",
        ...     technologies=["Air Zoom", "React"],
        ... )
        >>> product.mcm_id
        'MCM-001-BLK-42'
    """

    mcm_id: str = Field(
        ...,
        description="Unique MCM identifier. Primary key for all operations.",
        examples=["MCM-001-BLK-42", "MCM-500-WHT-38"],
    )
    brand: str = Field(
        ...,
        description="Brand name from Excel template.",
        examples=["Nike", "Adidas", "Puma"],
    )
    category: str = Field(
        ...,
        description="Top-level product category.",
        examples=["Обувь", "Одежда", "Аксессуары"],
    )
    product_group: str = Field(
        ...,
        description="Product type group — second-level classification.",
        examples=["Кроссовки", "Куртки", "Рюкзаки"],
    )
    product_subgroup: str = Field(
        ...,
        description="Specific product type — third-level classification.",
        examples=["Беговые кроссовки", "Повседневные кроссовки"],
    )
    product_name: str = Field(
        ...,
        description="Original product name from supplier.",
        examples=["Nike Air Zoom Pegasus 41"],
    )

    # --- Optional fields (enriched by UC1 agents) ---

    description: Optional[str] = Field(
        default=None,
        description="Supplier-provided description. Often incomplete.",
    )
    gender: Optional[str] = Field(
        default=None,
        description="Target gender.",
        examples=["Мужской", "Женский", "Унисекс"],
    )
    season: Optional[str] = Field(
        default=None,
        description="Season designation.",
        examples=["Весна-Лето 2026", "Осень-Зима 2025"],
    )
    color: Optional[str] = Field(
        default=None,
        description="Primary color name in Russian.",
        examples=["Чёрный", "Белый", "Красный"],
    )
    assortment_segment: Optional[str] = Field(
        default=None,
        description="TRD (trend) / PRO (professional) / KIDS.",
        examples=["TRD", "PRO", "KIDS"],
    )
    assortment_type: Optional[str] = Field(
        default=None,
        description="Basic / Fashion / Seasonal.",
        examples=["Basic", "Fashion", "Seasonal"],
    )
    assortment_level: Optional[str] = Field(
        default=None,
        description="Low / Mid / High / Premium. Affects processing profile.",
        examples=["Low", "Mid", "High", "Premium"],
    )
    technologies: Optional[list[str]] = Field(
        default=None,
        description="List of product technologies.",
        examples=[["Air Zoom", "React", "Flywire"]],
    )
    composition: Optional[dict[str, str]] = Field(
        default=None,
        description="Material composition as component→material pairs.",
        examples=[{"Верх": "Текстиль 80%, синтетика 20%", "Подошва": "Резина"}],
    )
    photo_urls: Optional[list[str]] = Field(
        default=None,
        description="Product photo URLs for Visual Interpreter.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:/Projects/Sportmaster_card && python -m pytest tests/models/test_product_input.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/sportmaster_card/models/product_input.py tests/models/test_product_input.py
git commit -m "feat(models): add ProductInput model with tests — TDD Phase 1"
```

---

## Task 2: Core Pydantic Models — RoutingProfile

**Files:**
- Create: `src/sportmaster_card/models/routing.py`
- Test: `tests/models/test_routing.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for RoutingProfile model.

RoutingProfile is the output of the Router Agent. It determines:
- flow_type: 1P / 3P (which pipeline to use)
- processing_profile: minimal / standard / premium / complex
- target_platforms: which marketplaces to generate content for
- attribute_class: product classification for agent configuration
"""
import pytest
from pydantic import ValidationError


def test_routing_profile_1p_basic():
    """RoutingProfile for a basic 1P product targeting only SM site."""
    from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile

    routing = RoutingProfile(
        mcm_id="MCM-001-BLK-42",
        flow_type=FlowType.FIRST_PARTY,
        processing_profile=ProcessingProfile.MINIMAL,
        target_platforms=["sm_site"],
        attribute_class="footwear.running",
    )

    assert routing.flow_type == FlowType.FIRST_PARTY
    assert routing.processing_profile == ProcessingProfile.MINIMAL
    assert "sm_site" in routing.target_platforms


def test_routing_profile_1p_premium_with_vmp():
    """Premium product targets SM + multiple external marketplaces."""
    from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile

    routing = RoutingProfile(
        mcm_id="MCM-003-RED-38",
        flow_type=FlowType.FIRST_PARTY,
        processing_profile=ProcessingProfile.PREMIUM,
        target_platforms=["sm_site", "wb", "ozon", "lamoda"],
        attribute_class="footwear.running",
    )

    assert routing.processing_profile == ProcessingProfile.PREMIUM
    assert len(routing.target_platforms) == 4


def test_routing_profile_3p():
    """3P products use the lightweight validation pipeline."""
    from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile

    routing = RoutingProfile(
        mcm_id="MCM-3P-001",
        flow_type=FlowType.THIRD_PARTY,
        processing_profile=ProcessingProfile.STANDARD,
        target_platforms=["sm_site"],
        attribute_class="footwear.casual",
    )

    assert routing.flow_type == FlowType.THIRD_PARTY


def test_routing_profile_requires_at_least_one_platform():
    """target_platforms must not be empty — at least one platform required."""
    from sportmaster_card.models.routing import FlowType, ProcessingProfile, RoutingProfile

    with pytest.raises(ValidationError, match="target_platforms"):
        RoutingProfile(
            mcm_id="MCM-ERR-001",
            flow_type=FlowType.FIRST_PARTY,
            processing_profile=ProcessingProfile.MINIMAL,
            target_platforms=[],
            attribute_class="footwear.running",
        )


def test_flow_type_enum_values():
    """FlowType enum has exactly two values: 1P and 3P."""
    from sportmaster_card.models.routing import FlowType

    assert FlowType.FIRST_PARTY.value == "1P"
    assert FlowType.THIRD_PARTY.value == "3P"


def test_processing_profile_enum_values():
    """ProcessingProfile covers all four levels from v0.3 spec."""
    from sportmaster_card.models.routing import ProcessingProfile

    values = {p.value for p in ProcessingProfile}
    assert values == {"minimal", "standard", "premium", "complex"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/Projects/Sportmaster_card && python -m pytest tests/models/test_routing.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `src/sportmaster_card/models/routing.py` with:
- `FlowType` enum (FIRST_PARTY="1P", THIRD_PARTY="3P")
- `ProcessingProfile` enum (MINIMAL, STANDARD, PREMIUM, COMPLEX)
- `RoutingProfile` Pydantic model with validator ensuring `target_platforms` is non-empty

- [ ] **Step 4: Run test to verify it passes**

Run: `cd D:/Projects/Sportmaster_card && python -m pytest tests/models/test_routing.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/sportmaster_card/models/routing.py tests/models/test_routing.py
git commit -m "feat(models): add RoutingProfile with FlowType and ProcessingProfile enums"
```

---

## Task 3: Core Pydantic Models — DataProvenance

**Files:**
- Create: `src/sportmaster_card/models/provenance.py`
- Test: `tests/models/test_provenance.py`

- [ ] **Step 1: Write the failing test**

Tests for DataProvenance and DataProvenanceLog — tracking the origin and confidence of every attribute. Key v0.3 feature: `is_disputed` flag triggers human review.

- [ ] **Step 2–5:** Same TDD cycle as Tasks 1–2.

---

## Task 4: Core Pydantic Models — ValidationReport & CompetitorBenchmark

**Files:**
- Create: `src/sportmaster_card/models/enrichment.py`
- Test: `tests/models/test_enrichment.py`

- [ ] **Step 1–5:** TDD cycle for UC1 agent output models.

---

## Task 5: Core Pydantic Models — ContentBrief, PlatformContent, QualityScore

**Files:**
- Create: `src/sportmaster_card/models/content.py`
- Test: `tests/models/test_content.py`

- [ ] **Step 1–5:** TDD cycle for UC2 agent output models. PlatformContent is the main output — includes product_name, description, benefits, SEO fields per platform.

---

## Task 6: Core Pydantic Models — PlatformProfile

**Files:**
- Create: `src/sportmaster_card/models/platform_profile.py`
- Create: `src/sportmaster_card/config/platforms/sm_site.yaml`
- Test: `tests/models/test_platform_profile.py`

- [ ] **Step 1–5:** TDD cycle for PlatformProfile (text_requirements, visual_requirements, attribute_requirements, seo_rules). Load from YAML config.

---

## Task 7: LLM Configuration Helper

**Files:**
- Create: `src/sportmaster_card/utils/llm_config.py`
- Test: `tests/test_llm_config.py`

- [ ] **Step 1–5:** TDD cycle for `get_llm()` helper that creates a CrewAI-compatible LLM instance via OpenRouter. Supports model selection per agent (Claude Sonnet, Claude Haiku, Gemini Flash).

---

## Task 8: Test Fixtures & Conftest

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1:** Create shared fixtures:
  - `sample_product_input()` — valid ProductInput for Nike running shoe
  - `sample_routing_profile()` — 1P Basic routing to SM
  - `sample_platform_profile_sm()` — SM site PlatformProfile
  - `mock_llm()` — mock LLM that returns canned responses (no API calls in unit tests)

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared fixtures for product input, routing, and mock LLM"
```

---

## Task 9: Agent Base Factory

**Files:**
- Create: `src/sportmaster_card/agents/base.py`
- Test: `tests/agents/test_base.py`

- [ ] **Step 1–5:** TDD cycle for `BaseAgentFactory` — loads agent config from YAML, creates CrewAI Agent with correct role/goal/backstory/model. All agents use this factory.

---

## Task 10: Agent Config YAML

**Files:**
- Create: `src/sportmaster_card/config/agents.yaml`

- [ ] **Step 1:** Write YAML config for Phase 1 agents:
  - `router` — Gemini Flash, classification role
  - `data_validator` — Gemini Flash, validation role
  - `external_researcher` — Gemini Flash + Web, parsing role
  - `content_generator` — Claude Sonnet, generation role
  - `copy_editor` — Claude Haiku, editing role

- [ ] **Step 2: Commit**

---

## Task 11: Router Agent

**Files:**
- Create: `src/sportmaster_card/agents/router.py`
- Test: `tests/agents/test_router.py`

- [ ] **Step 1: Write failing test** — RouterAgent takes ProductInput, returns RoutingProfile
- [ ] **Step 2: Run test, verify FAIL**
- [ ] **Step 3: Implement** — CrewAI Agent with classification task using product attributes
- [ ] **Step 4: Run test, verify PASS**
- [ ] **Step 5: Commit**

---

## Task 12: Data Validator Agent

**Files:**
- Create: `src/sportmaster_card/agents/data_validator.py`
- Test: `tests/agents/test_data_validator.py`

- [ ] **Step 1–5:** TDD cycle. Agent checks completeness of ProductInput fields, produces ValidationReport + DataProvenance[].

---

## Task 13: External Researcher Agent

**Files:**
- Create: `src/sportmaster_card/agents/external_researcher.py`
- Test: `tests/agents/test_external_researcher.py`

- [ ] **Step 1–5:** TDD cycle. Agent parses competitor cards (mocked in tests), produces CompetitorBenchmark + DataProvenance[].

---

## Task 14: Content Generator Agent

**Files:**
- Create: `src/sportmaster_card/agents/content_generator.py`
- Test: `tests/agents/test_content_generator.py`

- [ ] **Step 1–5:** TDD cycle. Agent generates PlatformContent for SM from CuratedProfile + ContentBrief + PlatformProfile. This is the KEY agent — most complex prompt.

---

## Task 15: Copy Editor Agent

**Files:**
- Create: `src/sportmaster_card/agents/copy_editor.py`
- Test: `tests/agents/test_copy_editor.py`

- [ ] **Step 1–5:** TDD cycle. Agent checks grammar, length limits, formatting. Produces EditedPlatformContent.

---

## Task 16: Excel Parser Tool

**Files:**
- Create: `src/sportmaster_card/tools/excel_parser.py`
- Test: `tests/tools/test_excel_parser.py`

- [ ] **Step 1–5:** TDD cycle. CrewAI Tool that reads one row from the Excel template and returns a ProductInput.

---

## Task 17: Pilot Flow — End-to-End Orchestration

**Files:**
- Create: `src/sportmaster_card/flows/pilot_flow.py`
- Test: `tests/flows/test_pilot_flow.py`

- [ ] **Step 1: Write failing integration test** — PilotFlow takes a ProductInput, runs all agents, returns PlatformContent
- [ ] **Step 2–4:** Implement CrewAI Flow with `@start` → router → `@listen` → crew (validator → researcher → generator → editor)
- [ ] **Step 5: Commit**

---

## Task 18: Integration Test — Full Pipeline

**Files:**
- Create: `tests/integration/test_full_pipeline.py`

- [ ] **Step 1:** Write end-to-end test with mocked LLM that validates:
  - ProductInput → Router → correct RoutingProfile
  - RoutingProfile → DataValidator → ValidationReport
  - Enriched data → ContentGenerator → PlatformContent with all required fields
  - PlatformContent → CopyEditor → EditedPlatformContent passes length limits

- [ ] **Step 2: Commit**

---

## Task 19: Documentation & README

**Files:**
- Create: `README.md`
- Create: `docs/architecture/phase1-pipeline.md`

- [ ] **Step 1:** Write comprehensive README with:
  - Project overview and architecture diagram (ASCII)
  - Quick start guide
  - Agent descriptions table
  - Model schema summary
  - Configuration guide (OpenRouter API key, YAML configs)

- [ ] **Step 2:** Write architecture doc with data flow diagrams

- [ ] **Step 3: Commit and push**

```bash
git add .
git commit -m "docs: add README and architecture documentation for Phase 1"
git push -u origin main
```

---

## Execution Order & Dependencies

```
Task 1 (ProductInput) ──┐
Task 2 (RoutingProfile) ─┤
Task 3 (DataProvenance) ─┤
Task 4 (Enrichment) ─────┤── All models independent
Task 5 (Content) ────────┤
Task 6 (PlatformProfile) ┘
         │
Task 7 (LLM Config) ─────── Independent
Task 8 (Conftest) ────────── Depends on Tasks 1-6
         │
Task 9 (Base Factory) ────── Depends on Task 7
Task 10 (Agents YAML) ────── Independent
         │
Task 11 (Router) ──────────┐
Task 12 (DataValidator) ───┤── Depend on Tasks 8-10
Task 13 (ExtResearcher) ───┤
Task 14 (ContentGen) ──────┤
Task 15 (CopyEditor) ──────┘
         │
Task 16 (Excel Parser) ──── Depends on Task 1
Task 17 (Pilot Flow) ─────── Depends on Tasks 11-16
Task 18 (Integration) ────── Depends on Task 17
Task 19 (Docs) ────────────── Last
```

**Parallelizable groups:**
- Group A (Tasks 1–6): all models — fully parallel
- Group B (Tasks 7, 10): configs — parallel with Group A
- Group C (Tasks 11–15): agents — parallel after Groups A+B
- Group D (Tasks 17–19): integration — sequential after all
