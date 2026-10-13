"""Unit tests for metadata quality, transparency, attribution, and age heuristics."""

from backend.retrieval.models import Evidence, SourceType
from backend.sources.heuristics import (
    detect_attribution,
    detect_primary_reporting,
    parse_source_age,
)
from backend.sources.metadata_analyzer import (
    evaluate_metadata_quality,
    evaluate_transparency,
)
from backend.sources.models import SourceAge, TransparencyLevel


def _make_evidence(
    title="Headline",
    publisher="Reuters",
    author="Jane Doe",
    published_at="2026-05-01T10:00:00Z",
    canonical_url="https://reuters.com/news/1",
    snippet="Sample article content with sufficient character length.",
) -> Evidence:
    return Evidence(
        evidence_id="ev_001",
        claim_id="c1",
        title=title,
        url="https://reuters.com/news/1",
        canonical_url=canonical_url,
        publisher=publisher,
        domain="reuters.com",
        author=author,
        published_at=published_at,
        snippet=snippet,
        provider="gdelt",
        query_used="test",
        source_type=SourceType.NEWS,
    )


def test_metadata_quality_complete():
    """Verify complete metadata achieves max completeness score."""
    ev = _make_evidence()
    meta = evaluate_metadata_quality(ev)
    assert meta.score >= 0.95
    assert meta.has_title is True
    assert meta.has_publisher is True
    assert meta.has_author is True
    assert meta.has_published_at is True
    assert meta.has_canonical_url is True
    assert meta.has_content is True


def test_metadata_quality_missing_author_and_date():
    """Verify missing optional fields decrease score predictably."""
    ev = _make_evidence(author=None, published_at=None)
    meta = evaluate_metadata_quality(ev)
    assert meta.score <= 0.85
    assert meta.has_author is False
    assert meta.has_published_at is False


def test_transparency_levels():
    """Verify TransparencyLevel mapping across completeness stages."""
    # Complete -> HIGH
    ev_high = _make_evidence()
    meta_high = evaluate_metadata_quality(ev_high)
    assert evaluate_transparency(meta_high) == TransparencyLevel.HIGH

    # Missing author only -> MEDIUM
    ev_med = _make_evidence(author=None)
    meta_med = evaluate_metadata_quality(ev_med)
    assert evaluate_transparency(meta_med) == TransparencyLevel.MEDIUM

    # Missing publisher and author -> LOW
    ev_low = _make_evidence(publisher=None, author=None, snippet="Short")
    meta_low = evaluate_metadata_quality(ev_low)
    assert evaluate_transparency(meta_low) in (TransparencyLevel.LOW, TransparencyLevel.UNKNOWN)


def test_attribution_detection_with_quotes_and_actors():
    """Verify detection of reported speech, quotes, and named spokespeople."""
    text = (
        'According to the Ministry spokesperson, "The economic reforms will take effect in July." '
        'Officials confirmed the decision.'
    )
    attrib = detect_attribution(text)
    assert attrib.present is True
    assert attrib.has_quotes is True
    assert "Spokesperson" in attrib.named_sources or "Officials" in attrib.named_sources


def test_attribution_detection_empty():
    """Verify absence of attribution indicators."""
    text = "Inflation numbers rose across the retail sector."
    attrib = detect_attribution(text)
    assert attrib.present is False
    assert attrib.has_quotes is False
    assert attrib.named_sources == []


def test_primary_reporting_detection():
    """Verify detection of firsthand reporting signals."""
    text = "In an exclusive interview with this publication, the governor explained the policy."
    prim = detect_primary_reporting(text)
    assert prim.present is True
    assert "exclusive_reporting" in prim.signals or "direct_interview" in prim.signals


def test_source_age_categories():
    """Verify source age categorization for ISO and GDELT date strings."""
    # GDELT timestamp
    age, days = parse_source_age("20260405T120000Z")
    assert age in (SourceAge.VERY_RECENT, SourceAge.RECENT, SourceAge.OLDER)

    # Missing date
    age_unknown, _ = parse_source_age(None)
    assert age_unknown == SourceAge.UNKNOWN
