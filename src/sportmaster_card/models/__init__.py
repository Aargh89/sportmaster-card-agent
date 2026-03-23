"""Pydantic models for the Sportmaster Card Agent system.

This module contains all data models used across agents and flows.
Models follow the v0.3 architecture specification.

Model hierarchy:
    Input models:
        ProductInput → raw Excel row data (209 columns, 13 blocks)
        RoutingProfile → routing decision (flow type, target platforms, processing profile)

    UC1 (Enrichment) models:
        DataProvenance → tracks origin of each attribute
        ValidationReport → Data Validator output
        ExtractedAttributes → Visual Interpreter output
        CompetitorBenchmark → External Researcher output
        InternalInsights → Internal Researcher output
        CreativeInsights → Synectics Agent output
        EnrichedProductProfile → Data Enricher output
        CuratedProfile → Data Curator output (source of truth)

    UC2 (Content) models:
        ContentBrief → Brief Selector output
        SEOProfile → SEO Analyst output
        ContentStructure → Structure Planner output
        PlatformContent → Content Generator output (per platform)
        QualityScore → Quality Controller output

    UC3 (Publication) models:
        MappedAttributes → Attribute Mapper output
        CompletenessReport → Completeness Monitor output
        PublicationResult → Publication Agent output
"""
