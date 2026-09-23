"""Domain classification based on TLD structure and source registry records.

Implements structural heuristics for identifying government, academic,
international, regulatory, media, and blog platforms.

CRITICAL RULE:
A `.org` domain is NOT automatically official, government, or high-trust.
Unless explicitly listed in the source registry, `.org` maps strictly to
SourceCategory.ORGANIZATION or UNKNOWN.
"""

from __future__ import annotations

import re
from typing import Optional
from backend.sources.models import SourceCategory
from backend.sources.source_registry import lookup_registered_source, normalize_domain_key


# TLD regex patterns
_GOVERNMENT_TLD_PATTERN = re.compile(
    r"(\.gov(\.[a-z]{2})?$)|(\.nic\.in$)|(\.mil(\.[a-z]{2})?$)",
    re.IGNORECASE,
)

_ACADEMIC_TLD_PATTERN = re.compile(
    r"(\.edu(\.[a-z]{2})?$)|(\.ac\.[a-z]{2,}$)",
    re.IGNORECASE,
)

_INTERNATIONAL_TLD_PATTERN = re.compile(
    r"\.int$",
    re.IGNORECASE,
)

# Known blog / self-publishing hosting platforms
_PERSONAL_BLOG_DOMAINS = {
    "substack.com",
    "medium.com",
    "blogspot.com",
    "wordpress.com",
    "blogger.com",
    "tumblr.com",
    "wixsite.com",
    "weebly.com",
}


def classify_domain(
    domain: Optional[str],
    source_type_hint: Optional[str] = None,
) -> SourceCategory:
    """Classify a domain into a descriptive SourceCategory.

    Evaluation hierarchy:
    1. Source registry lookup (exact or parent domain match)
    2. Structural TLD patterns (.gov, .nic.in, .edu, .ac.in, .int)
    3. Self-publishing / personal blog domain checks
    4. `.org` check -> ORGANIZATION (never automatically official/gov)
    5. Source type hints (e.g. FACT_CHECK from Evidence)
    6. Default -> UNKNOWN
    """
    if not domain:
        return SourceCategory.UNKNOWN

    clean_dom = normalize_domain_key(domain)

    # 1. Source registry override (curated verified entities)
    registry_entry = lookup_registered_source(clean_dom)
    if registry_entry:
        return registry_entry.category

    # 2. Government & Official State Bureau TLDs
    if _GOVERNMENT_TLD_PATTERN.search(clean_dom):
        return SourceCategory.GOVERNMENT

    # 3. Academic & Higher Education TLDs
    if _ACADEMIC_TLD_PATTERN.search(clean_dom):
        return SourceCategory.ACADEMIC

    # 4. International Treaty Organizations (.int)
    if _INTERNATIONAL_TLD_PATTERN.search(clean_dom):
        return SourceCategory.INTERNATIONAL_ORGANIZATION

    # 5. Personal blog & self-publishing platforms
    for blog_dom in _PERSONAL_BLOG_DOMAINS:
        if clean_dom == blog_dom or clean_dom.endswith(f".{blog_dom}"):
            return SourceCategory.PERSONAL_BLOG

    # 6. Specific Fact Check provider hint
    if source_type_hint and source_type_hint.upper() == "FACT_CHECK":
        return SourceCategory.FACT_CHECKER

    # 7. CRITICAL: Generic .org check
    # .org is open to anyone and must NOT be classified as government or academic.
    if clean_dom.endswith(".org") or clean_dom.endswith(".org.in"):
        return SourceCategory.ORGANIZATION

    # 8. Unclassified / commercial / generic
    return SourceCategory.UNKNOWN
