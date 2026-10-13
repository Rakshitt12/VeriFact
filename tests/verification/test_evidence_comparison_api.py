"""Integration tests for Part 7 stance comparison and evidence population in API endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.claim.models import Claim, ClaimType
from backend.ingestion.models import NormalizedArticle
from backend.retrieval.models import ClaimEvidence, Evidence, RetrievalResult, SourceType


@pytest.fixture
def client():
    return TestClient(app)


def test_api_verify_populates_evidence_stances_and_fact_checks(client, monkeypatch):
    """Verify /api/verify populates supporting, contradicting, and fact-check items."""
    mock_article = NormalizedArticle(
        source_type="text",
        original_input="The central government announced a 10 rupee reduction in petrol prices.",
        body="The central government announced a 10 rupee reduction in petrol prices.",
        extraction_method="direct_text",
    )
    monkeypatch.setattr("backend.api.routes.ingest_input", lambda input_type, content: mock_article)

    mock_claim = Claim(
        claim_id="cl_fuel_test",
        original_text="The central government announced a 10 rupee reduction in petrol prices.",
        normalized_text="The central government announced a 10 rupee reduction in petrol prices.",
        claim_type=ClaimType.POLICY,
        numbers=["10"],
        organizations=["central government"],
        source_sentence="The central government announced a 10 rupee reduction in petrol prices.",
    )
    monkeypatch.setattr("backend.api.routes.extract_claims", lambda article: [mock_claim])

    ev_support = Evidence(
        evidence_id="ev_supp_01",
        claim_id="cl_fuel_test",
        title="Centre announces ₹10 reduction in petrol prices",
        url="https://reuters.com/article/fuel-cut",
        publisher="Reuters",
        domain="reuters.com",
        snippet="The central government announced a ₹10 reduction in petrol prices per litre.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="petrol reduction",
    )

    ev_contra = Evidence(
        evidence_id="ev_contra_01",
        claim_id="cl_fuel_test",
        title="Ministry official denies reports of fuel price reduction",
        url="https://thehindu.com/news/fuel",
        publisher="The Hindu",
        domain="thehindu.com",
        snippet="The oil ministry denied reports of fuel price reduction and confirmed rates remain unchanged.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="petrol reduction",
    )

    ev_factcheck = Evidence(
        evidence_id="ev_fc_01",
        claim_id="cl_fuel_test",
        title="Fact Check: Viral claim on fuel cut is False",
        url="https://boomlive.in/fact-check/fuel",
        publisher="Boom Live",
        domain="boomlive.in",
        snippet="Claim: petrol cut by ₹10. Rating: False",
        source_type=SourceType.FACT_CHECK,
        provider="factcheck_api",
        query_used="fuel cut fact check",
        metadata={
            "verdict": "False",
            "rating": "False",
            "explanation": "No formal order has been issued by the ministry.",
        },
    )

    from backend.retrieval.models import QueryType, SearchQuery

    mock_retrieval = RetrievalResult(
        claims=[
            ClaimEvidence(
                claim_id="cl_fuel_test",
                evidence=[ev_support, ev_contra, ev_factcheck],
                queries_used=[
                    SearchQuery(
                        query="petrol reduction",
                        query_type=QueryType.DIRECT,
                        claim_id="cl_fuel_test",
                    )
                ],
            )
        ],
        total_evidence_count=3,
        retrieval_duration_ms=45.0,
    )

    async def mock_retrieve(claims):
        return mock_retrieval

    monkeypatch.setattr("backend.api.routes.retrieve_evidence", mock_retrieve)

    payload = {
        "input_type": "text",
        "content": "The central government announced a 10 rupee reduction in petrol prices.",
    }
    response = client.post("/api/verify", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert len(data["claims"]) == 1
    claim_res = data["claims"][0]

    # Verify supporting evidence list
    assert len(claim_res["supporting_evidence"]) == 1
    assert claim_res["supporting_evidence"][0]["evidence_id"] == "ev_supp_01"
    assert claim_res["supporting_evidence"][0]["stance"] == "SUPPORTING"
    assert claim_res["supporting_evidence"][0]["publisher"] == "Reuters"

    # Verify contradicting evidence list (from polarity denial)
    assert len(claim_res["contradicting_evidence"]) >= 1
    contra_ids = [e["evidence_id"] for e in claim_res["contradicting_evidence"]]
    assert "ev_contra_01" in contra_ids or "ev_fc_01" in contra_ids

    # Verify fact-check list
    assert len(claim_res["fact_checks"]) == 1
    assert claim_res["fact_checks"][0]["fact_checker"] == "Boom Live"
    assert claim_res["fact_checks"][0]["verdict"] == "False"
