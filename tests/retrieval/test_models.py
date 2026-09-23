"""Unit tests for retrieval models and enums."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.retrieval.models import (
    ClaimEvidence,
    Evidence,
    ProviderStatus,
    ProviderStatusCode,
    QueryType,
    RetrievalResult,
    SearchQuery,
    SourceType,
)


def test_source_type_enum():
    """Verify supported source types."""
    assert SourceType.NEWS == "NEWS"
    assert SourceType.FACT_CHECK == "FACT_CHECK"
    assert SourceType.OFFICIAL == "OFFICIAL"
    assert SourceType.PRIMARY_DOCUMENT == "PRIMARY_DOCUMENT"
    assert SourceType.ACADEMIC == "ACADEMIC"
    assert SourceType.WEB == "WEB"
    assert SourceType.OTHER == "OTHER"


def test_query_type_enum():
    """Verify supported query types."""
    assert QueryType.DIRECT == "DIRECT"
    assert QueryType.ENTITY_FOCUSED == "ENTITY_FOCUSED"
    assert QueryType.NUMERIC == "NUMERIC"
    assert QueryType.DATE_FOCUSED == "DATE_FOCUSED"
    assert QueryType.FACT_CHECK == "FACT_CHECK"
    assert QueryType.OFFICIAL == "OFFICIAL"


def test_evidence_model_valid():
    """Verify valid Evidence instance creation with required and optional fields."""
    ev = Evidence(
        evidence_id="ev_12345",
        claim_id="claim_001",
        title="RBI keeps repo rate unchanged at 6.5%",
        url="https://example.com/news/rbi-rate",
        canonical_url="https://example.com/news/rbi-rate",
        publisher="The Economic Times",
        domain="economictimes.indiatimes.com",
        author="John Doe",
        published_at="2026-04-05T10:00:00Z",
        snippet="The Reserve Bank of India has maintained the benchmark repo rate at 6.5 percent.",
        content=None,
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="RBI repo rate unchanged",
        metadata={"category": "finance"},
    )
    assert ev.evidence_id == "ev_12345"
    assert ev.source_type == SourceType.NEWS
    assert ev.provider == "gdelt"
    assert ev.retrieved_at is not None
    assert ev.metadata["category"] == "finance"


def test_evidence_model_missing_required_fields():
    """Verify validation error when required fields are omitted."""
    with pytest.raises(ValidationError):
        Evidence(
            # Missing evidence_id, claim_id, title, url, provider, query_used
            publisher="Unknown",
        )


def test_search_query_model():
    """Verify SearchQuery model validation."""
    sq = SearchQuery(
        query="Tesla announces factory in India",
        query_type=QueryType.DIRECT,
        claim_id="claim_100",
    )
    assert sq.query == "Tesla announces factory in India"
    assert sq.query_type == QueryType.DIRECT
    assert sq.claim_id == "claim_100"


def test_provider_status_model():
    """Verify ProviderStatus recording."""
    status = ProviderStatus(
        provider="gdelt",
        status=ProviderStatusCode.SUCCESS,
        results_count=8,
        duration_ms=210.5,
    )
    assert status.status == ProviderStatusCode.SUCCESS
    assert status.results_count == 8
    assert status.error is None


def test_retrieval_result_model():
    """Verify top-level RetrievalResult packaging."""
    ev = Evidence(
        evidence_id="ev_001",
        claim_id="c1",
        title="Title",
        url="https://news.com/1",
        provider="gdelt",
        query_used="test",
    )
    ce = ClaimEvidence(
        claim_id="c1",
        evidence=[ev],
        queries_used=[SearchQuery(query="test", query_type=QueryType.DIRECT, claim_id="c1")],
        provider_statuses=[
            ProviderStatus(provider="gdelt", status=ProviderStatusCode.SUCCESS, results_count=1)
        ],
        total_retrieved=1,
    )
    res = RetrievalResult(
        claims=[ce],
        total_evidence_count=1,
        retrieval_duration_ms=45.2,
    )
    assert len(res.claims) == 1
    assert res.total_evidence_count == 1
    assert res.claims[0].evidence[0].title == "Title"
