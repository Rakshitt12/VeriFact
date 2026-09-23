"""Unit tests for fact-check rating normalization and stance mapping."""

from backend.retrieval.models import Evidence, SourceType
from backend.verification.factcheck_mapper import (
    is_fact_check_evidence,
    map_fact_check_comparison,
    map_raw_rating_to_verdict_and_stance,
)
from backend.verification.models import EvidenceStance


def test_map_raw_rating_supporting():
    """Verify supporting rating labels map to SUPPORTING stance."""
    cases = ["True", "mostly true", "Correct", "Accurate", "Verified", "CONFIRMED"]
    for raw in cases:
        verdict, stance = map_raw_rating_to_verdict_and_stance(raw)
        assert stance == EvidenceStance.SUPPORTING, f"Expected SUPPORTING for '{raw}', got {stance}"
        assert verdict in ("True", "Mostly True")


def test_map_raw_rating_contradicting():
    """Verify false / debunked rating labels map to CONTRADICTING stance."""
    cases = [
        "False",
        "Pants on Fire",
        "Misleading",
        "Fake",
        "Fabricated",
        "Hoax",
        "Debunked",
        "Distorts the Facts",
        "Mostly False",
        "Bust",
    ]
    for raw in cases:
        verdict, stance = map_raw_rating_to_verdict_and_stance(raw)
        assert stance == EvidenceStance.CONTRADICTING, f"Expected CONTRADICTING for '{raw}', got {stance}"


def test_map_raw_rating_neutral_or_mixed():
    """Verify mixed / unproven rating labels map to NEUTRAL stance."""
    cases = ["Half True", "Mixture", "Partly False", "Unproven", "Inconclusive", "Needs Context"]
    for raw in cases:
        verdict, stance = map_raw_rating_to_verdict_and_stance(raw)
        assert stance == EvidenceStance.NEUTRAL, f"Expected NEUTRAL for '{raw}', got {stance}"


def test_is_fact_check_evidence_detection():
    """Verify fact check detection across source_type, provider, and domain."""
    ev_fc_type = Evidence(
        evidence_id="ev_fc_01",
        claim_id="cl_01",
        title="Fact Check: Viral claim",
        url="https://example.com/fc",
        source_type=SourceType.FACT_CHECK,
        provider="gdelt",
        query_used="test query",
    )
    assert is_fact_check_evidence(ev_fc_type) is True

    ev_politifact = Evidence(
        evidence_id="ev_fc_02",
        claim_id="cl_01",
        title="Checking claim about taxes",
        url="https://www.politifact.com/factchecks/123",
        domain="politifact.com",
        source_type=SourceType.NEWS,
        provider="web_search",
        query_used="test query",
    )
    assert is_fact_check_evidence(ev_politifact) is True

    ev_normal_news = Evidence(
        evidence_id="ev_news_01",
        claim_id="cl_01",
        title="Regular news coverage",
        url="https://www.bbc.com/news/world-123",
        domain="bbc.com",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="test query",
    )
    assert is_fact_check_evidence(ev_normal_news) is False


def test_map_fact_check_comparison_full():
    """Verify complete mapping of FactCheckComparison and corresponding EvidenceComparison."""
    ev = Evidence(
        evidence_id="ev_fc_boom",
        claim_id="cl_01",
        title="Fact Check: Viral message claiming ₹10 petrol cut is false",
        url="https://www.boomlive.in/fact-check/123",
        publisher="Boom Live",
        domain="boomlive.in",
        snippet="Claim reviewed: 'Government cut petrol price by ₹10'. Rating: False",
        source_type=SourceType.FACT_CHECK,
        provider="factcheck_api",
        query_used="petrol price cut fact check",
        metadata={
            "verdict": "False",
            "rating": "False",
            "explanation": "No such order was passed by the ministry.",
        },
    )

    fc_comp, ev_comp = map_fact_check_comparison(ev, "cl_01")
    assert fc_comp.fact_check_id == "ev_fc_boom"
    assert fc_comp.fact_checker == "Boom Live"
    assert fc_comp.verdict_normalized == "False"
    assert fc_comp.stance == EvidenceStance.CONTRADICTING
    assert ev_comp.stance == EvidenceStance.CONTRADICTING
    assert ev_comp.confidence >= 0.90
    assert "Boom Live" in ev_comp.reasoning
