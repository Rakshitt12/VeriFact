"""General web search provider with Tavily -> Brave automatic fallback.

Searches the open web for corroborating or refuting articles and reports.
Degrades gracefully to an unavailable status if neither provider key is configured.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional
from urllib.parse import urlparse
import httpx

from backend.config.settings import settings
from backend.logging_config import logger
from backend.retrieval.base import EvidenceProvider, ProviderError, ProviderTimeout, ProviderUnavailable
from backend.retrieval.deduplicator import canonicalize_url
from backend.retrieval.models import Evidence, SourceType


class WebSearchProvider(EvidenceProvider):
    """Web search provider supporting Tavily with Brave Search fallback."""

    TAVILY_URL = "https://api.tavily.com/search"
    BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        tavily_key: Optional[str] = None,
        brave_key: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.tavily_key = tavily_key or settings.TAVILY_API_KEY
        self.brave_key = brave_key or settings.BRAVE_SEARCH_API_KEY
        self.timeout_seconds = timeout_seconds or settings.RETRIEVAL_TIMEOUT_SECONDS
        self._client = client

    @property
    def provider_name(self) -> str:
        return "web_search"

    def _extract_domain(self, url: str) -> Optional[str]:
        try:
            netloc = urlparse(url).netloc
            return netloc.lower().removeprefix("www.")
        except Exception:
            return None

    def _generate_evidence_id(self, url: str, query: str, subprovider: str) -> str:
        clean = f"web_{subprovider}_{url.strip().lower()}_{query.strip().lower()}"
        digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:12]
        return f"ev_{digest}"

    async def search(self, query: str, limit: int = 10) -> List[Evidence]:
        """Attempt search via Tavily, falling back to Brave if unconfigured or failed."""
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Try Tavily if configured
        if self.tavily_key:
            try:
                return await self._search_tavily(clean_query, limit)
            except Exception as exc:
                logger.warning("Tavily search failed, attempting Brave fallback: %s", exc)

        # 2. Try Brave if configured
        if self.brave_key:
            try:
                return await self._search_brave(clean_query, limit)
            except Exception as exc:
                logger.warning("Brave search failed: %s", exc)
                raise ProviderError(f"Both Tavily and Brave web search failed: {exc}", self.provider_name) from exc

        # 3. Neither configured
        if not self.tavily_key and not self.brave_key:
            raise ProviderUnavailable(
                "Neither TAVILY_API_KEY nor BRAVE_SEARCH_API_KEY is configured",
                self.provider_name,
            )

        return []

    async def _search_tavily(self, query: str, limit: int) -> List[Evidence]:
        payload = {
            "api_key": self.tavily_key,
            "query": query,
            "max_results": min(max(limit, 1), 20),
            "search_depth": "basic",
            "include_answer": False,
        }

        try:
            if self._client:
                resp = await self._client.post(self.TAVILY_URL, json=payload, timeout=self.timeout_seconds)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(self.TAVILY_URL, json=payload, timeout=self.timeout_seconds)

            if resp.status_code != 200:
                raise ProviderError(f"Tavily returned HTTP {resp.status_code}", self.provider_name)

            data = resp.json()
            results = data.get("results", [])
            evidence_list: List[Evidence] = []

            for r in results:
                url = r.get("url")
                title = r.get("title")
                if not url or not title or not url.startswith(("http://", "https://")):
                    continue

                domain = self._extract_domain(url)
                evidence_list.append(
                    Evidence(
                        evidence_id=self._generate_evidence_id(url, query, "tavily"),
                        claim_id="",
                        title=title.strip(),
                        url=url.strip(),
                        canonical_url=canonicalize_url(url),
                        publisher=domain,
                        domain=domain,
                        author=None,
                        published_at=r.get("published_date"),
                        snippet=r.get("content"),
                        content=None,
                        source_type=SourceType.WEB,
                        provider="tavily",
                        query_used=query,
                        metadata={"raw_score": r.get("score")},
                    )
                )

            return evidence_list[:limit]

        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"Tavily timed out: {exc}", self.provider_name) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Tavily request error: {exc}", self.provider_name) from exc

    async def _search_brave(self, query: str, limit: int) -> List[Evidence]:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.brave_key,
        }
        params = {
            "q": query,
            "count": str(min(max(limit, 1), 20)),
        }

        try:
            if self._client:
                resp = await self._client.get(
                    self.BRAVE_URL,
                    headers=headers,
                    params=params,
                    timeout=self.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        self.BRAVE_URL,
                        headers=headers,
                        params=params,
                        timeout=self.timeout_seconds,
                    )

            if resp.status_code != 200:
                raise ProviderError(f"Brave returned HTTP {resp.status_code}", self.provider_name)

            data = resp.json()
            results = data.get("web", {}).get("results", [])
            evidence_list: List[Evidence] = []

            for r in results:
                url = r.get("url")
                title = r.get("title")
                if not url or not title or not url.startswith(("http://", "https://")):
                    continue

                domain = self._extract_domain(url)
                evidence_list.append(
                    Evidence(
                        evidence_id=self._generate_evidence_id(url, query, "brave"),
                        claim_id="",
                        title=title.strip(),
                        url=url.strip(),
                        canonical_url=canonicalize_url(url),
                        publisher=domain,
                        domain=domain,
                        author=None,
                        published_at=r.get("page_age"),
                        snippet=r.get("description"),
                        content=None,
                        source_type=SourceType.WEB,
                        provider="brave",
                        query_used=query,
                        metadata={},
                    )
                )

            return evidence_list[:limit]

        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"Brave search timed out: {exc}", self.provider_name) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Brave search request error: {exc}", self.provider_name) from exc
