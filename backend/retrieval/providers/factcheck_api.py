"""Google Fact Check Tools API provider.

Searches authoritative fact-checking databases for matching claims.
Preserves the publisher's verdict and rating in metadata without evaluating truth.
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


class GoogleFactCheckProvider(EvidenceProvider):
    """Fact-check retrieval provider using Google Fact Check Tools API."""

    FACTCHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = api_key or settings.GOOGLE_FACTCHECK_API_KEY
        self.timeout_seconds = timeout_seconds or settings.RETRIEVAL_TIMEOUT_SECONDS
        self._client = client

    @property
    def provider_name(self) -> str:
        return "factcheck_api"

    def _extract_domain(self, url: str) -> Optional[str]:
        try:
            netloc = urlparse(url).netloc
            return netloc.lower().removeprefix("www.")
        except Exception:
            return None

    def _generate_evidence_id(self, url: str, query: str) -> str:
        clean = f"fc_{url.strip().lower()}_{query.strip().lower()}"
        digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:12]
        return f"ev_fc_{digest}"

    async def search(self, query: str, limit: int = 10) -> List[Evidence]:
        """Query Fact Check Tools API and normalize claim reviews into Evidence."""
        if not self.api_key:
            raise ProviderUnavailable(
                "Google Fact Check API key is not configured",
                self.provider_name,
            )

        clean_query = query.strip()
        if not clean_query:
            return []

        params = {
            "query": clean_query,
            "key": self.api_key,
            "pageSize": min(max(limit, 1), 20),
        }

        try:
            if self._client:
                response = await self._client.get(
                    self.FACTCHECK_API_URL,
                    params=params,
                    timeout=self.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        self.FACTCHECK_API_URL,
                        params=params,
                        timeout=self.timeout_seconds,
                    )

            if response.status_code == 400:
                # Often invalid query syntax or unindexed term
                return []
            if response.status_code in (401, 403):
                raise ProviderUnavailable(
                    f"Google Fact Check API authentication failed (HTTP {response.status_code})",
                    self.provider_name,
                )
            if response.status_code != 200:
                raise ProviderError(
                    f"Google Fact Check API returned HTTP {response.status_code}",
                    self.provider_name,
                )

            data = response.json()
            raw_claims = data.get("claims", [])
            evidence_list: List[Evidence] = []

            for claim_item in raw_claims:
                reviewed_text = claim_item.get("text", "")
                claim_reviews = claim_item.get("claimReview", [])

                for review in claim_reviews:
                    review_url = review.get("url")
                    if not review_url or not review_url.startswith(("http://", "https://")):
                        continue

                    publisher_info = review.get("publisher", {})
                    publisher_name = publisher_info.get("name") or publisher_info.get("site")
                    domain = self._extract_domain(review_url)
                    review_title = review.get("title") or f"Fact Check: {reviewed_text[:80]}"
                    textual_rating = review.get("textualRating") or "Unknown"

                    evidence_list.append(
                        Evidence(
                            evidence_id=self._generate_evidence_id(review_url, clean_query),
                            claim_id="",  # Bound by RetrievalService
                            title=review_title,
                            url=review_url,
                            canonical_url=canonicalize_url(review_url),
                            publisher=publisher_name or domain,
                            domain=domain,
                            author=None,
                            published_at=review.get("reviewDate"),
                            snippet=f"Claim reviewed: '{reviewed_text}'. Rating: {textual_rating}",
                            content=None,
                            source_type=SourceType.FACT_CHECK,
                            provider=self.provider_name,
                            query_used=clean_query,
                            metadata={
                                "claim_reviewed": reviewed_text,
                                "verdict": textual_rating,
                                "rating": textual_rating,
                                "language_code": review.get("languageCode"),
                            },
                        )
                    )

            return evidence_list[:limit]

        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"Google Fact Check request timed out: {exc}", self.provider_name) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Google Fact Check network error: {exc}", self.provider_name) from exc
