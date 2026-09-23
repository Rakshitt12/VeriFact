"""Test 25: POST /api/analyze and /api/verify return report without breaking fields."""

from fastapi.testclient import TestClient

from backend.claim.models import Claim, ClaimType
from backend.ingestion.models import NormalizedArticle
from backend.main import app
from backend.retrieval.models import (
    ClaimEvidence,
    Evidence,
    QueryType,
    RetrievalResult,
    SearchQuery,
    SourceType,
)


def _mock_pipeline(monkeypatch):
    article = NormalizedArticle(
        source_type="text",
        original_input="The ministry approved a Rs 500 crore project.",
        body="The ministry approved a Rs 500 crore project.",
        title="Ministry approves project",
        extraction_method="direct_text",
    )
    monkeypatch.setattr("backend.api.routes.ingest_input", lambda input_type, content: article)
    claim = Claim(
        claim_id="c1",
        original_text="The ministry approved a Rs 500 crore project.",
        normalized_text="the ministry approved a rs 500 crore project",
        claim_type=ClaimType.ANNOUNCEMENT,
        source_sentence="The ministry approved a Rs 500 crore project.",
    )
    monkeypatch.setattr("backend.api.routes.extract_claims", lambda a: [claim])
    ev = Evidence(
        evidence_id="evidence_003",
        claim_id="c1",
        title="Official statement on project approval",
        url="https://example.gov.in/news/1",
        publisher="Official Source",
        domain="example.gov.in",
        snippet="The ministry approved the project as reported.",
        source_type=SourceType.NEWS,
        provider="test_provider",
        query_used="ministry project",
    )
    retrieval = RetrievalResult(
        claims=[ClaimEvidence(
            claim_id="c1", evidence=[ev],
            queries_used=[SearchQuery(query="ministry project",
                                      query_type=QueryType.DIRECT, claim_id="c1")])],
        total_evidence_count=1,
        retrieval_duration_ms=5.0,
    )

    async def _retrieve(claims):
        return retrieval

    monkeypatch.setattr("backend.api.routes.retrieve_evidence", _retrieve)
    # Force deterministic AI reasoning (no external LLM)
    from backend.ai.models import AIReasoningResult

    async def _reason(**kwargs):
        return AIReasoningResult(summary="Evidence supports approval.",
                                 ai_used=False, fallback_used=True)

    monkeypatch.setattr("backend.api.routes.reason_about_claim_evidence", _reason)


def _assert_report_shape(data):
    # Existing fields intact
    for field in ("request_id", "claims", "overall_score",
                  "overall_classification", "overall_summary", "limitations"):
        assert field in data, f"missing field {field}"
    assert len(data["claims"]) == 1
    # New report field present and structured
    assert data["report"] is not None
    rep = data["report"]
    for field in ("report_id", "generated_at", "methodology_version",
                  "input_summary", "overall_result", "executive_summary",
                  "claims", "evidence_summary", "citations", "limitations"):
        assert field in rep, f"missing report field {field}"
    # Score preservation between legacy + report views
    assert rep["overall_result"]["score"] == data["overall_score"]
    assert rep["overall_result"]["classification"] == data["overall_classification"]
    # Citation integrity: every citation URL must be real evidence
    evidence_urls = {e["url"] for c in data["claims"]
                     for e in c.get("retrieved_evidence", [])}
    for cite in rep["citations"]:
        assert cite["url"] in evidence_urls


def test_analyze_returns_report(monkeypatch):
    _mock_pipeline(monkeypatch)
    client = TestClient(app)
    resp = client.post("/api/analyze", json={
        "input_type": "text",
        "content": "The ministry approved a Rs 500 crore project.",
    })
    assert resp.status_code == 200, resp.text
    _assert_report_shape(resp.json())


def test_verify_returns_report(monkeypatch):
    _mock_pipeline(monkeypatch)
    client = TestClient(app)
    resp = client.post("/api/verify", json={
        "input_type": "text",
        "content": "The ministry approved a Rs 500 crore project.",
    })
    assert resp.status_code == 200, resp.text
    _assert_report_shape(resp.json())
