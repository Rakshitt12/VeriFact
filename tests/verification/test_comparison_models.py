"""Unit tests for Part 7 evidence comparison and stance detection data models."""

import pytest
from pydantic import ValidationError

from backend.verification.models import (
    AspectMatch,
    AspectType,
    ClaimEvidenceComparisonResult,
    Discrepancy,
    DiscrepancyType,
    EvidenceComparison,
    EvidenceStance,
    FactCheckComparison,
)


def test_evidence_stance_enum():
    """Verify evidence stance enum values adhere to specification."""
    assert EvidenceStance.SUPPORTING.value == "SUPPORTING"
    assert EvidenceStance.CONTRADICTING.value == "CONTRADICTING"
    assert EvidenceStance.NEUTRAL.value == "NEUTRAL"
    assert EvidenceStance.INSUFFICIENT.value == "INSUFFICIENT"
    # Ensure neither TRUE nor FALSE are used as stances
    stances = [s.value for s in EvidenceStance]
    assert "TRUE" not in stances
    assert "FALSE" not in stances


def test_aspect_type_and_match_model():
    """Test AspectType and AspectMatch instantiation and validation."""
    match = AspectMatch(
        aspect_type=AspectType.WHO,
        claim_value="Company A",
        evidence_value="Company A",
        status="SUPPORTED",
    )
    assert match.aspect_type == AspectType.WHO
    assert match.claim_value == "Company A"
    assert match.status == "SUPPORTED"


def test_discrepancy_model():
    """Test Discrepancy model creation and fields."""
    disc = Discrepancy(
        discrepancy_type=DiscrepancyType.NUMERIC,
        aspect="amount_crore",
        claim_value="₹500 crore",
        evidence_value="₹300 crore",
        snippet="...announced a ₹300 crore investment in Gujarat...",
        severity="MAJOR",
    )
    assert disc.discrepancy_type == DiscrepancyType.NUMERIC
    assert disc.severity == "MAJOR"
    assert disc.claim_value == "₹500 crore"
    assert disc.evidence_value == "₹300 crore"


def test_evidence_comparison_validation():
    """Test EvidenceComparison model instantiation and bounds enforcement."""
    comp = EvidenceComparison(
        evidence_id="ev_001",
        claim_id="cl_001",
        stance=EvidenceStance.SUPPORTING,
        confidence=0.88,
        relevance=0.92,
        reasoning="Evidence corroborates all key aspects.",
        supporting_points=["Point 1", "Point 2"],
    )
    assert comp.stance == EvidenceStance.SUPPORTING
    assert comp.confidence == 0.88
    assert comp.relevance == 0.92
    assert len(comp.supporting_points) == 2

    # Verify confidence bounds (0.0 to 1.0)
    with pytest.raises(ValidationError):
        EvidenceComparison(
            evidence_id="ev_001",
            claim_id="cl_001",
            stance=EvidenceStance.SUPPORTING,
            confidence=1.5,  # Out of bounds
            relevance=0.5,
            reasoning="Invalid",
        )


def test_fact_check_comparison_model():
    """Test FactCheckComparison model creation."""
    fc = FactCheckComparison(
        fact_check_id="fc_001",
        claim_id="cl_001",
        verdict_normalized="False",
        raw_rating="Pants on Fire",
        fact_checker="PolitiFact",
        url="https://politifact.com/factcheck/123",
        published_at="2026-09-20",
        stance=EvidenceStance.CONTRADICTING,
        explanation="The statement was thoroughly investigated and found false.",
    )
    assert fc.verdict_normalized == "False"
    assert fc.raw_rating == "Pants on Fire"
    assert fc.stance == EvidenceStance.CONTRADICTING


def test_claim_evidence_comparison_result():
    """Test ClaimEvidenceComparisonResult consolidated container."""
    res = ClaimEvidenceComparisonResult(
        claim_id="cl_001",
        supporting_count=3,
        contradicting_count=1,
        neutral_count=1,
        insufficient_count=0,
        independent_supporting_count=2,
        independent_contradicting_count=1,
        agreement_ratio=0.667,
        summary="2 independent sources corroborate while 1 contradicts.",
    )
    assert res.independent_supporting_count == 2
    assert res.independent_contradicting_count == 1
    assert res.agreement_ratio == 0.667
