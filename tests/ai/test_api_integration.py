"""Integration tests verifying Part 8 AI reasoning output via API endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.claim.models import Claim, ClaimType
from backend.ingestion.models import NormalizedArticle
from backend.retrieval.models import ClaimEvidence, Evidence, QueryType, RetrievalResult, SearchQuery, SourceType


@pytest.fixture
def client():
    return TestClient(app)


def _setup_mock_pipeline(monkeypatch):
    mock_article = NormalizedArticle(
        source_type="text",
        original_input="The central bank lowered the base interest rate by 50 basis points today.",
        body="The central bank lowered the base interest rate by 50 basis points today.",
        extraction_method="direct_text",
    )
    monkeypatch.setattr("backend.api.routes.ingest_input", lambda input_type, content: mock_article)

    mock_claim = Claim(
        claim_id="cl_rate_test",
        original_text="The central bank lowered the base interest rate by 50 basis points today.",
        normalized_text="The central bank lowered the base interest rate by 50 basis points today.",
        claim_text="The central bank lowered the base interest rate by 50 basis points today.",
        claim_type=ClaimType.FINANCIAL,
        numbers=["50"],
        organizations=["central bank"],
        source_sentence="The central bank lowered the base interest rate by 50 basis points today.",
    )
    monkeypatch.setattr("backend.api.routes.extract_claims", lambda article: [mock_claim])

    ev_support = Evidence(
        evidence_id="ev_supp_rate",
        claim_id="cl_rate_test",
        title="Central Bank cuts rate by 50 bps",
        url="https://reuters.com/rates/cut",
        publisher="Reuters",
        domain="reuters.com",
        snippet="The central bank lowered the base interest rate by 50 basis points in an emergency meeting.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="central bank interest rate",
    )

    mock_retrieval = RetrievalResult(
        claims=[
            ClaimEvidence(
                claim_id="cl_rate_test",
                evidence=[ev_support],
                queries_used=[
                    SearchQuery(
                        query="central bank rate",
                        query_type=QueryType.DIRECT,
                        claim_id="cl_rate_test",
                    )
                ],
            )
        ],
        total_evidence_count=1,
        retrieval_duration_ms=30.0,
    )

    async def mock_retrieve(claims):
        return mock_retrieval

    monkeypatch.setattr("backend.api.routes.retrieve_evidence", mock_retrieve)


def test_analyze_endpoint_returns_evidence_reasoning(client, monkeypatch):
    _setup_mock_pipeline(monkeypatch)
    payload = {
        "content": "The central bank lowered the base interest rate by 50 basis points today.",
        "input_type": "text",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "claims" in data
    assert len(data["claims"]) > 0

    first_claim = data["claims"][0]
    assert "evidence_reasoning" in first_claim
    reasoning = first_claim["evidence_reasoning"]
    assert reasoning is not None

    assert "summary" in reasoning
    assert isinstance(reasoning["summary"], str)
    assert "uncertainty" in reasoning
    assert reasoning["uncertainty"] in ["LOW", "MEDIUM", "HIGH"]
    assert "key_findings" in reasoning
    assert "verification_gaps" in reasoning
    assert "fallback_used" in reasoning

    # Check verification_gaps on claim
    assert "verification_gaps" in first_claim
    assert isinstance(first_claim["verification_gaps"], list)


def test_verify_endpoint_returns_evidence_reasoning(client, monkeypatch):
    _setup_mock_pipeline(monkeypatch)
    payload = {
        "content": "The central bank lowered the base interest rate by 50 basis points today.",
        "input_type": "text",
    }
    response = client.post("/api/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "claims" in data
    assert len(data["claims"]) > 0

    first_claim = data["claims"][0]
    assert "evidence_reasoning" in first_claim
    assert first_claim["evidence_reasoning"] is not None
    assert "summary" in first_claim["evidence_reasoning"]
