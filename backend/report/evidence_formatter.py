"""Formatter converting raw verification pipeline structures into auditable report cards."""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.ai.models import AIReasoningResult
from backend.report.models import (
    AIReasoningReport,
    ClusterCard,
    DiscrepancyCard,
    EvidenceCard,
    EvidenceSummary,
    FactCheckCard,
    IndependenceSummary,
    ScoreBreakdownReport,
    ScoreComponentCard,
    ScoreContribution,
    ScorePenaltyCard,
    SourceAnalysisCard,
)
from backend.retrieval.models import Evidence
from backend.scoring.models import ClaimCredibilityScore
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    ClusterType,
    EvidenceComparison,
    EvidenceStance,
    IndependenceAnalysis,
    RelationshipType,
)


class EvidenceFormatter:
    """Transforms raw pipeline data into presentation-ready, auditable report cards."""

    @staticmethod
    def format_evidence_cards(
        evidence_items: List[Evidence],
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
    ) -> Dict[str, List[EvidenceCard]]:
        """Group evidence items into supporting, contradicting, neutral, and insufficient lists."""
        sa_by_id = {sa.evidence_id: sa for sa in (source_analyses or [])}
        indep_by_id: Dict[str, IndependenceAnalysis] = {
            a.evidence_id: a for a in (independence_result.analyses if independence_result else [])
        }
        comp_by_id: Dict[str, EvidenceComparison] = {
            c.evidence_id: c for c in (comparison_result.comparisons if comparison_result else [])
        }

        cards_by_stance: Dict[str, List[EvidenceCard]] = {
            "SUPPORTING": [],
            "CONTRADICTING": [],
            "NEUTRAL": [],
            "INSUFFICIENT": [],
        }

        for ev in evidence_items:
            comp = comp_by_id.get(ev.evidence_id)
            sa = sa_by_id.get(ev.evidence_id)
            indep = indep_by_id.get(ev.evidence_id)

            stance_str = comp.stance.value if comp else "NEUTRAL"
            relevance = comp.relevance if comp else None
            cluster_id = indep.cluster_id if indep else None
            indep_status = indep.independence_status.value if indep else None
            src_category = sa.source_category.value.lower() if sa else None
            src_reliability = sa.reliability_label.value.lower() if sa else "unknown"

            card = EvidenceCard(
                evidence_id=ev.evidence_id,
                title=ev.title or "Untitled Evidence",
                publisher=ev.publisher or ev.domain,
                url=ev.url,
                publication_date=ev.published_at,
                snippet=ev.snippet,
                stance=stance_str,
                relevance=relevance,
                cluster_id=cluster_id,
                independence_status=indep_status,
                source_category=src_category,
                source_reliability=src_reliability,
            )

            if stance_str in cards_by_stance:
                cards_by_stance[stance_str].append(card)
            else:
                cards_by_stance["NEUTRAL"].append(card)

        # Deterministic sorting within each stance: higher relevance first, then evidence_id
        for stance_key in cards_by_stance:
            cards_by_stance[stance_key].sort(
                key=lambda c: (-(c.relevance or 0.0), c.evidence_id)
            )

        return cards_by_stance

    @staticmethod
    def build_evidence_summary(
        evidence_items: List[Evidence],
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
    ) -> EvidenceSummary:
        """Create a compact, unambiguous evidence count summary distinguishing raw vs independent."""
        total_retrieved = len(evidence_items)
        supp = comparison_result.supporting_count if comparison_result else 0
        contra = comparison_result.contradicting_count if comparison_result else 0
        neutral = comparison_result.neutral_count if comparison_result else 0
        insufficient = comparison_result.insufficient_count if comparison_result else 0
        fact_checks = len(comparison_result.fact_checks) if comparison_result else 0

        indep_count = (
            independence_result.independent_source_count
            if independence_result
            else total_retrieved
        )

        # Count duplicate and syndication clusters
        dup_count = 0
        syn_count = 0
        if independence_result:
            for rel in independence_result.relationships:
                if rel.relationship_type in (RelationshipType.EXACT_DUPLICATE, RelationshipType.NEAR_DUPLICATE):
                    dup_count += 1
                elif rel.relationship_type == RelationshipType.SYNDICATED:
                    syn_count += 1

        return EvidenceSummary(
            total_retrieved=total_retrieved,
            supporting_count=supp,
            contradicting_count=contra,
            neutral_count=neutral,
            insufficient_count=insufficient,
            independent_source_count=indep_count,
            duplicate_count=dup_count,
            syndicated_count=syn_count,
            fact_check_count=fact_checks,
        )

    @staticmethod
    def format_fact_checks(
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> List[FactCheckCard]:
        """Format normalized fact-check cards preserving original publisher ratings."""
        if not comparison_result or not comparison_result.fact_checks:
            return []

        cards: List[FactCheckCard] = []
        for fc in comparison_result.fact_checks:
            cards.append(
                FactCheckCard(
                    fact_check_id=fc.fact_check_id,
                    publisher=fc.fact_checker,
                    title=f"Fact Check by {fc.fact_checker}",
                    url=fc.url,
                    review_date=fc.published_at,
                    original_rating=fc.raw_rating,
                    normalized_rating=fc.verdict_normalized,
                    stance=fc.stance.value,
                    explanation=fc.explanation,
                    evidence_ids=[fc.fact_check_id],
                )
            )
        return cards

    @staticmethod
    def format_discrepancies(
        comparison_result: Optional[ClaimEvidenceComparisonResult],
    ) -> List[DiscrepancyCard]:
        """Format detected factual discrepancies."""
        if not comparison_result or not comparison_result.key_discrepancies:
            return []

        cards: List[DiscrepancyCard] = []
        for disc in comparison_result.key_discrepancies:
            desc = (
                f"Conflict in {disc.aspect}: claim asserts '{disc.claim_value}' "
                f"while evidence reports '{disc.evidence_value}'."
            )
            cards.append(
                DiscrepancyCard(
                    type=disc.discrepancy_type.value,
                    description=desc,
                    claim_value=disc.claim_value,
                    evidence_value=disc.evidence_value,
                    evidence_ids=[],
                    severity=disc.severity,
                )
            )
        return cards

    @staticmethod
    def format_source_analyses(
        source_analyses: Optional[List[SourceAnalysis]],
    ) -> List[SourceAnalysisCard]:
        """Format publisher source characteristics."""
        if not source_analyses:
            return []

        cards: List[SourceAnalysisCard] = []
        for sa in source_analyses:
            cards.append(
                SourceAnalysisCard(
                    publisher=sa.publisher or sa.domain,
                    domain=sa.domain,
                    source_category=sa.source_category.value.lower(),
                    reliability_label=sa.reliability_label.value,
                    reliability_score=sa.reliability_score,
                    transparency=sa.transparency.value,
                    metadata_quality=sa.metadata_quality.score,
                    attribution_signal=sa.attribution.present,
                    primary_reporting_signal=sa.primary_reporting.present,
                    limitations=sa.limitations,
                )
            )
        return cards

    @staticmethod
    def format_independence(
        independence_result: Optional[ClaimIndependenceResult],
    ) -> Optional[IndependenceSummary]:
        """Format syndication and duplicate cluster relationships."""
        if not independence_result:
            return None

        cluster_cards: List[ClusterCard] = []
        syn_clusters = 0
        dup_clusters = 0

        for cl in independence_result.clusters:
            if cl.cluster_type == ClusterType.SYNDICATION:
                syn_clusters += 1
            elif cl.cluster_type == ClusterType.DUPLICATE:
                dup_clusters += 1

            cluster_cards.append(
                ClusterCard(
                    cluster_id=cl.cluster_id,
                    cluster_type=cl.cluster_type.value,
                    member_count=len(cl.evidence_ids),
                    representative_evidence_id=cl.representative_evidence_id,
                    evidence_ids=cl.evidence_ids,
                )
            )

        limitations: List[str] = []
        if syn_clusters > 0:
            limitations.append(
                f"{syn_clusters} syndication cluster(s) detected: reprints from wire services "
                "or partner networks were grouped and counted as single independent sources."
            )

        return IndependenceSummary(
            independent_source_count=independence_result.independent_source_count,
            cluster_count=len(independence_result.clusters),
            syndication_clusters=syn_clusters,
            duplicate_clusters=dup_clusters,
            independence_limitations=limitations,
            clusters=cluster_cards,
        )

    @staticmethod
    def format_score_breakdown(
        score_result: Optional[ClaimCredibilityScore],
    ) -> Optional[ScoreBreakdownReport]:
        """Format full dimensional score breakdown and penalties."""
        if not score_result:
            return None

        comp_cards: List[ScoreComponentCard] = [
            ScoreComponentCard(
                factor=c.factor.value,
                label=c.label,
                raw_score=c.raw_score,
                weight=c.weight,
                weighted_contribution=c.weighted_contribution,
                explanation=c.explanation,
                evidence_ids=c.evidence_ids,
            )
            for c in score_result.components
        ]

        penalty_cards: List[ScorePenaltyCard] = [
            ScorePenaltyCard(
                penalty_type=p.penalty_type,
                amount=p.amount,
                explanation=p.explanation,
                evidence_ids=p.evidence_ids,
            )
            for p in score_result.penalties
        ]

        return ScoreBreakdownReport(
            components=comp_cards,
            penalties=penalty_cards,
            total_before_penalties=score_result.total_before_penalties,
            penalties_total=score_result.penalties_total,
            final_score=score_result.score,
            # Convert api.schemas.ScoreContribution -> report-local
            # ScoreContribution (identical fields, distinct classes for
            # circular-import safety).
            score_contributions=[
                ScoreContribution(
                    factor=s.factor,
                    label=s.label,
                    contribution=s.contribution,
                    detail=s.detail,
                )
                for s in (score_result.score_breakdown or [])
            ],
        )

    @staticmethod
    def format_ai_reasoning(
        reasoning_result: Optional[AIReasoningResult],
    ) -> Optional[AIReasoningReport]:
        """Format AI evidence reasoning and provenance."""
        if not reasoning_result:
            return None

        return AIReasoningReport(
            summary=reasoning_result.summary,
            supporting_findings=[f.text for f in reasoning_result.supporting_findings],
            contradicting_findings=[f.text for f in reasoning_result.contradicting_findings],
            important_discrepancies=reasoning_result.important_discrepancies,
            source_observations=reasoning_result.source_observations,
            independence_observations=reasoning_result.independence_observations,
            fact_check_observations=reasoning_result.fact_check_observations,
            verification_gaps=reasoning_result.verification_gaps,
            uncertainty=reasoning_result.uncertainty.value if hasattr(reasoning_result.uncertainty, "value") else str(reasoning_result.uncertainty),
            limitations=reasoning_result.limitations,
            ai_used=reasoning_result.ai_used,
            fallback_used=reasoning_result.fallback_used,
            provider=reasoning_result.provider,
            model=reasoning_result.model,
        )
