"""Service facade + serialization tests (spec section 40)."""

from backend.report.service import VerificationReportService
from tests.report.conftest import (
    make_ai_reasoning,
    make_article,
    make_claim,
    make_claim_score,
    make_comparison,
    make_doc_score,
    make_evidence,
    make_independence,
    make_source_analysis,
)


def test_service_generates_serializable_report():
    svc = VerificationReportService()
    claim = make_claim()
    report = svc.generate_report(
        article=make_article(),
        extracted_claims=[claim],
        all_evidence={claim.claim_id: [make_evidence()]},
        all_source_analyses={claim.claim_id: [make_source_analysis()]},
        all_independence={claim.claim_id: make_independence()},
        all_comparisons={claim.claim_id: make_comparison()},
        all_claim_scores={claim.claim_id: make_claim_score()},
        all_ai_reasoning={claim.claim_id: make_ai_reasoning()},
        doc_cred_score=make_doc_score(claim_scores=[make_claim_score()]),
        request_type="text",
    )
    dumped = report.model_dump()
    assert set(dumped) >= {"report_id", "generated_at", "methodology_version",
                           "input_summary", "overall_result", "executive_summary",
                           "claims", "evidence_summary", "citations", "limitations"}
    # Input summary preserves original text length + claim count
    assert dumped["input_summary"]["claim_count"] == 1
    assert dumped["input_summary"]["input_type"] == "text"
    # Source links preserved verbatim for frontend click-through
    assert dumped["citations"][0]["url"] == "https://example.gov.in/news/1"
