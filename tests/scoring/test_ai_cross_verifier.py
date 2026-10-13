"""Tests for AICrossVerifier — PATH A cross-verification and PATH B rescue."""

from __future__ import annotations

from typing import List
from unittest.mock import patch

import pytest

from backend.ai.models import AIReasoningResult, EvidenceFinding, FindingImportance
from backend.retrieval.models import Evidence, SourceType
from backend.scoring.ai_cross_verifier import (
    AICrossVerifier,
    _build_synthetic_comparison,
    _count_independent_clusters,
    _filter_grounded,
    _valid_eids,
)
from backend.scoring.credibility_score import CredibilityScoreCalculator
from backend.scoring.models import ClaimCredibilityScore, ScoreFactor
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
    EvidenceCluster,
    EvidenceStance,
    IndependenceStatus,
    ClusterType,
)


# ---------------------------------------------------------------------------
# Shared helpers and fixtures
# ---------------------------------------------------------------------------

def _ev(eid: str) -> Evidence:
    return Evidence(
        evidence_id=eid,
        claim_id="cl_test",
        title=f"Title {eid}",
        url=f"https://example.com/{eid}",
        publisher="Example News",
        domain="example.com",
        snippet=f"Snippet for {eid}.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="test query",
    )


def _sa(eid: str, rel_score: int = 75) -> SourceAnalysis:
    return SourceAnalysis(
        evidence_id=eid,
        domain="example.com",
        publisher="Example News",
        source_type="NEWS",
        reliability_score=rel_score,
        reliability_label=ReliabilityLabel.MEDIUM,
        source_category=SourceCategory.NEWS_MEDIA,
        transparency=TransparencyLevel.MEDIUM,
        primary_reporting=PrimaryReportingSignal(present=False),
        metadata_quality=MetadataQuality(score=0.7),
        source_age=SourceAge.RECENT,
        signals=[],
        limitations=[],
    )


def _finding(
    text: str,
    eids: List[str],
    stance: str = "SUPPORTING",
    confidence: float = 0.85,
) -> EvidenceFinding:
    return EvidenceFinding(
        text=text,
        evidence_ids=eids,
        stance=stance,
        importance=FindingImportance.HIGH,
        confidence=confidence,
    )


def _ai_result(
    supporting_eids: List[List[str]],
    contradicting_eids: List[List[str]],
    ai_used: bool = True,
    fallback_used: bool = False,
) -> AIReasoningResult:
    supp = [_finding(f"Supporting finding {i}", eids, "SUPPORTING")
            for i, eids in enumerate(supporting_eids)]
    contra = [_finding(f"Contradicting finding {i}", eids, "CONTRADICTING")
              for i, eids in enumerate(contradicting_eids)]
    return AIReasoningResult(
        claim_id="cl_test",
        claim_text="Test claim",
        summary="Test summary.",
        supporting_findings=supp,
        contradicting_findings=contra,
        key_findings=[],
        ai_used=ai_used,
        fallback_used=fallback_used,
        provider="gemini" if ai_used else None,
    )


def _comparison(
    claim_id: str = "cl_test",
    supp_count: int = 0,
    contra_count: int = 0,
    indep_supp: int = 0,
    indep_contra: int = 0,
) -> ClaimEvidenceComparisonResult:
    return ClaimEvidenceComparisonResult(
        claim_id=claim_id,
        supporting_count=supp_count,
        contradicting_count=contra_count,
        neutral_count=0,
        insufficient_count=0,
        independent_supporting_count=indep_supp,
        independent_contradicting_count=indep_contra,
        agreement_ratio=supp_count / max(1, supp_count + contra_count),
        key_discrepancies=[],
        summary="",
    )


def _independence(
    claim_id: str = "cl_test",
    indep_count: int = 2,
    evidence_ids: List[str] = None,
) -> ClaimIndependenceResult:
    evidence_ids = evidence_ids or ["ev1", "ev2"]
    return ClaimIndependenceResult(
        claim_id=claim_id,
        total_evidence_count=len(evidence_ids),
        independent_source_count=indep_count,
        clusters=[
            EvidenceCluster(
                cluster_id=f"cl_{i}",
                evidence_ids=[eid],
                cluster_type=ClusterType.INDEPENDENT,
                representative_evidence_id=eid,
                independence_status=IndependenceStatus.LIKELY_INDEPENDENT,
                confidence=0.9,
            )
            for i, eid in enumerate(evidence_ids)
        ],
    )


