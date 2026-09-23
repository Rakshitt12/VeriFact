"""Shared deterministic fixtures for Part 10 report tests (no external APIs)."""

from __future__ import annotations

import pytest

from backend.ai.models import AIReasoningResult
from backend.claim.models import Claim, ClaimImportance, ClaimType
from backend.ingestion.models import NormalizedArticle
from backend.retrieval.models import Evidence, SourceType
from backend.scoring.models import (
    ClaimCredibilityScore,
    DocumentCredibilityScore,
    ScoreComponent,
    ScoreFactor,
    ScorePenalty,
)
from backend.api.schemas import ScoreContribution
from backend.sources.models import (
    AttributionSignal,
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


def make_article() -> NormalizedArticle:
    return NormalizedArticle(
        source_type="text",
        original_input="The ministry approved a Rs 500 crore project.",
        body="The ministry approved a Rs 500 crore project.",
        title="Ministry approves project",
        publisher="Test Publisher",
        domain="testpublisher.example",
        url=None,
        extraction_method="direct_text",
    )


def make_claim(claim_id="c1", text="The ministry approved a Rs 500 crore project.",
               importance=ClaimImportance.HIGH) -> Claim:
    return Claim(
        claim_id=claim_id,
        original_text=text,
        normalized_text=text.lower(),
        claim_type=ClaimType.ANNOUNCEMENT,
        importance=importance,
        source_sentence=text,
    )


def make_evidence(evidence_id="evidence_003", claim_id="c1",
                  url="https://example.gov.in/news/1",
                  publisher="Official Source", domain="example.gov.in") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        claim_id=claim_id,
        title=f"Title for {evidence_id}",
        url=url,
        publisher=publisher,
        domain=domain,
        snippet=f"Snippet for {evidence_id} describing the ministry project approval.",
        source_type=SourceType.NEWS,
        provider="test_provider",
        query_used="ministry project",
    )


def make_source_analysis(evidence_id="evidence_003") -> SourceAnalysis:
    return SourceAnalysis(
        evidence_id=evidence_id,
        domain="example.gov.in",
        publisher="Official Source",
        source_type="NEWS",
        source_category=SourceCategory.GOVERNMENT,
        reliability_score=84,
        reliability_label=ReliabilityLabel.HIGH,
        transparency=TransparencyLevel.HIGH,
        attribution=AttributionSignal(present=True, has_quotes=True),
        primary_reporting=PrimaryReportingSignal(present=True, signals=["official_statement"]),
        metadata_quality=MetadataQuality(
            score=0.9, has_title=True, has_publisher=True,
            has_author=True, has_published_at=True,
            has_canonical_url=True, has_content=True,
        ),
        source_age=SourceAge.RECENT,
        signals=["official_domain"],
        limitations=[],
    )


def make_comparison(claim_id="c1", stance=EvidenceStance.SUPPORTING,
                    evidence_id="evidence_003") -> ClaimEvidenceComparisonResult:
    comp = EvidenceComparison(
        evidence_id=evidence_id,
        claim_id=claim_id,
        stance=stance,
        confidence=0.9,
        relevance=0.9,
        reasoning="Grounded in snippet text.",
    )
    counts = {"supporting": 0, "contradicting": 0, "neutral": 0, "insufficient": 0}
    if stance == EvidenceStance.SUPPORTING:
        counts["supporting"] = 1
    elif stance == EvidenceStance.CONTRADICTING:
        counts["contradicting"] = 1
    elif stance == EvidenceStance.NEUTRAL:
        counts["neutral"] = 1
    else:
        counts["insufficient"] = 1
    return ClaimEvidenceComparisonResult(
        claim_id=claim_id,
        comparisons=[comp],
        supporting_count=counts["supporting"],
        contradicting_count=counts["contradicting"],
        neutral_count=counts["neutral"],
        insufficient_count=counts["insufficient"],
        summary="stance summary",
    )


def make_independence(claim_id="c1", independent_count=1) -> ClaimIndependenceResult:
    return ClaimIndependenceResult(
        claim_id=claim_id,
        total_evidence_count=1,
        independent_source_count=independent_count,
        clusters=[
            EvidenceCluster(
                cluster_id="cluster_1",
                evidence_ids=["evidence_003"],
                cluster_type=ClusterType.INDEPENDENT,
                representative_evidence_id="evidence_003",
                independence_status=IndependenceStatus.LIKELY_INDEPENDENT,
                confidence=0.9,
            )
        ],
        relationships=[],
        analyses=[
            IndependenceAnalysis(
                evidence_id="evidence_003",
                cluster_id="cluster_1",
                independence_status=IndependenceStatus.LIKELY_INDEPENDENT,
                independence_confidence=0.9,
            )
        ],
    )


def make_claim_score(claim_id="c1", score=76, classification="Mostly Supported") -> ClaimCredibilityScore:
    return ClaimCredibilityScore(
        claim_id=claim_id,
        claim_text="The ministry approved a Rs 500 crore project.",
        score=score,
        classification=classification,
        is_insufficient_evidence=score is None,
        total_before_penalties=float(score or 0),
        penalties_total=0.0,
        final_score_raw=float(score or 0),
        components=[
            ScoreComponent(
                factor=ScoreFactor.EVIDENCE_AGREEMENT,
                label="Evidence Agreement",
                raw_score=0.72,
                weight=0.30,
                weighted_contribution=21.6,
                explanation="Independent evidence largely agrees.",
                evidence_ids=["evidence_003"],
            )
        ],
        penalties=[],
        score_breakdown=[
            ScoreContribution(
                factor="evidence_agreement",
                label="Evidence Agreement",
                contribution=21.6,
                detail="Independent evidence largely agrees.",
            )
        ],
        summary="Mostly supported summary.",
        limitations=[],
        methodology_version="v1.0",
    )


def make_ai_reasoning() -> AIReasoningResult:
    return AIReasoningResult(
        summary="Evidence largely supports the approval.",
        supporting_findings=[],
        contradicting_findings=[],
        verification_gaps=["The primary project document was not retrieved."],
        ai_used=False,
        fallback_used=True,
        provider=None,
        model=None,
    )


def make_doc_score(score=76, classification="Mostly Supported",
                   claim_scores=None) -> DocumentCredibilityScore:
    return DocumentCredibilityScore(
        overall_score=score,
        overall_classification=classification,
        claim_scores=claim_scores or [],
        summary="Document summary.",
        methodology_version="v1.0",
    )


@pytest.fixture
def report_bundle():
    article = make_article()
    claim = make_claim()
    ev = make_evidence()
    return {
        "article": article,
        "claim": claim,
        "evidence": [ev],
        "source_analyses": [make_source_analysis()],
        "independence": make_independence(),
        "comparison": make_comparison(),
        "claim_score": make_claim_score(),
        "ai": make_ai_reasoning(),
        "doc": make_doc_score(claim_scores=[make_claim_score()]),
    }
