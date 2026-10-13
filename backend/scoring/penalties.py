"""Penalty calculator for grounded deductions based on discrepancies and contradictions."""

from __future__ import annotations

from typing import List, Optional, Set

from backend.config.scoring_config import (
    PENALTY_ANONYMOUS_UNINDEXED,
    PENALTY_CRITICAL_DISCREPANCY,
    PENALTY_MAJOR_DISCREPANCY,
    PENALTY_REPUTABLE_CONTRADICTION,
)
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.scoring.models import ScorePenalty
from backend.sources.models import SourceAnalysis, SourceCategory
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    Discrepancy,
    EvidenceStance,
)


class PenaltyCalculator:
    """Computes grounded deductions applied to the raw weighted score."""

    def __init__(
        self,
        critical_discrepancy_penalty: float = PENALTY_CRITICAL_DISCREPANCY,
        major_discrepancy_penalty: float = PENALTY_MAJOR_DISCREPANCY,
        reputable_contradiction_penalty: float = PENALTY_REPUTABLE_CONTRADICTION,
        anonymous_unindexed_penalty: float = PENALTY_ANONYMOUS_UNINDEXED,
    ) -> None:
        self.critical_penalty = critical_discrepancy_penalty
        self.major_penalty = major_discrepancy_penalty
        self.reputable_penalty = reputable_contradiction_penalty
        self.anonymous_penalty = anonymous_unindexed_penalty

    def calculate_penalties(
        self,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
        source_analyses: Optional[List[SourceAnalysis]] = None,
        evidence_items: Optional[List[Evidence]] = None,
    ) -> List[ScorePenalty]:
        """Evaluate and return all applicable grounded penalties."""
        penalties: List[ScorePenalty] = []

        if not comparison_result:
            return penalties

        source_analyses = source_analyses or []
        evidence_items = evidence_items or []

        # 1. Evaluate Discrepancies
        discrepancy_penalties = self._evaluate_discrepancies(comparison_result)
        penalties.extend(discrepancy_penalties)

        # 2. Evaluate Reputable / Fact-Check Contradictions
        refutation_penalties = self._evaluate_reputable_refutations(comparison_result, source_analyses)
        penalties.extend(refutation_penalties)

        # 3. Evaluate Anonymous / Low-Transparency Supporting Sources
        anon_penalty = self._evaluate_anonymous_sources(comparison_result, source_analyses)
        if anon_penalty:
            penalties.append(anon_penalty)

        return penalties

    def _evaluate_discrepancies(
        self,
        comparison_result: ClaimEvidenceComparisonResult,
    ) -> List[ScorePenalty]:
        """Detect material discrepancies (numeric, temporal, status) and apply penalties."""
        penalties: List[ScorePenalty] = []
        seen_aspects: Set[str] = set()

        for disc in comparison_result.key_discrepancies:
            aspect_key = f"{disc.discrepancy_type.value}:{disc.aspect}"
            if aspect_key in seen_aspects:
                continue
            seen_aspects.add(aspect_key)

            sev = disc.severity.upper() if disc.severity else "MAJOR"
            if sev == "CRITICAL":
                amount = self.critical_penalty
                explanation = (
                    f"Critical {disc.discrepancy_type.value.lower()} discrepancy: claim asserts "
                    f"'{disc.claim_value}' but evidence reports '{disc.evidence_value}' ({disc.aspect})."
                )
            elif sev == "MAJOR":
                amount = self.major_penalty
                explanation = (
                    f"Major {disc.discrepancy_type.value.lower()} discrepancy: claim asserts "
                    f"'{disc.claim_value}' but evidence reports '{disc.evidence_value}' ({disc.aspect})."
                )
            else:
                amount = 5.0
                explanation = (
                    f"Minor {disc.discrepancy_type.value.lower()} variance between claim and evidence ({disc.aspect})."
                )

            penalties.append(
                ScorePenalty(
                    penalty_type=f"{disc.discrepancy_type.value.lower()}_discrepancy",
                    amount=amount,
                    explanation=explanation,
                    evidence_ids=[],
                )
            )

        return penalties

    def _evaluate_reputable_refutations(
        self,
        comparison_result: ClaimEvidenceComparisonResult,
        source_analyses: List[SourceAnalysis],
    ) -> List[ScorePenalty]:
        """Apply penalty when reputable fact-checkers or authoritative sources contradict claim."""
        penalties: List[ScorePenalty] = []
        sa_by_id = {sa.evidence_id: sa for sa in source_analyses}

        # Check contradicting fact checks
        seen_fact_checkers: Set[str] = set()
        for fc in comparison_result.fact_checks:
            if fc.stance == EvidenceStance.CONTRADICTING:
                if fc.fact_checker not in seen_fact_checkers:
                    seen_fact_checkers.add(fc.fact_checker)
                    penalties.append(
                        ScorePenalty(
                            penalty_type="fact_check_refutation",
                            amount=self.reputable_penalty,
                            explanation=(
                                f"Direct refutation by verified fact-checker {fc.fact_checker} "
                                f"(rated '{fc.raw_rating}' / {fc.verdict_normalized})."
                            ),
                            evidence_ids=[fc.fact_check_id],
                        )
                    )

        # Check contradicting high-reliability sources (reliability >= 75 or official/government)
        reputable_categories = {
            SourceCategory.GOVERNMENT,
            SourceCategory.REGULATORY,
            SourceCategory.INTERNATIONAL_ORGANIZATION,
            SourceCategory.ACADEMIC,
        }
        reputable_contradictions = []
        for comp in comparison_result.comparisons:
            if comp.stance == EvidenceStance.CONTRADICTING:
                sa = sa_by_id.get(comp.evidence_id)
                if sa and (sa.reliability_score >= 75 or sa.source_category in reputable_categories):
                    reputable_contradictions.append(comp.evidence_id)

        if reputable_contradictions and not seen_fact_checkers:
            # Only apply if not already penalized by fact check to avoid double-dipping on the same refutation event
            penalties.append(
                ScorePenalty(
                    penalty_type="reputable_source_refutation",
                    amount=self.reputable_penalty,
                    explanation=(
                        f"Direct contradiction by {len(reputable_contradictions)} high-reliability "
                        f"or authoritative source(s)."
                    ),
                    evidence_ids=reputable_contradictions[:3],
                )
            )

        return penalties

    def _evaluate_anonymous_sources(
        self,
        comparison_result: ClaimEvidenceComparisonResult,
        source_analyses: List[SourceAnalysis],
    ) -> Optional[ScorePenalty]:
        """Apply penalty if all supporting sources suffer from low transparency or unindexed provenance."""
        sa_by_id = {sa.evidence_id: sa for sa in source_analyses}
        supporting_eids = [
            comp.evidence_id
            for comp in comparison_result.comparisons
            if comp.stance == EvidenceStance.SUPPORTING
        ]

        if not supporting_eids:
            return None

        supporting_sa = [sa_by_id[eid] for eid in supporting_eids if eid in sa_by_id]
        if not supporting_sa:
            return None

        # Check if all supporting sources are low transparency (< 0.4) or low reliability (< 40)
        low_transparency_all = all(
            (
                sa.metadata_quality.score < 0.40
                if hasattr(sa, "metadata_quality") and sa.metadata_quality and sa.metadata_quality.score > 0.0
                else sa.transparency.value == "LOW"
            )
            for sa in supporting_sa
        )
        low_reliability_all = all(sa.reliability_score < 40 for sa in supporting_sa)

        if low_transparency_all or low_reliability_all:
            return ScorePenalty(
                penalty_type="anonymous_unindexed_sources",
                amount=self.anonymous_penalty,
                explanation=(
                    "Supporting sources lack transparent publisher, author, or contact disclosures "
                    "or have low baseline domain reliability."
                ),
                evidence_ids=[sa.evidence_id for sa in supporting_sa],
            )

        return None
