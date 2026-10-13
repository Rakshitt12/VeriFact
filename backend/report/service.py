"""Facade service for VerificationReport generation."""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.ai.models import AIReasoningResult
from backend.claim.models import Claim
from backend.ingestion.models import NormalizedArticle
from backend.report.models import VerificationReport
from backend.report.report_generator import ReportGenerator
from backend.retrieval.models import Evidence
from backend.scoring.models import ClaimCredibilityScore, DocumentCredibilityScore
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
)


class VerificationReportService:
    """Public facade for generating explainable verification reports.

    Instantiate once at module level and call ``generate_report`` per request.
    """

    def __init__(self) -> None:
        self._generator = ReportGenerator()

    def generate_report(
        self,
        article: NormalizedArticle,
        extracted_claims: List[Claim],
        all_evidence: Dict[str, List[Evidence]],
        all_source_analyses: Dict[str, List[SourceAnalysis]],
        all_independence: Dict[str, ClaimIndependenceResult],
        all_comparisons: Dict[str, ClaimEvidenceComparisonResult],
        all_claim_scores: Dict[str, ClaimCredibilityScore],
        all_ai_reasoning: Dict[str, AIReasoningResult],
        doc_cred_score: Optional[DocumentCredibilityScore],
        request_type: str = "text",
    ) -> VerificationReport:
        """Generate and return a complete VerificationReport for API or UI consumption."""
        return self._generator.build_report(
            article=article,
            extracted_claims=extracted_claims,
            all_evidence=all_evidence,
            all_source_analyses=all_source_analyses,
            all_independence=all_independence,
            all_comparisons=all_comparisons,
            all_claim_scores=all_claim_scores,
            all_ai_reasoning=all_ai_reasoning,
            doc_cred_score=doc_cred_score,
            request_type=request_type,
        )
