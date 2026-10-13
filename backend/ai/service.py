"""Service facade for AI Evidence Reasoning and fallback synthesis."""

from __future__ import annotations

from typing import List, Optional

from backend.ai.evidence_reasoner import EvidenceReasoner
from backend.ai.models import AIReasoningResult
from backend.claim.models import Claim
from backend.retrieval.models import Evidence
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
)


class AIReasoningService:
    """Service facade managing AI reasoning requests."""

    _default_reasoner = EvidenceReasoner()

    @classmethod
    async def reason_about_evidence(
        cls,
        claim: Claim,
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
    ) -> AIReasoningResult:
        """Asynchronously reason over the supplied evidence or engage fallback."""
        return await cls._default_reasoner.reason(
            claim=claim,
            evidence_items=evidence_items,
            source_analyses=source_analyses,
            independence_result=independence_result,
            comparison_result=comparison_result,
        )

    @classmethod
    def reason_about_evidence_sync(
        cls,
        claim: Claim,
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
    ) -> AIReasoningResult:
        """Synchronously reason over the supplied evidence or engage fallback."""
        return cls._default_reasoner.reason_sync(
            claim=claim,
            evidence_items=evidence_items,
            source_analyses=source_analyses,
            independence_result=independence_result,
            comparison_result=comparison_result,
        )


async def reason_about_claim_evidence(
    claim: Claim,
    evidence_items: List[Evidence],
    source_analyses: Optional[List[SourceAnalysis]] = None,
    independence_result: Optional[ClaimIndependenceResult] = None,
    comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
) -> AIReasoningResult:
    """Convenience async helper delegating to AIReasoningService."""
    return await AIReasoningService.reason_about_evidence(
        claim=claim,
        evidence_items=evidence_items,
        source_analyses=source_analyses,
        independence_result=independence_result,
        comparison_result=comparison_result,
    )


def reason_about_claim_evidence_sync(
    claim: Claim,
    evidence_items: List[Evidence],
    source_analyses: Optional[List[SourceAnalysis]] = None,
    independence_result: Optional[ClaimIndependenceResult] = None,
    comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
) -> AIReasoningResult:
    """Convenience synchronous helper delegating to AIReasoningService."""
    return AIReasoningService.reason_about_evidence_sync(
        claim=claim,
        evidence_items=evidence_items,
        source_analyses=source_analyses,
        independence_result=independence_result,
        comparison_result=comparison_result,
    )
