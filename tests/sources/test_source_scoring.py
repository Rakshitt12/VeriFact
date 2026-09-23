"""Unit tests for the source reliability heuristic scoring calculation."""

from backend.retrieval.models import Evidence, SourceType
from backend.sources.models import (
    AttributionSignal,
    MetadataQuality,
    PrimaryReportingSignal,
    ReliabilityLabel,
    SourceAge,
    SourceCategory,
    TransparencyLevel,
)
from backend.sources.source_scoring import calculate_source_reliability


def _build_test_evidence(domain="thehindu.com", publisher="The Hindu", author="Reporter"):
    return Evidence(
        evidence_id="ev_test",
        claim_id="c1",
        title="Major Economic Policy Announced",
        url=f"https://{domain}/article/1",
        canonical_url=f"https://{domain}/article/1",
        publisher=publisher,
        domain=domain,
        author=author,
        published_at="2026-05-15T10:00:00Z",
        snippet="Official statements from the ministry indicate swift execution.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="economic policy",
    )


def test_calculate_source_reliability_high_tier():
    """Verify high-transparency institutional source receives a high reliability score."""
    ev = _build_test_evidence(domain="pib.gov.in", publisher="PIB")
    meta = MetadataQuality(
        score=0.9,
        has_title=True,
        has_publisher=True,
        has_author=True,
        has_published_at=True,
        has_canonical_url=True,
        has_content=True,
    )
    attrib = AttributionSignal(present=True, has_quotes=True, named_sources=["Ministry Officials"])
    primary = PrimaryReportingSignal(present=True, signals=["official_filing"])

    score, label, signals, limitations = calculate_source_reliability(
        evidence=ev,
        category=SourceCategory.GOVERNMENT,
        transparency=TransparencyLevel.HIGH,
        attribution=attrib,
        primary_reporting=primary,
        metadata_quality=meta,
        source_age=SourceAge.VERY_RECENT,
    )

    assert score >= 75
    assert label == ReliabilityLabel.HIGH
    assert len(signals) >= 3
    assert any("publisher clearly identified" in s.lower() for s in signals)
    assert any("official" in s.lower() for s in signals)


def test_calculate_source_reliability_low_tier():
    """Verify anonymous personal blog with sparse metadata receives low reliability score."""
    ev = _build_test_evidence(domain="anonymousblog.blogspot.com", publisher=None, author=None)
    meta = MetadataQuality(
        score=0.2,
        has_title=True,
        has_publisher=False,
        has_author=False,
        has_published_at=False,
        has_canonical_url=False,
        has_content=False,
    )
    attrib = AttributionSignal(present=False, has_quotes=False, named_sources=[])
    primary = PrimaryReportingSignal(present=False, signals=[])

    score, label, signals, limitations = calculate_source_reliability(
        evidence=ev,
        category=SourceCategory.PERSONAL_BLOG,
        transparency=TransparencyLevel.LOW,
        attribution=attrib,
        primary_reporting=primary,
        metadata_quality=meta,
        source_age=SourceAge.UNKNOWN,
    )

    assert score < 50
    assert label in (ReliabilityLabel.LOW, ReliabilityLabel.UNKNOWN)
    assert len(limitations) >= 2
    assert any("author byline missing" in l.lower() for l in limitations)


def test_reliability_scoring_is_heuristic_boundary():
    """Verify that source reliability scoring does NOT determine claim truth or stance."""
    ev = _build_test_evidence()
    meta = MetadataQuality(score=0.8, has_title=True, has_publisher=True, has_canonical_url=True)
    attrib = AttributionSignal(present=False)
    primary = PrimaryReportingSignal(present=False)

    score, label, signals, limitations = calculate_source_reliability(
        evidence=ev,
        category=SourceCategory.NEWS_MEDIA,
        transparency=TransparencyLevel.MEDIUM,
        attribution=attrib,
        primary_reporting=primary,
        metadata_quality=meta,
        source_age=SourceAge.RECENT,
    )

    # Output contains purely source metadata observations, no claim veracity statements
    for s in signals:
        assert "true" not in s.lower()
        assert "false" not in s.lower()
        assert "verdict" not in s.lower()
    for l in limitations:
        assert "true" not in l.lower()
        assert "false" not in l.lower()
