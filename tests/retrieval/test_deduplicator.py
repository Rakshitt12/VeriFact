"""Unit tests for URL canonicalization and retrieval deduplication."""

from backend.retrieval.deduplicator import canonicalize_url, deduplicate_evidence
from backend.retrieval.models import Evidence, SourceType


def test_canonicalize_url_strips_tracking():
    """Verify that common marketing and tracking parameters are removed."""
    url = "https://example.com/news/article?id=123&utm_source=twitter&utm_medium=social&fbclid=XYZ123"
    canonical = canonicalize_url(url)
    assert "utm_source" not in canonical
    assert "utm_medium" not in canonical
    assert "fbclid" not in canonical
    assert "id=123" in canonical


def test_canonicalize_url_normalizes_scheme_and_domain():
    """Verify scheme and domain lowercasing and trailing slash removal."""
    url = "HTTPS://WWW.NewsSite.COM:443/world/india//"
    canonical = canonicalize_url(url)
    assert canonical.startswith("https://www.newssite.com/world/india")
    assert not canonical.endswith("//")


def test_canonicalize_url_strips_fragments():
    """Verify URL fragments are stripped."""
    url = "https://bbc.com/news/101#comments"
    canonical = canonicalize_url(url)
    assert "#comments" not in canonical


def test_deduplicate_identical_urls():
    """Verify exact URL duplicates are dropped."""
    e1 = Evidence(
        evidence_id="e1",
        claim_id="c1",
        title="Headline One",
        url="https://reuters.com/article/1",
        domain="reuters.com",
        provider="gdelt",
        query_used="q1",
    )
    e2 = Evidence(
        evidence_id="e2",
        claim_id="c1",
        title="Headline One Duplicate",
        url="https://reuters.com/article/1",
        domain="reuters.com",
        provider="web_search",
        query_used="q2",
    )
    results = deduplicate_evidence([e1, e2])
    assert len(results) == 1
    assert results[0].evidence_id == "e1"


def test_deduplicate_canonical_url_overlap():
    """Verify URLs differing only by tracking query parameters are merged."""
    e1 = Evidence(
        evidence_id="e1",
        claim_id="c1",
        title="Breaking News Report",
        url="https://thehindu.com/news/national/article100.html",
        domain="thehindu.com",
        provider="gdelt",
        query_used="q",
    )
    e2 = Evidence(
        evidence_id="e2",
        claim_id="c1",
        title="Breaking News Report",
        url="https://thehindu.com/news/national/article100.html?utm_source=newsletter&utm_campaign=daily",
        domain="thehindu.com",
        provider="web_search",
        query_used="q",
    )
    results = deduplicate_evidence([e1, e2])
    assert len(results) == 1


def test_deduplicate_same_domain_similar_title():
    """Verify same-domain articles with nearly identical titles are merged."""
    e1 = Evidence(
        evidence_id="e1",
        claim_id="c1",
        title="India signs major free trade agreement with UK on Tuesday",
        url="https://ndtv.com/business/fta-uk-signed-1",
        domain="ndtv.com",
        provider="gdelt",
        query_used="q",
    )
    e2 = Evidence(
        evidence_id="e2",
        claim_id="c1",
        title="India signs major free trade agreement with UK",
        url="https://ndtv.com/business/fta-uk-signed-2",
        domain="ndtv.com",
        provider="web_search",
        query_used="q",
    )
    results = deduplicate_evidence([e1, e2])
    assert len(results) == 1


def test_preserve_different_legitimate_articles():
    """Verify distinct articles from different sources or topics are preserved."""
    e1 = Evidence(
        evidence_id="e1",
        claim_id="c1",
        title="Cabinet approves PLI scheme for electronics",
        url="https://pib.gov.in/PressReleasePage.aspx?PRID=1",
        domain="pib.gov.in",
        provider="official_search",
        query_used="q",
    )
    e2 = Evidence(
        evidence_id="e2",
        claim_id="c1",
        title="Tech industry welcomes new PLI electronics incentives",
        url="https://livemint.com/industry/tech-pli-incentives",
        domain="livemint.com",
        provider="gdelt",
        query_used="q",
    )
    results = deduplicate_evidence([e1, e2])
    assert len(results) == 2
