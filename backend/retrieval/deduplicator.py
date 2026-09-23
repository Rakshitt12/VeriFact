"""URL canonicalization and retrieval-level evidence deduplication.

Removes redundant results without performing full semantic or source-independence
evaluations (which belong to later pipeline stages).
"""

from __future__ import annotations

import re
from typing import List, Set
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from backend.retrieval.models import Evidence


# Common tracking / noise query parameters to strip safely
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_cid", "utm_reader", "utm_name",
    "fbclid", "gclid", "gclsrc", "dclid", "zanpid",
    "msclkid", "_ga", "_gl", "mc_cid", "mc_eid",
    "ref", "ref_src", "source", "sr_share",
}


def canonicalize_url(url: str) -> str:
    """Normalize a URL for reliable equivalence matching.

    - Lowercases scheme and netloc
    - Strips fragment identifiers (#section)
    - Strips common marketing/analytics tracking parameters
    - Normalizes trailing slashes (preserves root slash)
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Remove default port if explicit
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        # Strip tracking params from query
        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        cleaned_pairs = [
            (k, v) for k, v in query_pairs if k.lower() not in _TRACKING_PARAMS
        ]
        # Keep query sorted for consistency
        cleaned_pairs.sort(key=lambda x: x[0])
        cleaned_query = urlencode(cleaned_pairs)

        # Normalize path
        path = parsed.path
        if path.endswith("/") and len(path) > 1:
            path = path.rstrip("/")

        return urlunparse((scheme, netloc, path, "", cleaned_query, ""))
    except Exception:
        # Fallback to trimmed original on parsing failure
        return url.strip()


def _normalize_title_for_comparison(title: str) -> str:
    """Strip punctuation and whitespace for fuzzy title comparison."""
    clean = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(clean.split())


def _title_jaccard_similarity(t1: str, t2: str) -> float:
    """Compute word Jaccard similarity between two normalized titles."""
    w1 = set(t1.split())
    w2 = set(t2.split())
    if not w1 or not w2:
        return 0.0
    return len(w1.intersection(w2)) / float(len(w1.union(w2)))


def deduplicate_evidence(items: List[Evidence]) -> List[Evidence]:
    """Filter out duplicate evidence items based on URL and title similarity.

    Rules:
    1. Items with identical canonical URLs are merged (first wins).
    2. Items with the exact same domain and highly similar titles (>= 0.80 Jaccard)
       are merged.
    3. Items with identical titles across providers are merged.
    """
    deduped: List[Evidence] = []
    seen_canonical_urls: Set[str] = set()

    for item in items:
        # Populate canonical URL if missing
        canon_url = item.canonical_url or canonicalize_url(item.url)
        item.canonical_url = canon_url

        if canon_url in seen_canonical_urls:
            continue

        item_norm_title = _normalize_title_for_comparison(item.title)

        is_duplicate = False
        for existing in deduped:
            existing_norm_title = _normalize_title_for_comparison(existing.title)

            # Exact title match
            if item_norm_title and item_norm_title == existing_norm_title:
                is_duplicate = True
                break

            # Same domain + highly similar title
            if item.domain and existing.domain and item.domain.lower() == existing.domain.lower():
                similarity = _title_jaccard_similarity(item_norm_title, existing_norm_title)
                if similarity >= 0.80:
                    is_duplicate = True
                    break

        if not is_duplicate:
            seen_canonical_urls.add(canon_url)
            deduped.append(item)

    return deduped
