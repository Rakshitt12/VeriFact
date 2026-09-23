"""Engine for deterministic claim credibility score calculation and classification."""

from __future__ import annotations

from typing import List, Optional

from backend.api.schemas import ClassificationLabel
from backend.config.scoring_config import (
    CLASSIFICATION_THRESHOLDS,
    MIN_CLASSIFIED_EVIDENCE_ITEMS,
    MIN_INDEPENDENT_SOURCES,
    SCORING_METHODOLOGY_VERSION,
)
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.scoring.component_calculator import ComponentCalculator
from backend.scoring.models import ClaimCredibilityScore
from backend.scoring.penalties import PenaltyCalculator
from backend.scoring.score_explanation import ScoreExplainer
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
)


def classify_credibility_score(score: Optional[int]) -> str:
    """Map an integer 0-100 score to the official human-readable ClassificationLabel."""
    if score is None:
        return ClassificationLabel.INSUFFICIENT_EVIDENCE.value

    if score >= CLASSIFICATION_THRESHOLDS["strongly_supported"]:
        return ClassificationLabel.STRONGLY_SUPPORTED.value
    if score >= CLASSIFICATION_THRESHOLDS["mostly_supported"]:
        return ClassificationLabel.MOSTLY_SUPPORTED.value
    if score >= CLASSIFICATION_THRESHOLDS["mixed_uncertain"]:
        return ClassificationLabel.MIXED_UNCERTAIN.value
    if score >= CLASSIFICATION_THRESHOLDS["weakly_supported"]:
        return ClassificationLabel.WEAKLY_SUPPORTED.value
    return ClassificationLabel.STRONGLY_CONTRADICTED.value


class CredibilityScoreCalculator:
    """Orchestrator for evaluating components, applying penalties, and classifying claim credibility."""

    def __init__(
        self,
        component_calc: Optional[ComponentCalculator] = None,
        penalty_calc: Optional[PenaltyCalculator] = None,
    ) -> None:
        self.component_calc = component_calc or ComponentCalculator()
        self.penalty_calc = penalty_calc or PenaltyCalculator()

    def calculate_claim_score(
        self,
        claim_id: str,
        claim_text: str,
        evidence_items: Optional[List[Evidence]] = None,
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
    ) -> ClaimCredibilityScore:
        """Compute the full credibility score for a factual claim."""
        evidence_items = evidence_items or []
        source_analyses = source_analyses or []

        # Check Insufficient Evidence threshold
        is_insufficient = self._check_insufficient_evidence(
            evidence_items=evidence_items,
            independence_result=independence_result,
            comparison_result=comparison_result,
        )

        # Calculate components and penalties
        components = self.component_calc.calculate_all(
            evidence_items=evidence_items,
            source_analyses=source_analyses,
            independence_result=independence_result,
            comparison_result=comparison_result,
        )

        penalties = self.penalty_calc.calculate_penalties(
            comparison_result=comparison_result,
            source_analyses=source_analyses,
            evidence_items=evidence_items,
        )

        indep_count = (
            independence_result.independent_source_count
            if independence_result
            else len(evidence_items)
        )

        if is_insufficient:
            classification = ClassificationLabel.INSUFFICIENT_EVIDENCE.value
            score = None
            total_before_penalties = 0.0
            penalties_total = 0.0
            final_raw = 0.0
        else:
            total_before_penalties = sum(c.weighted_contribution for c in components)
            penalties_total = sum(p.amount for p in penalties)
            final_raw = total_before_penalties - penalties_total
            clamped_score = max(0.0, min(100.0, final_raw))
            score = int(round(clamped_score))
            classification = classify_credibility_score(score)

        breakdown = ScoreExplainer.generate_breakdown(components, penalties)
        summary = ScoreExplainer.generate_summary(
            score=score,
            classification=classification,
            is_insufficient_evidence=is_insufficient,
            components=components,
            penalties=penalties,
        )
        limitations = ScoreExplainer.compile_limitations(
            is_insufficient_evidence=is_insufficient,
            penalties=penalties,
            independent_sources=indep_count,
        )

        return ClaimCredibilityScore(
            claim_id=claim_id,
            claim_text=claim_text,
            score=score,
            classification=classification,
            is_insufficient_evidence=is_insufficient,
            total_before_penalties=round(total_before_penalties, 2),
            penalties_total=round(penalties_total, 2),
            final_score_raw=round(final_raw, 2),
            components=components,
            penalties=penalties,
            score_breakdown=breakdown,
            summary=summary,
            limitations=limitations,
            methodology_version=SCORING_METHODOLOGY_VERSION,
        )

    def _check_insufficient_evidence(
        self,
        evidence_items: List[Evidence],
        independence_result: Optional[ClaimIndependenceResult],
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> bool:
        """Determine if available evidence meets the minimum rigor thresholds."""
        if not evidence_items:
            return True

        # Total classified decisive items (supporting + contradicting)
        classified_decisive = 0
        if comparison_result:
            classified_decisive = (
                comparison_result.supporting_count + comparison_result.contradicting_count
            )

        # Effective independent sources
        indep_count = 0
        if independence_result:
            indep_count = independence_result.independent_source_count
        elif comparison_result:
            indep_count = (
                comparison_result.independent_supporting_count
                + comparison_result.independent_contradicting_count
            )

        if indep_count < MIN_INDEPENDENT_SOURCES or classified_decisive < MIN_CLASSIFIED_EVIDENCE_ITEMS:
            logger.info(
                "Insufficient evidence triggered: independent_sources=%d (min %d), decisive_items=%d (min %d)",
                indep_count,
                MIN_INDEPENDENT_SOURCES,
                classified_decisive,
                MIN_CLASSIFIED_EVIDENCE_ITEMS,
            )
            return True

        return False
