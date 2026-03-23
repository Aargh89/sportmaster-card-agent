"""Tests for PlatformProfile model and SM site YAML configuration.

PlatformProfile describes a target marketplace/platform where product content
is published.  Each platform has its own text rules (length limits, required
sections, SEO constraints, tone) stored in TextRequirements.

Test strategy:
    - PlatformProfile round-trips with valid SM-site data
    - TextRequirements exposes all text-level constraints
    - PlatformType enum covers 1P / 3P / VMP marketplace types
    - from_yaml class method loads a real YAML file into a validated model
    - seo_rules list is present and populated in TextRequirements
"""

from pathlib import Path

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# 1. Valid SM-site PlatformProfile
# ---------------------------------------------------------------------------

def test_platform_profile_valid_sm():
    """PlatformProfile accepts valid Sportmaster website configuration."""
    from sportmaster_card.models.platform_profile import (
        PlatformProfile,
        PlatformType,
        TextRequirements,
    )

    profile = PlatformProfile(
        platform_id="sm_site",
        platform_type=PlatformType.FIRST_PARTY,
        platform_name="Sportmaster Website",
        text_requirements=TextRequirements(
            max_title_length=150,
            max_description_length=3000,
            required_sections=["description", "benefits", "technologies", "composition"],
            naming_rules="Бренд + Тип + Модель + Характеристика",
            seo_keywords_source="internal_seo_team",
            seo_rules=[
                "Ключевые слова в первом абзаце",
                "Title содержит бренд и категорию",
            ],
            tone_of_voice="professional",
            benefits_format="title + 1-2 sentence description",
            html_allowed=True,
        ),
    )

    assert profile.platform_id == "sm_site"
    assert profile.platform_type == PlatformType.FIRST_PARTY
    assert profile.platform_name == "Sportmaster Website"
    assert profile.text_requirements.max_title_length == 150
    assert profile.text_requirements.html_allowed is True


# ---------------------------------------------------------------------------
# 2. TextRequirements fields
# ---------------------------------------------------------------------------

def test_text_requirements():
    """TextRequirements exposes all text-constraint fields with correct types."""
    from sportmaster_card.models.platform_profile import TextRequirements

    reqs = TextRequirements(
        max_title_length=120,
        max_description_length=2000,
        required_sections=["description", "benefits"],
        forbidden_words=["лучший", "номер один"],
        naming_rules="Бренд + Тип",
        tone_of_voice="friendly",
    )

    assert reqs.max_title_length == 120
    assert reqs.max_description_length == 2000
    assert reqs.required_sections == ["description", "benefits"]
    assert reqs.forbidden_words == ["лучший", "номер один"]
    assert reqs.naming_rules == "Бренд + Тип"
    assert reqs.tone_of_voice == "friendly"
    # defaults
    assert reqs.seo_rules == []
    assert reqs.html_allowed is False


# ---------------------------------------------------------------------------
# 3. PlatformType enum
# ---------------------------------------------------------------------------

def test_platform_type_enum():
    """PlatformType has FIRST_PARTY, THIRD_PARTY, VMP with correct values."""
    from sportmaster_card.models.platform_profile import PlatformType

    assert PlatformType.FIRST_PARTY == "1P"
    assert PlatformType.THIRD_PARTY == "3P"
    assert PlatformType.VMP == "VMP"
    assert PlatformType("1P") is PlatformType.FIRST_PARTY


# ---------------------------------------------------------------------------
# 4. Load from YAML
# ---------------------------------------------------------------------------

def test_load_from_yaml():
    """PlatformProfile.from_yaml loads sm_site.yaml into a validated model."""
    from sportmaster_card.models.platform_profile import PlatformProfile, PlatformType

    yaml_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "sportmaster_card"
        / "config"
        / "platforms"
        / "sm_site.yaml"
    )
    profile = PlatformProfile.from_yaml(str(yaml_path))

    assert profile.platform_id == "sm_site"
    assert profile.platform_type == PlatformType.FIRST_PARTY
    assert profile.platform_name == "Sportmaster Website"
    assert profile.text_requirements.max_title_length == 150
    assert profile.text_requirements.html_allowed is True
    assert len(profile.text_requirements.required_sections) == 4
    assert "description" in profile.text_requirements.required_sections


# ---------------------------------------------------------------------------
# 5. SEO rules in TextRequirements
# ---------------------------------------------------------------------------

def test_seo_rules():
    """TextRequirements.seo_rules is a list of SEO constraint strings."""
    from sportmaster_card.models.platform_profile import PlatformProfile

    yaml_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "sportmaster_card"
        / "config"
        / "platforms"
        / "sm_site.yaml"
    )
    profile = PlatformProfile.from_yaml(str(yaml_path))

    assert isinstance(profile.text_requirements.seo_rules, list)
    assert len(profile.text_requirements.seo_rules) == 2
    assert "Ключевые слова в первом абзаце" in profile.text_requirements.seo_rules
    assert "Title содержит бренд и категорию" in profile.text_requirements.seo_rules
