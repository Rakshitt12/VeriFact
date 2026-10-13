"""Unit tests for the source registry."""

from backend.sources.models import SourceCategory
from backend.sources.source_registry import (
    RegistryEntry,
    lookup_registered_source,
    register_source,
)


def test_registry_lookup_known_sources():
    """Verify lookup of established news media, regulators, and fact checkers."""
    reuters = lookup_registered_source("reuters.com")
    assert reuters is not None
    assert reuters.name == "Reuters"
    assert reuters.category == SourceCategory.NEWS_MEDIA

    rbi = lookup_registered_source("rbi.org.in")
    assert rbi is not None
    assert rbi.is_regulator is True
    assert rbi.category == SourceCategory.REGULATORY

    altnews = lookup_registered_source("altnews.in")
    assert altnews is not None
    assert altnews.is_fact_checker is True
    assert altnews.category == SourceCategory.FACT_CHECKER


def test_registry_lookup_parent_domain_fallback():
    """Verify that subdomains fall back to parent domain record."""
    entry = lookup_registered_source("edition.cnn.com")  # parent cnn.com or bbc
    bbc_sub = lookup_registered_source("news.bbc.com")
    assert bbc_sub is not None
    assert bbc_sub.name == "BBC News"


def test_registry_lookup_unknown():
    """Verify unknown domain returns None."""
    assert lookup_registered_source("unregistered-website-987.com") is None
    assert lookup_registered_source(None) is None


def test_register_source_dynamically():
    """Verify runtime dynamic registration of a new source."""
    custom_entry = RegistryEntry(
        domain="custom-press-agency.org",
        name="Custom Press Agency",
        category=SourceCategory.NEWS_MEDIA,
        country="India",
        is_wire_service=True,
        reputation_score=82,
    )
    register_source(custom_entry)

    lookup = lookup_registered_source("custom-press-agency.org")
    assert lookup is not None
    assert lookup.name == "Custom Press Agency"
    assert lookup.is_wire_service is True
