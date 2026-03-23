"""Tests for ParallelContentFlow -- multi-platform content generation."""
import pytest


def test_parallel_flow_creation():
    """ParallelContentFlow can be instantiated."""
    from sportmaster_card.flows.parallel_flow import ParallelContentFlow
    flow = ParallelContentFlow()
    assert flow.max_workers == 4


def test_parallel_flow_single_platform(sample_product_input):
    """Single platform generates one PlatformContent."""
    from sportmaster_card.flows.parallel_flow import ParallelContentFlow
    flow = ParallelContentFlow()
    result = flow.run(sample_product_input, target_platforms=["sm_site"])

    assert result.platforms_generated == 1
    assert "sm_site" in result.content_set.contents
    assert result.content_set.contents["sm_site"].platform_id == "sm_site"


def test_parallel_flow_multi_platform(sample_product_input):
    """Multiple platforms generate unique content per platform."""
    from sportmaster_card.flows.parallel_flow import ParallelContentFlow
    flow = ParallelContentFlow()
    result = flow.run(
        sample_product_input,
        target_platforms=["sm_site", "wb", "ozon"]
    )

    assert result.platforms_generated == 3
    assert len(result.content_set.contents) == 3

    # Each platform has its own content
    for pid in ["sm_site", "wb", "ozon"]:
        assert pid in result.content_set.contents
        assert result.content_set.contents[pid].platform_id == pid


def test_parallel_flow_curated_profile_shared(sample_product_input):
    """All platforms share the same CuratedProfile from UC1."""
    from sportmaster_card.flows.parallel_flow import ParallelContentFlow
    flow = ParallelContentFlow()
    result = flow.run(
        sample_product_input,
        target_platforms=["sm_site", "wb"]
    )

    # CuratedProfile should be populated
    assert result.curated_profile.mcm_id == sample_product_input.mcm_id
    assert result.curated_profile.brand == "Nike"


def test_parallel_flow_quality_scores(sample_product_input):
    """Each platform gets its own QualityScore."""
    from sportmaster_card.flows.parallel_flow import ParallelContentFlow
    flow = ParallelContentFlow()
    result = flow.run(
        sample_product_input,
        target_platforms=["sm_site", "wb"]
    )

    assert len(result.content_set.quality_scores) == 2
    for pid in ["sm_site", "wb"]:
        assert pid in result.content_set.quality_scores
        score = result.content_set.quality_scores[pid]
        assert 0 <= score.overall_score <= 1


def test_parallel_flow_sequential_mode(sample_product_input):
    """max_workers=1 forces sequential execution."""
    from sportmaster_card.flows.parallel_flow import ParallelContentFlow
    flow = ParallelContentFlow(max_workers=1)
    result = flow.run(
        sample_product_input,
        target_platforms=["sm_site", "wb"]
    )
    assert result.platforms_generated == 2


def test_parallel_flow_default_platforms(sample_product_input):
    """Without target_platforms, defaults to sm_site only."""
    from sportmaster_card.flows.parallel_flow import ParallelContentFlow
    flow = ParallelContentFlow()
    result = flow.run(sample_product_input)

    assert result.platforms_generated == 1
    assert "sm_site" in result.content_set.contents
