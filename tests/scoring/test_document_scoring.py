"""Unit tests for multi-claim document credibility aggregation and importance weighting."""

import pytest

from backend.api.schemas import ClassificationLabel
from backend.claim.models import Claim, ClaimImportance, ClaimType
from backend.scoring.models import ClaimCredibilityScore
from backend.scoring.service import CredibilityScoringService


def _make_claim(cid: str, text: str, importance: ClaimImportance = ClaimImportance.HIGH) -> Claim:
    return Claim(
        claim_id=cid,
        original_text=text,
        normalized_text=text,
        claim_text=text,
        claim_type=ClaimType.EVENT,
        importance=importance,
        source_sentence=text,
    )


def _make_claim_score(cid: str, text: str, score: int | None, classification: str) -> ClaimCredibilityScore:
    return ClaimCredibilityScore(
        claim_id=cid,
        claim_text=text,
        score=score,
        classification=classification,
        is_insufficient_evidence=score is None,
        total_before_penalties=float(score or 0),
        penalties_total=0.0,
        final_score_raw=float(score or 0),
    )


def test_document_scoring_empty():
    """Verify document scoring with no claims."""
    service = CredibilityScoringService()
    doc_res = service.score_document([])
    assert doc_res.overall_score is None
    assert doc_res.overall_classification == "INSUFFICIENT EVIDENCE"


def test_document_scoring_all_insufficient():
    """Verify document scoring when all claims have insufficient evidence."""
    service = CredibilityScoringService()
    cs1 = _make_claim_score("c1", "Claim 1", None, "INSUFFICIENT EVIDENCE")
    cs2 = _make_claim_score("c2", "Claim 2", None, "INSUFFICIENT EVIDENCE")

    doc_res = service.score_document([cs1, cs2])
    assert doc_res.overall_score is None
    assert doc_res.overall_classification == "INSUFFICIENT EVIDENCE"


def test_document_scoring_weighted_aggregation():
    """Verify document scoring applies importance weights properly."""
    service = CredibilityScoringService()

    # c1 is HIGH (weight 1.0) with score 90
    # c2 is LOW (weight 0.4) with score 60
    c1 = _make_claim("c1", "High importance statement", ClaimImportance.HIGH)
    c2 = _make_claim("c2", "Low importance statement", ClaimImportance.LOW)

    cs1 = _make_claim_score("c1", "High importance statement", 90, "Strongly Supported")
    cs2 = _make_claim_score("c2", "Low importance statement", 60, "Mixed / Uncertain")

    doc_res = service.score_document(claim_scores=[cs1, cs2], claims=[c1, c2])

    # Expected: (90 * 1.0 + 60 * 0.4) / (1.0 + 0.4) = (90 + 24) / 1.4 = 114 / 1.4 = 81.43 -> 81
    assert doc_res.overall_score == 81
    assert doc_res.overall_classification == "Mostly Supported"
    assert "81/100" in doc_res.summary
