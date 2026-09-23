"""Unit tests for the evidence in-memory cache."""

import asyncio
import pytest
from backend.retrieval.cache import InMemoryCache
from backend.retrieval.models import Evidence, SourceType


@pytest.mark.anyio
async def test_cache_miss():
    """Verify cache returns None on unknown key."""
    cache = InMemoryCache(default_ttl_seconds=60)
    result = await cache.get("gdelt", "unknown query")
    assert result is None


@pytest.mark.anyio
async def test_cache_set_and_hit():
    """Verify storing and retrieving evidence."""
    cache = InMemoryCache(default_ttl_seconds=60)
    ev = Evidence(
        evidence_id="ev_test",
        claim_id="c1",
        title="Sample News",
        url="https://example.com/news",
        provider="gdelt",
        query_used="test query",
    )
    await cache.set("gdelt", "test query", [ev])

    cached = await cache.get("gdelt", "test query")
    assert cached is not None
    assert len(cached) == 1
    assert cached[0].title == "Sample News"


@pytest.mark.anyio
async def test_cache_normalized_key_matching():
    """Verify query casing and extraneous whitespace do not cause cache miss."""
    cache = InMemoryCache(default_ttl_seconds=60)
    ev = Evidence(
        evidence_id="ev_test",
        claim_id="c1",
        title="Title",
        url="https://example.com/1",
        provider="gdelt",
        query_used="q",
    )
    await cache.set("GDELT", "  Stock Market   Rally  ", [ev])

    hit = await cache.get("gdelt", "stock market rally")
    assert hit is not None
    assert len(hit) == 1


@pytest.mark.anyio
async def test_cache_ttl_expiration():
    """Verify items expire after their configured TTL."""
    # 0.1 second TTL
    cache = InMemoryCache(default_ttl_seconds=1)
    ev = Evidence(
        evidence_id="ev_exp",
        claim_id="c1",
        title="Expiring Item",
        url="https://example.com/exp",
        provider="gdelt",
        query_used="q",
    )
    await cache.set("gdelt", "q", [ev], ttl_seconds=0.05)

    # Immediate check
    assert await cache.get("gdelt", "q") is not None

    # Wait for expiry
    await asyncio.sleep(0.08)
    assert await cache.get("gdelt", "q") is None


@pytest.mark.anyio
async def test_cache_clear_and_size():
    """Verify clearing the cache and monitoring size."""
    cache = InMemoryCache(default_ttl_seconds=60)
    assert cache.size() == 0

    ev = Evidence(
        evidence_id="ev_1",
        claim_id="c1",
        title="Item",
        url="https://example.com/item",
        provider="gdelt",
        query_used="q",
    )
    await cache.set("gdelt", "q1", [ev])
    await cache.set("gdelt", "q2", [ev])
    assert cache.size() == 2

    await cache.clear()
    assert cache.size() == 0
    assert await cache.get("gdelt", "q1") is None