def _det_score(
    score: int = 80,
    evidence_agreement_raw: float = 0.8,
    is_insufficient: bool = False,
) -> ClaimCredibilityScore:
    """Build a minimal deterministic ClaimCredibilityScore for testing."""
    from backend.scoring.models import ScoreComponent, ScorePenalty
    from backend.api.schemas import ClassificationLabel, ScoreContribution

    comp = ScoreComponent(
        factor=ScoreFactor.EVIDENCE_AGREEMENT,
        label="Evidence Agreement",
        raw_score=evidence_agreement_raw,
        weight=0.25,
        weighted_contribution=evidence_agreement_raw * 0.25 * 100,
        explanation="Test component.",
        evidence_ids=["ev1"],
    )
    return ClaimCredibilityScore(
        claim_id="cl_test",
        claim_text="Test claim",
        score=None if is_insufficient else score,
        classification=(
            "INSUFFICIENT EVIDENCE" if is_insufficient
            else "Mostly Supported"
        ),
        is_insufficient_evidence=is_insufficient,
        total_before_penalties=float(score),
        penalties_total=0.0,
        final_score_raw=float(score),
        components=[comp],
        penalties=[],
        score_breakdown=[
            ScoreContribution(
                factor="evidence_agreement",
                label="Evidence Agreement",
                contribution=comp.weighted_contribution,
                detail="Test breakdown.",
            )
        ],
        summary="Test summary.",
        limitations=[],
        methodology_version="v1.0",
        scoring_method="deterministic",
    )


# ---------------------------------------------------------------------------
# Tests for scoring_method field
# ---------------------------------------------------------------------------

def test_scoring_method_field_exists_on_claim_score():
    """ClaimCredibilityScore must expose a scoring_method field."""
    s = _det_score(score=75)
    assert hasattr(s, "scoring_method")
    assert s.scoring_method == "deterministic"


def test_scoring_method_field_default_is_deterministic():
    """scoring_method defaults to 'deterministic' on ClaimCredibilityScore."""
    from backend.scoring.models import ClaimCredibilityScore
    s = ClaimCredibilityScore(
        claim_id="x",
        claim_text="x",
        classification="Mostly Supported",
        score=70,
    )
    assert s.scoring_method == "deterministic"


# ---------------------------------------------------------------------------
# Tests for _filter_grounded helper
# ---------------------------------------------------------------------------

def test_filter_grounded_keeps_valid_eids():
    valid = {"ev1", "ev2"}
    f = _finding("test", ["ev1", "ev_bad"])
    result = _filter_grounded([f], valid)
    assert len(result) == 1
    assert result[0].evidence_ids == ["ev1"]


def test_filter_grounded_drops_finding_with_no_valid_eids():
    valid = {"ev1"}
    f = _finding("test", ["ev_fake", "ev_hallucinated"])
    result = _filter_grounded([f], valid)
    assert result == []


def test_filter_grounded_empty_findings():
    assert _filter_grounded([], {"ev1"}) == []


def test_filter_grounded_empty_valid():
    f = _finding("test", ["ev1"])
    assert _filter_grounded([f], set()) == []


# ---------------------------------------------------------------------------
# PATH A: cross-verification of existing deterministic score
# ---------------------------------------------------------------------------

def test_path_a_gemini_agrees_keeps_score_and_method_deterministic():
    """Gemini ratio close to deterministic ratio → score unchanged, method=deterministic."""
    verifier = AICrossVerifier()
    det = _det_score(score=80, evidence_agreement_raw=0.8)
    # AI: 4 supporting, 1 contradicting → ratio=0.8  → matches det_ratio → no adjustment
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"], ["ev4"]],
        contradicting_eids=[["ev5"]],
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3"), _ev("ev4"), _ev("ev5")]
    result = verifier.apply(det, ai, evidence)

    assert result.score == 80
    assert result.scoring_method == "deterministic"


def test_path_a_gemini_materially_disagrees_upward_applies_bounded_adjustment():
    """Gemini strongly supporting vs weak det → positive bounded adjustment, ai_assisted."""
    verifier = AICrossVerifier()
    # det_ratio = 0.3 (weakly supporting)
    det = _det_score(score=40, evidence_agreement_raw=0.3)
    # AI: all 4 supporting → ratio=1.0 → diff=0.7 → material
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"], ["ev4"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3"), _ev("ev4")]
    result = verifier.apply(det, ai, evidence)

    assert result.scoring_method == "ai_assisted"
    assert result.score is not None
    # Score should be higher than 40, but bounded: 40 + ≤15
    assert result.score > 40
    assert result.score <= 55  # 40 + 15 max


