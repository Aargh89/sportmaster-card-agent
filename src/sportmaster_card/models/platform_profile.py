"""Platform profile models for marketplace-specific content configuration.

Every target platform (Sportmaster site, Wildberries, Ozon, etc.) has unique
requirements for product content: title length limits, required text sections,
SEO rules, forbidden words, tone of voice, and formatting constraints.

PlatformProfile captures all these rules in a single validated object that
downstream agents (Brief Selector, Content Generator, Quality Controller)
consume to produce and validate platform-compliant content.

Model hierarchy:
    PlatformType   — enum distinguishing 1P / 3P / VMP marketplace types
    TextRequirements — all text-level constraints for one platform
    PlatformProfile  — top-level config combining identity + text rules

Usage:
    >>> profile = PlatformProfile.from_yaml("config/platforms/sm_site.yaml")
    >>> profile.text_requirements.max_title_length
    150
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel


class PlatformType(str, Enum):
    """Marketplace ownership type.

    Determines processing flow and content strategy:
        FIRST_PARTY  — own platform (Sportmaster site), full control
        THIRD_PARTY  — external marketplace (WB, Ozon), strict API rules
        VMP          — virtual marketplace platform, hybrid rules
    """

    FIRST_PARTY = "1P"
    THIRD_PARTY = "3P"
    VMP = "VMP"


class TextRequirements(BaseModel):
    """Text-level constraints for a single platform.

    Attributes:
        max_title_length: Upper character limit for product title.
        max_description_length: Upper character limit for description body.
        required_sections: Section slugs that MUST appear in content.
        forbidden_words: Words/phrases banned by the platform.
        naming_rules: Human-readable naming convention pattern.
        seo_keywords_source: Where SEO keywords originate.
        seo_rules: List of SEO constraints the content must satisfy.
        tone_of_voice: Expected tone (professional, friendly, etc.).
        benefits_format: How product benefits should be formatted.
        html_allowed: Whether HTML markup is permitted in content.
    """

    max_title_length: int = 150
    max_description_length: int = 3000
    required_sections: list[str] = []
    forbidden_words: list[str] = []
    naming_rules: str = ""
    seo_keywords_source: str = ""
    seo_rules: list[str] = []
    tone_of_voice: str = "professional"
    benefits_format: str = ""
    html_allowed: bool = False


class PlatformProfile(BaseModel):
    """Complete platform configuration for content generation.

    Combines platform identity (id, type, name) with the full set of
    text requirements that agents use to produce compliant content.

    Attributes:
        platform_id: Short identifier used in routing ("sm_site", "wb").
        platform_type: Marketplace ownership category (1P / 3P / VMP).
        platform_name: Human-readable display name.
        text_requirements: All text-level constraints for this platform.
    """

    platform_id: str
    platform_type: PlatformType
    platform_name: str
    text_requirements: TextRequirements

    @classmethod
    def from_yaml(cls, path: str) -> PlatformProfile:
        """Load and validate a PlatformProfile from a YAML file.

        Args:
            path: Filesystem path to the YAML configuration file.

        Returns:
            Validated PlatformProfile instance.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            pydantic.ValidationError: If YAML content fails validation.
        """
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)
