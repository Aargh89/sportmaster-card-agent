# Phase 2: Full UC1 + UC2 for SM Site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the UC1 enrichment pipeline (add Visual Interpreter, Internal Researcher, Synectics Agent, Data Enricher, Data Curator) and UC2 content pipeline (add SEO Analyst, Structure Planner, Brand Compliance, Fact Checker, Quality Controller) for SM site, wired together through an upgraded PilotFlow.

**Architecture:** Extends Phase 1 by adding 10 new agents. UC1 gains 5 enrichment agents that produce a CuratedProfile (source of truth). UC2 gains 5 quality agents that wrap around the existing ContentGenerator. The PilotFlow is upgraded to run the full sequence. All agents remain rule/template-based (real LLM integration is Phase 2.5).

**Tech Stack:** Python 3.12, CrewAI 1.5+, Pydantic v2, pytest

---

## File Structure

```
src/sportmaster_card/
├── models/
│   ├── enrichment.py          # MODIFY: add InternalInsights, CreativeInsights, EnrichedProductProfile, CuratedProfile
│   └── content.py             # MODIFY: add ContentStructure, SEOProfile, ComplianceReport, FactCheckReport
├── agents/
│   ├── visual_interpreter.py  # CREATE: UC1 agent 1.2
│   ├── internal_researcher.py # CREATE: UC1 agent 1.4
│   ├── synectics_agent.py     # CREATE: UC1 agent 1.5
│   ├── data_enricher.py       # CREATE: UC1 agent 1.6
│   ├── data_curator.py        # CREATE: UC1 agent 1.7
│   ├── seo_analyst.py         # CREATE: UC2 agent 2.2
│   ├── structure_planner.py   # CREATE: UC2 agent 2.3
│   ├── brand_compliance.py    # CREATE: UC2 agent 2.5
│   ├── fact_checker.py        # CREATE: UC2 agent 2.6
│   └── quality_controller.py  # CREATE: UC2 agent 2.8
├── config/
│   └── agents.yaml            # MODIFY: add 10 new agent definitions
└── flows/
    └── pilot_flow.py          # MODIFY: upgrade to full UC1+UC2 sequence

tests/
├── models/
│   ├── test_enrichment.py     # MODIFY: add tests for new models
│   └── test_content.py        # MODIFY: add tests for new models
├── agents/
│   ├── test_visual_interpreter.py
│   ├── test_internal_researcher.py
│   ├── test_synectics_agent.py
│   ├── test_data_enricher.py
│   ├── test_data_curator.py
│   ├── test_seo_analyst.py
│   ├── test_structure_planner.py
│   ├── test_brand_compliance.py
│   ├── test_fact_checker.py
│   └── test_quality_controller.py
├── flows/
│   └── test_pilot_flow.py     # MODIFY: update for full pipeline
└── integration/
    └── test_full_pipeline.py  # MODIFY: update assertions
```

---

## Task 1: New UC1 Models — InternalInsights, CreativeInsights, EnrichedProductProfile, CuratedProfile

**Files:**
- Modify: `src/sportmaster_card/models/enrichment.py`
- Modify: `tests/models/test_enrichment.py`

- [ ] **Step 1: Write failing tests** for 4 new models:
  - `test_internal_insights_valid` — InternalInsights with insights list
  - `test_creative_insights_valid` — CreativeInsights with metaphors/associations
  - `test_enriched_product_profile_valid` — EnrichedProductProfile merging all UC1 data
  - `test_curated_profile_valid` — CuratedProfile as validated final profile

- [ ] **Step 2: Run tests, verify FAIL**
- [ ] **Step 3: Implement** — add 4 Pydantic models to enrichment.py:

```python
class InternalInsights(BaseModel):
    """Insights from internal research (UX reports, Q&A, returns)."""
    mcm_id: str
    insights: list[str] = []
    pain_points: list[str] = []  # From return reasons
    purchase_drivers: list[str] = []  # From CJM analysis
    source_documents: list[str] = []  # Which internal docs were used

class CreativeInsights(BaseModel):
    """Creative associations and metaphors from Synectics Agent."""
    mcm_id: str
    metaphors: list[str] = []
    associations: list[str] = []
    emotional_hooks: list[str] = []
    approved: bool = False  # Must be approved by ГПТК before use

class EnrichedProductProfile(BaseModel):
    """Merged enrichment from all UC1 agents (before curation)."""
    mcm_id: str
    base_product: ProductInput
    validation_report: ValidationReport
    competitor_benchmark: CompetitorBenchmark
    internal_insights: Optional[InternalInsights] = None
    creative_insights: Optional[CreativeInsights] = None
    provenance_log: DataProvenanceLog

class CuratedProfile(BaseModel):
    """Validated, curated product profile — single source of truth."""
    mcm_id: str
    product_name: str
    brand: str
    category: str
    description: str
    key_features: list[str] = []
    technologies: list[str] = []
    composition: dict[str, str] = {}
    benefits_data: list[str] = []  # Raw benefit material for Content Generator
    seo_material: list[str] = []  # Keywords, phrases from research
    provenance_log: DataProvenanceLog
```

