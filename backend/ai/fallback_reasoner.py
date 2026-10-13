"""Deterministic rule-based fallback reasoner when LLM is unavailable or disabled."""

from __future__ import annotations

from typing import List, Optional

from backend.ai.models import (
    AIReasoningResult,
    EvidenceFinding,
    EvidencePacket,
    FindingImportance,
    UncertaintyLevel,
)
from backend.retrieval.models import Evidence
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    EvidenceStance,
)

ABSENCE_GAP_NO_EVIDENCE = (
    "No relevant external evidence could be retrieved for this claim; "
    "no independent assessment was possible."
)
ABSENCE_GAP_NO_SUPPORT = (
    "No supporting evidence was retrieved for this claim in the searched "
    "sources; no independent source corroborates the assertion."
)


def ensure_evidence_absence_gaps(
    reasoning: AIReasoningResult,
    evidence_items: Optional[List[Evidence]] = None,
    comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
) -> AIReasoningResult:
    """Enforce the evidence-absence invariant on verification gaps.

    A report must never simultaneously show an empty evidence category and
    "no open gaps". When a claim has zero retrieved evidence overall — or
    zero supporting evidence — that absence is itself a verification gap,
    regardless of what the LLM (or fallback) originally produced. Idempotent:
    existing equivalent gaps are never duplicated.
    """
    gaps = list(reasoning.verification_gaps or [])
    lowered = [g.lower() for g in gaps]
    total = len(evidence_items or [])

    supporting = 0
    if comparison_result is not None:
        supporting = sum(
            1
            for comp in comparison_result.comparisons or []
            if comp.stance == EvidenceStance.SUPPORTING
        )

    if total == 0:
        if not any("no relevant external evidence" in g for g in lowered):
            gaps.append(ABSENCE_GAP_NO_EVIDENCE)
    elif supporting == 0:
        if not any("no supporting evidence" in g for g in lowered):
            gaps.append(ABSENCE_GAP_NO_SUPPORT)

    reasoning.verification_gaps = gaps
    return reasoning


