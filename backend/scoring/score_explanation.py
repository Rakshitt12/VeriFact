"""Explanation generator for score contributions, rankings, and plain-language summaries."""

from __future__ import annotations

from typing import List, Optional

from backend.api.schemas import ClassificationLabel, ScoreContribution
from backend.scoring.models import ScoreComponent, ScorePenalty


class ScoreExplainer:
    """Generates transparent, ordered score contribution lists and human-readable summaries."""

    @staticmethod
    def generate_breakdown(
        components: List[ScoreComponent],
        penalties: List[ScorePenalty],
    ) -> List[ScoreContribution]:
        """Convert components and penalties into a unified, impact-sorted list of ScoreContributions."""
        breakdown: List[ScoreContribution] = []

        # Add positive/neutral component contributions
        for comp in components:
            breakdown.append(
                ScoreContribution(
                    factor=comp.factor.value,
                    label=comp.label,
                    contribution=round(comp.weighted_contribution, 2),
                    detail=comp.explanation,
                )
            )

        # Add negative penalty contributions
        for pen in penalties:
            factor_label = pen.penalty_type.replace("_", " ").title()
            breakdown.append(
                ScoreContribution(
                    factor=pen.penalty_type,
                    label=f"Deduction: {factor_label}",
                    contribution=-round(pen.amount, 2),
                    detail=pen.explanation,
                )
            )

        # Sort by absolute impact descending
        breakdown.sort(key=lambda sc: abs(sc.contribution), reverse=True)
        return breakdown

    @staticmethod
    def generate_summary(
        score: Optional[int],
        classification: str,
        is_insufficient_evidence: bool,
        components: List[ScoreComponent],
        penalties: List[ScorePenalty],
    ) -> str:
        """Produce an evidence-grounded textual summary of the score."""
        if is_insufficient_evidence or score is None:
            return (
                "Insufficient evidence available to substantiate or refute this claim. "
                "Fewer than 2 independent reporting sources or decisive evidence items were retrieved."
            )

        parts: List[str] = [f"Claim evaluated as '{classification}' (score: {score}/100)."]

        # Highlight top positive factors
        pos_comps = [c for c in components if c.weighted_contribution > 5.0]
        if pos_comps:
            top_factors = ", ".join(c.label.lower() for c in pos_comps[:2])
            parts.append(f"Strengths include strong {top_factors}.")

        # Highlight penalties
        if penalties:
            top_pen = penalties[0]
            parts.append(f"Score reduced due to: {top_pen.explanation}")

        return " ".join(parts)

    @staticmethod
    def compile_limitations(
        is_insufficient_evidence: bool,
        penalties: List[ScorePenalty],
        independent_sources: int,
    ) -> List[str]:
        """Generate diagnostic caveats and limitations."""
        limitations: List[str] = []

        if is_insufficient_evidence:
            limitations.append(
                "Independent confirmation threshold not met: retrieved sources may be syndicated "
                "or too few to form a conclusive verdict."
            )

        if independent_sources < 3:
            limitations.append(
                f"Evaluation is based on {independent_sources} independent source cluster(s). "
                "Additional corroboration from secondary outlets recommended."
            )

        for pen in penalties:
            if "discrepancy" in pen.penalty_type:
                limitations.append(pen.explanation)

        return limitations
