# Sportmaster Card Agent

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Framework](https://img.shields.io/badge/framework-CrewAI-orange)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

Sportmaster Card Agent is a multi-agent system that automates the full lifecycle of product card creation for [Sportmaster](https://www.sportmaster.ru/) -- Russia's largest sporting goods retailer.

The system takes raw product data from Sportmaster's 209-column Excel template (one row = one MCM, a merchandising color model), enriches it with validation and competitor intelligence, generates SEO-optimized content tailored to each target platform, and polishes the result through automated editing. Phase 1 covers the pilot pipeline for the footwear category with five core agents operating in deterministic (rule-based) mode, ready for LLM integration in Phase 2.

Built on [CrewAI](https://www.crewai.com/) with [Pydantic](https://docs.pydantic.dev/) models and [OpenRouter](https://openrouter.ai/) for multi-model LLM access.

## Architecture

```
INPUT: Excel template (1 MCM row, 209 columns)
  |
  v
+-- Router Agent ----------------------------+
|  Classifies product (1P/3P),               |
|  selects pipeline & processing profile     |
|  IN:  ProductInput                         |
|  OUT: RoutingProfile                       |
+--------------------+-----------------------+
                     |
+-- UC1: Data Enrichment --------------------+
|  Data Validator                            |
|    -> ValidationReport + DataProvenance[]  |
|  External Researcher                       |
|    -> CompetitorBenchmark + DataProvenance[]|
+--------------------+-----------------------+
                     |
+-- UC2: Content Generation -----------------+
|  Content Generator                         |
|    -> PlatformContent (per platform)       |
|  Copy Editor                               |
|    -> PlatformContent (edited)             |
+--------------------+-----------------------+
                     |
                     v
OUTPUT: Edited PlatformContent
        (product name, description, benefits,
         SEO title, meta description, keywords)
```

## Agents

| # | Agent               | Role                              | Model (v0.3)    | Est. Cost/MCM |
|---|---------------------|-----------------------------------|-----------------|---------------|
| 1 | Router              | Classify product, select pipeline | gemini_flash    | ~$0.001       |
| 2 | Data Validator      | Check completeness & validity     | gemini_flash    | ~$0.002       |
| 3 | External Researcher | Competitor benchmarking           | gemini_flash    | ~$0.005       |
| 4 | Content Generator   | Generate platform content         | claude_sonnet   | ~$0.030       |
| 5 | Copy Editor         | Grammar, formatting, limits       | claude_haiku    | ~$0.005       |

**Total estimated cost per MCM: ~$0.04** (Phase 1 pilot).

## Quick Start

### Prerequisites

- Python 3.12+
- An [OpenRouter](https://openrouter.ai/) API key (for LLM-powered mode; not needed for deterministic Phase 1)

### Installation

```bash
git clone https://github.com/your-org/sportmaster-card-agent.git
cd sportmaster-card-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install with dev dependencies
pip install -e ".[dev]"
```

### Configuration

Set your OpenRouter API key (required only for LLM mode in Phase 2+):

```bash
export OPENROUTER_API_KEY="sk-or-v1-your-key-here"
```

### Run the Pilot Pipeline

```python
from sportmaster_card.models.product_input import ProductInput
from sportmaster_card.flows.pilot_flow import PilotFlow

# Create a product from Excel data
product = ProductInput(
    mcm_id="MCM-001-BLK-42",
    brand="Nike",
    category="Обувь",
    product_group="Кроссовки",
    product_subgroup="Беговые кроссовки",
    product_name="Nike Air Zoom Pegasus 41",
    description="Беговые кроссовки с амортизацией Air Zoom",
    gender="Мужской",
    season="Весна-Лето 2026",
    color="Чёрный",
    technologies=["Air Zoom", "React", "Flywire"],
)

# Run the full pipeline
flow = PilotFlow()
result = flow.run(product)

# Inspect outputs
print(result.routing_profile.processing_profile)   # standard
print(result.validation_report.overall_completeness) # 1.0
print(result.edited_content.product_name)            # SEO-optimized name
print(result.edited_content.description)             # Generated description
```

### Parse from Excel

```python
from sportmaster_card.tools.excel_parser import ExcelParserTool

parser = ExcelParserTool()
row = {
    "Код МЦМ": "MCM-001-BLK-42",
    "Бренд": "Nike",
    "Категория": "Обувь",
    "Группа товаров": "Кроссовки",
    "Товарная группа": "Беговые кроссовки",
    "Наименование товара": "Nike Air Zoom Pegasus 41",
    "Технологии": "Air Zoom, React, Flywire",
}
product = parser.parse_row(row)
```

## Project Structure

```
sportmaster-card-agent/
├── src/sportmaster_card/
│   ├── __init__.py              # Package metadata, version
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseAgentFactory (YAML -> CrewAI Agent)
│   │   ├── router.py            # RouterAgent -- product classification
│   │   ├── data_validator.py    # DataValidatorAgent -- completeness checks
│   │   ├── external_researcher.py # ExternalResearcherAgent -- competitor intel
│   │   ├── content_generator.py # ContentGeneratorAgent -- content creation
│   │   └── copy_editor.py       # CopyEditorAgent -- editing & polishing
│   ├── config/
│   │   ├── __init__.py
│   │   ├── agents.yaml          # Agent role/goal/model definitions
│   │   └── platforms/
│   │       └── sm_site.yaml     # Sportmaster site platform profile
│   ├── flows/
│   │   ├── __init__.py
│   │   └── pilot_flow.py        # PilotFlow -- end-to-end Phase 1 pipeline
│   ├── models/
│   │   ├── __init__.py          # Model hierarchy documentation
│   │   ├── product_input.py     # ProductInput -- Excel row entry point
│   │   ├── routing.py           # RoutingProfile, FlowType, ProcessingProfile
│   │   ├── enrichment.py        # ValidationReport, CompetitorBenchmark
│   │   ├── content.py           # PlatformContent, ContentBrief, QualityScore
│   │   ├── platform_profile.py  # PlatformProfile, TextRequirements
│   │   └── provenance.py        # DataProvenance, DataProvenanceLog
│   ├── tools/
│   │   ├── __init__.py
│   │   └── excel_parser.py      # ExcelParserTool -- Russian columns -> ProductInput
│   └── utils/
│       ├── __init__.py
│       └── llm_config.py        # OpenRouter LLM configuration helper
├── tests/
│   ├── agents/                  # Agent unit tests
│   ├── flows/                   # Flow integration tests
│   ├── models/                  # Model validation tests
│   ├── tools/                   # Tool unit tests
│   ├── integration/             # End-to-end integration tests
│   ├── conftest.py              # Shared fixtures
│   └── test_llm_config.py       # LLM config tests
├── docs/
│   └── architecture/
│       └── phase1-pipeline.md   # Detailed Phase 1 architecture
├── pyproject.toml               # Build config, dependencies, tool settings
└── README.md                    # This file
```

## Models

| Model                | Module           | Role                                          |
|----------------------|------------------|-----------------------------------------------|
| `ProductInput`       | `product_input`  | Raw Excel row data (MCM entry point)          |
| `RoutingProfile`     | `routing`        | Router output: flow type, profile, platforms   |
| `FlowType`           | `routing`        | Enum: `1P` (full) / `3P` (lightweight)        |
| `ProcessingProfile`  | `routing`        | Enum: minimal / standard / premium / complex   |
| `FieldValidation`    | `enrichment`     | Per-field validation result                    |
| `ValidationReport`   | `enrichment`     | Data Validator output: completeness report     |
| `CompetitorCard`     | `enrichment`     | Single competitor listing from marketplace     |
| `CompetitorBenchmark`| `enrichment`     | External Researcher output: competitor intel   |
| `ContentBrief`       | `content`        | Brief Selector output: generation instructions |
| `PlatformContent`    | `content`        | Content Generator output: all text per platform|
| `Benefit`            | `content`        | Product benefit bullet (title + description)   |
| `QualityScore`       | `content`        | Quality Controller output: multi-dim score     |
| `PlatformProfile`    | `platform_profile` | Platform config (text limits, SEO rules)     |
| `TextRequirements`   | `platform_profile` | Text constraints for a platform              |
| `PlatformType`       | `platform_profile` | Enum: 1P / 3P / VMP                         |
| `DataProvenance`     | `provenance`     | Attribute origin tracking record               |
| `DataProvenanceLog`  | `provenance`     | Aggregated provenance for one product          |
| `SourceType`         | `provenance`     | Enum: internal / external / photo / sketch / manual |
| `PipelineResult`     | `pilot_flow`     | Full pipeline output container                 |

## Configuration

### Agent Configuration (`config/agents.yaml`)

Agent behavior is configured in YAML, not code. Each agent definition includes:
- **role**: displayed in logs and traces
- **goal**: drives LLM behavior (the agent's objective)
- **backstory**: expertise context for the LLM persona
- **model**: LLM model key (`gemini_flash`, `claude_haiku`, `claude_sonnet`)

### Platform Profiles (`config/platforms/*.yaml`)

Each target platform has a YAML file defining:
- `max_title_length` / `max_description_length` -- character limits
- `required_sections` -- mandatory content sections
- `forbidden_words` -- banned terms
- `tone_of_voice` -- writing style (`professional`, `casual`, `sporty`)
- `seo_rules` -- SEO constraints
- `html_allowed` -- whether HTML markup is permitted

### LLM Configuration (`utils/llm_config.py`)

Models are routed through OpenRouter:

| Friendly Name    | OpenRouter Model ID             | Use Case                     |
|------------------|---------------------------------|------------------------------|
| `claude_sonnet`  | `anthropic/claude-sonnet-4`     | Content generation, quality  |
| `claude_haiku`   | `anthropic/claude-haiku-4-5`    | Editing, briefs, compliance  |
| `gemini_flash`   | `google/gemini-2.0-flash-001`   | Classification, validation   |

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sportmaster_card --cov-report=term-missing

# Run specific test module
pytest tests/models/test_content.py -v

# Run agent tests only
pytest tests/agents/ -v

# Run flow integration tests
pytest tests/flows/ -v

# Type checking
mypy src/sportmaster_card/

# Linting
ruff check src/ tests/
```

## Roadmap

### Phase 1 (Current) -- Pilot Pipeline

- [x] Pydantic models for all data contracts
- [x] 5 deterministic agents (Router, Validator, Researcher, Generator, Editor)
- [x] End-to-end PilotFlow orchestration
- [x] ExcelParserTool for MCM template ingestion
- [x] Platform profile system (SM site)
- [x] Data provenance tracking
- [x] Comprehensive test suite

### Phase 2 -- LLM Integration

- [ ] Connect agents to OpenRouter LLMs (Sonnet, Haiku, Gemini Flash)
- [ ] Real competitor scraping (Crawl4AI, Playwright)
- [ ] CrewAI Flow with `@start`/`@listen` decorators
- [ ] RAG integration (ChromaDB/Qdrant) for brand knowledge base
- [ ] Additional platform profiles (WB, Ozon, Lamoda)

### Phase 3 -- Full v0.3 Architecture

- [ ] All 30+ agents across UC1-UC4
- [ ] Visual content generation (UC4)
- [ ] Publication orchestration (UC3)
- [ ] Multi-MCM batch processing
- [ ] Quality feedback loops with automatic regeneration
- [ ] Production deployment and monitoring

See [v0.3 Architecture](docs/architecture/phase1-pipeline.md) for detailed pipeline documentation.
