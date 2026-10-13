"""Cluster-aware evidence consensus aggregation and agreement ratio analysis."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from backend.logging_config import logger
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    Discrepancy,
    EvidenceCluster,
    EvidenceComparison,
    EvidenceStance,
    FactCheckComparison,
)


def analyze_consensus(
    claim_id: str,
    comparisons: List[EvidenceComparison],
    fact_checks: List[FactCheckComparison],
    clusters: Optional[List[EvidenceCluster]] = None,
) -> ClaimEvidenceComparisonResult:
    """Aggregate individual evidence comparisons using duplicate/syndication cluster awareness.

    Ensures that multiple syndicated or duplicate reports from the same cluster
    count as only ONE independent confirmation when computing independent_supporting_count
    and agreement_ratio.
    """
    clusters = clusters or []

    # Map comparisons by evidence_id
    comp_by_id: Dict[str, EvidenceComparison] = {c.evidence_id: c for c in comparisons}

    # Count raw stances
    supporting_count = sum(1 for c in comparisons if c.stance == EvidenceStance.SUPPORTING)
    contradicting_count = sum(1 for c in comparisons if c.stance == EvidenceStance.CONTRADICTING)
    neutral_count = sum(1 for c in comparisons if c.stance == EvidenceStance.NEUTRAL)
    insufficient_count = sum(1 for c in comparisons if c.stance == EvidenceStance.INSUFFICIENT)

    # Cluster-aware independent aggregation
    # Build cluster mapping
    clustered_eids: Set[str] = set()
    independent_supporting_count = 0
    independent_contradicting_count = 0

    for cluster in clusters:
        # Determine the stance of this cluster
        rep_id = cluster.representative_evidence_id
        cluster_stances = [
            comp_by_id[eid].stance for eid in cluster.evidence_ids
            if eid in comp_by_id
        ]
        clustered_eids.update(cluster.evidence_ids)

        if not cluster_stances:
            continue

        # Prioritize representative stance, else majority
        if rep_id and rep_id in comp_by_id:
            cluster_stance = comp_by_id[rep_id].stance
        else:
            cluster_stance = max(set(cluster_stances), key=cluster_stances.count)

        if cluster_stance == EvidenceStance.SUPPORTING:
            independent_supporting_count += 1
        elif cluster_stance == EvidenceStance.CONTRADICTING:
            independent_contradicting_count += 1

    # Any comparison item that was not in any cluster counts as its own independent unit
    for eid, comp in comp_by_id.items():
        if eid not in clustered_eids:
            if comp.stance == EvidenceStance.SUPPORTING:
                independent_supporting_count += 1
            elif comp.stance == EvidenceStance.CONTRADICTING:
                independent_contradicting_count += 1

    # Compute agreement ratio
    total_evaluable = independent_supporting_count + independent_contradicting_count
    if total_evaluable > 0:
        agreement_ratio = round(independent_supporting_count / total_evaluable, 3)
    else:
        agreement_ratio = 0.0

    # Aggregate and deduplicate key discrepancies
    seen_disc = set()
    key_discrepancies: List[Discrepancy] = []
    for comp in comparisons:
        for d in comp.discrepancies:
            sig = (d.discrepancy_type.value, d.aspect, d.claim_value.lower(), d.evidence_value.lower())
            if sig not in seen_disc:
                seen_disc.add(sig)
                key_discrepancies.append(d)

    # Formulate human-readable summary
    summary_parts = []
    if fact_checks:
        fc_verdicts = [fc.verdict_normalized for fc in fact_checks]
        summary_parts.append(
            f"Found {len(fact_checks)} fact-check review(s) (ratings: {', '.join(set(fc_verdicts))})."
        )

    if independent_supporting_count > 0 and independent_contradicting_count == 0:
        summary_parts.append(
            f"{independent_supporting_count} independent source(s) corroborate the claim ({supporting_count} total article(s))."
        )
    elif independent_supporting_count > 0 and independent_contradicting_count > 0:
        summary_parts.append(
            f"Conflicting reporting: {independent_supporting_count} independent source(s) support, "
            f"while {independent_contradicting_count} contradict ({agreement_ratio * 100:.0f}% agreement)."
        )
    elif independent_contradicting_count > 0:
        summary_parts.append(
            f"{independent_contradicting_count} independent source(s) contradict the claim."
        )
    else:
        summary_parts.append(
            f"No conclusive supporting or contradicting evidence found across {len(comparisons)} retrieved item(s)."
        )

    if key_discrepancies:
        disc_desc = [f"{d.aspect}: {d.evidence_value}" for d in key_discrepancies[:2]]
        summary_parts.append(f"Material conflicts noted on {'; '.join(disc_desc)}.")

    summary = " ".join(summary_parts)

    return ClaimEvidenceComparisonResult(
        claim_id=claim_id,
        comparisons=comparisons,
        fact_checks=fact_checks,
        supporting_count=supporting_count,
        contradicting_count=contradicting_count,
        neutral_count=neutral_count,
        insufficient_count=insufficient_count,
        independent_supporting_count=independent_supporting_count,
        independent_contradicting_count=independent_contradicting_count,
        agreement_ratio=agreement_ratio,
        key_discrepancies=key_discrepancies,
        summary=summary,
    )
