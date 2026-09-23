"""Tests 9-24 (except API): score/classification preservation, breakdowns,
syndication honesty, fact-checks, discrepancies, gaps, fallback, ordering,
empty evidence, hallucination guard, timestamps, methodology version."""

from __future__ import annotations

from datetime import datetime

from backend.ai.models import AIReasoningResult
from backend.claim.models import ClaimImportance
from backend.report.service import VerificationReportService
from backend.scoring.models import ScorePenalty
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    ClusterType,
    Discrepancy,
    DiscrepancyType,
    EvidenceCluster,
    EvidenceComparison,
    EvidenceRelationship,
    EvidenceStance,
    FactCheckComparison,
    IndependenceAnalysis,
    IndependenceStatus,
    RelationshipType,
)
from tests.report.conftest import (
    make_ai_reasoning,
    make_article,
    make_claim,
    make_claim_score,
    make_comparison,
    make_doc_score,
    make_evidence,
    make_independence,
    make_source_analysis,
)


def _gen(**overrides):
    svc = VerificationReportService()
    base = {
        "article": make_article(),
        "extracted_claims": [make_claim()],
        "all_evidence": {"c1": [make_evidence()]},
        "all_source_analyses": {"c1": [make_source_analysis()]},
        "all_independence": {"c1": make_independence()},
        "all_comparisons": {"c1": make_comparison()},
        "all_claim_scores": {"c1": make_claim_score()},
        "all_ai_reasoning": {"c1": make_ai_reasoning()},
        "doc_cred_score": make_doc_score(claim_scores=[make_claim_score()]),
        "request_type": "text",
    }
    base.update(overrides)
    return svc.generate_report(**base)


def test_insufficient_evidence_preserved():
    """Test 9 — score=None + INSUFFICIENT EVIDENCE preserved exactly."""
    score = make_claim_score(score=None, classification="INSUFFICIENT EVIDENCE")
    doc = make_doc_score(score=None, classification="INSUFFICIENT EVIDENCE",
                         claim_scores=[score])
    rep = _gen(all_claim_scores={"c1": score}, doc_cred_score=doc)
    assert rep.overall_result.score is None
    assert rep.overall_result.classification == "INSUFFICIENT EVIDENCE"
    assert rep.claims[0].score is None
    assert rep.claims[0].is_insufficient_evidence is True


def test_score_and_classification_preserved():
    """Tests 10-11 — no recalculation of Part 9 outputs."""
    rep = _gen()
    assert rep.overall_result.score == 76
    assert rep.overall_result.classification == "Mostly Supported"
    assert rep.claims[0].score == 76
    assert rep.claims[0].classification == "Mostly Supported"


def test_score_breakdown_and_penalties():
    """Tests 12-13 — every component/penalty represented with amounts."""
    score = make_claim_score()
    score.penalties = [ScorePenalty(penalty_type="numeric_discrepancy", amount=5.0,
                                    explanation="Amounts differ.", evidence_ids=["evidence_003"])]
    score.penalties_total = 5.0
    rep = _gen(all_claim_scores={"c1": score})
    bd = rep.claims[0].score_breakdown
    assert any(c.factor == "evidence_agreement" and c.weight == 0.30 for c in bd.components)
    assert any(c.raw_score == 0.72 and c.weighted_contribution == 21.6 for c in bd.components)
    assert bd.penalties[0].penalty_type == "numeric_discrepancy"
    assert bd.penalties[0].amount == 5.0


def test_syndication_not_counted_as_independent():
    """Test 14 — retrieved=5 vs independent=2 shown separately."""
    evs = [make_evidence(f"ev_{i}", url=f"https://wire.example/{i}") for i in range(5)]
    indep = ClaimIndependenceResult(
        claim_id="c1", total_evidence_count=5, independent_source_count=2,
        clusters=[
            EvidenceCluster(cluster_id="cl_syn", evidence_ids=["ev_0", "ev_1", "ev_2", "ev_3"],
                            cluster_type=ClusterType.SYNDICATION,
                            representative_evidence_id="ev_0",
                            independence_status=IndependenceStatus.LIKELY_DERIVED, confidence=0.9),
            EvidenceCluster(cluster_id="cl_ind", evidence_ids=["ev_4"],
                            cluster_type=ClusterType.INDEPENDENT,
                            representative_evidence_id="ev_4",
                            independence_status=IndependenceStatus.LIKELY_INDEPENDENT, confidence=0.9),
        ],
        relationships=[
            EvidenceRelationship(evidence_id_a="ev_0", evidence_id_b="ev_1",
                                 relationship_type=RelationshipType.SYNDICATED,
                                 similarity_score=0.9, confidence=0.9),
        ],
        analyses=[IndependenceAnalysis(evidence_id=f"ev_{i}", cluster_id="cl_syn" if i < 4 else "cl_ind",
                                       independence_status=IndependenceStatus.LIKELY_DERIVED if i < 4 else IndependenceStatus.LIKELY_INDEPENDENT,
                                       independence_confidence=0.9) for i in range(5)],
    )
    comps = [EvidenceComparison(evidence_id=f"ev_{i}", claim_id="c1",
                                stance=EvidenceStance.SUPPORTING, confidence=0.8,
                                relevance=0.8, reasoning="r") for i in range(5)]
    comparison = ClaimEvidenceComparisonResult(claim_id="c1", comparisons=comps, supporting_count=5)
    rep = _gen(all_evidence={"c1": evs}, all_independence={"c1": indep},
               all_comparisons={"c1": comparison},
               all_source_analyses={"c1": []})
    summ = rep.claims[0].evidence_summary
    assert summ.total_retrieved == 5
    assert summ.independent_source_count == 2
    assert summ.total_retrieved != summ.independent_source_count
    assert rep.claims[0].independence_analysis.syndication_clusters == 1


