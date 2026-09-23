"""Unit tests for Deterministic Fallback Reasoner."""

from backend.ai.fallback_reasoner import generate_fallback_reasoning
from backend.ai.models import FindingImportance, UncertaintyLevel
from backend.ai.packet_builder import build_evidence_packet
from backend.claim.models import Claim, ClaimImportance, ClaimType
from backend.retrieval.models import Evidence, SourceType
from backend.sources.models import (
    ReliabilityLabel,
    SourceAge,
    SourceAnalysis,
    SourceCategory,
)
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    Discrepancy,
    DiscrepancyType,
    EvidenceCluster,
    EvidenceComparison,
    EvidenceStance,
)


def _make_claim(cid="c_1", text="Unemployment fell to 3.5% in July."):
    return Claim(
        claim_id=cid,
        original_text=text,
        normalized_text=text,
        claim_text=text,
        source_sentence=text,
        claim_type=ClaimType.STATISTIC,
        importance=ClaimImportance.HIGH,
        confidence=0.9,
    )


def _make_evidence(eid, domain="reuters.com", title="Jobs Report"):
    return Evidence(
        evidence_id=eid,
        claim_id="c_1",
        title=title,
        url=f"https://{domain}/{eid}",
        publisher="Reuters",
        domain=domain,
        snippet="The Bureau of Labor Statistics reported unemployment reached 3.5%.",
        source_type=SourceType.NEWS,
        provider="tavily",
        query_used="unemployment 3.5% july",
    )


def test_fallback_supporting_consensus():
    claim = _make_claim()
    ev1 = _make_evidence("ev_1", "reuters.com")
    ev2 = _make_evidence("ev_2", "apnews.com")

    sa1 = SourceAnalysis(
        evidence_id="ev_1",
        domain="reuters.com",
        publisher="Reuters",
        source_type="NEWS",
        source_category=SourceCategory.NEWS_MEDIA,
        source_age=SourceAge.RECENT,
        reliability_score=85,
        reliability_label=ReliabilityLabel.HIGH,
        transparency_score=0.85,
    )
    sa2 = SourceAnalysis(
        evidence_id="ev_2",
        domain="apnews.com",
        publisher="AP News",
        source_type="NEWS",
        source_category=SourceCategory.NEWS_MEDIA,
        source_age=SourceAge.RECENT,
        reliability_score=85,
        reliability_label=ReliabilityLabel.HIGH,
        transparency_score=0.85,
    )

    comparisons = [
        EvidenceComparison(
            evidence_id="ev_1",
            claim_id=claim.claim_id,
            stance=EvidenceStance.SUPPORTING,
            confidence=0.9,
            relevance=0.9,
            reasoning="Directly confirms 3.5% unemployment figure.",
        ),
        EvidenceComparison(
            evidence_id="ev_2",
            claim_id=claim.claim_id,
            stance=EvidenceStance.SUPPORTING,
            confidence=0.88,
            relevance=0.9,
            reasoning="Corroborates BLS data at 3.5%.",
        ),
    ]

    comp_result = ClaimEvidenceComparisonResult(
        claim_id=claim.claim_id,
        claim_text=claim.original_text,
        comparisons=comparisons,
    )

    cluster1 = EvidenceCluster(
        cluster_id="cl_1",
        evidence_ids=["ev_1"],
        representative_evidence_id="ev_1",
    )
    cluster2 = EvidenceCluster(
        cluster_id="cl_2",
        evidence_ids=["ev_2"],
        representative_evidence_id="ev_2",
    )
    indep_result = ClaimIndependenceResult(
        claim_id=claim.claim_id,
        total_sources=2,
        independent_source_count=2,
        clusters=[cluster1, cluster2],
    )

    packet = build_evidence_packet(
        claim=claim,
        evidence_items=[ev1, ev2],
        source_analyses=[sa1, sa2],
        independence_result=indep_result,
        comparison_result=comp_result,
    )

    result = generate_fallback_reasoning(packet)

    assert result.claim_id == claim.claim_id
    assert result.ai_used is False
    assert result.fallback_used is True
    assert result.provider == "deterministic_rule_engine"
    assert result.uncertainty in (UncertaintyLevel.LOW, UncertaintyLevel.MEDIUM)
    assert len(result.supporting_findings) >= 1
    assert len(result.contradicting_findings) == 0


def test_fallback_discrepancy_and_conflict():
    claim = _make_claim()
    ev1 = _make_evidence("ev_1", "reuters.com")
    ev2 = _make_evidence("ev_2", "blog.com")

    discrepancy = Discrepancy(
        discrepancy_type=DiscrepancyType.NUMERIC,
        aspect="rate",
        claim_value="3.5%",
        evidence_value="4.1%",
        snippet="Reports indicate unemployment is 4.1%",
        severity="MAJOR",
    )

    comparisons = [
        EvidenceComparison(
            evidence_id="ev_1",
            claim_id=claim.claim_id,
            stance=EvidenceStance.SUPPORTING,
            confidence=0.85,
            relevance=0.9,
            reasoning="Says 3.5%",
        ),
        EvidenceComparison(
            evidence_id="ev_2",
            claim_id=claim.claim_id,
            stance=EvidenceStance.CONTRADICTING,
            confidence=0.8,
            relevance=0.9,
            discrepancies=[discrepancy],
            reasoning="Claims 4.1%",
        ),
    ]

    comp_result = ClaimEvidenceComparisonResult(
        claim_id=claim.claim_id,
        claim_text=claim.original_text,
        comparisons=comparisons,
        key_discrepancies=[discrepancy],
    )

    packet = build_evidence_packet(
        claim=claim,
        evidence_items=[ev1, ev2],
        comparison_result=comp_result,
    )

    result = generate_fallback_reasoning(packet)

    assert result.uncertainty == UncertaintyLevel.HIGH
    assert len(result.important_discrepancies) >= 1
    assert len(result.supporting_findings) >= 1
    assert len(result.contradicting_findings) >= 1


def test_fallback_empty_evidence():
    claim = _make_claim()
    packet = build_evidence_packet(claim=claim, evidence_items=[])
    result = generate_fallback_reasoning(packet)

    assert result.uncertainty == UncertaintyLevel.HIGH
    assert "no independent corroborating sources" in result.summary.lower() or "insufficient" in result.summary.lower()
    assert len(result.verification_gaps) >= 1
    assert result.fallback_used is True
