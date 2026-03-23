"""Tests for DataProvenance and DataProvenanceLog models.

Validates that data provenance tracking correctly records the origin,
confidence, and dispute status of every product attribute extracted
by enrichment agents in the UC1 pipeline.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


def test_data_provenance_valid():
    """DataProvenance accepts valid data with all fields populated."""
    from sportmaster_card.models.provenance import DataProvenance, SourceType

    prov = DataProvenance(
        attribute_name="brand",
        value="Nike",
        source_type=SourceType.INTERNAL,
        source_name="Excel шаблон",
        confidence=0.95,
        is_disputed=False,
        agent_id="agent-1.3-data-validator",
        timestamp=datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert prov.attribute_name == "brand"
    assert prov.value == "Nike"
    assert prov.source_type == SourceType.INTERNAL
    assert prov.source_name == "Excel шаблон"
    assert prov.confidence == 0.95
    assert prov.is_disputed is False
    assert prov.agent_id == "agent-1.3-data-validator"
    assert prov.timestamp.year == 2026


def test_data_provenance_source_type_enum():
    """SourceType enum has all six expected values for attribute origins."""
    from sportmaster_card.models.provenance import SourceType

    assert SourceType.INTERNAL.value == "internal"
    assert SourceType.EXTERNAL.value == "external"
    assert SourceType.PHOTO.value == "photo"
    assert SourceType.SKETCH.value == "sketch"
    assert SourceType.INTERNET_PHOTO.value == "internet_photo"
    assert SourceType.MANUAL.value == "manual"
    # Exactly 6 members, no more
    assert len(SourceType) == 6


def test_data_provenance_disputed_flag():
    """DataProvenance with is_disputed=True indicates human review needed."""
    from sportmaster_card.models.provenance import DataProvenance, SourceType

    prov = DataProvenance(
        attribute_name="color",
        value="Красный",
        source_type=SourceType.PHOTO,
        source_name="supplier_photo_01.jpg",
        confidence=0.55,
        is_disputed=True,
        agent_id="agent-1.5-visual-interpreter",
        timestamp=datetime(2026, 3, 23, 14, 0, 0, tzinfo=timezone.utc),
    )
    assert prov.is_disputed is True


def test_data_provenance_confidence_range():
    """Confidence must be between 0.0 and 1.0 inclusive."""
    from sportmaster_card.models.provenance import DataProvenance, SourceType

    ts = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
    base = {
        "attribute_name": "gender",
        "value": "Мужской",
        "source_type": SourceType.MANUAL,
        "source_name": "operator input",
        "agent_id": "agent-manual",
        "timestamp": ts,
    }

    # Boundary: 0.0 is valid
    prov_zero = DataProvenance(**base, confidence=0.0)
    assert prov_zero.confidence == 0.0

    # Boundary: 1.0 is valid
    prov_one = DataProvenance(**base, confidence=1.0)
    assert prov_one.confidence == 1.0

    # Below range: -0.1 is invalid
    with pytest.raises(ValidationError, match="confidence"):
        DataProvenance(**base, confidence=-0.1)

    # Above range: 1.1 is invalid
    with pytest.raises(ValidationError, match="confidence"):
        DataProvenance(**base, confidence=1.1)


def test_data_provenance_log_creation():
    """DataProvenanceLog aggregates entries and computes disputed_count."""
    from sportmaster_card.models.provenance import (
        DataProvenance,
        DataProvenanceLog,
        SourceType,
    )

    ts = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
    entries = [
        DataProvenance(
            attribute_name="brand",
            value="Nike",
            source_type=SourceType.INTERNAL,
            source_name="Excel шаблон",
            confidence=0.99,
            is_disputed=False,
            agent_id="agent-1.3",
            timestamp=ts,
        ),
        DataProvenance(
            attribute_name="color",
            value="Красный",
            source_type=SourceType.PHOTO,
            source_name="photo_01.jpg",
            confidence=0.5,
            is_disputed=True,
            agent_id="agent-1.5",
            timestamp=ts,
        ),
        DataProvenance(
            attribute_name="season",
            value="Весна-Лето 2026",
            source_type=SourceType.EXTERNAL,
            source_name="WB",
            confidence=0.7,
            is_disputed=True,
            agent_id="agent-1.7",
            timestamp=ts,
        ),
    ]

    log = DataProvenanceLog(mcm_id="MCM-001-BLK-42", entries=entries)
    assert log.mcm_id == "MCM-001-BLK-42"
    assert len(log.entries) == 3
    assert log.disputed_count == 2


def test_data_provenance_log_alert_required():
    """alert_required is True when disputed_count > 0."""
    from sportmaster_card.models.provenance import (
        DataProvenance,
        DataProvenanceLog,
        SourceType,
    )

    ts = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)

    # Log with one disputed entry -> alert required
    log_with_dispute = DataProvenanceLog(
        mcm_id="MCM-002-WHT-40",
        entries=[
            DataProvenance(
                attribute_name="description",
                value="Some text",
                source_type=SourceType.INTERNET_PHOTO,
                source_name="competitor_site",
                confidence=0.4,
                is_disputed=True,
                agent_id="agent-1.6",
                timestamp=ts,
            ),
        ],
    )
    assert log_with_dispute.alert_required is True
    assert log_with_dispute.disputed_count == 1

    # Log with no disputed entries -> no alert
    log_clean = DataProvenanceLog(
        mcm_id="MCM-003-RED-38",
        entries=[
            DataProvenance(
                attribute_name="brand",
                value="Adidas",
                source_type=SourceType.INTERNAL,
                source_name="Excel шаблон",
                confidence=0.99,
                is_disputed=False,
                agent_id="agent-1.3",
                timestamp=ts,
            ),
        ],
    )
    assert log_clean.alert_required is False
    assert log_clean.disputed_count == 0

    # Empty log -> no alert
    log_empty = DataProvenanceLog(mcm_id="MCM-004-GRN-44")
    assert log_empty.alert_required is False
    assert log_empty.disputed_count == 0
