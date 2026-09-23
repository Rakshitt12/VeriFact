"""Unit tests for the distinct INSUFFICIENT_EVIDENCE threshold state."""

import pytest

from backend.api.schemas import ClassificationLabel
from backend.retrieval.models import Evidence, SourceType
from backend.scoring.credibility_score import CredibilityScoreCalculator
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    EvidenceComparison,
    EvidenceStance,
)


def _make_evidence(eid: str) -> Evidence:
    return Evidence(
        evidence_id=eid,
        claim_id="cl_insufficient",
        title=f"Article {eid}",
        url=f"https://example.com/{eid}",
        publisher="Example News",
        domain="example.com",
        snippet=f"Snippet for {eid}",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="test query",
    )


def test_insufficient_evidence_when_zero_evidence():
    """Verify 0 evidence items yields score=None and INSUFFICIENT EVIDENCE."""
    calc = CredibilityScoreCalculator()
    result = calc.calculate_claim_score(
        claim_id="cl_zero",
        claim_text="Unverifiable rumor statement.",
        evidence_items=[],
    )
    assert result.score is None
    assert result.classification == ClassificationLabel.INSUFFICIENT_EVIDENCE.value
    assert result.is_insufficient_evidence


def test_insufficient_evidence_when_single_independent_source():
    """Verify single independent source fails MIN_INDEPENDENT_SOURCES=2 threshold."""
    calc = CredibilityScoreCalculator()
    ev1 = _make_evidence("ev_single")

    indep = ClaimIndependenceResult(
        claim_id="cl_insufficient",
        total_evidence_count=1,
        independent_source_count=1,
    )
    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_insufficient",
        supporting_count=1,
        contradicting_count=0,
        independent_supporting_count=1,
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_single",
                claim_id="cl_insufficient",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.9,
                relevance=0.8,
                reasoning="Agrees",
            )
        ],
    )

    result = calc.calculate_claim_score(
        claim_id="cl_insufficient",
        claim_text="Single source statement.",
        evidence_items=[ev1],
        independence_result=indep,
        comparison_result=comp_res,
    )

    assert result.score is None
    assert result.classification == "INSUFFICIENT EVIDENCE"
    assert result.is_insufficient_evidence
    assert any("threshold not met" in lim.lower() for lim in result.limitations)


def test_insufficient_evidence_when_only_neutral_items():
    """Verify items without decisive stance fail MIN_CLASSIFIED_EVIDENCE_ITEMS=2 threshold."""
    calc = CredibilityScoreCalculator()
    ev1 = _make_evidence("ev_neu1")
    ev2 = _make_evidence("ev_neu2")

    indep = ClaimIndependenceResult(
        claim_id="cl_insufficient",
        total_evidence_count=2,
        independent_source_count=2,
    )
    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_insufficient",
        supporting_count=0,
        contradicting_count=0,
        neutral_count=2,
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_neu1",
                claim_id="cl_insufficient",
                stance=EvidenceStance.NEUTRAL,
                confidence=0.8,
                relevance=0.7,
                reasoning="Mentions topic vaguely",
            ),
            EvidenceComparison(
                evidence_id="ev_neu2",
                claim_id="cl_insufficient",
                stance=EvidenceStance.NEUTRAL,
                confidence=0.8,
                relevance=0.7,
                reasoning="Background context",
            ),
        ],
    )

    result = calc.calculate_claim_score(
        claim_id="cl_insufficient",
        claim_text="Vague topic statement.",
        evidence_items=[ev1, ev2],
        independence_result=indep,
        comparison_result=comp_res,
    )

    assert result.score is None
    assert result.classification == "INSUFFICIENT EVIDENCE"
    assert result.is_insufficient_evidence
