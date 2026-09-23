"""Tests 6-8: stance-routed evidence formatting."""

from backend.report.evidence_formatter import EvidenceFormatter
from backend.verification.models import EvidenceStance
from tests.report.conftest import (
    make_comparison,
    make_evidence,
    make_independence,
    make_source_analysis,
)


def test_supporting_evidence_section():
    """Test 6 — SUPPORTING evidence appears in the supporting section."""
    ev = make_evidence("evidence_003")
    comp = make_comparison(stance=EvidenceStance.SUPPORTING, evidence_id="evidence_003")
    cards = EvidenceFormatter.format_evidence_cards(
        [ev], comp, [make_source_analysis()], make_independence())
    assert [c.evidence_id for c in cards["SUPPORTING"]] == ["evidence_003"]
    assert cards["CONTRADICTING"] == []


def test_contradicting_evidence_preserved():
    """Test 7 — CONTRADICTING evidence is preserved and displayed."""
    ev = make_evidence("evidence_011", url="https://reg.example/doc")
    comp = make_comparison(stance=EvidenceStance.CONTRADICTING, evidence_id="evidence_011")
    cards = EvidenceFormatter.format_evidence_cards(
        [ev], comp, [make_source_analysis("evidence_011")], make_independence())
    assert [c.evidence_id for c in cards["CONTRADICTING"]] == ["evidence_011"]
    # Contradiction must not leak into supporting
    assert all(c.evidence_id != "evidence_011" for c in cards["SUPPORTING"])


def test_neutral_not_labelled_supporting():
    """Test 8 — NEUTRAL / INSUFFICIENT evidence stays out of supporting."""
    ev_n = make_evidence("ev_n", url="https://n.example/1")
    ev_i = make_evidence("ev_i", url="https://i.example/2")
    from backend.verification.models import ClaimEvidenceComparisonResult, EvidenceComparison
    comp = ClaimEvidenceComparisonResult(
        claim_id="c1",
        comparisons=[
            EvidenceComparison(evidence_id="ev_n", claim_id="c1",
                               stance=EvidenceStance.NEUTRAL, confidence=0.8,
                               relevance=0.5, reasoning="context only"),
            EvidenceComparison(evidence_id="ev_i", claim_id="c1",
                               stance=EvidenceStance.INSUFFICIENT, confidence=0.5,
                               relevance=0.3, reasoning="too vague"),
        ],
        neutral_count=1, insufficient_count=1,
    )
    cards = EvidenceFormatter.format_evidence_cards([ev_n, ev_i], comp, [], make_independence())
    assert [c.evidence_id for c in cards["NEUTRAL"]] == ["ev_n"]
    assert [c.evidence_id for c in cards["INSUFFICIENT"]] == ["ev_i"]
    assert cards["SUPPORTING"] == [] and cards["CONTRADICTING"] == []
