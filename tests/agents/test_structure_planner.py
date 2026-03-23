"""Tests for StructurePlannerAgent -- content structure planning from briefs.

Tests cover: instantiation, ContentStructure return type, non-empty sections,
required sections inclusion from ContentBrief, and section guidelines presence.
Phase 1 uses deterministic section mapping (no LLM calls).
"""

from __future__ import annotations

from sportmaster_card.agents.structure_planner import StructurePlannerAgent
from sportmaster_card.models.content import ContentBrief, ContentStructure


# ======================================================================
# Fixtures -- reusable content briefs for multiple tests
# ======================================================================


def _sample_brief() -> ContentBrief:
    """Build a ContentBrief with required sections for structure planning."""
    return ContentBrief(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        brief_type="standard",
        tone_of_voice="professional",
        required_sections=["description", "benefits", "technologies"],
        max_description_length=2000,
        max_title_length=120,
    )


# ======================================================================
# Tests
# ======================================================================


def test_creation():
    """StructurePlannerAgent can be instantiated without arguments."""
    agent = StructurePlannerAgent()
    assert agent is not None


def test_plan_returns_content_structure():
    """plan() returns an instance of ContentStructure."""
    agent = StructurePlannerAgent()
    brief = _sample_brief()

    result = agent.plan(brief)

    assert isinstance(result, ContentStructure)


def test_sections_not_empty():
    """plan() returns a ContentStructure with non-empty sections list."""
    agent = StructurePlannerAgent()
    brief = _sample_brief()

    result = agent.plan(brief)

    assert len(result.sections) > 0


def test_includes_required_sections():
    """All required_sections from the brief appear in the planned structure."""
    agent = StructurePlannerAgent()
    brief = _sample_brief()

    result = agent.plan(brief)

    for section in brief.required_sections:
        assert section in result.sections, (
            f"Required section '{section}' missing from planned structure"
        )


def test_has_section_guidelines():
    """plan() populates section_guidelines for at least one section."""
    agent = StructurePlannerAgent()
    brief = _sample_brief()

    result = agent.plan(brief)

    assert len(result.section_guidelines) > 0
    # Every guideline key should be a valid section
    for key in result.section_guidelines:
        assert key in result.sections, (
            f"Guideline key '{key}' not found in sections list"
        )
