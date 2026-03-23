# Phase 1 Pipeline Architecture

This document describes the Phase 1 pilot pipeline for the Sportmaster Card Agent system. It covers the end-to-end data flow, agent contracts, model specifications, platform configuration, and extension points for Phase 2.

## Table of Contents

- [Pipeline Overview](#pipeline-overview)
- [Data Flow](#data-flow)
- [Agent Descriptions](#agent-descriptions)
  - [1. Router Agent](#1-router-agent)
  - [2. Data Validator Agent](#2-data-validator-agent)
  - [3. External Researcher Agent](#3-external-researcher-agent)
  - [4. Content Generator Agent](#4-content-generator-agent)
  - [5. Copy Editor Agent](#5-copy-editor-agent)
- [Models at Each Stage](#models-at-each-stage)
- [PlatformProfile Configuration](#platformprofile-configuration)
- [Data Provenance System](#data-provenance-system)
- [Processing Profile Routing Matrix](#processing-profile-routing-matrix)
- [Extension Points for Phase 2](#extension-points-for-phase-2)

---

## Pipeline Overview

The Phase 1 pilot implements a sequential 5-agent pipeline for the **footwear category** on the **Sportmaster website** (sm_site). All agents operate in **deterministic mode** (no LLM calls) with template-based content generation and rule-based validation.

```
                        PHASE 1 PILOT PIPELINE
                        ======================

  Excel Template (.xlsx)
  209 columns, 13 blocks
  1 row = 1 MCM (merchandising color model)
         |
         v
  +-- ExcelParserTool ----+
  |  Russian headers ->   |
  |  English field names  |
  |  Type coercion        |
  +----------+------------+
             |
             v  ProductInput
  +----------+---------------------------+
  |  1. Router Agent                     |
  |     Deterministic classification     |
  |     IN:  ProductInput                |
  |     OUT: RoutingProfile              |
  |          (flow_type, profile,        |
  |           platforms, attr_class)     |
  +----------+---------------------------+
             |
             v  RoutingProfile
  +----------+---------------------------+
  |  2. Data Validator Agent             |
  |     Completeness & presence checks   |
  |     IN:  ProductInput                |
  |     OUT: ValidationReport            |
  |          + DataProvenance[]          |
  +----------+---------------------------+
             |
             v  ValidationReport
  +----------+---------------------------+
  |  3. External Researcher Agent        |
  |     Competitor intelligence (stub)   |
  |     IN:  ProductInput                |
  |     OUT: CompetitorBenchmark         |
  |          + DataProvenance[]          |
  +----------+---------------------------+
             |
             v  CompetitorBenchmark
  +----------+---------------------------+
  |  4. Content Generator Agent          |
  |     Template-based text generation   |
  |     IN:  ProductInput + platform_id  |
  |     OUT: PlatformContent             |
  +----------+---------------------------+
             |
             v  PlatformContent
  +----------+---------------------------+
  |  5. Copy Editor Agent                |
  |     Character limits, whitespace     |
  |     IN:  PlatformContent             |
  |     OUT: PlatformContent (edited)    |
  +----------+---------------------------+
             |
             v
  PipelineResult
  (all intermediate + final outputs)
```

## Data Flow

The pipeline processes one MCM at a time. Each agent receives specific inputs and produces typed Pydantic outputs. The `PilotFlow` class orchestrates the sequence:

```python
# Simplified PilotFlow.run() logic:

routing       = router.route(product, flow_type="1P")
validation, _ = validator.validate(product)
benchmark, _  = researcher.research(product)
generated     = generator.generate(product, platform_id="sm_site")
edited        = editor.edit(generated)

return PipelineResult(
    mcm_id=product.mcm_id,
    routing_profile=routing,
    validation_report=validation,
    competitor_benchmark=benchmark,
    generated_content=generated,
    edited_content=edited,
    provenance_entries=[...],
)
```

### Model Flow Diagram

```
ProductInput
  |
  +---> RoutingProfile
  |       flow_type: FlowType (1P/3P)
  |       processing_profile: ProcessingProfile (minimal/standard/premium/complex)
  |       target_platforms: ["sm_site"]
  |       attribute_class: "обувь.кроссовки"
  |
  +---> ValidationReport
  |       field_validations: list[FieldValidation]
  |       missing_required: list[str]
  |       overall_completeness: float (0-1)
  |       is_valid: bool
  |
  +---> CompetitorBenchmark
  |       competitors: list[CompetitorCard]
  |       benchmark_summary: str
  |       average_price: float | None
  |       common_features: list[str]
  |
  +---> PlatformContent (generated)
  |       product_name: str          # SEO-optimized
  |       description: str           # Main text block
  |       benefits: list[Benefit]    # 4-8 bullets
  |       seo_title: str             # HTML <title>
  |       seo_meta_description: str  # HTML meta
  |       seo_keywords: list[str]    # Target keywords
  |
  +---> PlatformContent (edited)
          Same structure, enforced limits
```

---

## Agent Descriptions

### 1. Router Agent

**Module:** `agents/router.py`
**Class:** `RouterAgent`
**v0.3 Agent ID:** Agent 1.2

**Purpose:** Classify the incoming product and determine the pipeline configuration. The Router is the entry point of the entire multi-agent system.

**Input:**

| Parameter   | Type           | Description                        |
|-------------|----------------|------------------------------------|
| `product`   | `ProductInput` | Raw Excel row data                 |
| `flow_type` | `str`          | `"1P"` or `"3P"` (default: `"1P"`) |

**Output:**

| Field                | Type                | Description                           |
|----------------------|---------------------|---------------------------------------|
| `mcm_id`             | `str`               | Correlation ID                        |
| `flow_type`          | `FlowType`          | `FIRST_PARTY` or `THIRD_PARTY`        |
| `processing_profile` | `ProcessingProfile` | `minimal` / `standard` / `premium` / `complex` |
| `target_platforms`    | `list[str]`         | Platform IDs (Phase 1: `["sm_site"]`) |
| `attribute_class`     | `str`               | Dot-notation category (e.g., `"обувь.кроссовки"`) |

**Routing Logic (Phase 1 -- deterministic):**

1. **Flow type:** `"3P"` input -> `THIRD_PARTY`; all other -> `FIRST_PARTY`
2. **Processing profile:** Derived from `assortment_type` x `assortment_level` matrix (see [Routing Matrix](#processing-profile-routing-matrix))
3. **Target platforms:** Hardcoded to `["sm_site"]` in Phase 1
4. **Attribute class:** `category.product_group` normalized to lowercase

**Phase 2 changes:** LLM-based classification for ambiguous products; dynamic platform selection.

---

### 2. Data Validator Agent

**Module:** `agents/data_validator.py`
**Class:** `DataValidatorAgent`
**v0.3 Agent ID:** Agent 1.3

**Purpose:** Check the completeness and validity of raw Excel data. Produces a validation report and data provenance entries for each field.

**Input:**

| Parameter | Type           | Description        |
|-----------|----------------|--------------------|
| `product` | `ProductInput` | Raw Excel row data |

**Output (tuple):**

| Component            | Type                   | Description                       |
|----------------------|------------------------|-----------------------------------|
| `ValidationReport`   | `ValidationReport`     | Per-field validation + completeness score |
| `provenance_entries` | `list[DataProvenance]` | One entry per validated field      |

**Required Fields (must be present for `is_valid=True`):**

`mcm_id`, `brand`, `category`, `product_group`, `product_subgroup`, `product_name`

**Optional Fields (tracked for completeness score):**

`description`, `gender`, `season`, `color`, `assortment_segment`, `assortment_type`, `assortment_level`, `technologies`, `composition`, `photo_urls`

**Completeness formula:**

```
overall_completeness = count(fields with non-None value) / total_fields_checked
```

**Phase 2 changes:** Format validation (e.g., MCM ID pattern), cross-field consistency checks, LLM-based quality assessment.

---

### 3. External Researcher Agent

**Module:** `agents/external_researcher.py`
**Class:** `ExternalResearcherAgent`
**v0.3 Agent ID:** Agent 1.5

**Purpose:** Research competitor product cards on external marketplaces and produce a competitive benchmark.

**Input:**

| Parameter | Type           | Description        |
|-----------|----------------|--------------------|
| `product` | `ProductInput` | Product to research |

**Output (tuple):**

| Component              | Type                   | Description                          |
|------------------------|------------------------|--------------------------------------|
| `CompetitorBenchmark`  | `CompetitorBenchmark`  | Aggregated competitor intelligence    |
| `provenance_entries`   | `list[DataProvenance]` | Provenance for extracted competitor data |

**Competitor Data Extracted:**

| Field          | Type       | Source                     |
|----------------|------------|----------------------------|
| `platform`     | `str`      | `"wb"`, `"ozon"`, `"lamoda"` |
| `product_name` | `str`      | Marketplace page title     |
| `description`  | `str`      | Product description block  |
| `price`        | `float`    | Current price in RUB       |
| `rating`       | `float`    | Star rating (1-5)          |
| `key_features` | `list[str]`| Extracted feature bullets  |
| `url`          | `str`      | Direct link to listing     |

**Phase 1 note:** Returns **stub data** -- no real scraping. The interface and data models are production-ready. Real scraping tools (Crawl4AI, Playwright, BeautifulSoup4) will be integrated in Phase 2.

**Phase 2 changes:** Real marketplace scraping; proxy rotation; rate limiting; result caching.

---

### 4. Content Generator Agent

**Module:** `agents/content_generator.py`
**Class:** `ContentGeneratorAgent`
**v0.3 Agent ID:** Agent 2.7

**Purpose:** Generate all text content for a product card on a specific platform. This is the **most important agent** in the pipeline.

**Input:**

| Parameter     | Type           | Description                        |
|---------------|----------------|------------------------------------|
| `product`     | `ProductInput` | Enriched product data              |
| `platform_id` | `str`          | Target platform (default: `"sm_site"`) |
| `max_title`   | `int`          | Title character limit (default: 150) |
| `max_desc`    | `int`          | Description character limit (default: 3000) |

**Output:**

| Field                      | Type           | Description                          |
|----------------------------|----------------|--------------------------------------|
| `mcm_id`                   | `str`          | Correlation ID                       |
| `platform_id`              | `str`          | Target platform                      |
| `product_name`             | `str`          | SEO-optimized product name           |
| `description`              | `str`          | Main description text                |
| `benefits`                 | `list[Benefit]`| 1-8 benefit bullets                  |
| `seo_title`                | `str`          | HTML title tag                       |
| `seo_meta_description`     | `str`          | HTML meta description                |
| `seo_keywords`             | `list[str]`    | Target keywords                      |
| `content_hash`             | `str`          | SHA-256 for change detection         |
| `source_curated_profile_hash` | `str`       | Source data version hash             |

**Content Generation Strategy (Phase 1 -- template-based):**

```
Product Name:  "{brand} {gender_adjective} {product_subgroup} {product_name}"
               Example: "Nike Мужские беговые кроссовки Air Zoom Pegasus 41"

Description:   "{product_subgroup} {brand} {product_name} -- {feature summary}.
               {technology details}. {composition details}."

Benefits:      One Benefit per technology in product.technologies
               title = technology name, description = generated from templates

SEO Title:     "Купить {product_name} | Sportmaster"
SEO Meta:      "{product_name} -- {product_subgroup} от {brand}. {key feature}."
SEO Keywords:  [brand.lower(), product_name.lower(), product_subgroup.lower(), ...]
```

**Phase 2 changes:** LLM-powered generation (Claude Sonnet); CuratedProfile input instead of raw ProductInput; ContentBrief + SEOProfile integration; per-platform tone adaptation.

---

### 5. Copy Editor Agent

**Module:** `agents/copy_editor.py`
**Class:** `CopyEditorAgent`
**v0.3 Agent ID:** Agent 2.10

**Purpose:** Polish generated content by enforcing character limits, cleaning whitespace, and ensuring consistent formatting.

**Input:**

| Parameter | Type              | Description             |
|-----------|-------------------|-------------------------|
| `content` | `PlatformContent` | Raw generated content   |
| `max_title` | `int`           | Title limit (default: 150) |
| `max_desc`  | `int`           | Description limit (default: 3000) |

**Output:**

| Field | Type              | Description                |
|-------|-------------------|----------------------------|
| Same  | `PlatformContent` | Edited content with enforced limits |

**Editing Rules (Phase 1 -- deterministic):**

1. **Truncation:** Truncate `product_name`, `description`, and `seo_title` to platform limits with word-boundary awareness (no mid-word cuts)
2. **Whitespace:** Strip leading/trailing whitespace from all text fields
3. **Benefit cleanup:** Strip whitespace from benefit titles and descriptions
4. **Passthrough:** `seo_keywords`, `content_hash`, and other fields pass through unchanged

**Phase 1 note:** Stylistic and grammar review is done **manually** by the GPTK team. The Copy Editor handles only mechanical formatting rules.

**Phase 2 changes:** LLM-powered grammar correction (Claude Haiku); style guide enforcement; brand tone verification.

---

## Models at Each Stage

### Entry Point

| Model          | Module           | Fields                                                |
|----------------|------------------|-------------------------------------------------------|
| `ProductInput` | `product_input`  | `mcm_id`, `brand`, `category`, `product_group`, `product_subgroup`, `product_name` + 9 optional fields |

### Routing Stage

| Model              | Module    | Key Fields                                              |
|--------------------|-----------|---------------------------------------------------------|
| `FlowType`         | `routing` | `FIRST_PARTY` ("1P"), `THIRD_PARTY` ("3P")              |
| `ProcessingProfile`| `routing` | `MINIMAL`, `STANDARD`, `PREMIUM`, `COMPLEX`             |
| `RoutingProfile`   | `routing` | `mcm_id`, `flow_type`, `processing_profile`, `target_platforms`, `attribute_class` |

### Enrichment Stage (UC1)

| Model                | Module       | Key Fields                                                |
|----------------------|--------------|-----------------------------------------------------------|
| `FieldValidation`    | `enrichment` | `field_name`, `is_present`, `is_valid`, `issue`           |
| `ValidationReport`   | `enrichment` | `mcm_id`, `field_validations`, `missing_required`, `overall_completeness`, `is_valid` |
| `CompetitorCard`     | `enrichment` | `platform`, `product_name`, `description`, `price`, `rating`, `key_features`, `url` |
| `CompetitorBenchmark`| `enrichment` | `mcm_id`, `competitors`, `benchmark_summary`, `average_price`, `common_features` |

### Content Stage (UC2)

| Model             | Module    | Key Fields                                                    |
|-------------------|-----------|---------------------------------------------------------------|
| `ContentBrief`    | `content` | `mcm_id`, `platform_id`, `brief_type`, `tone_of_voice`, `required_sections`, `max_description_length`, `max_title_length` |
| `Benefit`         | `content` | `title`, `description`                                        |
| `PlatformContent` | `content` | `mcm_id`, `platform_id`, `product_name`, `description`, `benefits`, `seo_title`, `seo_meta_description`, `seo_keywords`, `content_hash` |
| `QualityScore`    | `content` | `mcm_id`, `platform_id`, `overall_score`, `readability_score`, `seo_score`, `factual_accuracy_score`, `brand_compliance_score`, `uniqueness_score` |

### Provenance (cross-cutting)

| Model              | Module       | Key Fields                                                  |
|--------------------|--------------|-------------------------------------------------------------|
| `SourceType`       | `provenance` | `INTERNAL`, `EXTERNAL`, `PHOTO`, `SKETCH`, `INTERNET_PHOTO`, `MANUAL` |
| `DataProvenance`   | `provenance` | `attribute_name`, `value`, `source_type`, `source_name`, `confidence`, `is_disputed`, `agent_id`, `timestamp` |
| `DataProvenanceLog`| `provenance` | `mcm_id`, `entries`, `disputed_count` (computed), `alert_required` (computed) |

### Pipeline Result

| Model            | Module       | Key Fields                                                |
|------------------|--------------|-----------------------------------------------------------|
| `PipelineResult` | `pilot_flow` | `mcm_id`, `routing_profile`, `validation_report`, `competitor_benchmark`, `generated_content`, `edited_content`, `provenance_entries` |

---

## PlatformProfile Configuration

Each target platform is configured via a YAML file in `config/platforms/`. The `PlatformProfile` model loads and validates these files.

### SM Site Profile (`config/platforms/sm_site.yaml`)

```yaml
platform_id: sm_site
platform_type: "1P"
platform_name: "Sportmaster Website"
text_requirements:
  max_title_length: 150
  max_description_length: 3000
  required_sections:
    - description
    - benefits
    - technologies
    - composition
  forbidden_words: []
  naming_rules: "Бренд + Тип + Модель + Характеристика"
  seo_keywords_source: "internal_seo_team"
  seo_rules:
    - "Ключевые слова в первом абзаце"
    - "Title содержит бренд и категорию"
  tone_of_voice: "professional"
  benefits_format: "title + 1-2 sentence description"
  html_allowed: true
```

### Model Structure

```
PlatformProfile
├── platform_id: str          # "sm_site", "wb", "ozon"
├── platform_type: PlatformType  # 1P / 3P / VMP
├── platform_name: str        # Human-readable name
└── text_requirements: TextRequirements
    ├── max_title_length: int       # Default: 150
    ├── max_description_length: int # Default: 3000
    ├── required_sections: list[str]
    ├── forbidden_words: list[str]
    ├── naming_rules: str
    ├── seo_keywords_source: str
    ├── seo_rules: list[str]
    ├── tone_of_voice: str          # Default: "professional"
    ├── benefits_format: str
    └── html_allowed: bool          # Default: false
```

### Loading a Profile

```python
from sportmaster_card.models.platform_profile import PlatformProfile

profile = PlatformProfile.from_yaml("src/sportmaster_card/config/platforms/sm_site.yaml")
print(profile.text_requirements.max_title_length)  # 150
print(profile.text_requirements.tone_of_voice)      # "professional"
```

---

## Data Provenance System

Every attribute extracted or validated by an enrichment agent carries a `DataProvenance` record -- a "birth certificate" tracking where the value came from, how confident the extraction is, and whether the value is disputed.

### Provenance Flow

```
Agent 1.3 (Data Validator)
  --> DataProvenance(source_type=INTERNAL, source_name="Excel шаблон")

Agent 1.5 (External Researcher)
  --> DataProvenance(source_type=EXTERNAL, source_name="WB" / "Ozon")

              |
              v  (aggregated)
  DataProvenanceLog(mcm_id="MCM-...")
    disputed_count: int     # auto-computed
    alert_required: bool    # auto-computed (True if any disputes)
              |
              v
  Data Curator (Phase 2) reviews disputed entries
```

### Source Types

| SourceType       | Origin                              | Typical Confidence |
|------------------|-------------------------------------|--------------------|
| `INTERNAL`       | Excel template, Sportmaster DB, ERP | 0.9 - 1.0         |
| `EXTERNAL`       | Competitor sites (WB, Ozon), APIs   | 0.5 - 0.8         |
| `PHOTO`          | Official supplier product photos    | 0.6 - 0.9         |
| `SKETCH`         | Technical drawings                  | 0.7 - 0.95        |
| `INTERNET_PHOTO` | Web-scraped product images          | 0.3 - 0.7         |
| `MANUAL`         | Human operator manual entry         | 0.95 - 1.0        |

---

## Processing Profile Routing Matrix

The Router Agent uses this matrix to determine processing depth from product attributes:

| `assortment_type` \ `assortment_level` | Low     | Mid      | High    | Premium |
|----------------------------------------|---------|----------|---------|---------|
| **Basic**                              | MINIMAL | STANDARD | PREMIUM | PREMIUM |
| **Fashion**                            | STANDARD| STANDARD | PREMIUM | PREMIUM |
| **Seasonal**                           | MINIMAL | STANDARD | PREMIUM | PREMIUM |

**Special case:** Products flagged as complex (multi-sport, technical) -> `COMPLEX` regardless of matrix.

**Profile effects on agents:**

| Profile    | Enrichment Depth | Content Quality   | Throughput |
|------------|------------------|-------------------|------------|
| `MINIMAL`  | Basic checks     | Template content  | Highest    |
| `STANDARD` | Standard checks  | Balanced content  | Medium     |
| `PREMIUM`  | Deep research    | Polished content  | Low        |
| `COMPLEX`  | Specialist review| Custom handling   | Lowest     |

---

## Extension Points for Phase 2

The Phase 1 architecture is designed for incremental extension. Key integration points:

### 1. LLM Integration

**Where:** Each agent's internal methods (`_generate_*`, `_validate_*`, `_research_*`)

**How:** Replace template logic with LLM calls via `utils/llm_config.get_llm()`. The public interface (`route()`, `validate()`, `generate()`, `edit()`) stays unchanged.

```python
# Phase 1 (current):
def _generate_description(self, product: ProductInput) -> str:
    return f"{product.product_subgroup} {product.brand} {product.product_name}..."

# Phase 2 (planned):
def _generate_description(self, product: ProductInput, brief: ContentBrief) -> str:
    llm = get_llm("claude_sonnet")
    return llm.invoke(prompt_template.format(product=product, brief=brief))
```

### 2. CrewAI Flow Integration

**Where:** `flows/pilot_flow.py`

**How:** Replace the plain `PilotFlow` class with a CrewAI Flow using `@start` and `@listen` decorators. Agent sequencing becomes event-driven instead of procedural.

### 3. Additional Agents (v0.3 Architecture)

The full v0.3 architecture defines 30+ agents across four contours:

| Contour | Agents                                                        | Phase 1 Status |
|---------|---------------------------------------------------------------|----------------|
| UC1     | Data Validator, Visual Interpreter, External/Internal Researcher, Synectics Agent, Data Enricher, Data Curator | 2 of 7 implemented |
| UC2     | Brief Selector, SEO Analyst, Structure Planner, Content Generator, Fact Checker, Brand Compliance, Style Editor, Copy Editor, Quality Controller | 2 of 9 implemented |
| UC3     | Attribute Mapper, Completeness Monitor, Publication Agent      | 0 of 3         |
| UC4     | Visual Content Generator (GenAI)                               | 0 of 1         |

### 4. Additional Platform Profiles

**Where:** `config/platforms/`

**How:** Add YAML files for each marketplace:

- `wb.yaml` -- Wildberries (title: 60 chars, no HTML)
- `ozon.yaml` -- Ozon (title: 200 chars, rich text)
- `lamoda.yaml` -- Lamoda (fashion-focused tone)
- `megamarket.yaml` -- SberMegaMarket

### 5. RAG Knowledge Base

**Where:** New module `src/sportmaster_card/knowledge/`

**How:** ChromaDB or Qdrant vector store for brand guidelines, technology databases, and historical product cards. Agents query the knowledge base during enrichment and content generation.

### 6. Real Competitor Scraping

**Where:** `agents/external_researcher.py` internal methods

**Dependencies:** `crawl4ai`, `playwright`, `beautifulsoup4` (already in `pyproject.toml` optional deps)

**How:** Replace `_get_stub_competitors()` with real scraping methods:
- `_scrape_wb(product)` -- Wildberries API/scraping
- `_scrape_ozon(product)` -- Ozon API/scraping
- `_scrape_lamoda(product)` -- Lamoda scraping

### 7. Quality Gate

**Where:** Between Content Generator and Copy Editor

**How:** Insert `QualityScore` evaluation. If `overall_score < 0.7`, regenerate content with feedback from the `issues` list. The `QualityScore` model and `passes_threshold` property are already implemented.

```
Content Generator -> QualityScore check -> if passes -> Copy Editor
                                        -> if fails  -> regenerate with issues feedback
```
