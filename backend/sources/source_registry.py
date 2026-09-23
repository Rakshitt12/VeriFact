"""Configurable registry of recognized sources, regulators, and fact-checkers.

Provides curated metadata for known domains without hardcoding logic across
the rest of the verification system. Allows runtime and config-driven expansion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
from backend.sources.models import SourceCategory


@dataclass(frozen=True)
class RegistryEntry:
    """Metadata record for a registered source domain."""
    domain:           str
    name:             str
    category:         SourceCategory
    country:          Optional[str] = None
    is_fact_checker:  bool = False
    is_regulator:     bool = False
    is_government:    bool = False
    is_wire_service:  bool = False
    reputation_score: int  = 80  # Base heuristic reputation weight (0 - 100)


# Extensible in-memory registry of established institutions, news media, and fact-checkers
_SOURCE_REGISTRY: Dict[str, RegistryEntry] = {
    # Fact Checkers (IFCN signatories / verified fact-checking desks)
    "altnews.in": RegistryEntry(
        domain="altnews.in",
        name="Alt News",
        category=SourceCategory.FACT_CHECKER,
        country="India",
        is_fact_checker=True,
        reputation_score=85,
    ),
    "boomlive.in": RegistryEntry(
        domain="boomlive.in",
        name="BOOM Live",
        category=SourceCategory.FACT_CHECKER,
        country="India",
        is_fact_checker=True,
        reputation_score=85,
    ),
    "factly.in": RegistryEntry(
        domain="factly.in",
        name="Factly",
        category=SourceCategory.FACT_CHECKER,
        country="India",
        is_fact_checker=True,
        reputation_score=80,
    ),
    "snopes.com": RegistryEntry(
        domain="snopes.com",
        name="Snopes",
        category=SourceCategory.FACT_CHECKER,
        country="USA",
        is_fact_checker=True,
        reputation_score=85,
    ),
    "politifact.com": RegistryEntry(
        domain="politifact.com",
        name="PolitiFact",
        category=SourceCategory.FACT_CHECKER,
        country="USA",
        is_fact_checker=True,
        reputation_score=85,
    ),
    "factcheck.org": RegistryEntry(
        domain="factcheck.org",
        name="FactCheck.org",
        category=SourceCategory.FACT_CHECKER,
        country="USA",
        is_fact_checker=True,
        reputation_score=85,
    ),
    "fullfact.org": RegistryEntry(
        domain="fullfact.org",
        name="Full Fact",
        category=SourceCategory.FACT_CHECKER,
        country="UK",
        is_fact_checker=True,
        reputation_score=85,
    ),

    # Regulators & Central Banks
    "rbi.org.in": RegistryEntry(
        domain="rbi.org.in",
        name="Reserve Bank of India",
        category=SourceCategory.REGULATORY,
        country="India",
        is_regulator=True,
        reputation_score=95,
    ),
    "sebi.gov.in": RegistryEntry(
        domain="sebi.gov.in",
        name="Securities and Exchange Board of India",
        category=SourceCategory.REGULATORY,
        country="India",
        is_regulator=True,
        is_government=True,
        reputation_score=95,
    ),
    "sec.gov": RegistryEntry(
        domain="sec.gov",
        name="US Securities and Exchange Commission",
        category=SourceCategory.REGULATORY,
        country="USA",
        is_regulator=True,
        is_government=True,
        reputation_score=95,
    ),
    "fda.gov": RegistryEntry(
        domain="fda.gov",
        name="US Food and Drug Administration",
        category=SourceCategory.REGULATORY,
        country="USA",
        is_regulator=True,
        is_government=True,
        reputation_score=95,
    ),

    # Government Portals & Official Information Bureaus
    "pib.gov.in": RegistryEntry(
        domain="pib.gov.in",
        name="Press Information Bureau (Govt of India)",
        category=SourceCategory.GOVERNMENT,
        country="India",
        is_government=True,
        reputation_score=90,
    ),
    "india.gov.in": RegistryEntry(
        domain="india.gov.in",
        name="National Portal of India",
        category=SourceCategory.GOVERNMENT,
        country="India",
        is_government=True,
        reputation_score=90,
    ),
    "gov.uk": RegistryEntry(
        domain="gov.uk",
        name="UK Government Official Portal",
        category=SourceCategory.GOVERNMENT,
        country="UK",
        is_government=True,
        reputation_score=90,
    ),
    "whitehouse.gov": RegistryEntry(
        domain="whitehouse.gov",
        name="The White House",
        category=SourceCategory.GOVERNMENT,
        country="USA",
        is_government=True,
        reputation_score=90,
    ),

    # International Organizations
    "who.int": RegistryEntry(
        domain="who.int",
        name="World Health Organization",
        category=SourceCategory.INTERNATIONAL_ORGANIZATION,
        reputation_score=90,
    ),
    "un.org": RegistryEntry(
        domain="un.org",
        name="United Nations",
        category=SourceCategory.INTERNATIONAL_ORGANIZATION,
        reputation_score=90,
    ),
    "imf.org": RegistryEntry(
        domain="imf.org",
        name="International Monetary Fund",
        category=SourceCategory.INTERNATIONAL_ORGANIZATION,
        reputation_score=90,
    ),
    "worldbank.org": RegistryEntry(
        domain="worldbank.org",
        name="The World Bank",
        category=SourceCategory.INTERNATIONAL_ORGANIZATION,
        reputation_score=90,
    ),

    # Wire Services & Major News Outlets
    "reuters.com": RegistryEntry(
        domain="reuters.com",
        name="Reuters",
        category=SourceCategory.NEWS_MEDIA,
        country="International",
        is_wire_service=True,
        reputation_score=90,
    ),
    "apnews.com": RegistryEntry(
        domain="apnews.com",
        name="Associated Press",
        category=SourceCategory.NEWS_MEDIA,
        country="International",
        is_wire_service=True,
        reputation_score=90,
    ),
    "afp.com": RegistryEntry(
        domain="afp.com",
        name="Agence France-Presse",
        category=SourceCategory.NEWS_MEDIA,
        country="International",
        is_wire_service=True,
        reputation_score=90,
    ),
    "bloomberg.com": RegistryEntry(
        domain="bloomberg.com",
        name="Bloomberg",
        category=SourceCategory.NEWS_MEDIA,
        country="International",
        reputation_score=85,
    ),
    "bbc.com": RegistryEntry(
        domain="bbc.com",
        name="BBC News",
        category=SourceCategory.NEWS_MEDIA,
        country="UK",
        reputation_score=85,
    ),
    "thehindu.com": RegistryEntry(
        domain="thehindu.com",
        name="The Hindu",
        category=SourceCategory.NEWS_MEDIA,
        country="India",
        reputation_score=85,
    ),
    "indianexpress.com": RegistryEntry(
        domain="indianexpress.com",
        name="The Indian Express",
        category=SourceCategory.NEWS_MEDIA,
        country="India",
        reputation_score=85,
    ),
    "hindustantimes.com": RegistryEntry(
        domain="hindustantimes.com",
        name="Hindustan Times",
        category=SourceCategory.NEWS_MEDIA,
        country="India",
        reputation_score=80,
    ),
    "timesofindia.indiatimes.com": RegistryEntry(
        domain="timesofindia.indiatimes.com",
        name="The Times of India",
        category=SourceCategory.NEWS_MEDIA,
        country="India",
        reputation_score=80,
    ),
    "livemint.com": RegistryEntry(
        domain="livemint.com",
        name="Mint",
        category=SourceCategory.NEWS_MEDIA,
        country="India",
        reputation_score=80,
    ),
    "ndtv.com": RegistryEntry(
        domain="ndtv.com",
        name="NDTV",
        category=SourceCategory.NEWS_MEDIA,
        country="India",
        reputation_score=80,
    ),
}


def normalize_domain_key(domain: str) -> str:
    """Clean and normalize a domain string for registry lookups."""
    dom = domain.lower().strip()
    if dom.startswith("www."):
        dom = dom[4:]
    return dom


def lookup_registered_source(domain: Optional[str]) -> Optional[RegistryEntry]:
    """Look up a domain in the source registry, checking exact and parent domains."""
    if not domain:
        return None

    clean_dom = normalize_domain_key(domain)

    # 1. Direct exact match
    if clean_dom in _SOURCE_REGISTRY:
        return _SOURCE_REGISTRY[clean_dom]

    # 2. Check parent domain if sub-domain (e.g. news.bbc.com -> bbc.com)
    parts = clean_dom.split(".")
    if len(parts) > 2:
        parent_dom = ".".join(parts[-2:])
        if parent_dom in _SOURCE_REGISTRY:
            return _SOURCE_REGISTRY[parent_dom]
        # In case of 3-level TLDs like .gov.in, .co.uk
        if len(parts) > 3:
            parent_dom_3 = ".".join(parts[-3:])
            if parent_dom_3 in _SOURCE_REGISTRY:
                return _SOURCE_REGISTRY[parent_dom_3]

    return None


def register_source(entry: RegistryEntry) -> None:
    """Programmatically register or update a source domain in the registry."""
    clean_dom = normalize_domain_key(entry.domain)
    _SOURCE_REGISTRY[clean_dom] = entry


def get_all_registered_domains() -> list[str]:
    """Return all currently registered domain keys."""
    return list(_SOURCE_REGISTRY.keys())
