"""Duplicate and near-duplicate evidence detection.

Determines whether two evidence items represent the identical underlying article
via canonical URL equivalence or high title/text similarity.
"""

from __future__ import annotations

from typing import Optional
from backend.config.scoring_config import (
    DUPLICATE_SIMILARITY_THRESHOLD,
    EXACT_DUPLICATE_THRESHOLD,
    NEAR_DUPLICATE_THRESHOLD,
)
from backend.retrieval.deduplicator import canonicalize_url
from backend.retrieval.models import Evidence
from backend.verification.models import EvidenceRelationship, RelationshipType
from backend.verification.similarity import (
    compute_content_similarity,
    compute_title_similarity,
    normalize_text_for_similarity,
)


def detect_duplicate_relationship(
    ev_a: Evidence,
    ev_b: Evidence,
) -> Optional[EvidenceRelationship]:
    """Evaluate whether ev_a and ev_b are exact duplicates or near duplicates.

    Returns an EvidenceRelationship if a duplicate condition is met, else None.
    """
    if ev_a.evidence_id == ev_b.evidence_id:
        return None

    signals = []
    limitations = []

    # 1. Canonical URL check
    canon_a = ev_a.canonical_url or canonicalize_url(ev_a.url)
    canon_b = ev_b.canonical_url or canonicalize_url(ev_b.url)

    if canon_a and canon_b and canon_a.lower() == canon_b.lower():
        signals.append(f"Identical canonical URL ({canon_a})")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.EXACT_DUPLICATE,
            similarity_score=1.0,
            confidence=0.98,
            signals=signals,
            limitations=[],
        )

    # 2. Title & Content similarity
    title_sim = compute_title_similarity(ev_a.title, ev_b.title)
    text_a = ev_a.content or ev_a.snippet or ""
    text_b = ev_b.content or ev_b.snippet or ""
    content_sim = compute_content_similarity(text_a, text_b) if (text_a and text_b) else 0.0

    norm_title_a = normalize_text_for_similarity(ev_a.title)
    norm_title_b = normalize_text_for_similarity(ev_b.title)

    # Exact matching title and content
    if norm_title_a == norm_title_b and (content_sim >= 0.90 or not (text_a and text_b)):
        signals.append("Verbatim identical headline")
        if content_sim >= 0.90:
            signals.append("Verbatim identical article content")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.EXACT_DUPLICATE,
            similarity_score=max(title_sim, content_sim, 0.95),
            confidence=0.95,
            signals=signals,
            limitations=[],
        )

    # Same domain + high title similarity (>= NEAR_DUPLICATE_THRESHOLD or title >= 0.65 and content >= 0.50)
    same_domain = bool(ev_a.domain and ev_b.domain and ev_a.domain.lower() == ev_b.domain.lower())
    if same_domain and (title_sim >= NEAR_DUPLICATE_THRESHOLD or (title_sim >= 0.65 and content_sim >= 0.50)):
        signals.append(f"Same publisher domain ({ev_a.domain}) with high title similarity ({title_sim:.2f})")
        if content_sim >= 0.50:
            signals.append(f"Substantial content overlap ({content_sim:.2f})")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.NEAR_DUPLICATE,
            similarity_score=round(max(title_sim, content_sim), 3),
            confidence=0.90,
            signals=signals,
            limitations=["Published under different URLs on the same domain"],
        )

    # Different domains, but very high title and content similarity
    if title_sim >= 0.88 and content_sim >= 0.80:
        signals.append(f"Extremely high cross-domain title similarity ({title_sim:.2f})")
        signals.append(f"High body text similarity ({content_sim:.2f})")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.NEAR_DUPLICATE,
            similarity_score=round((title_sim + content_sim) / 2.0, 3),
            confidence=0.88,
            signals=signals,
            limitations=["Cross-domain reprint with minor editorial edits"],
        )

    return None
