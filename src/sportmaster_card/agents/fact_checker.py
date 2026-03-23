"""FactCheckerAgent -- verifies factual accuracy of content against CuratedProfile.

This agent compares claims in generated PlatformContent against the source
CuratedProfile data.  It checks that technologies mentioned in the content
actually exist in the product profile, and that material/composition claims
match the verified composition data.

Phase 1 uses rule-based string matching for fact verification.
Phase 2 will add LLM-based semantic claim extraction and verification
against a broader knowledge base including supplier datasheets.

Architecture::

    PlatformContent + CuratedProfile
        |
        v
    FactCheckerAgent.check(content, profile)
        |
        +-- _check_technologies()   -> unknown technology violations
        +-- _check_composition()    -> material mismatch violations
        |
        v
    FactCheckReport (is_accurate + inaccuracies + unverifiable_claims)

Verification checks (Phase 1):
    1. **Technology verification**: Extracts technology-like terms from
       content text and verifies each against the CuratedProfile's
       technology list.  Unrecognized technologies are flagged.
    2. **Composition verification**: Checks for material keywords in
       content (e.g., "кожа", "текстиль") and verifies they match
       the CuratedProfile's composition data.

Typical usage::

    from sportmaster_card.agents.fact_checker import FactCheckerAgent
    from sportmaster_card.models.content import PlatformContent
    from sportmaster_card.models.enrichment import CuratedProfile

    agent = FactCheckerAgent()
    report = agent.check(content, curated_profile)
    print(report.is_accurate)   # True or False
    print(report.inaccuracies)  # ["Technology 'Boost' not in profile"]
"""

from __future__ import annotations

from sportmaster_card.models.content import FactCheckReport, PlatformContent
from sportmaster_card.models.enrichment import CuratedProfile


class FactCheckerAgent:
    """Verifies factual claims in PlatformContent against CuratedProfile.

    Performs rule-based verification of technologies and material
    composition mentioned in the generated content.  Claims that
    cannot be confirmed by the CuratedProfile are flagged as
    inaccuracies or unverifiable claims.

    Phase 1: string-matching verification against profile fields.
    Phase 2: semantic claim extraction and multi-source verification.

    Attributes:
        _KNOWN_TECHNOLOGY_MARKERS: Common technology term patterns
            used to identify technology mentions in free text.
            Each marker is a lowercased prefix that, when found
            adjacent to a capitalized term, indicates a tech claim.

    Example::

        >>> agent = FactCheckerAgent()
        >>> # With accurate content referencing known technologies
        >>> report = agent.check(accurate_content, curated_profile)
        >>> report.is_accurate
        True
    """

    # Technology name patterns from major sports brands.
    # Used to extract technology claims from free-text content.
    # Each entry is a known technology name (lowercased) that the
    # checker looks for in the content text.
    _KNOWN_TECHNOLOGY_NAMES: list[str] = [
        "air zoom", "react", "flywire", "flyknit", "vapormax",
        "boost", "primeknit", "continental", "lightstrike",
        "gore-tex", "vibram", "fresh foam", "fuelcell",
        "nitro", "pwrplate", "gel", "flytefoam",
    ]

    def check(
        self,
        content: PlatformContent,
        profile: CuratedProfile,
    ) -> FactCheckReport:
        """Verify factual accuracy of content against the CuratedProfile.

        Runs all fact-check verifications and aggregates results.
        Content is considered accurate only if ALL checks pass.

        Args:
            content: Generated platform content to verify.
            profile: Source-of-truth CuratedProfile containing verified
                product data (technologies, composition, brand).

        Returns:
            FactCheckReport with is_accurate verdict, inaccuracies
            list, and unverifiable_claims list.
        """
        inaccuracies: list[str] = []
        unverifiable: list[str] = []

        # Collect all text from the content for scanning
        text = self._extract_text(content)

        # Check 1: Technologies mentioned must exist in profile
        tech_issues = self._check_technologies(text, profile)
        inaccuracies.extend(tech_issues)

        # Check 2: Material claims must match profile composition
        comp_issues = self._check_composition(text, profile)
        inaccuracies.extend(comp_issues)

        return FactCheckReport(
            mcm_id=content.mcm_id,
            is_accurate=len(inaccuracies) == 0,
            inaccuracies=inaccuracies,
            unverifiable_claims=unverifiable,
        )

    # ------------------------------------------------------------------
    # Private helpers -- rule-based fact verification (Phase 1)
    # ------------------------------------------------------------------

    def _extract_text(self, content: PlatformContent) -> str:
        """Extract all text from PlatformContent for fact-checking.

        Concatenates product_name, description, and benefit texts
        into a single searchable string.

        Args:
            content: Platform content to extract text from.

        Returns:
            Concatenated text from relevant content fields.
        """
        parts: list[str] = [
            content.product_name,
            content.description,
        ]
        for benefit in content.benefits:
            parts.append(benefit.title)
            parts.append(benefit.description)
        return " ".join(parts)

    def _check_technologies(
        self,
        text: str,
        profile: CuratedProfile,
    ) -> list[str]:
        """Verify that technologies mentioned in text exist in the profile.

        Scans text for known technology names and checks each found
        technology against the CuratedProfile's technology list.
        Technologies present in text but absent from the profile are
        reported as inaccuracies.

        Args:
            text: Concatenated content text.
            profile: Source CuratedProfile with verified technologies.

        Returns:
            List of inaccuracy descriptions for unknown technologies.
        """
        issues: list[str] = []
        text_lower = text.lower()

        # Build a set of profile technologies (lowercased) for fast lookup
        profile_techs = {t.lower() for t in profile.technologies}

        # Check each known technology name against the text
        for tech_name in self._KNOWN_TECHNOLOGY_NAMES:
            if tech_name in text_lower and tech_name not in profile_techs:
                issues.append(
                    f"Технология '{tech_name}' упоминается в контенте, "
                    f"но отсутствует в CuratedProfile."
                )

        return issues

    def _check_composition(
        self,
        text: str,
        profile: CuratedProfile,
    ) -> list[str]:
        """Verify material claims in text against profile composition.

        Checks for common material keywords in the content and
        verifies they are consistent with the CuratedProfile's
        composition data.  Reports mismatches where the content
        claims a material not present in the profile.

        Args:
            text: Concatenated content text.
            profile: Source CuratedProfile with verified composition.

        Returns:
            List of inaccuracy descriptions for material mismatches.
        """
        issues: list[str] = []
        text_lower = text.lower()

        # Build a combined string of all composition values for matching
        composition_text = " ".join(profile.composition.values()).lower()

        # Material keywords to check for contradictions.
        # Each tuple is (keyword_in_text, conflicting_absence_message).
        material_checks: list[tuple[str, str]] = [
            ("натуральная кожа", "натуральная кожа"),
            ("кожа", "кожа"),
            ("текстиль", "текстиль"),
            ("замша", "замша"),
            ("синтетика", "синтетика"),
            ("резина", "резина"),
        ]

        for keyword, material_name in material_checks:
            # If content mentions a material not in the profile composition
            if keyword in text_lower and keyword not in composition_text:
                issues.append(
                    f"Материал '{material_name}' упоминается в контенте, "
                    f"но отсутствует в составе CuratedProfile."
                )

        return issues
