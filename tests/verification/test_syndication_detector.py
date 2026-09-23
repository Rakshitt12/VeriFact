"""Unit tests for syndication and wire-service republication detection."""

from backend.retrieval.models import Evidence, SourceType
from backend.verification.models import RelationshipType
from backend.verification.syndication_detector import detect_syndication_relationship


def _make_ev(eid, domain, publisher, title, snippet) -> Evidence:
    return Evidence(
        evidence_id=eid,
        claim_id="c1",
        title=title,
        url=f"https://{domain}/news/article",
        canonical_url=f"https://{domain}/news/article",
        domain=domain,
        publisher=publisher,
        snippet=snippet,
        provider="gdelt",
        query_used="q",
        source_type=SourceType.NEWS,
    )


def test_detect_syndicated_wire_report():
    """Verify that cross-outlet articles attributing the same wire agency are flagged as SYNDICATED."""
    ev_a = _make_ev(
        "ev1",
        domain="timesofindia.indiatimes.com",
        publisher="Times of India",
        title="India approves semiconductor plant in Gujarat, PTI reports",
        snippet="New Delhi, PTI: The Cabinet on Tuesday approved a new semiconductor fabrication unit.",
    )
    ev_b = _make_ev(
        "ev2",
        domain="theprint.in",
        publisher="ThePrint",
        title="Cabinet clears semiconductor fabrication unit in Gujarat: PTI",
        snippet="According to PTI, the Cabinet on Tuesday approved a new semiconductor fabrication unit.",
    )

    rel = detect_syndication_relationship(ev_a, ev_b)
    assert rel is not None
    assert rel.relationship_type == RelationshipType.SYNDICATED
    assert rel.confidence >= 0.85
    assert any("PTI" in s for s in rel.signals)


def test_detect_likely_derived_reporting():
    """Verify that secondary reporting citing another publisher is flagged as LIKELY_DERIVED."""
    ev_a = _make_ev(
        "ev1",
        domain="reuters.com",
        publisher="Reuters",
        title="Exclusive: Major automaker plans 5000 job cuts in Europe",
        snippet="An internal memo seen by Reuters shows plans to eliminate 5,000 corporate positions.",
    )
    ev_b = _make_ev(
        "ev2",
        domain="financialexpress.com",
        publisher="Financial Express",
        title="Automaker to lay off 5000 workers in Europe: Report",
        snippet="Citing Reuters, the company plans to eliminate 5000 corporate positions across European operations.",
    )

    rel = detect_syndication_relationship(ev_a, ev_b)
    assert rel is not None
    assert rel.relationship_type == RelationshipType.LIKELY_DERIVED
    assert any("Reuters" in s for s in rel.signals)


def test_detect_syndication_shared_distinctive_phrases():
    """Verify that substantial identical phrase sequences across domains trigger syndication."""
    ev_a = _make_ev(
        "ev1",
        domain="outlet1.com",
        publisher="Outlet 1",
        title="National health guidelines unveiled today",
        snippet="Under the new framework, all designated healthcare facilities must report quarterly clinical metrics directly to the state monitoring cell.",
    )
    ev_b = _make_ev(
        "ev2",
        domain="outlet2.com",
        publisher="Outlet 2",
        title="New national health framework released",
        snippet="Under the new framework, all designated healthcare facilities must report quarterly clinical metrics directly to the state monitoring cell.",
    )

    rel = detect_syndication_relationship(ev_a, ev_b)
    assert rel is not None
    assert rel.relationship_type == RelationshipType.SYNDICATED


def test_independent_outlets_return_none():
    """Verify that truly independent articles discussing an event without syndication cues return None."""
    ev_a = _make_ev(
        "ev1",
        domain="bbc.com",
        publisher="BBC News",
        title="Climate summit ends with cautious agreement on emissions",
        snippet="Delegates celebrated late into the night after delegates reached a compromise on coal phase-down targets.",
    )
    ev_b = _make_ev(
        "ev2",
        domain="aljazeera.com",
        publisher="Al Jazeera",
        title="Developing nations criticize climate pact outcome as inadequate",
        snippet="Representatives from island nations expressed deep disappointment over delayed loss and damage financing mechanisms.",
    )

    rel = detect_syndication_relationship(ev_a, ev_b)
    assert rel is None