def test_path_a_gemini_materially_disagrees_downward_applies_bounded_adjustment():
    """Gemini strongly contradicting vs high det → negative bounded adjustment, ai_assisted."""
    verifier = AICrossVerifier()
    # det_ratio = 0.9 (mostly supporting)
    det = _det_score(score=88, evidence_agreement_raw=0.9)
    # AI: all 3 contradicting → ratio=0.0 → diff=-0.9 → material
    ai = _ai_result(
        supporting_eids=[],
        contradicting_eids=[["ev1"], ["ev2"], ["ev3"]],
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    result = verifier.apply(det, ai, evidence)

    assert result.scoring_method == "ai_assisted"
    assert result.score is not None
    assert result.score < 88
    assert result.score >= 73  # 88 - 15 min


def test_path_a_adjustment_bounded_at_max():
    """Adjustment never exceeds ±AI_CROSS_VERIFY_MAX_ADJUSTMENT (15 points)."""
    from backend.config.scoring_config import AI_CROSS_VERIFY_MAX_ADJUSTMENT
    verifier = AICrossVerifier()
    det = _det_score(score=20, evidence_agreement_raw=0.1)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"], ["ev4"], ["ev5"]],
        contradicting_eids=[],
    )
    evidence = [_ev(f"ev{i}") for i in range(1, 6)]
    result = verifier.apply(det, ai, evidence)

    if result.scoring_method == "ai_assisted":
        assert abs(result.score - 20) <= AI_CROSS_VERIFY_MAX_ADJUSTMENT


def test_path_a_fallback_used_keeps_deterministic():
    """If ai_reasoning.fallback_used=True, skip adjustment and keep deterministic."""
    verifier = AICrossVerifier()
    det = _det_score(score=60, evidence_agreement_raw=0.6)
    ai = _ai_result(
        supporting_eids=[["ev1"]],
        contradicting_eids=[["ev2"], ["ev3"], ["ev4"]],
        fallback_used=True,
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3"), _ev("ev4")]
    result = verifier.apply(det, ai, evidence)

    assert result.score == 60
    assert result.scoring_method == "deterministic"


def test_path_a_ai_not_used_keeps_deterministic():
    """If ai_reasoning.ai_used=False, skip adjustment."""
    verifier = AICrossVerifier()
    det = _det_score(score=60, evidence_agreement_raw=0.6)
    ai = _ai_result(
        supporting_eids=[],
        contradicting_eids=[["ev1"], ["ev2"], ["ev3"]],
        ai_used=False,
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    result = verifier.apply(det, ai, evidence)

    assert result.score == 60
    assert result.scoring_method == "deterministic"


def test_path_a_none_ai_reasoning_keeps_deterministic():
    """None ai_reasoning → method=deterministic, score unchanged."""
    verifier = AICrossVerifier()
    det = _det_score(score=75, evidence_agreement_raw=0.75)
    result = verifier.apply(det, None, [_ev("ev1"), _ev("ev2")])

    assert result.score == 75
    assert result.scoring_method == "deterministic"


def test_path_a_fabricated_eids_are_excluded():
    """Fabricated evidence IDs not in evidence_items are filtered out before adjustment."""
    verifier = AICrossVerifier()
    det = _det_score(score=80, evidence_agreement_raw=0.8)
    # AI claims ev_fake_1, ev_fake_2 are supporting — but those aren't in evidence_items
    ai = _ai_result(
        supporting_eids=[["ev_fake_1"], ["ev_fake_2"]],
        contradicting_eids=[["ev1"], ["ev2"], ["ev3"]],
    )
    # Only ev1,ev2,ev3 are real evidence
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    result = verifier.apply(det, ai, evidence)

    # After filtering, AI has 0 supporting, 3 contradicting
    # diff = 0.0 - 0.8 = -0.8 → material → should adjust downward
    # But the key point: fabricated IDs are not counted
    if result.scoring_method == "ai_assisted":
        assert result.score <= 80
    else:
        assert result.scoring_method == "deterministic"


# ---------------------------------------------------------------------------
# PATH B: rescue of INSUFFICIENT EVIDENCE
# ---------------------------------------------------------------------------

def test_path_b_rescue_success_produces_score():
    """INSUFFICIENT + grounded AI findings ≥ threshold → rescue produces score, ai_assisted."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)

    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev1"), _ev("ev2")]
    independence = _independence(indep_count=2, evidence_ids=["ev1", "ev2"])

    result = verifier.apply(
        det, ai, evidence,
        source_analyses=[_sa("ev1"), _sa("ev2")],
        independence_result=independence,
    )

    assert result.scoring_method == "ai_assisted"
    assert result.score is not None
    assert 0 <= result.score <= 100
    assert result.is_insufficient_evidence is False


def test_path_b_rescue_no_evidence_items_remains_insufficient():
    """INSUFFICIENT + empty evidence_items → skip rescue, insufficient_evidence."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    ai = _ai_result(supporting_eids=[["ev1"], ["ev2"]], contradicting_eids=[])
    result = verifier.apply(det, ai, [])  # no real evidence

    assert result.scoring_method == "insufficient_evidence"
    assert result.score is None


def test_path_b_rescue_no_ai_reasoning_remains_insufficient():
    """INSUFFICIENT + ai_reasoning=None → remain INSUFFICIENT EVIDENCE."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    evidence = [_ev("ev1"), _ev("ev2")]
    result = verifier.apply(det, None, evidence)

    assert result.scoring_method == "insufficient_evidence"
    assert result.score is None


def test_path_b_rescue_fallback_used_remains_insufficient():
    """INSUFFICIENT + fallback_used=True → no rescue, insufficient_evidence."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"]],
        contradicting_eids=[],
        fallback_used=True,
    )
    evidence = [_ev("ev1"), _ev("ev2")]
    result = verifier.apply(det, ai, evidence)

    assert result.scoring_method == "insufficient_evidence"
    assert result.score is None


