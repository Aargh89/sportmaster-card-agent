"""Sportmaster Card Agent — multi-agent system for product card lifecycle.

This package implements a multi-agent system that automates the full lifecycle
of product card (КТ) creation and management for Sportmaster retail chain.

Architecture:
    - 4 contours: UC1 (data enrichment), UC2 (text content),
      UC3 (publication orchestration), UC4 (visual content via GenAI)
    - 3 flows: 1P (own fronts), 3P (internal marketplace), VMP (external marketplaces)
    - Parallel content generation per platform from a single CuratedProfile

Key concepts:
    - MCM (мерчендайзинговая цветомодель): atomic product unit, NOT SKU
    - CuratedProfile: validated enriched data — single source of truth
    - PlatformProfile: per-marketplace configuration (text limits, SEO rules, tone)
    - DataProvenance: tracks origin and confidence of every attribute
"""

__version__ = "0.1.0"
