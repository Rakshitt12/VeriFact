"""Evidence comparator coordinating stance classification across evidence and fact-checks."""

from __future__ import annotations

from typing import List, Optional, Tuple

from backend.claim.models import Claim
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.verification.factcheck_mapper import is_fact_check_evidence, map_fact_check_comparison
from backend.verification.models import EvidenceComparison, FactCheckComparison
from backend.verification.stance_detector import classify_evidence_stance


def compare_all_evidence_for_claim(
    claim: Claim,
    evidence_items: List[Evidence],
) -> Tuple[List[EvidenceComparison], List[FactCheckComparison]]:
    """Compare all retrieved evidence items and fact-checks against a single claim.

    Returns:
        Tuple of (List[EvidenceComparison], List[FactCheckComparison])
    """
    comparisons: List[EvidenceComparison] = []
    fact_checks: List[FactCheckComparison] = []

    for ev in evidence_items:
        try:
            if is_fact_check_evidence(ev):
                fc_comp, ev_comp = map_fact_check_comparison(ev, claim.claim_id)
                fact_checks.append(fc_comp)
                comparisons.append(ev_comp)
            else:
                ev_comp = classify_evidence_stance(claim, ev)
                comparisons.append(ev_comp)
        except Exception as exc:
            logger.error("Error comparing evidence item %s: %s", ev.evidence_id, exc, exc_info=True)
            # Create a safe fallback INSUFFICIENT comparison
            comparisons.append(
                EvidenceComparison(
                    evidence_id=ev.evidence_id,
                    claim_id=claim.claim_id,
                    stance="INSUFFICIENT",
                    confidence=0.5,
                    relevance=0.0,
                    reasoning=f"Comparison evaluation failed: {exc}",
                    limitations=["Processing error encountered during comparison"],
                )
            )

    return comparisons, fact_checks
