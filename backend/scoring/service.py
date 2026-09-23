"""Service facade for single-claim and multi-claim document credibility scoring."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.api.schemas import ClassificationLabel
from backend.claim.models import Claim
from backend.config.scoring_config import SCORING_METHODOLOGY_VERSION
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.scoring.credibility_score import (
    CredibilityScoreCalculator,
    classify_credibility_score,
)
from backend.scoring.models import ClaimCredibilityScore, DocumentCredibilityScore
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
)


class CredibilityScoringService:
    """High-level service interface for computing claim and document credibility."""

    def __init__(self, calculator: Optional[CredibilityScoreCalculator] = None) -> None:
        self.calculator = calculator or CredibilityScoreCalculator()

    def score_claim(
        self,
        claim_id: str,
        claim_text: str,
        evidence_items: Optional[List[Evidence]] = None,
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
    ) -> ClaimCredibilityScore:
        """Calculate the explainable credibility score for a single claim."""
        return self.calculator.calculate_claim_score(
            claim_id=claim_id,
            claim_text=claim_text,
            evidence_items=evidence_items,
            source_analyses=source_analyses,
            independence_result=independence_result,
            comparison_result=comparison_result,
        )

    def score_document(
        self,
        claim_scores: List[ClaimCredibilityScore],
        claims: Optional[List[Claim]] = None,
    ) -> DocumentCredibilityScore:
        """Aggregate per-claim credibility scores into an overall document-level assessment."""
        if not claim_scores:
            return DocumentCredibilityScore(
                overall_score=None,
                overall_classification=ClassificationLabel.INSUFFICIENT_EVIDENCE.value,
                claim_scores=[],
                summary="No claims were extracted or scored for this document.",
                methodology_version=SCORING_METHODOLOGY_VERSION,
            )

        # Map claim weights by importance if claims metadata is provided
        importance_weights: Dict[str, float] = {}
        if claims:
            for c in claims:
                # Default weight based on claim importance or type
                weight = 1.0
                if hasattr(c, "importance"):
                    imp = str(c.importance).upper()
                    if "HIGH" in imp:
                        weight = 1.0
                    elif "MEDIUM" in imp:
                        weight = 0.7
                    elif "LOW" in imp:
                        weight = 0.4
                importance_weights[c.claim_id] = weight

        # Filter valid scored claims (exclude insufficient evidence)
        scored_items = [cs for cs in claim_scores if cs.score is not None]

        if not scored_items:
            return DocumentCredibilityScore(
                overall_score=None,
                overall_classification=ClassificationLabel.INSUFFICIENT_EVIDENCE.value,
                claim_scores=claim_scores,
                summary=(
                    f"Insufficient evidence across all {len(claim_scores)} extracted factual claim(s) "
                    "to substantiate or refute the document."
                ),
                methodology_version=SCORING_METHODOLOGY_VERSION,
            )

        # Calculate weighted average
        total_weighted_points = 0.0
        total_weight = 0.0

        for cs in scored_items:
            w = importance_weights.get(cs.claim_id, 1.0)
            total_weighted_points += (cs.score or 0) * w
            total_weight += w

        weighted_avg = total_weighted_points / total_weight if total_weight > 0 else 0.0
        overall_score = int(round(weighted_avg))
        overall_classification = classify_credibility_score(overall_score)

        # Tally counts for document summary
        strongly_supp = sum(1 for cs in claim_scores if cs.classification == ClassificationLabel.STRONGLY_SUPPORTED.value)
        mostly_supp = sum(1 for cs in claim_scores if cs.classification == ClassificationLabel.MOSTLY_SUPPORTED.value)
        contra = sum(1 for cs in claim_scores if cs.classification == ClassificationLabel.STRONGLY_CONTRADICTED.value)
        insufficient = sum(1 for cs in claim_scores if cs.is_insufficient_evidence)

        summary_parts = [
            f"Document evaluated with an overall score of {overall_score}/100 ('{overall_classification}') "
            f"across {len(claim_scores)} factual claim(s)."
        ]
        if strongly_supp or mostly_supp:
            summary_parts.append(f"{strongly_supp + mostly_supp} claim(s) supported by evidence.")
        if contra:
            summary_parts.append(f"{contra} claim(s) contradicted or refuted.")
        if insufficient:
            summary_parts.append(f"{insufficient} claim(s) have insufficient independent evidence.")

        summary = " ".join(summary_parts)

        return DocumentCredibilityScore(
            overall_score=overall_score,
            overall_classification=overall_classification,
            claim_scores=claim_scores,
            summary=summary,
            methodology_version=SCORING_METHODOLOGY_VERSION,
        )
