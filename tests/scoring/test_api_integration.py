"""Integration tests verifying Part 9 credibility score outputs via API endpoints."""

import pytest
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


@pytest.fixture
def client():
    return TestClient(app)


def test_api_verify_populates_credibility_score(client, monkeypatch):
    """Verify /api/verify populates claim scores, classifications, breakdowns, and overall document score."""
    mock_article = NormalizedArticle(
        source_type="text",
        original_input="Central government announced a 10 rupee reduction in petrol prices.",
        body="Central government announced a 10 rupee reduction in petrol prices.",
        extraction_method="direct_text",
    )
    monkeypatch.setattr("backend.api.routes.ingest_input", lambda input_type, content: mock_article)

    mock_claim = Claim(
        claim_id="cl_score_test",
        original_text="Central government announced a 10 rupee reduction in petrol prices.",
        normalized_text="Central government announced a 10 rupee reduction in petrol prices.",
        claim_text="Central government announced a 10 rupee reduction in petrol prices.",
        claim_type=ClaimType.POLICY,
        numbers=["10"],
        organizations=["central government"],
        source_sentence="Central government announced a 10 rupee reduction in petrol prices.",
    )
    monkeypatch.setattr("backend.api.routes.extract_claims", lambda article: [mock_claim])

    ev1 = Evidence(
        evidence_id="ev_supp_1",
        claim_id="cl_score_test",
        title="Centre cuts petrol by ₹10",
        url="https://reuters.com/news/1",
        publisher="Reuters",
        domain="reuters.com",
        snippet="Central government announced a 10 rupee reduction in petrol prices today.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="petrol reduction",
    )
    ev2 = Evidence(
        evidence_id="ev_supp_2",
        claim_id="cl_score_test",
        title="Cabinet approves ₹10 fuel reduction",
        url="https://apnews.com/news/2",
        publisher="Associated Press",
        domain="apnews.com",
        snippet="The cabinet has approved a 10 rupee reduction in petrol rates.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="petrol reduction",
    )

    mock_retrieval = RetrievalResult(
        claims=[
            ClaimEvidence(
                claim_id="cl_score_test",
                evidence=[ev1, ev2],
                queries_used=[
                    SearchQuery(
                        query="petrol reduction",
                        query_type=QueryType.DIRECT,
                        claim_id="cl_score_test",
                    )
                ],
            )
        ],
        total_evidence_count=2,
        retrieval_duration_ms=40.0,
    )

    async def mock_retrieve(claims):
        return mock_retrieval

    monkeypatch.setattr("backend.api.routes.retrieve_evidence", mock_retrieve)

    payload = {
        "input_type": "text",
        "content": "Central government announced a 10 rupee reduction in petrol prices.",
    }
    response = client.post("/api/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "claims" in data
    assert len(data["claims"]) == 1
    claim_res = data["claims"][0]

    # Verify score exists and is within [0, 100]
    assert claim_res["score"] is not None
    assert 0 <= claim_res["score"] <= 100
    assert claim_res["classification"] in [
        "Strongly Supported",
        "Mostly Supported",
        "Mixed / Uncertain",
        "Weakly Supported",
        "Strongly Contradicted",
    ]

    # Verify score breakdown is present and populated
    assert len(claim_res["score_breakdown"]) > 0
    for item in claim_res["score_breakdown"]:
        assert "factor" in item
        assert "label" in item
        assert "contribution" in item
        assert "detail" in item

    # Verify overall document credibility
    assert data["overall_score"] is not None
    assert 0 <= data["overall_score"] <= 100
    assert "overall_classification" in data
    assert "overall_summary" in data
