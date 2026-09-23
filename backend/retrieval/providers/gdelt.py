"""GDELT 2.0 Doc API news provider.

Free, open global news index requiring no API key.
Provides the always-available baseline for news reporting.
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Optional
from urllib.parse import urlparse
import httpx

from backend.config.settings import settings
from backend.logging_config import logger
from backend.retrieval.base import EvidenceProvider, ProviderError, ProviderTimeout
from backend.retrieval.deduplicator import canonicalize_url
from backend.retrieval.models import Evidence, SourceType


class GDELTProvider(EvidenceProvider):
    """News retrieval provider utilizing the free GDELT 2.0 Doc API."""

    GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(
        self,
        timespan_days: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.timespan_days = timespan_days or settings.GDELT_TIMESPAN_DAYS
        self.timeout_seconds = timeout_seconds or settings.RETRIEVAL_TIMEOUT_SECONDS
        self._client = client

    @property
    def provider_name(self) -> str:
        return "gdelt"

    def _extract_domain(self, url: str) -> Optional[str]:
        try:
            netloc = urlparse(url).netloc
            return netloc.lower().removeprefix("www.")
        except Exception:
            return None

    def _generate_evidence_id(self, url: str, query: str) -> str:
        clean = f"gdelt_{url.strip().lower()}_{query.strip().lower()}"
        digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:12]
        return f"ev_gdelt_{digest}"

    async def search(self, query: str, limit: int = 10) -> List[Evidence]:
        """Query GDELT 2.0 Doc API and normalize results."""
        clean_query = query.strip()
        if not clean_query:
            return []

        # GDELT supports max 250 records per call; limit to requested amount
        records_to_request = min(max(limit, 1), 50)
        params = {
            "query": clean_query,
            "mode": "artlist",
            "maxrecords": str(records_to_request),
            "format": "json",
            "timespan": f"{self.timespan_days}d",
            "sort": "date",
        }

        try:
            if self._client:
                response = await self._client.get(
                    self.GDELT_API_URL,
                    params=params,
                    timeout=self.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        self.GDELT_API_URL,
                        params=params,
                        timeout=self.timeout_seconds,
                    )

            if response.status_code != 200:
                raise ProviderError(
                    f"GDELT API responded with HTTP {response.status_code}",
                    self.provider_name,
                )

            # GDELT occasionally returns plain HTML error or empty text on no match
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type.lower() and not response.text.strip().startswith("{"):
                # No matches found or plain notice
                return []

            try:
                data = response.json()
            except Exception:
                # Malformed JSON or empty string
                return []

            articles = data.get("articles", [])
            evidence_list: List[Evidence] = []

            for art in articles:
                raw_url = art.get("url")
                raw_title = art.get("title")

                # Discard items without valid URL or title
                if not raw_url or not raw_title:
                    continue

                raw_url = raw_url.strip()
                raw_title = raw_title.strip()
                if not raw_url.startswith(("http://", "https://")):
                    continue

                domain = art.get("domain") or self._extract_domain(raw_url)
                seendate = art.get("seendate")  # Format: YYYYMMDDTHHMMSSZ

                evidence_list.append(
                    Evidence(
                        evidence_id=self._generate_evidence_id(raw_url, clean_query),
                        claim_id="",  # Bound later by RetrievalService
                        title=raw_title,
                        url=raw_url,
                        canonical_url=canonicalize_url(raw_url),
                        publisher=domain,
                        domain=domain,
                        author=None,
                        published_at=seendate,
                        snippet=art.get("socialimage") or None,  # GDELT snippet is limited
                        content=None,
                        source_type=SourceType.NEWS,
                        provider=self.provider_name,
                        query_used=clean_query,
                        metadata={
                            "language": art.get("language"),
                            "sourcecountry": art.get("sourcecountry"),
                        },
                    )
                )

            return evidence_list[:limit]

        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"GDELT request timed out: {exc}", self.provider_name) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"GDELT network request failed: {exc}", self.provider_name) from exc