def generate_fallback_reasoning(packet: EvidencePacket) -> AIReasoningResult:
    """Generate a high-fidelity, deterministic evidence reasoning result without calling an external LLM.

    Synthesizes structured findings, discrepancies, cluster observations, and
    verification gaps from the supplied EvidencePacket.
    """
    supporting_items = [ev for ev in packet.evidence if ev.stance == "SUPPORTING"]
    contradicting_items = [ev for ev in packet.evidence if ev.stance == "CONTRADICTING"]
    neutral_items = [ev for ev in packet.evidence if ev.stance == "NEUTRAL"]

    # 1. Findings
    supporting_findings: List[EvidenceFinding] = []
    for ev in supporting_items:
        text = (
            ev.supporting_points[0]
            if ev.supporting_points
            else f"{ev.publisher} reports corroboration for the claim."
        )
        supporting_findings.append(
            EvidenceFinding(
                text=text,
                evidence_ids=[ev.evidence_id],
                stance="SUPPORTING",
                importance=FindingImportance.HIGH if ev.source_reliability == "high" else FindingImportance.MEDIUM,
                confidence=ev.stance_confidence,
            )
        )

    contradicting_findings: List[EvidenceFinding] = []
    for ev in contradicting_items:
        text = (
            ev.contradicting_points[0]
            if ev.contradicting_points
            else f"{ev.publisher} contradicts or refutes the claim."
        )
        contradicting_findings.append(
            EvidenceFinding(
                text=text,
                evidence_ids=[ev.evidence_id],
                stance="CONTRADICTING",
                importance=FindingImportance.HIGH,
                confidence=ev.stance_confidence,
            )
        )

    # Key findings combination
    key_findings: List[EvidenceFinding] = []
    if supporting_findings:
        key_findings.append(supporting_findings[0])
    if contradicting_findings:
        key_findings.append(contradicting_findings[0])
    if not key_findings and packet.evidence:
        key_findings.append(
            EvidenceFinding(
                text=f"{packet.evidence[0].publisher} discusses the topic, but provides inconclusive evidence.",
                evidence_ids=[packet.evidence[0].evidence_id],
                stance=packet.evidence[0].stance,
                importance=FindingImportance.LOW,
                confidence=0.7,
            )
        )

    # 2. Discrepancies
    important_discrepancies: List[str] = []
    for d in packet.discrepancies:
        important_discrepancies.append(
            f"Conflict on {d.get('aspect')}: claim asserts '{d.get('claim_value')}', but evidence reports '{d.get('evidence_value')}'."
        )

    # 3. Source & Independence Observations
    source_observations: List[str] = []
    has_primary = any(ev.source_category in ("government", "institution") for ev in packet.evidence)
    if has_primary:
        source_observations.append("Primary institutional or government documentation was identified among retrieved sources.")
    else:
        source_observations.append("Retrieved sources consist primarily of secondary journalistic coverage.")

    high_rep_count = sum(1 for ev in packet.evidence if ev.source_reliability == "high")
    if high_rep_count > 0:
        source_observations.append(f"{high_rep_count} high-reliability publisher(s) are present in the evidence corpus.")

    independence_observations: List[str] = []
    if packet.clusters_summary:
        multi_item_clusters = [cl for cl in packet.clusters_summary if cl.get("size", 1) > 1]
        if multi_item_clusters:
            independence_observations.append(
                f"{len(multi_item_clusters)} multi-article syndication cluster(s) detected. "
                f"Effective independent source count is {packet.independent_source_count}."
            )
        else:
            independence_observations.append("All retrieved articles appear to originate from distinct reporting sources.")
    else:
        independence_observations.append(f"Effective independent source count is {packet.independent_source_count}.")

    # 4. Fact-check Observations
    fact_check_observations: List[str] = []
    for fc in packet.fact_checks:
        fact_check_observations.append(
            f"Fact check by {fc.get('fact_checker')} rated the claim '{fc.get('raw_rating')}' ({fc.get('verdict')})."
        )
    if not fact_check_observations:
        fact_check_observations.append("No third-party fact-check reviews were located for this claim.")

    # 5. Verification Gaps
    verification_gaps: List[str] = []
    if packet.independent_source_count < 2:
        verification_gaps.append(
            f"Limited independent corroboration: only {packet.independent_source_count} independent source group(s) found."
        )
    if not has_primary:
        verification_gaps.append("No primary official document was retrieved to independently verify the claim.")
    if important_discrepancies:
        verification_gaps.append(
            "Unresolved numerical or temporal discrepancies exist between reporting outlets."
        )
    if not packet.evidence:
        verification_gaps.append("No relevant external evidence could be retrieved.")

    # 6. Uncertainty
    if not packet.evidence:
        uncertainty = UncertaintyLevel.HIGH
    elif contradicting_items or important_discrepancies:
        uncertainty = UncertaintyLevel.HIGH
    elif packet.independent_source_count < 2 or not supporting_items:
        uncertainty = UncertaintyLevel.MEDIUM
    else:
        uncertainty = UncertaintyLevel.LOW

    # 7. Summary
    summary_parts = []
    if packet.fact_checks:
        fc = packet.fact_checks[0]
        summary_parts.append(f"A third-party fact check by {fc.get('fact_checker')} rated this claim '{fc.get('verdict')}'.")

    if packet.independent_source_count > 0:
        summary_parts.append(
            f"Retrieved evidence resolved into {packet.independent_source_count} independent cluster(s) "
            f"({len(supporting_items)} supporting, {len(contradicting_items)} contradicting)."
        )
    else:
        summary_parts.append("Evidence retrieval yielded no independent corroborating sources.")

    if important_discrepancies:
        summary_parts.append(important_discrepancies[0])

    summary = " ".join(summary_parts)

    reasoning_steps = [
        "1. Decomposed claim into material factual assertions.",
        "2. Evaluated stance and aspect alignment across retrieved evidence.",
        "3. Clustered syndicated and duplicate reports into independent confirmation streams.",
        "4. Detected numerical, temporal, and polarity discrepancies.",
        "5. Formulated grounded findings and identified open verification gaps.",
    ]

    limitations = [
        "Generated using deterministic verification rules (AI model synthesis was unavailable or disabled).",
    ]

    return AIReasoningResult(
        claim_id=packet.claim_id,
        claim_text=packet.claim_text,
        summary=summary,
        key_findings=key_findings,
        supporting_findings=supporting_findings,
        contradicting_findings=contradicting_findings,
        important_discrepancies=important_discrepancies,
        source_observations=source_observations,
        independence_observations=independence_observations,
        fact_check_observations=fact_check_observations,
        verification_gaps=verification_gaps,
        uncertainty=uncertainty,
        reasoning_steps=reasoning_steps,
        limitations=limitations,
        ai_used=False,
        provider="deterministic_rule_engine",
        model="heuristic-v1",
        fallback_used=True,
    )
