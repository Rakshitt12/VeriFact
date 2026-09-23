"""Unit tests for individual evidence retrieval providers using mocked HTTP clients."""

import httpx
import pytest

from backend.retrieval.base import ProviderError, ProviderTimeout, ProviderUnavailable
from backend.retrieval.models import ProviderStatusCode, SourceType
from backend.retrieval.providers.factcheck_api import GoogleFactCheckProvider
from backend.retrieval.providers.gdelt import GDELTProvider
from backend.retrieval.providers.official_search import OfficialSearchProvider
from backend.retrieval.providers.web_search import WebSearchProvider


# ---------------------------------------------------------------------------
# 1. GDELT Provider Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_gdelt_success():
    """Verify GDELT successful response parsing and normalization."""
    mock_payload = {
        "articles": [
            {
                "url": "https://www.reuters.com/business/tech/india-semiconductor-plant-approved-2026.html",
                "title": "India approves $10 bln semiconductor fabrication initiative",
                "seendate": "20260405T120000Z",
                "domain": "reuters.com",
                "language": "English",
                "sourcecountry": "India",
            }
        ]
    }

    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, json=mock_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider = GDELTProvider(client=client)
        results = await provider.search("semiconductor india", limit=5)

    assert len(results) == 1
    item = results[0]
    assert item.title == "India approves $10 bln semiconductor fabrication initiative"
    assert item.domain == "reuters.com"
    assert item.source_type == SourceType.NEWS
    assert item.provider == "gdelt"
    assert item.published_at == "20260405T120000Z"
    assert item.url.startswith("https://")


@pytest.mark.anyio
async def test_gdelt_empty_or_non_json():
    """Verify GDELT gracefully returns empty list on non-JSON or empty response."""
    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, text="No articles matched your search query", headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider = GDELTProvider(client=client)
        results = await provider.search("completely nonexistent query 12345", limit=5)

    assert results == []


@pytest.mark.anyio
async def test_gdelt_server_error():
    """Verify GDELT HTTP errors trigger ProviderError and safe_search status."""
    async def mock_handler(request: httpx.Request):
        return httpx.Response(500, text="Server Error")

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider = GDELTProvider(client=client)
        results, status = await provider.safe_search("query")

    assert results == []
    assert status.status == ProviderStatusCode.ERROR
    assert "500" in (status.error or "")


# ---------------------------------------------------------------------------
# 2. Google Fact Check Provider Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_factcheck_missing_api_key():
    """Verify unconfigured fact check API key signals ProviderUnavailable."""
    provider = GoogleFactCheckProvider(api_key=None)
    results, status = await provider.safe_search("query")
    assert results == []
    assert status.status == ProviderStatusCode.UNAVAILABLE
    assert "not configured" in (status.error or "").lower()


@pytest.mark.anyio
async def test_factcheck_success():
    """Verify parsing of Fact Check Tools response and metadata extraction."""
    mock_payload = {
        "claims": [
            {
                "text": "The government banned 500 rupee currency notes.",
                "claimReview": [
                    {
                        "publisher": {"name": "PIB Fact Check", "site": "pib.gov.in"},
                        "url": "https://pib.gov.in/factcheck/500-note-ban",
                        "title": "Fact Check: Viral claim about demonetization of 500 notes is fake",
                        "reviewDate": "2026-03-12T00:00:00Z",
                        "textualRating": "Fake",
                        "languageCode": "en",
                    }
                ],
            }
        ]
    }

    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, json=mock_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider = GoogleFactCheckProvider(api_key="fake-test-key", client=client)
        results = await provider.search("500 rupee note ban", limit=5)

    assert len(results) == 1
    ev = results[0]
    assert ev.source_type == SourceType.FACT_CHECK
    assert ev.publisher == "PIB Fact Check"
    assert ev.metadata["verdict"] == "Fake"
    assert "Claim reviewed: 'The government banned 500 rupee currency notes.'" in ev.snippet


# ---------------------------------------------------------------------------
# 3. Web Search Provider Tests (Tavily -> Brave Fallback)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_web_search_unconfigured():
    """Verify WebSearchProvider returns unavailable when no API keys are present."""
    provider = WebSearchProvider(tavily_key=None, brave_key=None)
    results, status = await provider.safe_search("test")
    assert results == []
    assert status.status == ProviderStatusCode.UNAVAILABLE


@pytest.mark.anyio
async def test_web_search_tavily_success():
    """Verify Tavily web search parsing."""
    mock_payload = {
        "results": [
            {
                "title": "ISRO launches navigation satellite into orbit",
                "url": "https://thehindu.com/sci-tech/isro-satellite-orbit.html",
                "content": "The Indian Space Research Organisation has successfully placed...",
                "published_date": "2026-05-10",
                "score": 0.94,
            }
        ]
    }

    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, json=mock_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider = WebSearchProvider(tavily_key="tavily-test-key", client=client)
        results = await provider.search("isro satellite launch", limit=5)

    assert len(results) == 1
    assert results[0].title == "ISRO launches navigation satellite into orbit"
    assert results[0].source_type == SourceType.WEB
    assert results[0].provider == "tavily"


@pytest.mark.anyio
async def test_web_search_fallback_to_brave():
    """Verify fallback from failing Tavily to Brave."""
    brave_payload = {
        "web": {
            "results": [
                {
                    "title": "Brave result for space mission",
                    "url": "https://space.com/india-mission",
                    "description": "Details on the recent mission...",
                    "page_age": "2026-05-11",
                }
            ]
        }
    }

    async def mock_handler(request: httpx.Request):
        if "tavily" in str(request.url):
            return httpx.Response(500, text="Tavily unavailable")
        return httpx.Response(200, json=brave_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        provider = WebSearchProvider(
            tavily_key="tavily-failing-key",
            brave_key="brave-working-key",
            client=client,
        )
        results = await provider.search("space mission", limit=5)

    assert len(results) == 1
    assert results[0].provider == "brave"
    assert results[0].title == "Brave result for space mission"


# ---------------------------------------------------------------------------
# 4. Official Search Provider Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_official_search_provider():
    """Verify official search tags results with SourceType.OFFICIAL and checks domains."""
    mock_payload = {
        "results": [
            {
                "title": "Ministry of Electronics Notification",
                "url": "https://meity.gov.in/notifications/semiconductor.pdf",
                "content": "Official gazette notification regarding incentives...",
                "published_date": "2026-04-01",
            }
        ]
    }

    async def mock_handler(request: httpx.Request):
        return httpx.Response(200, json=mock_payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        web_provider = WebSearchProvider(tavily_key="mock-key", client=client)
        official_prov = OfficialSearchProvider(web_provider=web_provider)
        results = await official_prov.search("semiconductor notification", limit=5)

    assert len(results) == 1
    item = results[0]
    assert item.source_type == SourceType.OFFICIAL
    assert item.provider == "official_search"
    assert item.metadata.get("is_verified_official_domain") is True
