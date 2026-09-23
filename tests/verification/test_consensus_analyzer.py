"""Unit tests for cluster-aware evidence consensus and agreement ratio analysis."""

from backend.verification.consensus_analyzer import analyze_consensus
from backend.verification.models import (
    ClusterType,
    Discrepancy,
    DiscrepancyType,
    EvidenceCluster,
    EvidenceComparison,
    EvidenceStance,
    FactCheckComparison,
)


def test_consensus_cluster_deduplication():
    """Verify that multiple syndicated articles in one cluster count as only 1 independent confirmation."""
    # Cluster 1: 3 syndicated copies all SUPPORTING (e.g. Reuters wire copy)
    c1 = EvidenceComparison(
        evidence_id="ev_wire_origin",
        claim_id="cl_01",
        stance=EvidenceStance.SUPPORTING,
        confidence=0.9,
        relevance=0.95,
        reasoning="Wire report corroborates claim.",
    )
    c2 = EvidenceComparison(
        evidence_id="ev_reprint_1",
        claim_id="cl_01",
        stance=EvidenceStance.SUPPORTING,
        confidence=0.9,
        relevance=0.95,
        reasoning="Reprint corroborates claim.",
    )
    c3 = EvidenceComparison(
        evidence_id="ev_reprint_2",
        claim_id="cl_01",
        stance=EvidenceStance.SUPPORTING,
        confidence=0.9,
        relevance=0.95,
        reasoning="Reprint corroborates claim.",
    )

    # Independent item: 1 separate outlet CONTRADICTING
    c4 = EvidenceComparison(
        evidence_id="ev_independent_contra",
        claim_id="cl_01",
        stance=EvidenceStance.CONTRADICTING,
        confidence=0.88,
        relevance=0.9,
        reasoning="Independent outlet refutes claim.",
    )

    cluster_syndicated = EvidenceCluster(
        cluster_id="cluster_wire",
        evidence_ids=["ev_wire_origin", "ev_reprint_1", "ev_reprint_2"],
        cluster_type=ClusterType.SYNDICATION,
        representative_evidence_id="ev_wire_origin",
    )

    res = analyze_consensus(
        claim_id="cl_01",
        comparisons=[c1, c2, c3, c4],
        fact_checks=[],
        clusters=[cluster_syndicated],
    )

    assert res.supporting_count == 3
    assert res.contradicting_count == 1
    # Despite 3 supporting articles, cluster awareness means independent_supporting_count is 1!
    assert res.independent_supporting_count == 1
    assert res.independent_contradicting_count == 1
    assert res.agreement_ratio == 0.50


def test_consensus_unanimous_support():
    """Verify 3 separate independent sources yield agreement ratio of 1.0."""
    c1 = EvidenceComparison(
        evidence_id="ev_1",
        claim_id="cl_01",
        stance=EvidenceStance.SUPPORTING,
        confidence=0.9,
        relevance=0.9,
        reasoning="Source 1 corroborates.",
    )
    c2 = EvidenceComparison(
        evidence_id="ev_2",
        claim_id="cl_01",
        stance=EvidenceStance.SUPPORTING,
        confidence=0.85,
        relevance=0.9,
        reasoning="Source 2 corroborates.",
    )
    c3 = EvidenceComparison(
        evidence_id="ev_3",
        claim_id="cl_01",
        stance=EvidenceStance.SUPPORTING,
        confidence=0.88,
        relevance=0.92,
        reasoning="Source 3 corroborates.",
    )

    res = analyze_consensus(
        claim_id="cl_01",
        comparisons=[c1, c2, c3],
        fact_checks=[],
        clusters=[],
    )

    assert res.independent_supporting_count == 3
    assert res.independent_contradicting_count == 0
    assert res.agreement_ratio == 1.0
    assert "3 independent source(s)" in res.summary


def test_consensus_key_discrepancies_aggregated():
    """Verify discrepancies from comparisons are surfaced in key_discrepancies."""
    disc = Discrepancy(
        discrepancy_type=DiscrepancyType.NUMERIC,
        aspect="amount_crore",
        claim_value="₹500 crore",
        evidence_value="₹300 crore",
        severity="MAJOR",
    )
    c1 = EvidenceComparison(
        evidence_id="ev_disc",
        claim_id="cl_01",
        stance=EvidenceStance.CONTRADICTING,
        confidence=0.88,
        relevance=0.9,
        discrepancies=[disc],
        reasoning="Reports ₹300 crore instead of ₹500 crore.",
    )

    res = analyze_consensus(
        claim_id="cl_01",
        comparisons=[c1],
        fact_checks=[],
        clusters=[],
    )

    assert len(res.key_discrepancies) == 1
    assert res.key_discrepancies[0].aspect == "amount_crore"
