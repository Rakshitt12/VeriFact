"""Regression tests: empty evidence categories must surface as verification gaps.

A report must never show an empty evidence section alongside "no open gaps".
The absence invariant is enforced on every reasoning result, whether it came
from the LLM (which may return zero gaps) or the deterministic fallback.
"""

import pytest

from backend.ai.evidence_reasoner import EvidenceReasoner
from backend.ai.fallback_reasoner import ensure_evidence_absence_gaps
from backend.ai.models import AIReasoningResult
from backend.claim.models import Claim, ClaimType
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    EvidenceComparison,
    EvidenceStance,
)


def _claim() -> Claim:
    return Claim(
        claim_id="cl_gap",
        original_text="The ministry approved a funding package.",
        normalized_text="The ministry approved a funding package.",
        claim_type=ClaimType.ANNOUNCEMENT,
        source_sentence="The ministry approved a funding package.",
    )


def _bare_result() -> AIReasoningResult:
    # Simulates an LLM output that listed zero gaps.
    return AIReasoningResult(summary="s", verification_gaps=[])


def test_zero_evidence_yields_absence_gap():
    result = ensure_evidence_absence_gaps(
        _bare_result(),
        evidence_items=[],
        comparison_result=ClaimEvidenceComparisonResult(claim_id="cl_gap"),
    )
    assert len(result.verification_gaps) >= 1
    assert any("no relevant external evidence" in g.lower() for g in result.verification_gaps)


def test_zero_supporting_yields_support_gap():
    comparison = ClaimEvidenceComparisonResult(
        claim_id="cl_gap",
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_n",
                claim_id="cl_gap",
                stance=EvidenceStance.NEUTRAL,
                confidence=0.8,
                relevance=0.5,
                reasoning="context only",
            )
        ],
        neutral_count=1,
    )
    result = ensure_evidence_absence_gaps(
        _bare_result(),
        evidence_items=["placeholder-evidence"],
        comparison_result=comparison,
    )
    assert any("no supporting evidence" in g.lower() for g in result.verification_gaps)


def test_supported_claim_gets_no_absence_gap():
    comparison = ClaimEvidenceComparisonResult(
        claim_id="cl_gap",
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_s",
                claim_id="cl_gap",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.9,
                relevance=0.9,
                reasoning="supports",
            )
        ],
        supporting_count=1,
    )
    result = ensure_evidence_absence_gaps(
        _bare_result(),
        evidence_items=["placeholder-evidence"],
        comparison_result=comparison,
    )
    assert result.verification_gaps == []


def test_enforcer_is_idempotent():
    pre = ["No relevant external evidence could be retrieved."]
    result = AIReasoningResult(summary="s", verification_gaps=list(pre))
    out = ensure_evidence_absence_gaps(result, evidence_items=[], comparison_result=None)
    assert out.verification_gaps == pre


@pytest.mark.anyio
async def test_reasoner_empty_evidence_never_reports_no_gaps():
    """End-to-end through the reasoner: zero evidence => non-empty gaps."""
    result = await EvidenceReasoner().reason(
        claim=_claim(),
        evidence_items=[],
        source_analyses=[],
        independence_result=None,
        comparison_result=ClaimEvidenceComparisonResult(claim_id="cl_gap"),
    )
    assert len(result.verification_gaps) >= 1
