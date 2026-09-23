"""Unit tests for duplicate and near-duplicate detection."""

from backend.retrieval.models import Evidence, SourceType
from backend.verification.duplicate_detector import detect_duplicate_relationship
from backend.verification.models import RelationshipType


def _make_ev(eid, url, title, snippet="", domain="example.com") -> Evidence:
    return Evidence(
        evidence_id=eid,
        claim_id="c1",
        title=title,
        url=url,
        canonical_url=url.split("?")[0],
        domain=domain,
        snippet=snippet,
        provider="gdelt",
        query_used="q",
        source_type=SourceType.NEWS,
    )


def test_detect_exact_duplicate_by_canonical_url():
    """Verify that identical canonical URLs are flagged as EXACT_DUPLICATE."""
    ev_a = _make_ev("ev1", "https://reuters.com/business/tech-deal-123?utm_source=twitter", "Tech Deal Signed")
    ev_b = _make_ev("ev2", "https://reuters.com/business/tech-deal-123?utm_medium=social", "Tech Deal Signed")

    rel = detect_duplicate_relationship(ev_a, ev_b)
    assert rel is not None
    assert rel.relationship_type == RelationshipType.EXACT_DUPLICATE
    assert rel.similarity_score == 1.0
    assert rel.confidence >= 0.95


def test_detect_exact_duplicate_verbatim_title_and_content():
    """Verify that verbatim identical headline and content are flagged as EXACT_DUPLICATE."""
    ev_a = _make_ev(
        "ev1",
        "https://news.com/article1",
        "India launches satellite into polar orbit",
        snippet="ISRO has successfully launched its satellite today into sun-synchronous polar orbit.",
    )
    ev_b = _make_ev(
        "ev2",
        "https://mirror.com/article2",
        "India launches satellite into polar orbit",
        snippet="ISRO has successfully launched its satellite today into sun-synchronous polar orbit.",
    )

    rel = detect_duplicate_relationship(ev_a, ev_b)
    assert rel is not None
    assert rel.relationship_type == RelationshipType.EXACT_DUPLICATE
    assert rel.confidence >= 0.95


def test_detect_near_duplicate_same_domain():
    """Verify that same domain with minor headline variation is flagged as NEAR_DUPLICATE."""
    ev_a = _make_ev(
        "ev1",
        "https://ndtv.com/business/trade-pact-signed-1",
        "India signs landmark trade agreement with UK on Tuesday",
        domain="ndtv.com",
        snippet="Details of the free trade agreement signed in New Delhi.",
    )
    ev_b = _make_ev(
        "ev2",
        "https://ndtv.com/business/trade-pact-signed-2",
        "India signs landmark trade pact with UK",
        domain="ndtv.com",
        snippet="Details of the bilateral free trade agreement signed in New Delhi.",
    )

    rel = detect_duplicate_relationship(ev_a, ev_b)
    assert rel is not None
    assert rel.relationship_type == RelationshipType.NEAR_DUPLICATE
    assert rel.confidence >= 0.85


def test_distinct_articles_return_none():
    """Verify that legitimately distinct articles do not trigger duplicate detection."""
    ev_a = _make_ev("ev1", "https://thehindu.com/1", "RBI holds repo rate at 6.5 percent", snippet="Monetary policy announcement.")
    ev_b = _make_ev("ev2", "https://pib.gov.in/2", "Cabinet approves railway corridor project", snippet="Infrastructure initiative approved.")

    rel = detect_duplicate_relationship(ev_a, ev_b)
    assert rel is None
