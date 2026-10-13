"""Test 1-2: Report model validation and missing optional fields."""

from backend.report.models import EvidenceCard, VerificationReport
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
from backend.report.service import VerificationReportService


def _build_minimal_report():
    svc = VerificationReportService()
    article = make_article()
    claim = make_claim()
    ev = make_evidence()
    return svc.generate_report(
        article=article,
        extracted_claims=[claim],
        all_evidence={claim.claim_id: [ev]},
        all_source_analyses={claim.claim_id: [make_source_analysis()]},
        all_independence={claim.claim_id: make_independence()},
        all_comparisons={claim.claim_id: make_comparison()},
        all_claim_scores={claim.claim_id: make_claim_score()},
        all_ai_reasoning={claim.claim_id: make_ai_reasoning()},
        doc_cred_score=make_doc_score(claim_scores=[make_claim_score()]),
        request_type="text",
    )


def test_report_model_validation():
    """Test 1 — Valid report passes Pydantic validation and serializes."""
    report = _build_minimal_report()
    assert isinstance(report, VerificationReport)
    dumped = report.model_dump()
    assert dumped["report_id"]
    assert dumped["overall_result"]["score"] == 76
    # Re-validate from dumped dict
    assert VerificationReport.model_validate(dumped).report_id == report.report_id


def test_missing_optional_fields():
    """Test 2 — Missing publisher/snippet/date/source analysis must not crash."""
    from backend.retrieval.models import Evidence, SourceType
    svc = VerificationReportService()
    article = make_article()
    claim = make_claim()
    sparse = Evidence(
        evidence_id="ev_sparse",
        claim_id=claim.claim_id,
        title="Sparse item",
        url="https://unknown.example/sparse",
        publisher=None,
        domain=None,
        snippet=None,
        published_at=None,
        source_type=SourceType.WEB,
        provider="test_provider",
        query_used="ministry project",
    )
    report = svc.generate_report(
        article=article,
        extracted_claims=[claim],
        all_evidence={claim.claim_id: [sparse]},
        all_source_analyses={claim.claim_id: []},
        all_independence={claim.claim_id: make_independence()},
        all_comparisons={claim.claim_id: make_comparison(evidence_id="ev_sparse")},
        all_claim_scores={claim.claim_id: make_claim_score()},
        all_ai_reasoning={claim.claim_id: make_ai_reasoning()},
        doc_cred_score=make_doc_score(claim_scores=[make_claim_score()]),
        request_type="text",
    )
    assert len(report.claims) == 1
    card = report.claims[0].neutral_evidence + report.claims[0].supporting_evidence
    assert len(card) == 1
    assert isinstance(card[0], EvidenceCard)
