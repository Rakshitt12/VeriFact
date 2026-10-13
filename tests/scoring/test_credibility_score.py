"""Unit tests for CredibilityScoreCalculator and classification."""

import pytest

from backend.api.schemas import ClassificationLabel
from backend.retrieval.models import Evidence, SourceType
from backend.scoring.credibility_score import (
    CredibilityScoreCalculator,
    classify_credibility_score,
)
from backend.sources.models import (
    MetadataQuality,
    PrimaryReportingSignal,
    ReliabilityLabel,
    SourceAge,
    SourceAnalysis,
    SourceCategory,
    TransparencyLevel,
)
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    Discrepancy,
    DiscrepancyType,
    EvidenceComparison,
    EvidenceStance,
    FactCheckComparison,
)


def _make_evidence(eid: str) -> Evidence:
    return Evidence(
        evidence_id=eid,
        claim_id="cl_test",
        title=f"Article {eid}",
        url=f"https://domain.com/{eid}",
        publisher="Domain News",
        domain="domain.com",
        snippet=f"Snippet for {eid}",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="test",
    )


def _make_source_analysis(eid: str, rel_score: int = 85) -> SourceAnalysis:
    return SourceAnalysis(
        evidence_id=eid,
        domain="domain.com",
        publisher="Domain News",
        source_type="NEWS",
        source_category=SourceCategory.NEWS_MEDIA,
        reliability_score=rel_score,
        reliability_label=ReliabilityLabel.HIGH if rel_score >= 75 else ReliabilityLabel.MEDIUM,
        transparency=TransparencyLevel.HIGH,
        primary_reporting=PrimaryReportingSignal(present=True),
        metadata_quality=MetadataQuality(score=0.9),
        source_age=SourceAge.RECENT,
    )


def test_classify_credibility_score_boundaries():
    """Verify classification thresholds."""
    assert classify_credibility_score(None) == "INSUFFICIENT EVIDENCE"
    assert classify_credibility_score(100) == "Strongly Supported"
    assert classify_credibility_score(90) == "Strongly Supported"
    assert classify_credibility_score(89) == "Mostly Supported"
    assert classify_credibility_score(75) == "Mostly Supported"
    assert classify_credibility_score(74) == "Mixed / Uncertain"
    assert classify_credibility_score(50) == "Mixed / Uncertain"
    assert classify_credibility_score(49) == "Weakly Supported"
    assert classify_credibility_score(25) == "Weakly Supported"
    assert classify_credibility_score(24) == "Strongly Contradicted"
    assert classify_credibility_score(0) == "Strongly Contradicted"


def test_strongly_supported_score_calculation():
    """Verify calculation produces a Strongly Supported score when all signals align."""
    calc = CredibilityScoreCalculator()

    ev1 = _make_evidence("ev1")
    ev2 = _make_evidence("ev2")
    ev3 = _make_evidence("ev3")

    sa1 = _make_source_analysis("ev1", rel_score=95)
    sa2 = _make_source_analysis("ev2", rel_score=90)
    sa3 = _make_source_analysis("ev3", rel_score=92)

    indep = ClaimIndependenceResult(
        claim_id="cl_test",
        total_evidence_count=3,
        independent_source_count=3,
    )

    fc = FactCheckComparison(
        fact_check_id="fc1",
        claim_id="cl_test",
        verdict_normalized="True",
        raw_rating="True",
        fact_checker="Reuters Fact Check",
        url="https://reuters.com/factcheck",
        stance=EvidenceStance.SUPPORTING,
        explanation="Confirmed accurate",
    )

    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        supporting_count=3,
        contradicting_count=0,
        independent_supporting_count=3,
        independent_contradicting_count=0,
        agreement_ratio=1.0,
        comparisons=[
            EvidenceComparison(
                evidence_id="ev1",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.95,
                relevance=0.9,
                reasoning="Agrees",
            ),
            EvidenceComparison(
                evidence_id="ev2",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.95,
                relevance=0.9,
                reasoning="Agrees",
            ),
            EvidenceComparison(
                evidence_id="ev3",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.95,
                relevance=0.9,
                reasoning="Agrees",
            ),
        ],
        fact_checks=[fc],
    )

    result = calc.calculate_claim_score(
        claim_id="cl_test",
        claim_text="Inflation rose by 3% in Q2.",
        evidence_items=[ev1, ev2, ev3],
        source_analyses=[sa1, sa2, sa3],
        independence_result=indep,
        comparison_result=comp_res,
    )

    assert result.score is not None
    assert result.score >= 80
    assert not result.is_insufficient_evidence
    assert len(result.components) == 6
    assert len(result.score_breakdown) > 0
    # Ranked by impact
    assert abs(result.score_breakdown[0].contribution) >= abs(result.score_breakdown[-1].contribution)


def test_strongly_contradicted_with_penalties():
    """Verify calculation produces a Strongly Contradicted score when refutations and penalties apply."""
    calc = CredibilityScoreCalculator()

    ev1 = _make_evidence("ev1")
    ev2 = _make_evidence("ev2")
    sa1 = _make_source_analysis("ev1", rel_score=85)
    sa2 = _make_source_analysis("ev2", rel_score=85)

    indep = ClaimIndependenceResult(
        claim_id="cl_test",
        total_evidence_count=2,
        independent_source_count=2,
    )

    fc = FactCheckComparison(
        fact_check_id="fc_contra",
        claim_id="cl_test",
        verdict_normalized="False",
        raw_rating="False",
        fact_checker="AFP Fact Check",
        url="https://factcheck.afp.com/123",
        stance=EvidenceStance.CONTRADICTING,
        explanation="Refuted entirely",
    )

    disc = Discrepancy(
        discrepancy_type=DiscrepancyType.POLARITY,
        aspect="law_status",
        claim_value="banned",
        evidence_value="not banned",
        severity="CRITICAL",
    )

    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        supporting_count=0,
        contradicting_count=2,
        independent_supporting_count=0,
        independent_contradicting_count=2,
        agreement_ratio=0.0,
        comparisons=[
            EvidenceComparison(
                evidence_id="ev1",
                claim_id="cl_test",
                stance=EvidenceStance.CONTRADICTING,
                confidence=0.9,
                relevance=0.9,
                reasoning="Denies",
            ),
            EvidenceComparison(
                evidence_id="ev2",
                claim_id="cl_test",
                stance=EvidenceStance.CONTRADICTING,
                confidence=0.9,
                relevance=0.9,
                reasoning="Denies",
            ),
        ],
        fact_checks=[fc],
        key_discrepancies=[disc],
    )

    result = calc.calculate_claim_score(
        claim_id="cl_test",
        claim_text="Country bans all social media.",
        evidence_items=[ev1, ev2],
        source_analyses=[sa1, sa2],
        independence_result=indep,
        comparison_result=comp_res,
    )

    assert result.score is not None
    assert result.score < 25
    assert result.classification == "Strongly Contradicted"
    assert result.penalties_total > 0
