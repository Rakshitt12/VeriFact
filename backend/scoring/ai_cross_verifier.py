"""AI cross-verification and Gemini rescue for INSUFFICIENT EVIDENCE claims.

Two scoring paths:

PATH A — Deterministic score exists (score ≠ None):
  Gemini's grounded supporting/contradicting findings are compared against
  the deterministic agreement ratio.  If the disagreement is material
  (≥ AI_CROSS_VERIFY_MATERIAL_RATIO_THRESHOLD), a bounded point adjustment
  (≤ ± AI_CROSS_VERIFY_MAX_ADJUSTMENT) is applied.
  scoring_method = "ai_assisted" | "deterministic"

PATH B — INSUFFICIENT EVIDENCE + retrieved evidence exists:
  Gemini's already-validated findings (produced by Part 8 EvidenceReasoner)
  are filtered for grounded evidence_ids.  If enough grounded findings meet
  AI_RESCUE_MIN_GROUNDED_FINDINGS, a synthetic ClaimEvidenceComparisonResult
  is built and fed to the EXISTING CredibilityScoreCalculator.
  Gemini NEVER chooses the numerical score — the deterministic engine does.
  scoring_method = "ai_assisted" | "insufficient_evidence"

CRITICAL CONTRACTS:
  - All LLM/API errors are caught here; they never reach the caller.
  - Gemini is never exposed as an evidence source, citation, or provider.
  - The deterministic result is always the fallback when AI is unavailable.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from backend.ai.models import AIReasoningResult, EvidenceFinding
from backend.config.scoring_config import (
    AI_CROSS_VERIFY_ENABLED,
    AI_CROSS_VERIFY_MATERIAL_RATIO_THRESHOLD,
    AI_CROSS_VERIFY_MAX_ADJUSTMENT,
    AI_RESCUE_MIN_GROUNDED_FINDINGS,
)
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.scoring.models import ClaimCredibilityScore
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    EvidenceComparison,
    EvidenceStance,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _valid_eids(evidence_items: List[Evidence]) -> Set[str]:
    return {ev.evidence_id for ev in evidence_items}


def _filter_grounded(
    findings: List[EvidenceFinding],
    valid: Set[str],
) -> List[EvidenceFinding]:
    """Keep only findings that reference at least one valid evidence_id.

    Each returned finding has its evidence_ids narrowed to the valid subset.
    """
    out: List[EvidenceFinding] = []
    for f in findings:
        kept = [eid for eid in f.evidence_ids if eid in valid]
        if kept:
            out.append(
                EvidenceFinding(
                    text=f.text,
                    evidence_ids=kept,
                    stance=f.stance,
                    importance=f.importance,
                    confidence=f.confidence,
                )
            )
    return out


def _count_independent_clusters(
    findings: List[EvidenceFinding],
    independence_result: Optional[ClaimIndependenceResult],
) -> int:
    """Estimate the number of independent source clusters referenced.

    When independence_result is available, uses cluster membership.
    Otherwise, each unique evidence_id is counted as its own cluster
    (conservative upper-bound).
    """
    if not independence_result:
        unique_eids: Set[str] = set()
        for f in findings:
            unique_eids.update(f.evidence_ids)
        return max(len(unique_eids), 1) if unique_eids else 0

    eid_to_cluster: Dict[str, str] = {}
    for cl in independence_result.clusters:
        for eid in cl.evidence_ids:
            eid_to_cluster[eid] = cl.cluster_id

    unique_clusters: Set[str] = set()
    for f in findings:
        for eid in f.evidence_ids:
            # Fall back to eid itself when no cluster mapping exists
            unique_clusters.add(eid_to_cluster.get(eid, eid))

    return len(unique_clusters)


def _build_synthetic_comparison(
    claim_id: str,
    supporting: List[EvidenceFinding],
    contradicting: List[EvidenceFinding],
    independence_result: Optional[ClaimIndependenceResult],
) -> ClaimEvidenceComparisonResult:
    """Build a minimal ClaimEvidenceComparisonResult from grounded AI findings.

    Each unique evidence_id referenced in supporting/contradicting findings
    becomes one EvidenceComparison with the corresponding stance.  Fact-checks
    and discrepancies are left empty so no fabricated data enters scoring.
    """
    comparisons: List[EvidenceComparison] = []
    seen: Set[str] = set()

    for f in supporting:
        for eid in f.evidence_ids:
            if eid not in seen:
                seen.add(eid)
                comparisons.append(
                    EvidenceComparison(
                        evidence_id=eid,
                        claim_id=claim_id,
                        stance=EvidenceStance.SUPPORTING,
                        confidence=f.confidence,
                        relevance=0.75,
                        reasoning=f.text,
                        supporting_points=[f.text],
                        contradicting_points=[],
                        neutral_points=[],
                    )
                )

    for f in contradicting:
        for eid in f.evidence_ids:
            if eid not in seen:
                seen.add(eid)
                comparisons.append(
                    EvidenceComparison(
                        evidence_id=eid,
                        claim_id=claim_id,
                        stance=EvidenceStance.CONTRADICTING,
                        confidence=f.confidence,
                        relevance=0.75,
                        reasoning=f.text,
                        supporting_points=[],
                        contradicting_points=[f.text],
                        neutral_points=[],
                    )
                )

    supp_count  = len(supporting)
    contra_count = len(contradicting)
    total_decisive = supp_count + contra_count
    agreement_ratio = supp_count / total_decisive if total_decisive > 0 else 0.0

    indep_supp   = _count_independent_clusters(supporting,    independence_result)
    indep_contra = _count_independent_clusters(contradicting, independence_result)

    return ClaimEvidenceComparisonResult(
        claim_id=claim_id,
        comparisons=comparisons,
        fact_checks=[],
        supporting_count=supp_count,
        contradicting_count=contra_count,
        neutral_count=0,
        insufficient_count=0,
        independent_supporting_count=indep_supp,
        independent_contradicting_count=indep_contra,
        agreement_ratio=agreement_ratio,
        key_discrepancies=[],
        summary=(
            f"AI-assisted evidence classification: "
            f"{supp_count} grounded supporting, {contra_count} grounded contradicting."
        ),
    )


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class AICrossVerifier:
    """Applies AI cross-verification (PATH A) and INSUFFICIENT EVIDENCE rescue (PATH B).

    PATH A — a deterministic score already exists:
      Compare Gemini's grounded finding ratio against the deterministic
      evidence-agreement ratio.  Apply a bounded score adjustment only when
      the disagreement is material.  On any failure, return the original score.

    PATH B — deterministic result is INSUFFICIENT EVIDENCE + evidence exists:
      Reuse the already-validated AIReasoningResult produced by Part 8.
      Filter findings to grounded evidence_ids only.  If enough findings pass,
      build a synthetic ClaimEvidenceComparisonResult and re-run the EXISTING
      CredibilityScoreCalculator.  Gemini never picks the number.
    """

    def __init__(
        self,
        calculator=None,  # CredibilityScoreCalculator injected for testability
    ) -> None:
        # Import here to avoid circular imports at module level
        from backend.scoring.credibility_score import (  # noqa: PLC0415
            CredibilityScoreCalculator,
            classify_credibility_score,
        )
        self._calc_cls = CredibilityScoreCalculator
        self._classify  = classify_credibility_score
        self._calculator = calculator or CredibilityScoreCalculator()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(
        self,
        deterministic_score: ClaimCredibilityScore,
        ai_reasoning: Optional[AIReasoningResult],
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
    ) -> ClaimCredibilityScore:
        """Apply AI cross-verification or rescue as appropriate.

        Returns the (possibly modified) ClaimCredibilityScore.
        All exceptions are caught; the deterministic result is always
        returned on failure.
        """
        if not AI_CROSS_VERIFY_ENABLED:
            return self._stamp_method(deterministic_score)

        try:
            return self._dispatch(
                deterministic_score, ai_reasoning, evidence_items,
                source_analyses, independence_result,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AICrossVerifier unexpected error for claim %s: %s — "
                "returning deterministic result unchanged.",
                deterministic_score.claim_id, exc, exc_info=True,
            )
            return self._stamp_method(deterministic_score)

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _stamp_method(self, score: ClaimCredibilityScore) -> ClaimCredibilityScore:
        """Set scoring_method when cross-verification is disabled or skipped."""
        method = (
            "insufficient_evidence"
            if score.is_insufficient_evidence
            else "deterministic"
        )
        return score.model_copy(update={"scoring_method": method})

    def _dispatch(
        self,
        score: ClaimCredibilityScore,
        ai_reasoning: Optional[AIReasoningResult],
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]],
        independence_result: Optional[ClaimIndependenceResult],
    ) -> ClaimCredibilityScore:
        valid = _valid_eids(evidence_items)

        if score.is_insufficient_evidence:
            if evidence_items and ai_reasoning:
                return self._path_b_rescue(
                    score, ai_reasoning, evidence_items, valid,
                    source_analyses, independence_result,
                )
            return score.model_copy(update={"scoring_method": "insufficient_evidence"})

        # PATH A — deterministic score is not None
        return self._path_a_cross_verify(score, ai_reasoning, valid)

    # ------------------------------------------------------------------
    # PATH A
    # ------------------------------------------------------------------

    def _path_a_cross_verify(
        self,
        score: ClaimCredibilityScore,
        ai_reasoning: Optional[AIReasoningResult],
        valid: Set[str],
    ) -> ClaimCredibilityScore:
        """Cross-verify an existing deterministic score against grounded AI findings."""
        # Skip if no real AI output
        if (
            ai_reasoning is None
            or not ai_reasoning.ai_used
            or ai_reasoning.fallback_used
            or score.score is None
        ):
            return score.model_copy(update={"scoring_method": "deterministic"})

        grounded_supp   = _filter_grounded(ai_reasoning.supporting_findings, valid)
        grounded_contra = _filter_grounded(ai_reasoning.contradicting_findings, valid)

        ai_total = len(grounded_supp) + len(grounded_contra)
        if ai_total == 0:
            return score.model_copy(update={"scoring_method": "deterministic"})

        ai_ratio = len(grounded_supp) / ai_total

        # Retrieve deterministic evidence-agreement raw score from components
        det_ratio: Optional[float] = None
        for c in score.components:
            if c.factor.value == "evidence_agreement":
                det_ratio = c.raw_score
                break

        if det_ratio is None:
            return score.model_copy(update={"scoring_method": "deterministic"})

        diff = ai_ratio - det_ratio
        if abs(diff) < AI_CROSS_VERIFY_MATERIAL_RATIO_THRESHOLD:
            # Gemini agrees with the deterministic assessment
            return score.model_copy(update={"scoring_method": "deterministic"})

        # Material disagreement — compute bounded adjustment
        raw_adj = diff * AI_CROSS_VERIFY_MAX_ADJUSTMENT * 2.0
        adj = max(-AI_CROSS_VERIFY_MAX_ADJUSTMENT,
                  min(AI_CROSS_VERIFY_MAX_ADJUSTMENT, raw_adj))

        new_score = int(round(max(0.0, min(100.0, (score.score or 0) + adj))))
        new_cls   = self._classify(new_score)

        logger.info(
            "PATH A: score adjusted %d → %d for claim %s "
            "(ai_ratio=%.2f det_ratio=%.2f adj=%.1f)",
            score.score, new_score, score.claim_id, ai_ratio, det_ratio, adj,
        )

        new_limitations = list(score.limitations) + [
            f"Score adjusted by {adj:+.1f} point(s) via AI cross-verification "
            f"(AI agreement ratio: {ai_ratio:.0%}, "
            f"deterministic agreement ratio: {det_ratio:.0%})."
        ]
        return score.model_copy(update={
            "score":          new_score,
            "classification": new_cls,
            "scoring_method": "ai_assisted",
            "limitations":    new_limitations,
        })

    # ------------------------------------------------------------------
    # PATH B
    # ------------------------------------------------------------------

    def _path_b_rescue(
        self,
        original: ClaimCredibilityScore,
        ai_reasoning: AIReasoningResult,
        evidence_items: List[Evidence],
        valid: Set[str],
        source_analyses: Optional[List[SourceAnalysis]],
        independence_result: Optional[ClaimIndependenceResult],
    ) -> ClaimCredibilityScore:
        """Attempt to rescue an INSUFFICIENT EVIDENCE result.

        Uses the already-validated AIReasoningResult from Part 8.
        No additional Gemini call is made here.
        """
        if not ai_reasoning.ai_used or ai_reasoning.fallback_used:
            return original.model_copy(update={"scoring_method": "insufficient_evidence"})

        grounded_supp   = _filter_grounded(ai_reasoning.supporting_findings, valid)
        grounded_contra = _filter_grounded(ai_reasoning.contradicting_findings, valid)
        total_grounded  = len(grounded_supp) + len(grounded_contra)

        logger.info(
            "PATH B rescue: claim=%s grounded_supporting=%d "
            "grounded_contradicting=%d threshold=%d",
            original.claim_id, len(grounded_supp), len(grounded_contra),
            AI_RESCUE_MIN_GROUNDED_FINDINGS,
        )

        if total_grounded < AI_RESCUE_MIN_GROUNDED_FINDINGS:
            logger.info(
                "PATH B rescue: %d grounded findings < threshold %d — "
                "remaining INSUFFICIENT EVIDENCE for claim %s.",
                total_grounded, AI_RESCUE_MIN_GROUNDED_FINDINGS, original.claim_id,
            )
            return original.model_copy(update={"scoring_method": "insufficient_evidence"})

        # Build synthetic comparison from grounded findings only
        synthetic = _build_synthetic_comparison(
            claim_id=original.claim_id,
            supporting=grounded_supp,
            contradicting=grounded_contra,
            independence_result=independence_result,
        )

        # Re-run the full deterministic scoring pipeline (Gemini never picks the number)
        rescued = self._calculator.calculate_claim_score(
            claim_id=original.claim_id,
            claim_text=original.claim_text,
            evidence_items=evidence_items,
            source_analyses=source_analyses or [],
            independence_result=independence_result,
            comparison_result=synthetic,
        )

        if rescued.is_insufficient_evidence or rescued.score is None:
            # Deterministic engine still says insufficient after AI stances
            logger.info(
                "PATH B rescue: deterministic engine returned insufficient "
                "even after AI stances for claim %s.",
                original.claim_id,
            )
            return original.model_copy(update={"scoring_method": "insufficient_evidence"})

        logger.info(
            "PATH B rescue SUCCESS: claim=%s score=%d ('%s') via AI-assisted scoring.",
            original.claim_id, rescued.score, rescued.classification,
        )

        new_limitations = list(rescued.limitations) + [
            "Score produced via AI-assisted evidence classification: "
            "the deterministic stance detector found insufficient decisive evidence, "
            "but grounded AI findings provided enough stance signal to re-run scoring. "
            "Gemini was not used as a source or evidence provider."
        ]
        return rescued.model_copy(update={
            "scoring_method": "ai_assisted",
            "limitations":    new_limitations,
        })
