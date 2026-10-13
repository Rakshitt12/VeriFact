"""Citation manager ensuring auditable provenance, URL validation, and deduplication."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from backend.logging_config import logger
from backend.report.models import CitationItem
from backend.retrieval.models import Evidence


class CitationManager:
    """Maintains an evidence citation registry ensuring integrity and deduplication."""

    def __init__(self, allowed_evidence: Optional[List[Evidence]] = None) -> None:
        self._valid_urls: Set[str] = set()
        self._evidence_by_id: Dict[str, Evidence] = {}
        self._citations_by_id: Dict[str, CitationItem] = {}

        if allowed_evidence:
            self.register_evidence_pool(allowed_evidence)

    def register_evidence_pool(self, evidence_items: List[Evidence]) -> None:
        """Register authentic evidence items to establish the validation whitelist."""
        for ev in evidence_items:
            self._evidence_by_id[ev.evidence_id] = ev
            if ev.url:
                self._valid_urls.add(ev.url.strip().lower())

    def add_citation(
        self,
        evidence_id: str,
        title: str,
        publisher: str,
        url: str,
        publication_date: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> bool:
        """Add a citation after validating integrity against registered evidence.

        Returns:
            True if citation is valid and registered/recorded.
            False if rejected due to citation integrity violation (fabricated URL).
        """
        clean_url = (url or "").strip().lower()

        # If evidence pool is registered, enforce strict URL whitelist
        if self._valid_urls and clean_url not in self._valid_urls:
            logger.warning(
                "Citation rejected: URL '%s' for evidence_id '%s' was not found in retrieved evidence.",
                url,
                evidence_id,
            )
            return False

        # Deduplicate by evidence_id
        if evidence_id not in self._citations_by_id:
            # If domain missing, attempt to extract or lookup from registered evidence
            ev_ref = self._evidence_by_id.get(evidence_id)
            final_domain = domain or (ev_ref.domain if ev_ref else None)
            final_publisher = publisher or (ev_ref.publisher if ev_ref else "Unknown Publisher")
            final_title = title or (ev_ref.title if ev_ref else "Untitled Article")
            final_date = publication_date or (ev_ref.published_at if ev_ref else None)

            self._citations_by_id[evidence_id] = CitationItem(
                evidence_id=evidence_id,
                title=final_title,
                publisher=final_publisher,
                url=url,
                publication_date=final_date,
                domain=final_domain,
            )

        return True

    def build_citations_from_evidence(self, evidence_items: List[Evidence]) -> List[CitationItem]:
        """Convenience method to register and extract unique valid citations."""
        self.register_evidence_pool(evidence_items)
        for ev in evidence_items:
            self.add_citation(
                evidence_id=ev.evidence_id,
                title=ev.title,
                publisher=ev.publisher or ev.domain or "Unknown",
                url=ev.url,
                publication_date=ev.published_at,
                domain=ev.domain,
            )
        return self.get_citations()

    def get_citations(self) -> List[CitationItem]:
        """Return all deduplicated, validated citations."""
        return list(self._citations_by_id.values())

    def register_evidence_batch(self, evidence_items: List[Evidence]) -> None:
        """Register a batch of evidence items and auto-add citations for each.

        Designed for use by ReportGenerator which calls this per-claim.
        """
        self.register_evidence_pool(evidence_items)
        for ev in evidence_items:
            self.add_citation(
                evidence_id=ev.evidence_id,
                title=ev.title,
                publisher=ev.publisher or ev.domain or "Unknown",
                url=ev.url,
                publication_date=ev.published_at,
                domain=ev.domain,
            )

    def build_citation_list(self) -> List[CitationItem]:
        """Return all accumulated, deduplicated citations (alias for get_citations)."""
        return self.get_citations()
