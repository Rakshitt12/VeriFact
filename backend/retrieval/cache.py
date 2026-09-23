"""Lightweight in-memory cache for evidence retrieval results.

Caches query results by provider and normalized query with a configurable TTL.
Designed to be interchangeable with a Redis or database cache backend later.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple
from backend.retrieval.models import Evidence
from backend.config.settings import settings


class InMemoryCache:
    """In-memory cache with expiration support."""

    def __init__(self, default_ttl_seconds: Optional[int] = None) -> None:
        self.default_ttl = (
            default_ttl_seconds
            if default_ttl_seconds is not None
            else settings.RETRIEVAL_CACHE_TTL_SECONDS
        )
        # key -> (expiry_timestamp, list[Evidence])
        self._store: Dict[str, Tuple[float, List[Evidence]]] = {}

    @staticmethod
    def build_key(provider: str, query: str) -> str:
        """Construct normalized cache key."""
        clean_q = " ".join(query.lower().strip().split())
        return f"{provider.lower()}::{clean_q}"

    async def get(self, provider: str, query: str) -> Optional[List[Evidence]]:
        """Retrieve cached evidence if present and unexpired."""
        key = self.build_key(provider, query)
        entry = self._store.get(key)
        if entry is None:
            return None

        expiry, data = entry
        if time.time() > expiry:
            # expired, clean up
            del self._store[key]
            return None

        return data

    async def set(
        self,
        provider: str,
        query: str,
        results: List[Evidence],
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Store evidence in cache with expiry timestamp."""
        key = self.build_key(provider, query)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = time.time() + ttl
        self._store[key] = (expiry, results)

    async def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    def size(self) -> int:
        """Return count of cached entries (including potentially expired ones)."""
        return len(self._store)
