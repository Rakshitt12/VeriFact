"""Unit tests for Part 9 scoring models."""

import pytest
from pydantic import ValidationError

from backend.api.schemas import ClassificationLabel, ScoreContribution
from backend.scoring.models import (
    ClaimCredibilityScore,
    DocumentCredibilityScore,
    ScoreComponent,
    ScoreFactor,
    ScorePenalty,
)


def test_score_factor_enumeration():
    """Verify all 6 core factors exist in ScoreFactor enum."""
    assert ScoreFactor.EVIDENCE_AGREEMENT == "evidence_agreement"
    assert ScoreFactor.SOURCE_QUALITY == "source_quality"
    assert ScoreFactor.INDEPENDENT_SOURCES == "independent_sources"
    assert ScoreFactor.FACT_CHECKS == "fact_checks"
    assert ScoreFactor.OFFICIAL_EVIDENCE == "official_evidence"
    assert ScoreFactor.TRANSPARENCY == "transparency"


def test_score_component_validation():
    """Verify ScoreComponent validation constraints."""
    comp = ScoreComponent(
        factor=ScoreFactor.EVIDENCE_AGREEMENT,
        label="Evidence Agreement",
        raw_score=0.85,
        weight=0.30,
        weighted_contribution=25.5,
        explanation="Strong corroboration across independent clusters.",
        evidence_ids=["ev_1", "ev_2"],
    )
    assert comp.factor == ScoreFactor.EVIDENCE_AGREEMENT
    assert comp.raw_score == 0.85
    assert comp.weighted_contribution == 25.5
    assert len(comp.evidence_ids) == 2

    # raw_score out of bounds [0.0, 1.0]
    with pytest.raises(ValidationError):
        ScoreComponent(
            factor=ScoreFactor.EVIDENCE_AGREEMENT,
            label="Invalid",
            raw_score=1.5,
            weight=0.30,
            weighted_contribution=45.0,
            explanation="Invalid",
        )


def test_score_penalty_model():
    """Verify ScorePenalty properties."""
    penalty = ScorePenalty(
        penalty_type="numeric_discrepancy",
        amount=20.0,
        explanation="Critical variance in financial figures",
        evidence_ids=["ev_disc_1"],
    )
    assert penalty.penalty_type == "numeric_discrepancy"
    assert penalty.amount == 20.0
    assert len(penalty.evidence_ids) == 1


def test_claim_credibility_score_model():
    """Verify ClaimCredibilityScore initialization."""
    claim_score = ClaimCredibilityScore(
        claim_id="cl_001",
        claim_text="Inflation dropped to 3% in August.",
        score=82,
        classification=ClassificationLabel.MOSTLY_SUPPORTED.value,
        is_insufficient_evidence=False,
        total_before_penalties=82.0,
        penalties_total=0.0,
        final_score_raw=82.0,
        components=[],
        penalties=[],
        score_breakdown=[],
        summary="Claim evaluated as mostly supported.",
        limitations=[],
    )
    assert claim_score.claim_id == "cl_001"
    assert claim_score.score == 82
    assert claim_score.classification == "Mostly Supported"
    assert not claim_score.is_insufficient_evidence


def test_claim_credibility_score_insufficient():
    """Verify ClaimCredibilityScore with None score when evidence is insufficient."""
    claim_score = ClaimCredibilityScore(
        claim_id="cl_002",
        claim_text="Unverifiable rumor statement.",
        score=None,
        classification=ClassificationLabel.INSUFFICIENT_EVIDENCE.value,
        is_insufficient_evidence=True,
        total_before_penalties=0.0,
        penalties_total=0.0,
        final_score_raw=0.0,
    )
    assert claim_score.score is None
    assert claim_score.classification == "INSUFFICIENT EVIDENCE"
    assert claim_score.is_insufficient_evidence


def test_document_credibility_score_model():
    """Verify DocumentCredibilityScore holds aggregated metrics."""
    doc_score = DocumentCredibilityScore(
        overall_score=85,
        overall_classification=ClassificationLabel.MOSTLY_SUPPORTED.value,
        claim_scores=[],
        summary="Document contains corroborated assertions.",
    )
    assert doc_score.overall_score == 85
    assert doc_score.overall_classification == "Mostly Supported"
