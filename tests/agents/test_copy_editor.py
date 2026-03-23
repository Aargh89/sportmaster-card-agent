"""Tests for CopyEditorAgent -- rule-based content editing and polishing.

Tests cover: instantiation, return type, truncation of long descriptions,
truncation of long titles, preservation of valid content, and whitespace
stripping. No LLM calls -- the editor is purely deterministic.
"""

from __future__ import annotations

from sportmaster_card.agents.copy_editor import CopyEditorAgent
from sportmaster_card.models.content import Benefit, PlatformContent


# ======================================================================
# Fixtures -- reusable PlatformContent for multiple tests
# ======================================================================


def _sample_content(
    product_name: str = "Nike Air Zoom Pegasus 41",
    description: str = "Lightweight running shoes with Air Zoom cushioning.",
    seo_title: str = "Buy Nike Pegasus | Sportmaster",
) -> PlatformContent:
    """Build a PlatformContent with sensible defaults for testing."""
    return PlatformContent(
        mcm_id="MCM-001-BLK-42",
        platform_id="sm_site",
        product_name=product_name,
        description=description,
        benefits=[Benefit(title="Cushioning", description="Air Zoom technology.")],
        seo_title=seo_title,
        seo_meta_description="Nike Pegasus 41 running shoes.",
        seo_keywords=["nike pegasus", "running shoes"],
        content_hash="abc123",
        source_curated_profile_hash="def456",
    )


# ======================================================================
# Test: instantiation
# ======================================================================


class TestCopyEditorCreation:
    """CopyEditorAgent can be instantiated without any arguments."""

    def test_copy_editor_creation(self) -> None:
        """Agent is created successfully as a plain object."""
        agent = CopyEditorAgent()
        assert agent is not None


# ======================================================================
# Test: edit returns PlatformContent
# ======================================================================


class TestEditReturnsPlatformContent:
    """edit() returns a PlatformContent instance."""

    def test_edit_returns_platform_content(self) -> None:
        """Return type is PlatformContent, not a dict or other type."""
        agent = CopyEditorAgent()
        content = _sample_content()

        result = agent.edit(content)

        assert isinstance(result, PlatformContent)


# ======================================================================
# Test: truncates long description
# ======================================================================


class TestEditTruncatesLongDescription:
    """Description exceeding max_description_length gets truncated."""

    def test_edit_truncates_long_description(self) -> None:
        """A 200-char description with max_length=50 is truncated with ellipsis."""
        long_desc = "word " * 40  # 200 chars
        agent = CopyEditorAgent()
        content = _sample_content(description=long_desc)

        result = agent.edit(content, max_description_length=50)

        assert len(result.description) <= 51  # 50 + ellipsis char
        assert result.description.endswith("\u2026")


# ======================================================================
# Test: truncates long title
# ======================================================================


class TestEditTruncatesLongTitle:
    """Product name exceeding max_title_length gets truncated."""

    def test_edit_truncates_long_title(self) -> None:
        """A long product name with max_title_length=20 is truncated."""
        long_name = "Nike Air Zoom Pegasus 41 Running Shoes For Men"
        agent = CopyEditorAgent()
        content = _sample_content(product_name=long_name)

        result = agent.edit(content, max_title_length=20)

        assert len(result.product_name) <= 21  # 20 + ellipsis char
        assert result.product_name.endswith("\u2026")


# ======================================================================
# Test: preserves valid content
# ======================================================================


class TestEditPreservesValidContent:
    """Content within all limits is returned unchanged."""

    def test_edit_preserves_valid_content(self) -> None:
        """Short content stays identical after editing."""
        agent = CopyEditorAgent()
        content = _sample_content()

        result = agent.edit(content)

        assert result.product_name == content.product_name
        assert result.description == content.description
        assert result.seo_title == content.seo_title
        assert result.benefits == content.benefits


# ======================================================================
# Test: strips whitespace
# ======================================================================


class TestEditStripsWhitespace:
    """Extra whitespace is trimmed from all text fields."""

    def test_edit_strips_whitespace(self) -> None:
        """Leading/trailing whitespace removed from name, description, SEO fields."""
        agent = CopyEditorAgent()
        content = _sample_content(
            product_name="  Nike Pegasus  ",
            description="  Some description  ",
            seo_title="  SEO Title  ",
        )

        result = agent.edit(content)

        assert result.product_name == "Nike Pegasus"
        assert result.description == "Some description"
        assert result.seo_title == "SEO Title"
        assert result.seo_meta_description == "Nike Pegasus 41 running shoes."
