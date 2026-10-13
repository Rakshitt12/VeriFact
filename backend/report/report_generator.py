"""Orchestrator that assembles a complete VerificationReport from pipeline outputs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.ai.models import AIReasoningResult
from backend.claim.models import Claim, ClaimImportance
from backend.config.scoring_config import SCORING_METHODOLOGY_VERSION
from backend.ingestion.models import NormalizedArticle
from backend.report.citation_manager import CitationManager
from backend.report.evidence_formatter import EvidenceFormatter
from backend.report.models import (
    CitationItem,
    ClaimVerificationReport,
    EvidenceSummary,
    ReportInputSummary,
    ReportOverallResult,
    VerificationReport,
)
from backend.report.summary_generator import SummaryGenerator
from backend.retrieval.models import Evidence
from backend.scoring.models import ClaimCredibilityScore, DocumentCredibilityScore
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
)

_IMPORTANCE_ORDER: Dict[str, int] = {
    ClaimImportance.HIGH.value: 0,
    ClaimImportance.MEDIUM.value: 1,
    ClaimImportance.LOW.value: 2,
}


class ReportGenerator:
    """Orchestrates CitationManager, EvidenceFormatter, and SummaryGenerator
    to produce a fully structured, auditable VerificationReport."""

    def build_report(
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
        """Build and return a complete VerificationReport.

        Claims are ordered deterministically: HIGH importance first, then MEDIUM,
        then LOW. Within each tier the original extraction order is preserved.
        """
        report_id = str(uuid.uuid4())
        generated_at = datetime.now(timezone.utc).isoformat()

        # --- Input summary ---
        input_summary = ReportInputSummary(
            input_type=request_type,
            headline=article.title,
            source_url=article.url,
            text_length=len(article.body or ""),
            claim_count=len(extracted_claims),
            verification_timestamp=generated_at,
        )

        # --- Overall result ---
        if doc_cred_score:
            overall_score = doc_cred_score.overall_score
            overall_classification = doc_cred_score.overall_classification
            overall_doc_summary = doc_cred_score.summary
        else:
            overall_score = None
            overall_classification = "INSUFFICIENT EVIDENCE"
            overall_doc_summary = (
                "No discrete verifiable factual assertions detected in submitted content."
            )

        overall_result = ReportOverallResult(
            score=overall_score,
            classification=overall_classification,
            summary=overall_doc_summary,
        )

        # --- Sort claims: importance tier first, then extraction index ---
        sorted_claims = sorted(
            enumerate(extracted_claims),
            key=lambda pair: (
                _IMPORTANCE_ORDER.get(pair[1].importance.value, 1),
                pair[0],  # original extraction index
            ),
        )

        # --- Build per-claim citation manager to collect all URLs ---
        citation_manager = CitationManager()

        # --- Build per-claim reports ---
        claim_reports: List[ClaimVerificationReport] = []
        formatter = EvidenceFormatter()

        for _orig_idx, claim in sorted_claims:
            claim_id = claim.claim_id
            ev_items = all_evidence.get(claim_id, [])
            source_analyses = all_source_analyses.get(claim_id, [])
            independence_result = all_independence.get(claim_id)
            comparison_result = all_comparisons.get(claim_id)
            claim_score = all_claim_scores.get(claim_id)
            ai_reasoning = all_ai_reasoning.get(claim_id)

            # Register evidence URLs in the citation manager
            citation_manager.register_evidence_batch(ev_items)

            # Format evidence cards grouped by stance
            cards_by_stance = formatter.format_evidence_cards(
                evidence_items=ev_items,
                comparison_result=comparison_result,
                source_analyses=source_analyses,
                independence_result=independence_result,
            )

            # Build evidence summary counts
            evidence_summary = formatter.build_evidence_summary(
                evidence_items=ev_items,
                comparison_result=comparison_result,
                independence_result=independence_result,
            )

            # Format supplementary data
            fact_check_cards = formatter.format_fact_checks(comparison_result)
            discrepancy_cards = formatter.format_discrepancies(comparison_result)
            source_analysis_cards = formatter.format_source_analyses(source_analyses)
            independence_summary = formatter.format_independence(independence_result)
            score_breakdown = formatter.format_score_breakdown(claim_score)
            ai_reasoning_report = formatter.format_ai_reasoning(ai_reasoning)

            # Verification gaps from AI reasoning
            verification_gaps: List[str] = (
                ai_reasoning.verification_gaps if ai_reasoning else []
            )

            # Insufficient-evidence flag
            is_insufficient = (
                claim_score.is_insufficient_evidence
                if claim_score
                else True
            )

            classification = (
                claim_score.classification
                if claim_score
                else "INSUFFICIENT EVIDENCE"
            )
            score = claim_score.score if claim_score else None

            # Deterministic claim summary
            summary = SummaryGenerator.generate_claim_summary(
                classification=classification,
                score=score,
                is_insufficient_evidence=is_insufficient,
                independent_sources=(
                    independence_result.independent_source_count
                    if independence_result
                    else 0
                ),
                supporting_count=evidence_summary.supporting_count,
                contradicting_count=evidence_summary.contradicting_count,
                discrepancy_count=len(discrepancy_cards),
                fact_check_count=len(fact_check_cards),
            )

            # Compile claim-level limitations
            limitations: List[str] = []
            if is_insufficient:
                limitations.append(
                    "Insufficient independent corroboration found for reliable scoring."
                )
            if ai_reasoning and ai_reasoning.fallback_used:
                limitations.append(
                    "AI reasoning used a deterministic fallback (no live AI call was made)."
                )

            claim_reports.append(
                ClaimVerificationReport(
                    claim_id=claim_id,
                    claim_text=claim.original_text,
                    claim_type=claim.claim_type.value,
                    importance=claim.importance.value,
                    score=score,
                    classification=classification,
                    is_insufficient_evidence=is_insufficient,
                    summary=summary,
                    evidence_summary=evidence_summary,
                    supporting_evidence=cards_by_stance.get("SUPPORTING", []),
                    contradicting_evidence=cards_by_stance.get("CONTRADICTING", []),
                    neutral_evidence=cards_by_stance.get("NEUTRAL", []),
                    insufficient_evidence=cards_by_stance.get("INSUFFICIENT", []),
                    fact_checks=fact_check_cards,
                    discrepancies=discrepancy_cards,
                    verification_gaps=verification_gaps,
                    source_analysis=source_analysis_cards,
                    independence_analysis=independence_summary,
                    score_breakdown=score_breakdown,
                    ai_reasoning=ai_reasoning_report,
                    limitations=limitations,
                )
            )

        # --- Aggregate document-level evidence summary ---
        doc_evidence_summary = self._aggregate_evidence_summary(claim_reports)

        # --- Executive summary ---
        executive_summary = SummaryGenerator.generate_executive_summary(
            claim_reports=claim_reports,
            overall_score=overall_score,
            overall_classification=overall_classification,
        )

        # --- Citations ---
        citations = citation_manager.build_citation_list()

        # --- Document-level limitations ---
        doc_limitations = [
            "Credibility score is deterministic and reflects currently indexed and retrieved evidence.",
            "This system cannot access paywalled content.",
            "Evidence retrieval is limited to sources indexed by configured providers.",
            "The credibility score represents evidence strength, not a guaranteed truth determination.",
        ]

        return VerificationReport(
            report_id=report_id,
            generated_at=generated_at,
            methodology_version=SCORING_METHODOLOGY_VERSION,
            input_summary=input_summary,
            overall_result=overall_result,
            executive_summary=executive_summary,
            claims=claim_reports,
            evidence_summary=doc_evidence_summary,
            citations=citations,
            limitations=doc_limitations,
        )

    @staticmethod
    def _aggregate_evidence_summary(
        claim_reports: List[ClaimVerificationReport],
    ) -> EvidenceSummary:
        """Aggregate evidence counts across all claim reports for the document level."""
        total = sum(c.evidence_summary.total_retrieved for c in claim_reports)
        supp = sum(c.evidence_summary.supporting_count for c in claim_reports)
        contra = sum(c.evidence_summary.contradicting_count for c in claim_reports)
        neutral = sum(c.evidence_summary.neutral_count for c in claim_reports)
        insuf = sum(c.evidence_summary.insufficient_count for c in claim_reports)
        indep = sum(c.evidence_summary.independent_source_count for c in claim_reports)
        dup = sum(c.evidence_summary.duplicate_count for c in claim_reports)
        syn = sum(c.evidence_summary.syndicated_count for c in claim_reports)
        fc = sum(c.evidence_summary.fact_check_count for c in claim_reports)
        return EvidenceSummary(
            total_retrieved=total,
            supporting_count=supp,
            contradicting_count=contra,
            neutral_count=neutral,
            insufficient_count=insuf,
            independent_source_count=indep,
            duplicate_count=dup,
            syndicated_count=syn,
            fact_check_count=fc,
        )
