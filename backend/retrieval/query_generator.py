"""Query generator for transforming Claims into targeted search queries.

Generates multiple distinct query strategies per claim:
- DIRECT: normalized text stripped of extraneous conversational fluff
- ENTITY_FOCUSED: combinations of key named entities (PERSON, ORG, GPE) + subject
- NUMERIC: quantitative entities + context keywords
- DATE_FOCUSED: temporal entities + context keywords
- FACT_CHECK: targeted query formatted specifically for fact-checking databases
- OFFICIAL: targeted query aimed at institutional / government statements
"""

from __future__ import annotations

import re
from typing import List, Set
from backend.claim.models import Claim
from backend.retrieval.models import QueryType, SearchQuery
from backend.config.settings import settings


_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "that", "which", "who", "whom", "this", "these", "those", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "must", "can", "could",
    "and", "but", "or", "nor", "so", "yet", "as", "if", "into", "through",
    "during", "before", "after", "above", "below", "up", "down", "out", "off",
    "over", "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "not", "only", "own", "same", "than", "too",
    "very", "s", "t", "just", "don", "shouldn", "now"
}


def _extract_keywords(text: str, max_words: int = 8) -> List[str]:
    """Extract significant content words from text."""
    words = re.findall(r"\b[A-Za-z0-9\$\%€₹\-]+\b", text)
    filtered = [w for w in words if w.lower() not in _STOPWORDS and len(w) > 1]
    return filtered[:max_words]


def generate_queries(claim: Claim, max_queries: int | None = None) -> List[SearchQuery]:
    """Generate up to `max_queries` distinct, typed search queries from a Claim.

    Does NOT simply repeat the full sentence. Leverages detected entities,
    numbers, dates, and speaker attribution.
    """
    if max_queries is None:
        max_queries = settings.MAX_QUERIES_PER_CLAIM

    queries: List[SearchQuery] = []
    seen_texts: Set[str] = set()

    def add_query(q_text: str, q_type: QueryType):
        clean = " ".join(q_text.split()).strip()
        clean_lower = clean.lower()
        if clean and clean_lower not in seen_texts and len(clean.split()) >= 2:
            seen_texts.add(clean_lower)
            queries.append(
                SearchQuery(
                    query=clean,
                    query_type=q_type,
                    claim_id=claim.claim_id,
                )
            )

    # 1. DIRECT query: Core keywords from normalized claim
    keywords = _extract_keywords(claim.normalized_text, max_words=7)
    if keywords:
        add_query(" ".join(keywords), QueryType.DIRECT)

    # 2. ENTITY_FOCUSED: Combine high-signal entities (Orgs, Persons, Locations)
    entity_terms: List[str] = []
    if claim.attribution and claim.attribution.speaker:
        entity_terms.append(claim.attribution.speaker)
    entity_terms.extend(claim.organizations[:2])
    entity_terms.extend(claim.persons[:2])
    entity_terms.extend(claim.locations[:2])

    # Add 2-3 distinguishing content words from the claim
    topic_keywords = [w for w in keywords if w not in entity_terms][:3]
    if entity_terms:
        combined = entity_terms + topic_keywords
        add_query(" ".join(combined), QueryType.ENTITY_FOCUSED)

    # 3. NUMERIC query: If claim contains quantitative facts
    if claim.numbers:
        num_terms = claim.numbers[:2] + entity_terms[:2] + topic_keywords[:2]
        add_query(" ".join(num_terms), QueryType.NUMERIC)

    # 4. DATE_FOCUSED query: If claim anchors on specific dates/times
    if claim.dates:
        date_terms = entity_terms[:2] + topic_keywords[:2] + claim.dates[:1]
        add_query(" ".join(date_terms), QueryType.DATE_FOCUSED)

    # 5. FACT_CHECK query: Targeted for fact-checking databases
    # Uses key entities or top keywords + "fact check"
    core_phrase = " ".join((entity_terms[:2] + topic_keywords[:3]) or keywords[:4])
    if core_phrase:
        add_query(f"{core_phrase} fact check", QueryType.FACT_CHECK)

    # 6. OFFICIAL query: Targeted for official statements / releases
    anchor = claim.organizations[0] if claim.organizations else (claim.persons[0] if claim.persons else None)
    if anchor:
        official_terms = [anchor, "official statement"] + topic_keywords[:2]
        add_query(" ".join(official_terms), QueryType.OFFICIAL)

    # Fallback if too few queries were generated
    if not queries:
        fallback = " ".join(claim.normalized_text.split()[:8])
        add_query(fallback, QueryType.DIRECT)

    return queries[:max_queries]