- [ ] **Step 4: Run tests, verify PASS**
- [ ] **Step 5: Commit** `feat(models): add UC1 enrichment models — InternalInsights, CreativeInsights, EnrichedProductProfile, CuratedProfile`

---

## Task 2: New UC2 Models — SEOProfile, ContentStructure, ComplianceReport, FactCheckReport

**Files:**
- Modify: `src/sportmaster_card/models/content.py`
- Modify: `tests/models/test_content.py`

- [ ] **Step 1-5: TDD cycle** for:

```python
class SEOProfile(BaseModel):
    """SEO keyword profile for a specific platform."""
    mcm_id: str
    platform_id: str
    primary_keywords: list[str]
    secondary_keywords: list[str] = []
    title_recommendation: str = ""
    meta_description_recommendation: str = ""

class ContentStructure(BaseModel):
    """Planned content structure before generation."""
    mcm_id: str
    platform_id: str
    sections: list[str]  # Ordered section names
    section_guidelines: dict[str, str] = {}  # section_name → guidelines
    target_word_count: int = 500

class ComplianceReport(BaseModel):
    """Brand compliance check result."""
    mcm_id: str
    is_compliant: bool
    violations: list[str] = []
    suggestions: list[str] = []

class FactCheckReport(BaseModel):
    """Fact-checking result against CuratedProfile."""
    mcm_id: str
    is_accurate: bool
    inaccuracies: list[str] = []
    unverifiable_claims: list[str] = []
```

- [ ] **Commit** `feat(models): add UC2 quality models — SEOProfile, ContentStructure, ComplianceReport, FactCheckReport`

---

## Task 3: Visual Interpreter Agent (UC1 — 1.2)

**Files:**
- Create: `src/sportmaster_card/agents/visual_interpreter.py`
- Create: `tests/agents/test_visual_interpreter.py`

- [ ] **Step 1-5: TDD cycle**

Stub agent that extracts attributes from product photos. Phase 1 stub: returns extracted attributes based on product category (e.g., for footwear: sole type, closure, upper material). Multi-mode support: real_photo / sketch / no_visual.

Tests: creation, interpret returns ExtractedAttributes dict, handles no_visual mode, produces DataProvenance with source_type=PHOTO.

- [ ] **Commit** `feat(agents): add VisualInterpreterAgent with stub extraction`

---

## Task 4: Internal Researcher Agent (UC1 — 1.4)

**Files:**
- Create: `src/sportmaster_card/agents/internal_researcher.py`
- Create: `tests/agents/test_internal_researcher.py`

- [ ] **Step 1-5: TDD cycle**

Stub agent that extracts insights from internal documents (UX reports, Q&A, returns). Returns InternalInsights. Stub: returns generic insights based on category.

- [ ] **Commit** `feat(agents): add InternalResearcherAgent with stub insights`

---

## Task 5: Synectics Agent (UC1 — 1.5)

**Files:**
- Create: `src/sportmaster_card/agents/synectics_agent.py`
- Create: `tests/agents/test_synectics_agent.py`

- [ ] **Step 1-5: TDD cycle**

Creative agent that finds metaphors and associations. Returns CreativeInsights with approved=False (requires ГПТК review). Stub: generates associations based on product technologies and use cases.

- [ ] **Commit** `feat(agents): add SynecticsAgent with creative insight generation`

---

## Task 6: Data Enricher Agent (UC1 — 1.6)

**Files:**
- Create: `src/sportmaster_card/agents/data_enricher.py`
- Create: `tests/agents/test_data_enricher.py`

- [ ] **Step 1-5: TDD cycle**

Merges data from agents 1.1-1.4, resolves conflicts, marks disputed characteristics. Two-step process: Step A merges validated data, Step B integrates approved creative insights. Returns EnrichedProductProfile.

Tests: merges validation + research + internal insights, handles missing optional inputs, marks disputed attributes in provenance.

- [ ] **Commit** `feat(agents): add DataEnricherAgent with two-step merge logic`

---

## Task 7: Data Curator Agent (UC1 — 1.7)

**Files:**
- Create: `src/sportmaster_card/agents/data_curator.py`
- Create: `tests/agents/test_data_curator.py`

- [ ] **Step 1-5: TDD cycle**

Validates enriched profile against Sportmaster reference data. Produces CuratedProfile — the single source of truth for UC2. Stub: passes through enriched data with basic consistency checks.

