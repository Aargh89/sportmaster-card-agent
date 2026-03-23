"""Tests for RoutingProfile model.

RoutingProfile is the output of the Router Agent. It determines:
- flow_type: 1P / 3P (which pipeline to use)
- processing_profile: minimal / standard / premium / complex
- target_platforms: which marketplaces to generate content for
- attribute_class: product classification for agent configuration

Test strategy:
    - Enum values match v0.3 specification exactly
    - 1P basic routing with single platform
    - 1P premium routing with multiple VMP platforms
    - 3P routing
    - Empty target_platforms rejected (validator)
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
    """target_platforms must not be empty."""
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
