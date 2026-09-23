"""Unit tests for the RetrievalService orchestration."""

from typing import List
import pytest

from backend.claim.models import Claim, ClaimImportance, ClaimType
from backend.retrieval.base import EvidenceProvider, ProviderError, ProviderUnavailable
from backend.retrieval.cache import InMemoryCache
from backend.retrieval.models import Evidence, ProviderStatusCode, SourceType
from backend.retrieval.service import RetrievalService


class MockProvider(EvidenceProvider):
    def __init__(self, name: str, items: List[Evidence], error_type=None):
        self._name = name
        self._items = items
        self._error_type = error_type
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def search(self, query: str, limit: int = 10) -> List[Evidence]:
        self.call_count += 1
        if self._error_type == "unavailable":
            raise ProviderUnavailable("API Key Missing", self.provider_name)
        if self._error_type == "error":
            raise ProviderError("Network Glitch", self.provider_name)
        return self._items[:limit]


def _make_sample_claim(cid: str, text: str) -> Claim:
    return Claim(
        claim_id=cid,
        original_text=text,
        normalized_text=text,
        claim_type=ClaimType.EVENT,
        importance=ClaimImportance.HIGH,
        entities=[],
        source_sentence=text,
    )


@pytest.mark.anyio
async def test_retrieval_service_multiple_providers_success():
    """Verify results from multiple working providers are combined and deduplicated."""
    e1 = Evidence(
        evidence_id="e1",
        claim_id="",
        title="News Article",
        url="https://news.com/a",
        provider="mock_news",
        query_used="q",
        source_type=SourceType.NEWS,
    )
    e2 = Evidence(
        evidence_id="e2",
        claim_id="",
        title="Fact Check Report",
        url="https://fc.org/b",
        provider="mock_fc",
        query_used="q",
        source_type=SourceType.FACT_CHECK,
    )

    news_prov = MockProvider("mock_news", [e1])
    fc_prov = MockProvider("mock_fc", [e2])
    web_prov = MockProvider("mock_web", [])
    cache = InMemoryCache()

    service = RetrievalService(
        news_provider=news_prov,
        factcheck_provider=fc_prov,
        web_provider=web_prov,
        cache=cache,
    )

    claims = [_make_sample_claim("c1", "India signs landmark trade deal")]
    result = await service.retrieve_evidence(claims)

    assert len(result.claims) == 1
    ce = result.claims[0]
    assert ce.claim_id == "c1"
    assert len(ce.evidence) == 2
    # Verify claim_id was bound
    assert ce.evidence[0].claim_id == "c1"
    assert ce.evidence[1].claim_id == "c1"


@pytest.mark.anyio
async def test_retrieval_service_one_provider_failure():
    """Verify that failure in one provider does not prevent other providers from returning results."""
    e1 = Evidence(
        evidence_id="e1",
        claim_id="",
        title="Valid News Report",
        url="https://reuters.com/item",
        provider="mock_news",
        query_used="q",
    )

    news_prov = MockProvider("mock_news", [e1])
    failing_fc = MockProvider("mock_fc", [], error_type="unavailable")
    cache = InMemoryCache()

    service = RetrievalService(
        news_provider=news_prov,
        factcheck_provider=failing_fc,
        cache=cache,
    )

    claims = [_make_sample_claim("c1", "Test claim")]
    result = await service.retrieve_evidence(claims)

    assert len(result.claims) == 1
    ce = result.claims[0]
    assert len(ce.evidence) == 1
    assert ce.evidence[0].title == "Valid News Report"

    # Status of failing provider recorded
    statuses = {s.provider: s for s in ce.provider_statuses}
    assert "mock_fc" in statuses
    assert statuses["mock_fc"].status == ProviderStatusCode.UNAVAILABLE


@pytest.mark.anyio
async def test_retrieval_service_all_providers_unavailable():
    """Verify that when all providers fail, the service returns empty evidence gracefully."""
    failing_news = MockProvider("news", [], error_type="error")
    failing_fc = MockProvider("fc", [], error_type="unavailable")
    cache = InMemoryCache()

    service = RetrievalService(
        news_provider=failing_news,
        factcheck_provider=failing_fc,
        cache=cache,
    )

    claims = [_make_sample_claim("c1", "Test claim")]
    result = await service.retrieve_evidence(claims)

    assert len(result.claims) == 1
    ce = result.claims[0]
    assert ce.evidence == []
    assert len(ce.provider_statuses) >= 1


@pytest.mark.anyio
async def test_retrieval_service_caching_behavior():
    """Verify that a second query uses cached results and does not hit the provider again."""
    e1 = Evidence(
        evidence_id="e1",
        claim_id="",
        title="Cached News",
        url="https://news.com/cached",
        provider="mock_news",
        query_used="q",
    )
    news_prov = MockProvider("mock_news", [e1])
    cache = InMemoryCache()

    service = RetrievalService(news_provider=news_prov, cache=cache)
    claim = _make_sample_claim("c1", "Consistent Claim Text")

    # First run: cache miss
    await service.retrieve_evidence([claim])
    first_count = news_prov.call_count
    assert first_count > 0

    # Second run: cache hit
    await service.retrieve_evidence([claim])
    assert news_prov.call_count == first_count  # No additional calls made to provider


@pytest.mark.anyio
async def test_retrieval_service_empty_claims():
    """Verify passing empty claims returns empty result immediately."""
    service = RetrievalService()
    result = await service.retrieve_evidence([])
    assert result.claims == []
    assert result.total_evidence_count == 0
