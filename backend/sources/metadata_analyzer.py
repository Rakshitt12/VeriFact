"""Metadata completeness and transparency evaluation for evidence items."""

from __future__ import annotations

from typing import Optional, Tuple
from backend.retrieval.models import Evidence
from backend.sources.models import MetadataQuality, TransparencyLevel


def evaluate_metadata_quality(evidence: Evidence) -> MetadataQuality:
    """Evaluate completeness of article metadata on an Evidence item."""
    has_title = bool(evidence.title and evidence.title.strip())
    has_publisher = bool(evidence.publisher and evidence.publisher.strip())
    has_author = bool(evidence.author and evidence.author.strip())
    has_published_at = bool(evidence.published_at and evidence.published_at.strip())
    has_canonical_url = bool(evidence.canonical_url and evidence.canonical_url.strip())
    has_content = bool(
        (evidence.content and len(evidence.content.strip()) >= 20)
        or (evidence.snippet and len(evidence.snippet.strip()) >= 20)
    )

    # Weighted score (max 1.0)
    weights = [
        (has_title, 0.20),
        (has_publisher, 0.20),
        (has_canonical_url, 0.20),
        (has_content, 0.20),
        (has_published_at, 0.10),
        (has_author, 0.10),
    ]
    score = sum(w for condition, w in weights if condition)

    return MetadataQuality(
        score=round(score, 2),
        has_title=has_title,
        has_publisher=has_publisher,
        has_author=has_author,
        has_published_at=has_published_at,
        has_canonical_url=has_canonical_url,
        has_content=has_content,
    )


def evaluate_transparency(meta: MetadataQuality) -> TransparencyLevel:
    """Assess publisher transparency and disclosure level from metadata completeness."""
    # Complete attribution with named author and publication date
    if meta.has_publisher and meta.has_canonical_url and meta.has_content:
        if meta.has_author and meta.has_published_at:
            return TransparencyLevel.HIGH
        elif meta.has_author or meta.has_published_at:
            return TransparencyLevel.MEDIUM

    if meta.has_publisher and (meta.has_canonical_url or meta.has_content):
        return TransparencyLevel.MEDIUM

    if meta.score >= 0.3:
        return TransparencyLevel.LOW

    return TransparencyLevel.UNKNOWN
