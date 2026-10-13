"""Unit tests for VerificationService facade."""

from backend.retrieval.models import Evidence, SourceType
from backend.verification.models import ClusterType, IndependenceStatus
from backend.verification.service import VerificationService, analyze_evidence_independence


def _make_ev(eid, domain, title, snippet="", url=None) -> Evidence:
    u = url or f"https://{domain}/news/{eid}"
    return Evidence(
        evidence_id=eid,
        claim_id="c1",
        title=title,
        url=u,
        canonical_url=u.split("?")[0],
        domain=domain,
        snippet=snippet,
        provider="gdelt",
        query_used="q",
        source_type=SourceType.NEWS,
    )


def test_service_empty_evidence():
    """Verify service returns clean empty result on empty input."""
    res = analyze_evidence_independence([], claim_id="c_empty")
    assert res.total_evidence_count == 0
    assert res.independent_source_count == 0
    assert res.clusters == []
    assert res.relationships == []


def test_service_single_evidence():
    """Verify single evidence item forms 1 independent cluster."""
    ev = _make_ev("ev1", "reuters.com", "Headline 1", snippet="Content here")
    res = analyze_evidence_independence([ev], claim_id="c_single")
    assert res.total_evidence_count == 1
    assert res.independent_source_count == 1
    assert len(res.clusters) == 1
    assert res.clusters[0].cluster_type == ClusterType.INDEPENDENT
    assert res.analyses[0].independence_status == IndependenceStatus.LIKELY_INDEPENDENT


def test_service_mixed_ecosystem():
    """Verify realistic ecosystem with duplicate URLs and distinct reporting."""
    # Two identical URLs (e.g. from 2 search queries)
    ev1 = _make_ev("ev1", "ndtv.com", "NDTV Report", url="https://ndtv.com/story?ref=1")
    ev2 = _make_ev("ev2", "ndtv.com", "NDTV Report", url="https://ndtv.com/story?ref=2")
    # One distinct outlet
    ev3 = _make_ev("ev3", "thehindu.com", "The Hindu Report", snippet="Distinct reporting angle")

    res = VerificationService.analyze_evidence_independence([ev1, ev2, ev3], claim_id="c_mixed")
    assert res.total_evidence_count == 3
    assert res.independent_source_count == 2
    assert len(res.clusters) == 2