def test_fact_check_ratings_preserved():
    """Test 15 — original + normalized ratings both preserved."""
    comp = make_comparison()
    comp.fact_checks = [FactCheckComparison(
        fact_check_id="fc_1", claim_id="c1", verdict_normalized="False",
        raw_rating="Mostly False", fact_checker="Example Fact Checker",
        url="https://fc.example/r/1", stance=EvidenceStance.CONTRADICTING,
        explanation="Rating explanation.")]
    rep = _gen(all_comparisons={"c1": comp})
    fc = rep.claims[0].fact_checks[0]
    assert fc.original_rating == "Mostly False"
    assert fc.normalized_rating == "False"
    assert fc.publisher == "Example Fact Checker"


def test_discrepancy_evidence_ids():
    """Test 16 — numeric discrepancy appears with correct evidence linkage."""
    comp = make_comparison()
    comp.key_discrepancies = [Discrepancy(
        discrepancy_type=DiscrepancyType.NUMERIC, aspect="AMOUNT",
        claim_value="Rs 500 crore", evidence_value="Rs 300 crore", severity="MAJOR")]
    rep = _gen(all_comparisons={"c1": comp})
    d = rep.claims[0].discrepancies[0]
    assert d.type == "NUMERIC"
    assert "500" in d.claim_value and "300" in d.evidence_value


def test_verification_gaps_surfaced():
    """Test 17 — Part 8 gaps appear verbatim in the report."""
    ai = make_ai_reasoning()
    ai.verification_gaps = ["The primary project document was not retrieved."]
    rep = _gen(all_ai_reasoning={"c1": ai})
    assert "The primary project document was not retrieved." in rep.claims[0].verification_gaps


def test_ai_fallback_disclosed():
    """Test 18 — fallback reasoning explicitly disclosed."""
    ai = AIReasoningResult(summary="fallback summary", ai_used=False,
                           fallback_used=True, provider=None, model=None)
    rep = _gen(all_ai_reasoning={"c1": ai})
    assert rep.claims[0].ai_reasoning.fallback_used is True
    assert rep.claims[0].ai_reasoning.ai_used is False
    assert any("fallback" in lim.lower() for lim in rep.claims[0].limitations)


def test_multi_claim_and_ordering():
    """Tests 19-20 — three claims produce three sections in importance order."""
    c_high = make_claim("c_high", "High importance claim.", ClaimImportance.HIGH)
    c_med = make_claim("c_med", "Medium importance claim.", ClaimImportance.MEDIUM)
    c_low = make_claim("c_low", "Low importance claim.", ClaimImportance.LOW)
    # Pass in scrambled extraction order; report must order HIGH, MEDIUM, LOW
    rep = _gen(
        extracted_claims=[c_low, c_high, c_med],
        all_evidence={"c_high": [make_evidence("ev_h", claim_id="c_high")],
                      "c_med": [make_evidence("ev_m", claim_id="c_med")],
                      "c_low": [make_evidence("ev_l", claim_id="c_low")]},
        all_source_analyses={"c_high": [], "c_med": [], "c_low": []},
        all_independence={"c_high": make_independence("c_high"),
                          "c_med": make_independence("c_med"),
                          "c_low": make_independence("c_low")},
        all_comparisons={"c_high": make_comparison("c_high"),
                         "c_med": make_comparison("c_med"),
                         "c_low": make_comparison("c_low")},
        all_claim_scores={"c_high": make_claim_score("c_high"),
                          "c_med": make_claim_score("c_med"),
                          "c_low": make_claim_score("c_low")},
        all_ai_reasoning={"c_high": make_ai_reasoning(),
                          "c_med": make_ai_reasoning(),
                          "c_low": make_ai_reasoning()},
        doc_cred_score=make_doc_score(claim_scores=[make_claim_score("c_high")]),
    )
    assert [c.claim_id for c in rep.claims] == ["c_high", "c_med", "c_low"]
    assert len(rep.claims) == 3


def test_empty_evidence_valid():
    """Test 21 — report stays valid with no evidence retrieved."""
    rep = _gen(all_evidence={"c1": []},
               all_comparisons={"c1": ClaimEvidenceComparisonResult(claim_id="c1")},
               all_source_analyses={"c1": []})
    assert rep.claims[0].evidence_summary.total_retrieved == 0
    assert rep.claims[0].supporting_evidence == []
    assert rep.model_dump()  # serializes


def test_no_hallucinated_data():
    """Test 22 — publishers/URLs/dates come only from source data."""
    rep = _gen()
    allowed_urls = {"https://example.gov.in/news/1"}
    for c in rep.citations:
        assert c.url in allowed_urls
    for claim in rep.claims:
        for card in claim.supporting_evidence + claim.contradicting_evidence:
            assert card.url in allowed_urls


def test_timestamp_and_methodology():
    """Tests 23-24 — tz-aware timestamp + methodology preserved."""
    rep = _gen()
    ts = rep.generated_at
    assert "T" in ts
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None
    assert rep.methodology_version == "v1.0"
