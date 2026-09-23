"""Tests 3-5: Citation integrity, fabrication rejection, deduplication."""

from backend.report.citation_manager import CitationManager
from tests.report.conftest import make_evidence


def test_citation_integrity():
    """Test 3 — All report citations correspond to actual evidence IDs."""
    ev1 = make_evidence("evidence_001", url="https://a.example/1", publisher="A", domain="a.example")
    ev2 = make_evidence("evidence_002", url="https://b.example/2", publisher="B", domain="b.example")
    mgr = CitationManager()
    cites = mgr.build_citations_from_evidence([ev1, ev2])
    assert {c.evidence_id for c in cites} == {"evidence_001", "evidence_002"}
    urls = {c.url for c in cites}
    assert "https://a.example/1" in urls and "https://b.example/2" in urls


def test_fabricated_citation_rejected():
    """Test 4 — URL not present in evidence must be rejected/omitted."""
    ev = make_evidence("evidence_001", url="https://a.example/1")
    mgr = CitationManager(allowed_evidence=[ev])
    ok = mgr.add_citation(
        evidence_id="evidence_fake",
        title="Fake",
        publisher="FakeNews",
        url="https://fabricated.example/fake-story",
    )
    assert ok is False
    assert all(c.url != "https://fabricated.example/fake-story" for c in mgr.get_citations())


def test_duplicate_citation_deduplicated():
    """Test 5 — Same evidence referenced repeatedly yields one citation record."""
    ev = make_evidence("evidence_001", url="https://a.example/1")
    mgr = CitationManager()
    mgr.register_evidence_batch([ev])
    mgr.register_evidence_batch([ev])  # second section references same evidence
    mgr.add_citation(evidence_id="evidence_001", title=ev.title,
                     publisher="A", url="https://a.example/1")
    cites = mgr.build_citation_list()
    assert len([c for c in cites if c.evidence_id == "evidence_001"]) == 1
