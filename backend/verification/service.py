"""Service facade for duplicate detection, syndication identification, and source independence."""

from __future__ import annotations

from typing import List, Optional

from backend.claim.models import Claim
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.sources.models import SourceAnalysis
from backend.verification.consensus_analyzer import analyze_consensus
from backend.verification.evidence_comparator import compare_all_evidence_for_claim
from backend.verification.independence_analyzer import cluster_and_analyze_independence
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    EvidenceCluster,
)


class VerificationService:
    """Service orchestrating evidence relationship analysis, clustering, and stance comparison."""

    @staticmethod
    def analyze_evidence_independence(
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]] = None,
        claim_id: str = "",
    ) -> ClaimIndependenceResult:
        """Analyze duplicates, detect syndications, group into clusters, and count independent sources."""
        logger.info(
            "Analyzing evidence independence for claim %s across %d evidence item(s)",
            claim_id,
            len(evidence_items),
        )

        result = cluster_and_analyze_independence(
            evidence_items=evidence_items,
            source_analyses=source_analyses,
            claim_id=claim_id,
        )

        logger.info(
            "Claim %s: %d total evidence items resolved into %d independent cluster(s)",
            claim_id,
            result.total_evidence_count,
            result.independent_source_count,
        )

        return result

    @staticmethod
    def compare_evidence(
        claim: Claim,
        evidence_items: List[Evidence],
        clusters: Optional[List[EvidenceCluster]] = None,
    ) -> ClaimEvidenceComparisonResult:
        """Evaluate evidence stances, match claim aspects, detect discrepancies, and compute consensus."""
        logger.info(
            "Comparing %d evidence items against claim %s",
            len(evidence_items),
            claim.claim_id,
        )

        comparisons, fact_checks = compare_all_evidence_for_claim(
            claim=claim,
            evidence_items=evidence_items,
        )

        result = analyze_consensus(
            claim_id=claim.claim_id,
            comparisons=comparisons,
            fact_checks=fact_checks,
            clusters=clusters or [],
        )

        logger.info(
            "Claim %s comparison completed: %d supporting (%d independent), %d contradicting (%d independent), agreement ratio: %.2f",
            claim.claim_id,
            result.supporting_count,
            result.independent_supporting_count,
            result.contradicting_count,
            result.independent_contradicting_count,
            result.agreement_ratio,
        )

        return result


# Module-level convenience functions
def analyze_evidence_independence(
    evidence_items: List[Evidence],
    source_analyses: Optional[List[SourceAnalysis]] = None,
    claim_id: str = "",
) -> ClaimIndependenceResult:
    """Convenience function delegating to VerificationService."""
    return VerificationService.analyze_evidence_independence(
        evidence_items=evidence_items,
        source_analyses=source_analyses,
        claim_id=claim_id,
    )


def compare_evidence_for_claim(
    claim: Claim,
    evidence_items: List[Evidence],
    clusters: Optional[List[EvidenceCluster]] = None,
) -> ClaimEvidenceComparisonResult:
    """Convenience function delegating to VerificationService.compare_evidence."""
    return VerificationService.compare_evidence(
        claim=claim,
        evidence_items=evidence_items,
        clusters=clusters,
    )
