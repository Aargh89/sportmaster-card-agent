"""CrewAI Flows for orchestrating the product card pipeline.

Flows manage the high-level control flow:
    - RouterFlow: classifies product and selects pipeline
    - EnrichmentFlow (UC1): data validation, enrichment, curation
    - ContentFlow (UC2): parallel content generation per platform
    - PublicationFlow (UC3): mapping, completeness, publishing
    - VisualFlow (UC4): visual content generation via GenAI

Each Flow contains one or more Crews as execution units.
"""
