"""Unit tests for domain classification and strict TLD heuristics."""

from backend.sources.domain_classifier import classify_domain
from backend.sources.models import SourceCategory


def test_classify_government_domains():
    """Verify official state bureau TLDs (.gov, .gov.in, .nic.in)."""
    assert classify_domain("pib.gov.in") == SourceCategory.GOVERNMENT
    assert classify_domain("whitehouse.gov") == SourceCategory.GOVERNMENT
    assert classify_domain("eci.nic.in") == SourceCategory.GOVERNMENT
    assert classify_domain("finance.gov.in") == SourceCategory.GOVERNMENT
    assert classify_domain("defense.gov") == SourceCategory.GOVERNMENT


def test_classify_academic_domains():
    """Verify higher education and academic institutional TLDs (.edu, .ac.in, .ac.uk)."""
    assert classify_domain("harvard.edu") == SourceCategory.ACADEMIC
    assert classify_domain("iitd.ac.in") == SourceCategory.ACADEMIC
    assert classify_domain("ox.ac.uk") == SourceCategory.ACADEMIC
    assert classify_domain("cambridge.edu.au") == SourceCategory.ACADEMIC


def test_classify_international_domains():
    """Verify treaty / international organization TLD (.int)."""
    assert classify_domain("who.int") == SourceCategory.INTERNATIONAL_ORGANIZATION
    assert classify_domain("interpol.int") == SourceCategory.INTERNATIONAL_ORGANIZATION


def test_critical_dot_org_rule():
    """CRITICAL TEST: Verify .org is NOT automatically official, government, or academic.

    A generic .org domain must be classified as ORGANIZATION, never GOVERNMENT.
    """
    assert classify_domain("random-advocacy-group.org") == SourceCategory.ORGANIZATION
    assert classify_domain("my-opinion.org") == SourceCategory.ORGANIZATION
    assert classify_domain("crypto-foundation.org") == SourceCategory.ORGANIZATION
    assert classify_domain("state-watch.org.in") == SourceCategory.ORGANIZATION

    # Must NOT be classified as government or regulatory
    assert classify_domain("random-advocacy-group.org") != SourceCategory.GOVERNMENT
    assert classify_domain("random-advocacy-group.org") != SourceCategory.REGULATORY


def test_classify_personal_blog_platforms():
    """Verify common self-publishing and personal blog platforms."""
    assert classify_domain("author.substack.com") == SourceCategory.PERSONAL_BLOG
    assert classify_domain("techwriter.medium.com") == SourceCategory.PERSONAL_BLOG
    assert classify_domain("dailythoughts.blogspot.com") == SourceCategory.PERSONAL_BLOG
    assert classify_domain("personalblog.wordpress.com") == SourceCategory.PERSONAL_BLOG


def test_classify_registered_domains_take_priority():
    """Verify registered source overrides (e.g. RBI as REGULATORY, AltNews as FACT_CHECKER)."""
    assert classify_domain("rbi.org.in") == SourceCategory.REGULATORY
    assert classify_domain("altnews.in") == SourceCategory.FACT_CHECKER
    assert classify_domain("reuters.com") == SourceCategory.NEWS_MEDIA
    assert classify_domain("un.org") == SourceCategory.INTERNATIONAL_ORGANIZATION


def test_classify_with_fact_check_hint():
    """Verify unclassified domain with fact_check hint gets categorized as FACT_CHECKER."""
    assert classify_domain("new-factcheck-desk.info", source_type_hint="FACT_CHECK") == SourceCategory.FACT_CHECKER


def test_classify_unknown_domain():
    """Verify unclassified commercial domain returns UNKNOWN."""
    assert classify_domain("completely-random-shop123.biz") == SourceCategory.UNKNOWN
    assert classify_domain(None) == SourceCategory.UNKNOWN
