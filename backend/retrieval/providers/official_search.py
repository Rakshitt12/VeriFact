"""Official and primary source search provider.

Targets government (.gov, .gov.in, .nic.in), educational (.edu, .ac.in),
and institutional (.int, .org) domains to find primary statements, decrees,
and regulatory releases.
"""

from __future__ import annotations

import re
from typing import List, Optional
from backend.retrieval.base import EvidenceProvider, ProviderError, ProviderUnavailable
from backend.retrieval.models import Evidence, SourceType
from backend.retrieval.providers.web_search import WebSearchProvider


_OFFICIAL_TLD_PATTERNS = [
    r"\.gov(\.[a-z]{2})?$",
    r"\.nic\.in$",
    r"\.edu(\.[a-z]{2})?$",
    r"\.ac(\.[a-z]{2})?$",
    r"\.int$",
    r"\.europa\.eu$",
    r"\.who\.int$",
    r"\.un\.org$",
]

_OFFICIAL_FILTER_QUERY = "(site:gov OR site:gov.in OR site:nic.in OR site:edu OR site:int)"


class OfficialSearchProvider(EvidenceProvider):
    """Retrieves official, government, and institutional documents by querying targeted domains."""

    def __init__(self, web_provider: Optional[WebSearchProvider] = None) -> None:
        self.web_provider = web_provider or WebSearchProvider()

    @property
    def provider_name(self) -> str:
        return "official_search"

    def _is_official_domain(self, domain: Optional[str]) -> bool:
        if not domain:
            return False
        dom_lower = domain.lower()
        return any(re.search(pat, dom_lower) for pat in _OFFICIAL_TLD_PATTERNS)

    async def search(self, query: str, limit: int = 10) -> List[Evidence]:
        """Search targeted official domains and normalize to SourceType.OFFICIAL."""
        clean_query = query.strip()
        if not clean_query:
            return []

        # Augment search with official domain operators
        official_query = f"{clean_query} {_OFFICIAL_FILTER_QUERY}"

        try:
            raw_results = await self.web_provider.search(official_query, limit=limit * 2)
        except ProviderUnavailable:
            raise ProviderUnavailable(
                "Official search requires an underlying web search provider configuration",
                self.provider_name,
            )
        except Exception as exc:
            raise ProviderError(f"Official search query failed: {exc}", self.provider_name) from exc

        official_evidence: List[Evidence] = []
        for item in raw_results:
            # Reclassify as OFFICIAL
            item.source_type = SourceType.OFFICIAL
            item.provider = self.provider_name
            item.query_used = clean_query

            # Prioritize genuine official domains
            if self._is_official_domain(item.domain):
                item.metadata["is_verified_official_domain"] = True
            else:
                item.metadata["is_verified_official_domain"] = False

            official_evidence.append(item)

        return official_evidence[:limit]
