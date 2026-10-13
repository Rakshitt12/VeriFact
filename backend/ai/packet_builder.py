"""Constructs strictly bounded, privacy-sanitized evidence packets for AI reasoning."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.claim.models import Claim
from backend.config.scoring_config import (
    MAX_CHARS_PER_EVIDENCE,
    MAX_EVIDENCE_ITEMS_FOR_REASONING,
    MAX_FACT_CHECKS_FOR_REASONING,
    MAX_TOTAL_EVIDENCE_CHARS,
)
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    EvidenceComparison,
    EvidenceStance,
)
from backend.ai.models import EvidencePacket, EvidencePacketItem


def build_evidence_packet(
    claim: Claim,
    evidence_items: List[Evidence],
    source_analyses: Optional[List[SourceAnalysis]] = None,
    independence_result: Optional[ClaimIndependenceResult] = None,
    comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
) -> EvidencePacket:
    """Build a character-bounded and analytically ordered EvidencePacket for AI reasoning.

    Orders evidence by analytical priority:
      1. Fact-checks and primary sources
      2. Clear supporting/contradicting evidence
      3. Evidence with discrepancies
      4. Contextual/neutral items
    """
    source_analyses = source_analyses or []
    sa_by_id = {sa.evidence_id: sa for sa in source_analyses}
    
    comparisons = comparison_result.comparisons if comparison_result else []
    comp_by_id = {c.evidence_id: c for c in comparisons}

    clusters = independence_result.clusters if independence_result else []
    cluster_by_eid: Dict[str, str] = {}
    for cl in clusters:
        for eid in cl.evidence_ids:
            cluster_by_eid[eid] = cl.cluster_id

    # 1. Score priority for ordering
    def _evidence_priority(ev: Evidence) -> int:
        comp = comp_by_id.get(ev.evidence_id)
        sa = sa_by_id.get(ev.evidence_id)
        is_fc = ev.source_type.value == "FACT_CHECK" or (comp and comp.fact_check_rating is not None)
        is_primary = sa.primary_reporting.present if sa else False

        if is_fc:
            return 100
        if is_primary:
            return 90
        if comp:
            if comp.discrepancies:
                return 80
            if comp.stance in (EvidenceStance.SUPPORTING, EvidenceStance.CONTRADICTING):
                return 70
            if comp.stance == EvidenceStance.NEUTRAL:
                return 40
        return 20

    sorted_evidence = sorted(evidence_items, key=_evidence_priority, reverse=True)

    # 2. Build packet items subject to limits
    packet_items: List[EvidencePacketItem] = []
    total_chars = 0
    fact_check_count = 0

    for ev in sorted_evidence:
        if len(packet_items) >= MAX_EVIDENCE_ITEMS_FOR_REASONING:
            break

        is_fc = ev.source_type.value == "FACT_CHECK"
        if is_fc:
            if fact_check_count >= MAX_FACT_CHECKS_FOR_REASONING:
                continue
            fact_check_count += 1

        comp = comp_by_id.get(ev.evidence_id)
        sa = sa_by_id.get(ev.evidence_id)

        raw_snippet = ev.snippet or getattr(ev, "content", "") or ""
        # Sanitize prompt injection attempts and pseudo-closing tags
        raw_snippet = re.sub(r"</?UNTRUSTED_EXTERNAL_EVIDENCE_PACKET>", "", raw_snippet, flags=re.IGNORECASE)
        raw_snippet = re.sub(r"<script[\s\S]*?</script>", "", raw_snippet, flags=re.IGNORECASE)

        # Deterministic truncation
        if len(raw_snippet) > MAX_CHARS_PER_EVIDENCE:
            trunc_marker = " ... [truncated]"
            snippet = raw_snippet[: MAX_CHARS_PER_EVIDENCE - len(trunc_marker)].rstrip() + trunc_marker
        else:
            snippet = raw_snippet.strip()

        if total_chars + len(snippet) > MAX_TOTAL_EVIDENCE_CHARS and len(packet_items) >= 2:
            break

        total_chars += len(snippet)

        packet_items.append(
            EvidencePacketItem(
                evidence_id=ev.evidence_id,
                title=ev.title,
                publisher=ev.publisher or ev.domain or "Unknown",
                domain=ev.domain,
                url=ev.url,
                publication_date=ev.published_at,
                snippet=snippet,
                source_category=sa.source_category.value if sa else "unknown",
                source_reliability=sa.reliability_label.value.lower() if sa else "unknown",
                cluster_id=cluster_by_eid.get(ev.evidence_id),
                independence_status=(
                    "LIKELY_INDEPENDENT"
                    if not cluster_by_eid.get(ev.evidence_id)
                    else "CLUSTERED"
                ),
                stance=comp.stance.value if comp else "NEUTRAL",
                stance_confidence=comp.confidence if comp else 0.7,
                relevance=comp.relevance if comp else 0.7,
                supporting_points=comp.supporting_points if comp else [],
                contradicting_points=comp.contradicting_points if comp else [],
                discrepancies=[
                    f"{d.aspect}: claim asserts '{d.claim_value}', evidence reports '{d.evidence_value}'"
                    for d in (comp.discrepancies if comp else [])
                ],
                is_fact_check=is_fc,
                fact_check_rating=comp.fact_check_rating if comp else None,
            )
        )

    # 3. Summaries of fact checks, discrepancies, clusters
    fact_checks_summary = []
    if comparison_result and comparison_result.fact_checks:
        for fc in comparison_result.fact_checks:
            fact_checks_summary.append({
                "fact_check_id": fc.fact_check_id,
                "fact_checker": fc.fact_checker,
                "verdict": fc.verdict_normalized,
                "raw_rating": fc.raw_rating,
                "explanation": fc.explanation,
                "url": fc.url,
            })

    discrepancies_summary = []
    if comparison_result and comparison_result.key_discrepancies:
        for d in comparison_result.key_discrepancies:
            discrepancies_summary.append({
                "type": d.discrepancy_type.value,
                "aspect": d.aspect,
                "claim_value": d.claim_value,
                "evidence_value": d.evidence_value,
                "severity": d.severity,
            })

    clusters_summary = []
    if clusters:
        for cl in clusters:
            clusters_summary.append({
                "cluster_id": cl.cluster_id,
                "cluster_type": cl.cluster_type.value,
                "size": len(cl.evidence_ids),
                "representative_id": cl.representative_evidence_id,
            })

    claim_aspects = {
        "persons": claim.persons,
        "organizations": claim.organizations,
        "locations": claim.locations,
        "dates": claim.dates,
        "numbers": claim.numbers,
        "claim_type": claim.claim_type.value,
    }

    return EvidencePacket(
        claim_id=claim.claim_id,
        claim_text=claim.original_text,
        claim_aspects=claim_aspects,
        independent_source_count=(
            independence_result.independent_source_count if independence_result else len(packet_items)
        ),
        evidence=packet_items,
        fact_checks=fact_checks_summary,
        discrepancies=discrepancies_summary,
        clusters_summary=clusters_summary,
    )