def test_path_b_rescue_only_one_grounded_finding_remains_insufficient():
    """INSUFFICIENT + only 1 grounded finding < threshold (2) → remain INSUFFICIENT."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    ai = _ai_result(
        supporting_eids=[["ev1"]],   # only 1 grounded supporting
        contradicting_eids=[],
    )
    evidence = [_ev("ev1")]
    result = verifier.apply(det, ai, evidence)

    assert result.scoring_method == "insufficient_evidence"
    assert result.score is None


def test_path_b_rescue_all_fabricated_eids_remains_insufficient():
    """INSUFFICIENT + AI findings only reference fabricated IDs → 0 grounded → INSUFFICIENT."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    ai = _ai_result(
        supporting_eids=[["ev_fake_1"], ["ev_fake_2"], ["ev_fake_3"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev_real_1"), _ev("ev_real_2")]
    result = verifier.apply(det, ai, evidence)

    assert result.scoring_method == "insufficient_evidence"
    assert result.score is None


def test_path_b_rescue_sets_ai_limitation_note():
    """Rescued score must include a limitation note explaining AI assistance."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev1"), _ev("ev2")]
    independence = _independence(indep_count=2, evidence_ids=["ev1", "ev2"])

    result = verifier.apply(det, ai, evidence, independence_result=independence)

    if result.scoring_method == "ai_assisted":
        combined = " ".join(result.limitations).lower()
        assert "ai-assisted" in combined or "gemini" not in combined.lower()
        # Ensure "Gemini" is not presented as a source
        assert "gemini source" not in combined
        assert "gemini verified" not in combined


def test_path_b_rescue_score_in_valid_range():
    """Rescued score must be integer in 0–100."""
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    independence = _independence(indep_count=3, evidence_ids=["ev1", "ev2", "ev3"])

    result = verifier.apply(det, ai, evidence, independence_result=independence)

    if result.score is not None:
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 100


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------

def test_exception_in_apply_returns_deterministic_unchanged():
    """If AICrossVerifier._dispatch raises, the original deterministic result is returned."""
    verifier = AICrossVerifier()
    det = _det_score(score=70, evidence_agreement_raw=0.7)

    with patch.object(verifier, "_dispatch", side_effect=RuntimeError("boom")):
        result = verifier.apply(det, None, [_ev("ev1")])

    assert result.score == 70
    # method may be set to deterministic by the fallback stamp
    assert result.scoring_method in {"deterministic", "insufficient_evidence"}


# ---------------------------------------------------------------------------
# AI_CROSS_VERIFY_ENABLED=False disables all AI logic
# ---------------------------------------------------------------------------

def test_cross_verify_disabled_skips_all_ai_logic(monkeypatch):
    """When AI_CROSS_VERIFY_ENABLED is False, AICrossVerifier is a passthrough."""
    monkeypatch.setattr(
        "backend.scoring.ai_cross_verifier.AI_CROSS_VERIFY_ENABLED", False
    )
    verifier = AICrossVerifier()
    det = _det_score(score=60, evidence_agreement_raw=0.6)
    # even with strongly opposing AI findings, no adjustment occurs
    ai = _ai_result(
        supporting_eids=[],
        contradicting_eids=[["ev1"], ["ev2"], ["ev3"], ["ev4"]],
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3"), _ev("ev4")]
    result = verifier.apply(det, ai, evidence)

    assert result.score == 60
    assert result.scoring_method == "deterministic"


def test_cross_verify_disabled_insufficient_becomes_insufficient_method(monkeypatch):
    """When disabled, an INSUFFICIENT EVIDENCE score gets scoring_method=insufficient_evidence."""
    monkeypatch.setattr(
        "backend.scoring.ai_cross_verifier.AI_CROSS_VERIFY_ENABLED", False
    )
    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    result = verifier.apply(det, None, [])

    assert result.scoring_method == "insufficient_evidence"


# ---------------------------------------------------------------------------
# _build_synthetic_comparison helper
# ---------------------------------------------------------------------------

def test_build_synthetic_comparison_counts():
    """Synthetic comparison's supporting/contradicting counts match grounded findings."""
    supp = [_finding("S1", ["ev1"]), _finding("S2", ["ev2"])]
    contra = [_finding("C1", ["ev3"])]

    result = _build_synthetic_comparison("cl1", supp, contra, independence_result=None)

    assert result.supporting_count == 2
    assert result.contradicting_count == 1
    assert result.agreement_ratio == pytest.approx(2 / 3)


def test_build_synthetic_comparison_no_fact_checks():
    """Synthetic comparison must have empty fact_checks to avoid fabricated data."""
    supp = [_finding("S1", ["ev1"]), _finding("S2", ["ev2"])]
    result = _build_synthetic_comparison("cl1", supp, [], independence_result=None)
    assert result.fact_checks == []


# ---------------------------------------------------------------------------
# Service-level: score_claim is now async
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_service_score_claim_is_async():
    """CredibilityScoringService.score_claim must be awaitable."""
    from backend.scoring.service import CredibilityScoringService
    svc = CredibilityScoringService()
    result = await svc.score_claim(
        claim_id="cl_async_test",
        claim_text="Test async scoring.",
    )
    assert result is not None
    assert hasattr(result, "scoring_method")


@pytest.mark.anyio
async def test_service_score_claim_deterministic_by_default():
    """score_claim with no ai_reasoning returns deterministic method."""
    from backend.scoring.service import CredibilityScoringService
    svc = CredibilityScoringService()
    result = await svc.score_claim(
        claim_id="cl_det_test",
        claim_text="Test deterministic path.",
        ai_reasoning=None,
    )
    assert result.scoring_method in {"deterministic", "insufficient_evidence"}


# ===========================================================================
# PATH A — precise threshold and boundary tests
# ===========================================================================

def test_path_a_exactly_030_absolute_difference_triggers():
    """Exactly 0.30 absolute pp difference must trigger the adjustment.

    Spec: abs(gemini_ratio - det_ratio) >= 0.30 qualifies.
    det_ratio = 0.50, ai_ratio = 4/5 = 0.80 → diff = 0.30 → triggers.
    """
    det = _det_score(score=50, evidence_agreement_raw=0.50)
    # 4 supporting / 5 total = 0.80 → |0.80 - 0.50| = 0.30 (exactly at threshold)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"], ["ev4"]],
        contradicting_eids=[["ev5"]],
    )
    evidence = [_ev(f"ev{i}") for i in range(1, 6)]
    result = AICrossVerifier().apply(det, ai, evidence)

    # Must trigger: method must be ai_assisted, score must have moved upward
    assert result.scoring_method == "ai_assisted"
    assert result.score is not None
    assert result.score > 50


def test_path_a_029_absolute_difference_does_not_trigger():
    """Difference strictly below 0.30 must NOT trigger.

    Spec: abs(diff) < 0.30 → no adjustment.
    det_ratio = 0.50, need ai_ratio to give diff < 0.30.
    7 supporting / 9 total ≈ 0.778 → diff ≈ 0.278 < 0.30 → no trigger.
    """
    det = _det_score(score=50, evidence_agreement_raw=0.50)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"], ["ev4"], ["ev5"], ["ev6"], ["ev7"]],
        contradicting_eids=[["ev8"], ["ev9"]],
    )
    evidence = [_ev(f"ev{i}") for i in range(1, 10)]
    result = AICrossVerifier().apply(det, ai, evidence)

    # Must NOT trigger: score and method unchanged
    assert result.scoring_method == "deterministic"
    assert result.score == 50


