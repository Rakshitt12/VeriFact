"""Calculates the 6 grounded scoring dimension components for a claim."""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.config.scoring_config import (
    INDEPENDENT_SOURCES_TARGET,
    SCORING_WEIGHTS,
)
from backend.logging_config import logger
from backend.retrieval.models import Evidence, SourceType
from backend.scoring.models import ScoreComponent, ScoreFactor
from backend.sources.models import SourceAnalysis, SourceCategory
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    EvidenceStance,
)


class ComponentCalculator:
    """Computes normalized [0.0, 1.0] raw scores and weighted contributions across 6 dimensions."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = weights or SCORING_WEIGHTS
        # Validate weights sum to 1.0 (with slight float tolerance)
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            logger.warning("Scoring weights sum to %.3f (expected 1.0). Normalizing weights.", total_weight)
            self.weights = {k: v / total_weight for k, v in self.weights.items()}

    def calculate_all(
        self,
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
    ) -> List[ScoreComponent]:
        """Compute all 6 score components for a claim."""
        source_analyses = source_analyses or []
        components: List[ScoreComponent] = [
            self._calc_evidence_agreement(comparison_result),
            self._calc_source_quality(evidence_items, source_analyses, comparison_result),
            self._calc_independent_sources(independence_result, comparison_result),
            self._calc_fact_checks(comparison_result),
            self._calc_official_evidence(evidence_items, source_analyses, comparison_result),
            self._calc_transparency(source_analyses),
        ]
        return components

    def _calc_evidence_agreement(
        self,
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> ScoreComponent:
        factor = ScoreFactor.EVIDENCE_AGREEMENT
        weight = self.weights.get(factor.value, 0.30)

        if not comparison_result:
            return ScoreComponent(
                factor=factor,
                label="Evidence Agreement",
                raw_score=0.0,
                weight=weight,
                weighted_contribution=0.0,
                explanation="No evidence comparisons available to evaluate agreement.",
                evidence_ids=[],
            )

        indep_supp = comparison_result.independent_supporting_count
        indep_contra = comparison_result.independent_contradicting_count
        decisive_total = indep_supp + indep_contra

        if decisive_total > 0:
            raw_score = indep_supp / decisive_total
            pct = int(raw_score * 100)
            explanation = (
                f"{indep_supp} independent source cluster(s) support vs {indep_contra} contradicting "
                f"({pct}% agreement ratio)."
            )
        else:
            # Only neutral or insufficient evidence items
            if comparison_result.neutral_count > 0:
                raw_score = 0.5
                explanation = "All retrieved evidence is neutral or contextual; no decisive stance."
            else:
                raw_score = 0.0
                explanation = "No corroborating or refuting evidence found."

        # Collect evidence IDs involved
        evidence_ids = [
            comp.evidence_id
            for comp in comparison_result.comparisons
            if comp.stance in (EvidenceStance.SUPPORTING, EvidenceStance.CONTRADICTING)
        ]

        contribution = round(raw_score * weight * 100.0, 2)
        return ScoreComponent(
            factor=factor,
            label="Evidence Agreement",
            raw_score=round(raw_score, 4),
            weight=weight,
            weighted_contribution=contribution,
            explanation=explanation,
            evidence_ids=evidence_ids,
        )

    def _calc_source_quality(
        self,
        evidence_items: List[Evidence],
        source_analyses: List[SourceAnalysis],
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> ScoreComponent:
        factor = ScoreFactor.SOURCE_QUALITY
        weight = self.weights.get(factor.value, 0.20)

        sa_by_id = {sa.evidence_id: sa for sa in source_analyses}
        supporting_eids = set()
        if comparison_result:
            for comp in comparison_result.comparisons:
                if comp.stance == EvidenceStance.SUPPORTING:
                    supporting_eids.add(comp.evidence_id)

        supporting_analyses = [sa_by_id[eid] for eid in supporting_eids if eid in sa_by_id]

        if supporting_analyses:
            avg_rel = sum(sa.reliability_score for sa in supporting_analyses) / len(supporting_analyses)
            raw_score = min(max(avg_rel / 100.0, 0.0), 1.0)
            explanation = (
                f"Supporting sources average reliability heuristic score of {avg_rel:.1f}/100 "
                f"across {len(supporting_analyses)} publisher(s)."
            )
            evidence_ids = [sa.evidence_id for sa in supporting_analyses]
        elif source_analyses:
            # Fallback to general corpus reliability if no supporting items
            avg_rel = sum(sa.reliability_score for sa in source_analyses) / len(source_analyses)
            raw_score = min(max((avg_rel / 100.0) * 0.5, 0.0), 1.0)
            explanation = f"General source corpus average reliability of {avg_rel:.1f}/100."
            evidence_ids = [sa.evidence_id for sa in source_analyses[:3]]
        else:
            raw_score = 0.0
            explanation = "No source reliability analyses available."
            evidence_ids = []

        contribution = round(raw_score * weight * 100.0, 2)
        return ScoreComponent(
            factor=factor,
            label="Source Quality",
            raw_score=round(raw_score, 4),
            weight=weight,
            weighted_contribution=contribution,
            explanation=explanation,
            evidence_ids=evidence_ids,
        )

    def _calc_independent_sources(
        self,
        independence_result: Optional[ClaimIndependenceResult],
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> ScoreComponent:
        factor = ScoreFactor.INDEPENDENT_SOURCES
        weight = self.weights.get(factor.value, 0.20)

        # Count independent supporting clusters
        indep_supp = 0
        if comparison_result:
            indep_supp = comparison_result.independent_supporting_count
        elif independence_result:
            indep_supp = independence_result.independent_source_count

        raw_score = min(indep_supp / INDEPENDENT_SOURCES_TARGET, 1.0)
        contribution = round(raw_score * weight * 100.0, 2)

        explanation = (
            f"{indep_supp} independent source cluster(s) corroborate the claim "
            f"(target for maximum score: {INDEPENDENT_SOURCES_TARGET})."
        )

        evidence_ids = []
        if independence_result:
            for cl in independence_result.clusters:
                if cl.representative_evidence_id:
                    evidence_ids.append(cl.representative_evidence_id)

        return ScoreComponent(
            factor=factor,
            label="Independent Sources",
            raw_score=round(raw_score, 4),
            weight=weight,
            weighted_contribution=contribution,
            explanation=explanation,
            evidence_ids=evidence_ids,
        )

    def _calc_fact_checks(
        self,
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> ScoreComponent:
        factor = ScoreFactor.FACT_CHECKS
        weight = self.weights.get(factor.value, 0.15)

        fact_checks = comparison_result.fact_checks if comparison_result else []
        evidence_ids = [fc.fact_check_id for fc in fact_checks]

        if fact_checks:
            scores = []
            for fc in fact_checks:
                if fc.stance == EvidenceStance.SUPPORTING:
                    scores.append(1.0)
                elif fc.stance == EvidenceStance.CONTRADICTING:
                    scores.append(0.0)
                else:
                    scores.append(0.5)

            raw_score = sum(scores) / len(scores)
            fc_names = ", ".join({fc.fact_checker for fc in fact_checks})
            explanation = (
                f"{len(fact_checks)} fact-check review(s) found from {fc_names} "
                f"with average rating score of {raw_score:.2f}."
            )
        else:
            # Baseline when no fact check exists: neutral 0.5 (neither penalizing nor boosting)
            raw_score = 0.5
            explanation = "No existing fact checks found in verified databases (neutral baseline)."

        contribution = round(raw_score * weight * 100.0, 2)
        return ScoreComponent(
            factor=factor,
            label="Fact-Check Evidence",
            raw_score=round(raw_score, 4),
            weight=weight,
            weighted_contribution=contribution,
            explanation=explanation,
            evidence_ids=evidence_ids,
        )

    def _calc_official_evidence(
        self,
        evidence_items: List[Evidence],
        source_analyses: List[SourceAnalysis],
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> ScoreComponent:
        factor = ScoreFactor.OFFICIAL_EVIDENCE
        weight = self.weights.get(factor.value, 0.10)

        sa_by_id = {sa.evidence_id: sa for sa in source_analyses}
        official_categories = {
            SourceCategory.GOVERNMENT,
            SourceCategory.REGULATORY,
            SourceCategory.INTERNATIONAL_ORGANIZATION,
            SourceCategory.ACADEMIC,
        }

        supporting_eids = set()
        if comparison_result:
            for comp in comparison_result.comparisons:
                if comp.stance == EvidenceStance.SUPPORTING:
                    supporting_eids.add(comp.evidence_id)

        has_official_support = False
        has_primary_support = False
        official_eids: List[str] = []

        for ev in evidence_items:
            sa = sa_by_id.get(ev.evidence_id)
            is_official = (
                ev.source_type in (SourceType.OFFICIAL, SourceType.PRIMARY_DOCUMENT)
                or (sa and sa.source_category in official_categories)
            )
            is_primary = sa.primary_reporting.present if sa else False

            if ev.evidence_id in supporting_eids:
                if is_official:
                    has_official_support = True
                    official_eids.append(ev.evidence_id)
                if is_primary:
                    has_primary_support = True
                    official_eids.append(ev.evidence_id)

        if has_official_support:
            raw_score = 1.0
            explanation = "Direct confirmation from an official government, regulatory, or institutional source."
        elif has_primary_support:
            raw_score = 0.8
            explanation = "Primary firsthand journalistic reporting corroborates the claim."
        else:
            raw_score = 0.0
            explanation = "No primary official or government documentation retrieved."

        contribution = round(raw_score * weight * 100.0, 2)
        return ScoreComponent(
            factor=factor,
            label="Official / Primary Evidence",
            raw_score=round(raw_score, 4),
            weight=weight,
            weighted_contribution=contribution,
            explanation=explanation,
            evidence_ids=official_eids,
        )

    def _calc_transparency(
        self,
        source_analyses: List[SourceAnalysis],
    ) -> ScoreComponent:
        factor = ScoreFactor.TRANSPARENCY
        weight = self.weights.get(factor.value, 0.05)

        if source_analyses:
            scores = []
            for sa in source_analyses:
                if hasattr(sa, "metadata_quality") and sa.metadata_quality and sa.metadata_quality.score > 0.0:
                    scores.append(sa.metadata_quality.score)
                elif sa.transparency.value == "HIGH":
                    scores.append(1.0)
                elif sa.transparency.value == "MEDIUM":
                    scores.append(0.7)
                elif sa.transparency.value == "LOW":
                    scores.append(0.3)
                else:
                    scores.append(0.5)
            avg_trans = sum(scores) / len(scores) if scores else 0.5
            raw_score = min(max(avg_trans, 0.0), 1.0)
            explanation = f"Sources exhibit average metadata transparency score of {avg_trans:.2f}."
            evidence_ids = [sa.evidence_id for sa in source_analyses]
        else:
            raw_score = 0.5
            explanation = "Standard default transparency baseline applied."
            evidence_ids = []

        contribution = round(raw_score * weight * 100.0, 2)
        return ScoreComponent(
            factor=factor,
            label="Source Transparency",
            raw_score=round(raw_score, 4),
            weight=weight,
            weighted_contribution=contribution,
            explanation=explanation,
            evidence_ids=evidence_ids,
        )
