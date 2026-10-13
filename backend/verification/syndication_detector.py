"""Syndication and wire-service republication detection.

Detects news reports syndicated from common wire agencies (Reuters, AP, PTI, AFP, ANI)
or republished across different outlet domains with minor headline modifications.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set
from backend.config.scoring_config import (
    SYNDICATION_TEXT_THRESHOLD,
    SYNDICATION_TITLE_THRESHOLD,
    WIRE_SERVICE_NAMES,
)
from backend.retrieval.models import Evidence
from backend.verification.models import EvidenceRelationship, RelationshipType
from backend.verification.similarity import (
    compute_content_similarity,
    compute_title_similarity,
    extract_distinctive_phrases,
    normalize_text_for_similarity,
)


_WIRE_REGEX = re.compile(
    r"\b(reuters|associated press|\bap\b|pti|press trust of india|afp|agence france-presse|"
    r"ani|asian news international|bloomberg|wire reports?|agency reports?)\b",
    re.IGNORECASE,
)

_DERIVATION_PATTERNS = [
    re.compile(r"\baccording to (the )?([A-Za-z0-9\s]+?)(,|;|\.|\s+reported)\b", re.IGNORECASE),
    re.compile(r"\bfirst reported by (the )?([A-Za-z0-9\s]+)\b", re.IGNORECASE),
    re.compile(r"\bciting (the )?([A-Za-z0-9\s]+)\b", re.IGNORECASE),
]


def _extract_wire_agencies(text: str) -> Set[str]:
    """Find mentions of recognized news wire agencies in text."""
    if not text:
        return set()
    matches = _WIRE_REGEX.findall(text)
    clean_matches = set()
    for m in matches:
        m_lower = m.lower()
        if m_lower in ("ap", "associated press"):
            clean_matches.add("Associated Press")
        elif m_lower in ("pti", "press trust of india"):
            clean_matches.add("PTI")
        elif m_lower in ("afp", "agence france-presse"):
            clean_matches.add("AFP")
        elif m_lower in ("ani", "asian news international"):
            clean_matches.add("ANI")
        elif m_lower in ("reuters",):
            clean_matches.add("Reuters")
        elif m_lower in ("bloomberg",):
            clean_matches.add("Bloomberg")
        else:
            clean_matches.add("News Wire Agency")
    return clean_matches


def detect_syndication_relationship(
    ev_a: Evidence,
    ev_b: Evidence,
) -> Optional[EvidenceRelationship]:
    """Detect whether ev_a and ev_b share a syndicated wire service or derived reporting."""
    if ev_a.evidence_id == ev_b.evidence_id:
        return None

    # Skip if exact same domain (handled by duplicate detector)
    if ev_a.domain and ev_b.domain and ev_a.domain.lower() == ev_b.domain.lower():
        return None

    signals: List[str] = []
    limitations: List[str] = []

    text_a = f"{ev_a.title} {ev_a.snippet or ''} {ev_a.content or ''}"
    text_b = f"{ev_b.title} {ev_b.snippet or ''} {ev_b.content or ''}"

    title_sim = compute_title_similarity(ev_a.title, ev_b.title)
    content_sim = compute_content_similarity(text_a, text_b)

    # 1. Wire agency attribution match
    wires_a = _extract_wire_agencies(f"{ev_a.publisher or ''} {text_a}")
    wires_b = _extract_wire_agencies(f"{ev_b.publisher or ''} {text_b}")
    common_wires = wires_a.intersection(wires_b)

    # 2. Distinctive verbatim phrase sequences
    distinctive_phrases = extract_distinctive_phrases(text_a, text_b, min_words=5)

    # 3. Direct citation/derivation check (e.g. Article B citing Article A's publisher)
    is_derived = False
    citing_name = None
    if ev_a.publisher and len(ev_a.publisher) > 3:
        if re.search(rf"\b(according to|citing|reported by)\s+{re.escape(ev_a.publisher)}\b", text_b, re.IGNORECASE):
            is_derived = True
            citing_name = ev_a.publisher
    if not is_derived and ev_b.publisher and len(ev_b.publisher) > 3:
        if re.search(rf"\b(according to|citing|reported by)\s+{re.escape(ev_b.publisher)}\b", text_a, re.IGNORECASE):
            is_derived = True
            citing_name = ev_b.publisher

    # Case A: Explicit derivation
    if is_derived:
        signals.append(f"Explicit secondary citation detected (references {citing_name})")
        if content_sim >= 0.40:
            signals.append(f"Shared content overlap ({content_sim:.2f})")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.LIKELY_DERIVED,
            similarity_score=round(max(content_sim, title_sim), 3),
            confidence=0.88,
            signals=signals,
            limitations=["One article appears to be reporting on or citing the other"],
        )

    # Case B: Common wire service + moderate to high text/title similarity
    if common_wires and (content_sim >= SYNDICATION_TEXT_THRESHOLD or title_sim >= 0.60 or len(distinctive_phrases) >= 2):
        wires_str = ", ".join(common_wires)
        signals.append(f"Both articles attribute reporting to common wire agency ({wires_str})")
        if distinctive_phrases:
            signals.append(f"Contains {len(distinctive_phrases)} shared verbatim distinctive phrase sequence(s)")
        signals.append(f"Cross-outlet text similarity ({content_sim:.2f})")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.SYNDICATED,
            similarity_score=round(max(content_sim, title_sim), 3),
            confidence=0.92,
            signals=signals,
            limitations=["Independent confirmation not established; shares common wire copy"],
        )

    # Case C: High cross-domain content similarity and distinctive phrase overlap without named wire
    if content_sim >= SYNDICATION_TEXT_THRESHOLD and len(distinctive_phrases) >= 2:
        signals.append(f"Significant cross-domain verbatim text overlap ({content_sim:.2f})")
        signals.append(f"Shared {len(distinctive_phrases)} identical phrase sequences across independent domains")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.SYNDICATED,
            similarity_score=content_sim,
            confidence=0.85,
            signals=signals,
            limitations=["Likely syndicated copy or common press release distribution"],
        )

    return None