- [ ] **Commit** `feat(agents): add DataCuratorAgent producing CuratedProfile`

---

## Task 8: SEO Analyst Agent (UC2 — 2.2)

**Files:**
- Create: `src/sportmaster_card/agents/seo_analyst.py`
- Create: `tests/agents/test_seo_analyst.py`

- [ ] **Step 1-5: TDD cycle**

Generates SEO keyword profile for the target platform. Stub: extracts keywords from product name, brand, category, technologies. Returns SEOProfile.

- [ ] **Commit** `feat(agents): add SEOAnalystAgent with keyword extraction`

---

## Task 9: Structure Planner Agent (UC2 — 2.3)

**Files:**
- Create: `src/sportmaster_card/agents/structure_planner.py`
- Create: `tests/agents/test_structure_planner.py`

- [ ] **Step 1-5: TDD cycle**

Plans content structure before generation. Determines which sections to include and in what order, based on ContentBrief and platform requirements. Returns ContentStructure.

- [ ] **Commit** `feat(agents): add StructurePlannerAgent for content planning`

---

## Task 10: Brand Compliance Agent (UC2 — 2.5)

**Files:**
- Create: `src/sportmaster_card/agents/brand_compliance.py`
- Create: `tests/agents/test_brand_compliance.py`

- [ ] **Step 1-5: TDD cycle**

Checks generated content against brand guidelines. Stub: checks for forbidden words, ensures brand name is correctly formatted. Returns ComplianceReport.

- [ ] **Commit** `feat(agents): add BrandComplianceAgent with guideline checking`

---

## Task 11: Fact Checker Agent (UC2 — 2.6)

**Files:**
- Create: `src/sportmaster_card/agents/fact_checker.py`
- Create: `tests/agents/test_fact_checker.py`

- [ ] **Step 1-5: TDD cycle**

Verifies factual accuracy of generated content against CuratedProfile. Checks that all claimed features exist in the source data. Returns FactCheckReport.

- [ ] **Commit** `feat(agents): add FactCheckerAgent verifying content against CuratedProfile`

---

## Task 12: Quality Controller Agent (UC2 — 2.8)

**Files:**
- Create: `src/sportmaster_card/agents/quality_controller.py`
- Create: `tests/agents/test_quality_controller.py`

- [ ] **Step 1-5: TDD cycle**

Final quality assessment: scoring by readability, SEO, factual accuracy, brand compliance, uniqueness. Aggregates reports from 2.5 and 2.6. Returns QualityScore with passes_threshold.

- [ ] **Commit** `feat(agents): add QualityControllerAgent with multi-dimension scoring`

---

## Task 13: Update agents.yaml with 10 new agent definitions

**Files:**
- Modify: `src/sportmaster_card/config/agents.yaml`

- [ ] **Step 1:** Add configs for: visual_interpreter, internal_researcher, synectics, data_enricher, data_curator, seo_analyst, structure_planner, brand_compliance, fact_checker, quality_controller

- [ ] **Commit** `config: add Phase 2 agent definitions to agents.yaml`

---

## Task 14: Upgrade PilotFlow to Full UC1+UC2 Pipeline

**Files:**
- Modify: `src/sportmaster_card/flows/pilot_flow.py`
- Modify: `tests/flows/test_pilot_flow.py`
- Modify: `tests/integration/test_full_pipeline.py`

- [ ] **Step 1-5: TDD cycle**

Upgrade PilotFlow.run() to sequence all 15 agents:
```
Router → DataValidator → VisualInterpreter → ExternalResearcher → InternalResearcher
  → SynecticsAgent → DataEnricher → DataCurator (→ CuratedProfile)
  → SEOAnalyst → StructurePlanner → ContentGenerator → BrandCompliance
  → FactChecker → CopyEditor → QualityController
```

Update PipelineResult to include all intermediate outputs.
Update integration tests to validate the full chain.

- [ ] **Commit** `feat(flows): upgrade PilotFlow to full UC1+UC2 with 15 agents`

---

## Task 15: Push and documentation update

- [ ] Update `docs/architecture/phase1-pipeline.md` → rename/extend to cover Phase 2
- [ ] `git push`
- [ ] **Commit** `docs: update architecture for Phase 2 — full UC1+UC2 pipeline`

---

## Execution Order

```
Task 1 (UC1 models) ──┐
Task 2 (UC2 models) ──┤── Parallel (independent)
                      │
Tasks 3-7 (UC1 agents)┤── Parallel after Task 1
Tasks 8-12 (UC2 agents)── Parallel after Task 2
                      │
Task 13 (YAML config) ─── After Tasks 3-12
Task 14 (Flow upgrade) ── After all agents
Task 15 (Docs + push) ─── Last
```