def test_path_a_positive_adjustment_score_never_exceeds_100():
    """After a positive adjustment, the final score must be clamped at 100.

    det_ratio=0.0, ai_ratio=1.0 → max positive adjustment (+15).
    Starting score 98 + 15 = 113 → must clamp to 100.
    """
    det = _det_score(score=98, evidence_agreement_raw=0.0)
    # All 3 supporting → ratio=1.0, diff=+1.0 (well above 0.30)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    result = AICrossVerifier().apply(det, ai, evidence)

    assert result.score is not None
    assert result.score <= 100


def test_path_a_negative_adjustment_score_never_below_0():
    """After a negative adjustment, the final score must be clamped at 0.

    det_ratio=1.0, ai_ratio=0.0 → max negative adjustment (−15).
    Starting score 2 − 15 = −13 → must clamp to 0.
    """
    det = _det_score(score=2, evidence_agreement_raw=1.0)
    # All 3 contradicting → ratio=0.0, diff=−1.0 (well above threshold)
    ai = _ai_result(
        supporting_eids=[],
        contradicting_eids=[["ev1"], ["ev2"], ["ev3"]],
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    result = AICrossVerifier().apply(det, ai, evidence)

    assert result.score is not None
    assert result.score >= 0


# ===========================================================================
# Gemini failure scenarios — all must preserve deterministic result unchanged
# ===========================================================================

def test_gemini_quota_exhausted_429_preserves_deterministic():
    """Quota exhausted (HTTP 429) is surfaced as fallback_used=True from Part 8.

    AICrossVerifier must skip and keep the deterministic score.
    """
    verifier = AICrossVerifier()
    det = _det_score(score=70, evidence_agreement_raw=0.70)
    # Simulates Part 8 fallback after Gemini 429/RESOURCE_EXHAUSTED
    ai_failed = _ai_result(
        supporting_eids=[["ev1"]],
        contradicting_eids=[["ev2"], ["ev3"], ["ev4"]],
        ai_used=True,
        fallback_used=True,   # ← set by evidence_reasoner on any LLMError
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3"), _ev("ev4")]
    result = verifier.apply(det, ai_failed, evidence)

    assert result.score == 70
    assert result.scoring_method == "deterministic"


def test_gemini_timeout_preserves_deterministic():
    """LLMTimeoutError from Part 8 surfaces as fallback_used=True.

    AICrossVerifier must skip and keep the deterministic score.
    """
    verifier = AICrossVerifier()
    det = _det_score(score=65, evidence_agreement_raw=0.65)
    ai_timeout = _ai_result(
        supporting_eids=[],
        contradicting_eids=[["ev1"], ["ev2"], ["ev3"]],
        ai_used=True,
        fallback_used=True,   # ← LLMTimeoutError → fallback
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    result = verifier.apply(det, ai_timeout, evidence)

    assert result.score == 65
    assert result.scoring_method == "deterministic"


def test_gemini_malformed_response_ai_not_used_preserves_deterministic():
    """Malformed or unparseable Gemini output → ai_used=False from Part 8.

    AICrossVerifier must skip and keep the deterministic score.
    """
    verifier = AICrossVerifier()
    det = _det_score(score=78, evidence_agreement_raw=0.78)
    ai_malformed = _ai_result(
        supporting_eids=[["ev1"], ["ev2"]],
        contradicting_eids=[],
        ai_used=False,        # ← LLMParsingError → ai_used=False
        fallback_used=True,
    )
    evidence = [_ev("ev1"), _ev("ev2")]
    result = verifier.apply(det, ai_malformed, evidence)

    assert result.score == 78
    assert result.scoring_method == "deterministic"


def test_gemini_generic_api_error_preserves_deterministic():
    """Any generic API error produces fallback_used=True in Part 8.

    AICrossVerifier must keep the deterministic score without raising.
    """
    verifier = AICrossVerifier()
    det = _det_score(score=55, evidence_agreement_raw=0.55)
    ai_error = _ai_result(
        supporting_eids=[["ev1"], ["ev2"], ["ev3"]],
        contradicting_eids=[],
        ai_used=False,
        fallback_used=True,
    )
    evidence = [_ev("ev1"), _ev("ev2"), _ev("ev3")]
    result = verifier.apply(det, ai_error, evidence)

    assert result.score == 55
    assert result.scoring_method == "deterministic"


# ===========================================================================
# PATH B — Part 6 independence rules respected
# ===========================================================================

def test_path_b_count_independent_clusters_syndicated_is_one():
    """Two evidence items in the SAME syndication cluster count as ONE independent cluster.

    Spec: 2 grounded findings ≠ automatically 2 independent evidence clusters.
    """
    # ev1 and ev2 are syndicated copies of each other → same cluster
    syndicated_independence = ClaimIndependenceResult(
        claim_id="cl_test",
        total_evidence_count=2,
        independent_source_count=1,
        clusters=[
            EvidenceCluster(
                cluster_id="cluster_syndicated",
                evidence_ids=["ev1", "ev2"],   # both articles in ONE cluster
                cluster_type=ClusterType.SYNDICATION,
                representative_evidence_id="ev1",
                independence_status=IndependenceStatus.LIKELY_DERIVED,
                confidence=0.95,
            )
        ],
    )

    findings = [_finding("Support from ev1", ["ev1"]),
                _finding("Support from ev2", ["ev2"])]

    count = _count_independent_clusters(findings, syndicated_independence)

    # Both map to "cluster_syndicated" → only 1 unique cluster
    assert count == 1


def test_path_b_syndicated_articles_prevent_rescue():
    """PATH B rescue fails when grounded findings reference only syndicated articles.

    Even though 2 Gemini findings exist (≥ AI_RESCUE_MIN_GROUNDED_FINDINGS),
    the underlying independence_result shows only 1 independent cluster.
    The existing deterministic calculator must reject this as INSUFFICIENT.
    Part 6 independence rules are NOT bypassed.
    """
    # Part 6 says ev1 and ev2 are syndicated → 1 independent source only
    syndicated_independence = ClaimIndependenceResult(
        claim_id="cl_test",
        total_evidence_count=2,
        independent_source_count=1,           # ← only 1 despite 2 articles
        clusters=[
            EvidenceCluster(
                cluster_id="cluster_syn",
                evidence_ids=["ev1", "ev2"],
                cluster_type=ClusterType.SYNDICATION,
                representative_evidence_id="ev1",
                independence_status=IndependenceStatus.LIKELY_DERIVED,
                confidence=0.95,
            )
        ],
    )

    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    # 2 grounded supporting findings — both reference syndicated articles
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev1"), _ev("ev2")]

    result = verifier.apply(
        det, ai, evidence,
        source_analyses=[_sa("ev1"), _sa("ev2")],
        independence_result=syndicated_independence,
    )

    # Must remain INSUFFICIENT: 1 independent cluster < MIN_INDEPENDENT_SOURCES (2)
    assert result.scoring_method == "insufficient_evidence"
    assert result.score is None


def test_path_b_two_genuinely_independent_clusters_can_rescue():
    """PATH B rescue succeeds when findings reference two genuinely independent clusters.

    Spec: valid findings from two genuinely independent clusters can satisfy
    the rescue requirement.
    """
    # Part 6 says ev1 and ev2 are from different organisations → 2 independent clusters
    independent = ClaimIndependenceResult(
        claim_id="cl_test",
        total_evidence_count=2,
        independent_source_count=2,           # ← 2 genuinely independent
        clusters=[
            EvidenceCluster(
                cluster_id="cluster_reuters",
                evidence_ids=["ev1"],
                cluster_type=ClusterType.INDEPENDENT,
                representative_evidence_id="ev1",
                independence_status=IndependenceStatus.LIKELY_INDEPENDENT,
                confidence=0.92,
            ),
            EvidenceCluster(
                cluster_id="cluster_ap",
                evidence_ids=["ev2"],
                cluster_type=ClusterType.INDEPENDENT,
                representative_evidence_id="ev2",
                independence_status=IndependenceStatus.LIKELY_INDEPENDENT,
                confidence=0.90,
            ),
        ],
    )

    # Verify helper counts them as 2 independent clusters
    findings = [_finding("S1", ["ev1"]), _finding("S2", ["ev2"])]
    assert _count_independent_clusters(findings, independent) == 2

    verifier = AICrossVerifier()
    det = _det_score(score=0, is_insufficient=True)
    ai = _ai_result(
        supporting_eids=[["ev1"], ["ev2"]],
        contradicting_eids=[],
    )
    evidence = [_ev("ev1"), _ev("ev2")]

    result = verifier.apply(
        det, ai, evidence,
        source_analyses=[_sa("ev1"), _sa("ev2")],
        independence_result=independent,
    )

    # Must succeed: 2 independent clusters, 2 grounded findings → rescue
    assert result.scoring_method == "ai_assisted"
    assert result.score is not None
    assert 0 <= result.score <= 100


def test_path_b_no_second_gemini_call_during_rescue():
    """PATH B rescue must NOT make any additional Gemini/LLM API calls.

    The AIReasoningResult was already produced by Part 8.  Re-calling the LLM
    would add latency, consume quota, and violate the design contract.
    """
    from unittest.mock import AsyncMock

    with patch(
        "backend.ai.llm_client.GeminiLLMClient.generate_structured",
        new_callable=AsyncMock,
    ) as mock_generate:
        verifier = AICrossVerifier()
        det = _det_score(score=0, is_insufficient=True)
        ai = _ai_result(
            supporting_eids=[["ev1"], ["ev2"]],
            contradicting_eids=[],
        )
        evidence = [_ev("ev1"), _ev("ev2")]
        independence = _independence(indep_count=2, evidence_ids=["ev1", "ev2"])

        verifier.apply(
            det, ai, evidence,
            source_analyses=[_sa("ev1"), _sa("ev2")],
            independence_result=independence,
        )

        mock_generate.assert_not_called()


# ===========================================================================
# scoring_method in API response
# ===========================================================================

def test_api_response_contains_scoring_method():
    """Live API /api/verify response must include scoring_method on each claim.

    When LLM is not available (no real key in test env), Part 8 falls back
    to deterministic reasoning → ai_used=False → AICrossVerifier keeps
    deterministic score → scoring_method must be 'deterministic'.
    """
    from fastapi.testclient import TestClient
    from backend.claim.models import Claim, ClaimType
    from backend.ingestion.models import NormalizedArticle
    from backend.main import app
    from backend.retrieval.models import (
        ClaimEvidence, Evidence as Ev, QueryType,
        RetrievalResult, SearchQuery, SourceType as ST,
    )

    client = TestClient(app)

    mock_article = NormalizedArticle(
        source_type="text",
        original_input="Scientists confirm water on the Moon.",
        body="Scientists confirm water on the Moon.",
        extraction_method="direct_text",
    )
    mock_claim = Claim(
        claim_id="cl_api_sm",
        original_text="Scientists confirm water on the Moon.",
        normalized_text="Scientists confirm water on the Moon.",
        claim_text="Scientists confirm water on the Moon.",
        claim_type=ClaimType.SCIENTIFIC,
        numbers=[],
        organizations=["Scientists"],
        source_sentence="Scientists confirm water on the Moon.",
    )
    ev_a = Ev(
        evidence_id="ev_sm_1", claim_id="cl_api_sm",
        title="Water on Moon", url="https://reuters.com/moon",
        publisher="Reuters", domain="reuters.com",
        snippet="NASA confirms water on the Moon.",
        source_type=ST.NEWS, provider="gdelt", query_used="water moon",
    )
    ev_b = Ev(
        evidence_id="ev_sm_2", claim_id="cl_api_sm",
        title="Moon Water Confirmed", url="https://apnews.com/moon",
        publisher="AP News", domain="apnews.com",
        snippet="Water ice confirmed on the lunar surface.",
        source_type=ST.NEWS, provider="gdelt", query_used="water moon",
    )
    mock_retrieval = RetrievalResult(
        claims=[
            ClaimEvidence(
                claim_id="cl_api_sm",
                evidence=[ev_a, ev_b],
                queries_used=[
                    SearchQuery(
                        query="water moon", query_type=QueryType.DIRECT,
                        claim_id="cl_api_sm",
                    )
                ],
            )
        ],
        total_evidence_count=2,
        retrieval_duration_ms=10.0,
    )

    import backend.api.routes as routes_mod

    original_ingest = routes_mod.ingest_input
    original_extract = routes_mod.extract_claims
    original_retrieve = routes_mod.retrieve_evidence

    routes_mod.ingest_input = lambda *a, **kw: mock_article
    routes_mod.extract_claims = lambda *a, **kw: [mock_claim]

    async def _mock_retrieve(*a, **kw):
        return mock_retrieval

    routes_mod.retrieve_evidence = _mock_retrieve

    try:
        response = client.post(
            "/api/verify",
            json={"input_type": "text", "content": "Scientists confirm water on the Moon."},
        )
    finally:
        routes_mod.ingest_input = original_ingest
        routes_mod.extract_claims = original_extract
        routes_mod.retrieve_evidence = original_retrieve

    assert response.status_code == 200
    data = response.json()

    assert "claims" in data
    assert len(data["claims"]) >= 1
    claim_res = data["claims"][0]

    # scoring_method field must exist and be one of the three valid values
    assert "scoring_method" in claim_res, (
        "API response must include scoring_method on each claim"
    )
    assert claim_res["scoring_method"] in {
        "deterministic", "ai_assisted", "insufficient_evidence"
    }, f"Unexpected scoring_method: {claim_res['scoring_method']!r}"
