"""Unit tests for independence analysis, clustering, and representative article selection."""

from backend.retrieval.models import Evidence, SourceType
from backend.sources.models import (
    MetadataQuality,
    PrimaryReportingSignal,
    ReliabilityLabel,
    SourceAnalysis,
    SourceCategory,
    TransparencyLevel,
)
from backend.verification.independence_analyzer import (
    cluster_and_analyze_independence,
    evaluate_pair_independence,
)
from backend.verification.models import ClusterType, IndependenceStatus, RelationshipType


def _make_ev(eid, domain, publisher, title, snippet="", url=None) -> Evidence:
    full_url = url or f"https://{domain}/article/{eid}"
    return Evidence(
        evidence_id=eid,
        claim_id="c1",
        title=title,
        url=full_url,
        canonical_url=full_url,
        domain=domain,
        publisher=publisher,
        snippet=snippet,
        provider="gdelt",
        query_used="q",
        source_type=SourceType.NEWS,
    )


def _make_sa(eid, domain, category=SourceCategory.NEWS_MEDIA, primary=False) -> SourceAnalysis:
    return SourceAnalysis(
        evidence_id=eid,
        domain=domain,
        source_type="NEWS",
        source_category=category,
        reliability_score=80,
        reliability_label=ReliabilityLabel.HIGH,
        transparency=TransparencyLevel.HIGH,
        primary_reporting=PrimaryReportingSignal(present=primary),
        metadata_quality=MetadataQuality(score=0.9),
    )


def test_cluster_syndicated_and_duplicate_sources():
    """CRITICAL TEST: Verify that 4 articles originating from 1 wire + 1 independent report

    resolve into exactly 2 independent source clusters (Rule: # of articles != # of sources).
    """
    # Group 1: Reuters original + 2 reprints (Times of India, NDTV citing Reuters)
    ev_reuters = _make_ev(
        "ev_reuters", "reuters.com", "Reuters",
        "India approves $10 bln semiconductor project in Gujarat",
        snippet="New Delhi (Reuters) - India's cabinet on Tuesday approved a $10 billion semiconductor plan.",
    )
    ev_toi = _make_ev(
        "ev_toi", "timesofindia.indiatimes.com", "Times of India",
        "India clears $10bn chip plant in Gujarat: Reuters",
        snippet="New Delhi: According to Reuters, the cabinet approved a $10 billion semiconductor plan.",
    )
    ev_ndtv = _make_ev(
        "ev_ndtv", "ndtv.com", "NDTV",
        "India approves $10 billion chip plant in Gujarat: Reuters report",
        snippet="New Delhi: According to Reuters, the cabinet approved a $10 billion semiconductor plan.",
    )

    # Group 2: Independent analysis by BBC News with distinct text and angle
    ev_bbc = _make_ev(
        "ev_bbc", "bbc.com", "BBC News",
        "Can India become a global semiconductor manufacturing powerhouse?",
        snippet="Analysis of supply chain challenges, water resources, and geopolitical positioning in Gujarat.",
    )

    items = [ev_reuters, ev_toi, ev_ndtv, ev_bbc]
    analyses = [
        _make_sa("ev_reuters", "reuters.com", primary=True),
        _make_sa("ev_toi", "timesofindia.indiatimes.com"),
        _make_sa("ev_ndtv", "ndtv.com"),
        _make_sa("ev_bbc", "bbc.com", primary=True),
    ]

    res = cluster_and_analyze_independence(items, source_analyses=analyses, claim_id="claim_001")

    assert res.total_evidence_count == 4
    # Crucial assertion: 4 articles must collapse into 2 independent source clusters!
    assert res.independent_source_count == 2
    assert len(res.clusters) == 2

    # Check that Reuters was chosen as representative of the syndicated cluster
    syn_cluster = next(c for c in res.clusters if len(c.evidence_ids) == 3)
    assert syn_cluster.representative_evidence_id == "ev_reuters"
    assert syn_cluster.cluster_type in (ClusterType.SYNDICATION, ClusterType.MIXED)


def test_all_independent_sources():
    """Verify that distinct independent outlets each count as an independent source."""
    ev1 = _make_ev("e1", "thehindu.com", "The Hindu", "Headline A", snippet="Report on economic indices.")
    ev2 = _make_ev("e2", "pib.gov.in", "PIB", "Headline B", snippet="Official release regarding finance.")
    ev3 = _make_ev("e3", "wsj.com", "WSJ", "Headline C", snippet="Wall Street analysis on markets.")

    res = cluster_and_analyze_independence([ev1, ev2, ev3], claim_id="c1")
    assert res.total_evidence_count == 3
    assert res.independent_source_count == 3
    for cl in res.clusters:
        assert cl.cluster_type == ClusterType.INDEPENDENT


def test_exact_duplicates_clustered():
    """Verify that identical canonical URLs are collapsed into 1 independent source."""
    url = "https://example.com/breaking-news"
    ev1 = _make_ev("e1", "example.com", "Example", "Breaking News", url=f"{url}?utm_source=twitter")
    ev2 = _make_ev("e2", "example.com", "Example", "Breaking News", url=f"{url}?utm_source=fb")

    res = cluster_and_analyze_independence([ev1, ev2], claim_id="c1")
    assert res.total_evidence_count == 2
    assert res.independent_source_count == 1
    assert res.clusters[0].cluster_type == ClusterType.DUPLICATE
