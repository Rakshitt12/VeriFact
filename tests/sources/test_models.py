"""Unit tests for source analysis data models and enums."""

import pytest
from pydantic import ValidationError

from backend.sources.models import (
    AttributionSignal,
    MetadataQuality,
    PrimaryReportingSignal,
    ReliabilityLabel,
    SourceAge,
    SourceAnalysis,
    SourceCategory,
    TransparencyLevel,
)


def test_source_category_enum():
    """Verify supported domain categories."""
    assert SourceCategory.GOVERNMENT == "GOVERNMENT"
    assert SourceCategory.ACADEMIC == "ACADEMIC"
    assert SourceCategory.INTERNATIONAL_ORGANIZATION == "INTERNATIONAL_ORGANIZATION"
    assert SourceCategory.REGULATORY == "REGULATORY"
    assert SourceCategory.NEWS_MEDIA == "NEWS_MEDIA"
    assert SourceCategory.FACT_CHECKER == "FACT_CHECKER"
    assert SourceCategory.ORGANIZATION == "ORGANIZATION"
    assert SourceCategory.PERSONAL_BLOG == "PERSONAL_BLOG"
    assert SourceCategory.UNKNOWN == "UNKNOWN"


def test_transparency_level_enum():
    """Verify transparency categorical values."""
    assert TransparencyLevel.HIGH == "HIGH"
    assert TransparencyLevel.MEDIUM == "MEDIUM"
    assert TransparencyLevel.LOW == "LOW"
    assert TransparencyLevel.UNKNOWN == "UNKNOWN"


def test_reliability_label_enum():
    """Verify qualitative reliability tiers."""
    assert ReliabilityLabel.HIGH == "HIGH"
    assert ReliabilityLabel.MEDIUM == "MEDIUM"
    assert ReliabilityLabel.LOW == "LOW"
    assert ReliabilityLabel.UNKNOWN == "UNKNOWN"


def test_source_age_enum():
    """Verify source age bins."""
    assert SourceAge.VERY_RECENT == "VERY_RECENT"
    assert SourceAge.RECENT == "RECENT"
    assert SourceAge.OLDER == "OLDER"
    assert SourceAge.UNKNOWN == "UNKNOWN"


def test_source_analysis_valid_creation():
    """Verify valid SourceAnalysis construction."""
    sa = SourceAnalysis(
        evidence_id="ev_123",
        domain="reuters.com",
        publisher="Reuters",
        source_type="NEWS",
        source_category=SourceCategory.NEWS_MEDIA,
        reliability_score=85,
        reliability_label=ReliabilityLabel.HIGH,
        transparency=TransparencyLevel.HIGH,
        attribution=AttributionSignal(present=True, has_quotes=True, named_sources=["Finance Minister"]),
        primary_reporting=PrimaryReportingSignal(present=True, signals=["exclusive_reporting"]),
        metadata_quality=MetadataQuality(score=0.9, has_title=True, has_publisher=True, has_author=True),
        source_age=SourceAge.VERY_RECENT,
        signals=["Publisher clearly identified", "Named author credited"],
        limitations=[],
    )
    assert sa.evidence_id == "ev_123"
    assert sa.reliability_score == 85
    assert sa.source_category == SourceCategory.NEWS_MEDIA
    assert "not a guarantee of factual accuracy" in sa.heuristic_notes.lower()


def test_source_analysis_score_bounds():
    """Verify reliability_score is bounded between 0 and 100."""
    with pytest.raises(ValidationError):
        SourceAnalysis(
            evidence_id="ev_invalid",
            domain="example.com",
            source_type="NEWS",
            reliability_score=105,  # Exceeds 100
            reliability_label=ReliabilityLabel.HIGH,
        )
    with pytest.raises(ValidationError):
        SourceAnalysis(
            evidence_id="ev_invalid",
            domain="example.com",
            source_type="NEWS",
            reliability_score=-5,  # Below 0
            reliability_label=ReliabilityLabel.LOW,
        )
