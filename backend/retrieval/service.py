"""Evidence retrieval service orchestrator.

Coordinates query generation, provider execution, in-memory caching,
evidence normalization, and deduplication across all extracted claims.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional

from backend.claim.models import Claim
from backend.config.settings import settings
from backend.logging_config import logger
from backend.retrieval.base import EvidenceProvider
from backend.retrieval.cache import InMemoryCache
from backend.retrieval.deduplicator import deduplicate_evidence
from backend.retrieval.models import (
    ClaimEvidence,
    Evidence,
    ProviderStatus,
    ProviderStatusCode,
    QueryType,
    RetrievalResult,
    SearchQuery,
)
from backend.retrieval.providers.factcheck_api import GoogleFactCheckProvider
from backend.retrieval.providers.gdelt import GDELTProvider
from backend.retrieval.providers.official_search import OfficialSearchProvider
from backend.retrieval.providers.web_search import WebSearchProvider
from backend.retrieval.query_generator import generate_queries


# Global singleton cache
_retrieval_cache = InMemoryCache()


class RetrievalService:
    """Service orchestrating evidence collection from heterogeneous providers."""

    def __init__(
        self,
        news_provider: Optional[EvidenceProvider] = None,
        factcheck_provider: Optional[EvidenceProvider] = None,
        web_provider: Optional[EvidenceProvider] = None,
        official_provider: Optional[EvidenceProvider] = None,
        cache: Optional[InMemoryCache] = None,
    ) -> None:
        self.news_provider = news_provider or GDELTProvider()
        self.factcheck_provider = factcheck_provider or GoogleFactCheckProvider()
        self.web_provider = web_provider or WebSearchProvider()
        self.official_provider = official_provider or OfficialSearchProvider(
            web_provider=self.web_provider if isinstance(self.web_provider, WebSearchProvider) else None
        )
        self.cache = cache or _retrieval_cache

    def _select_providers_for_query(self, query: SearchQuery) -> List[EvidenceProvider]:
        """Route query types to the most relevant providers to minimize unnecessary API calls."""
        if query.query_type == QueryType.FACT_CHECK:
            return [self.factcheck_provider, self.web_provider]
        if query.query_type == QueryType.OFFICIAL:
            return [self.official_provider, self.news_provider]
        if query.query_type in (QueryType.NUMERIC, QueryType.DATE_FOCUSED):
            return [self.news_provider, self.web_provider]
        # DIRECT, ENTITY_FOCUSED
        return [self.news_provider, self.web_provider, self.factcheck_provider]

    async def _search_provider_with_cache(
        self,
        provider: EvidenceProvider,
        query_str: str,
        limit: int,
    ) -> tuple[List[Evidence], ProviderStatus]:
        """Check cache first, otherwise execute safe_search and update cache."""
        cached = await self.cache.get(provider.provider_name, query_str)
        if cached is not None:
            # Cache hit: clone items with fresh timestamp/status
            return [e.model_copy() for e in cached], ProviderStatus(
                provider=provider.provider_name,
                status=ProviderStatusCode.SUCCESS,
                results_count=len(cached),
                duration_ms=0.0,
            )

        results, status = await provider.safe_search(query_str, limit=limit)
        if status.status == ProviderStatusCode.SUCCESS and results:
            await self.cache.set(provider.provider_name, query_str, results)

        return results, status

    async def retrieve_for_claim(self, claim: Claim) -> ClaimEvidence:
        """Execute multi-provider retrieval for an individual claim."""
        queries = generate_queries(claim, max_queries=settings.MAX_QUERIES_PER_CLAIM)
        all_raw_evidence: List[Evidence] = []
        statuses_by_provider: Dict[str, ProviderStatus] = {}

        # Collect asynchronous search tasks across all queries and targeted providers
        search_coros = []
        for q in queries:
            target_providers = self._select_providers_for_query(q)
            for prov in target_providers:
                search_coros.append(
                    self._search_provider_with_cache(
                        prov,
                        q.query,
                        limit=settings.MAX_RESULTS_PER_PROVIDER,
                    )
                )

        if search_coros:
            outcomes = await asyncio.gather(*search_coros, return_exceptions=True)
            for res in outcomes:
                if isinstance(res, Exception):
                    logger.error("Unhandled error in retrieval task: %s", res)
                    continue

                ev_items, status = res
                # Record or update latest status for each provider
                statuses_by_provider[status.provider] = status

                for item in ev_items:
                    # Bind claim ID and ensure canonical URL
                    item.claim_id = claim.claim_id
                    all_raw_evidence.append(item)

        total_retrieved = len(all_raw_evidence)

        # Deduplicate results
        deduped = deduplicate_evidence(all_raw_evidence)

        # Apply maximum total evidence limit per claim
        final_evidence = deduped[:settings.MAX_TOTAL_EVIDENCE_PER_CLAIM]

        logger.info(
            "Claim %s: retrieved %d total, %d deduped, returning %d evidence items.",
            claim.claim_id,
            total_retrieved,
            len(deduped),
            len(final_evidence),
        )

        return ClaimEvidence(
            claim_id=claim.claim_id,
            evidence=final_evidence,
            queries_used=queries,
            provider_statuses=list(statuses_by_provider.values()),
            total_retrieved=total_retrieved,
        )

    async def retrieve_evidence(self, claims: List[Claim]) -> RetrievalResult:
        """Orchestrate retrieval concurrently across a list of extracted claims."""
        t0 = time.perf_counter()

        if not claims:
            return RetrievalResult(
                claims=[],
                total_evidence_count=0,
                retrieval_duration_ms=0.0,
            )

        # Process all claims concurrently
        tasks = [self.retrieve_for_claim(c) for c in claims]
        claim_evidences = await asyncio.gather(*tasks)

        total_ev = sum(len(ce.evidence) for ce in claim_evidences)
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)

        return RetrievalResult(
            claims=list(claim_evidences),
            total_evidence_count=total_ev,
            retrieval_duration_ms=duration_ms,
        )


# Default module-level convenience function
async def retrieve_evidence(claims: List[Claim]) -> RetrievalResult:
    """Convenience function delegating to default RetrievalService."""
    service = RetrievalService()
    return await service.retrieve_evidence(claims)
