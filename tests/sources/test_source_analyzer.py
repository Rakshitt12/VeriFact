"""Unit tests for the end-to-end SourceAnalyzer service."""

from backend.retrieval.models import Evidence, SourceType
from backend.sources.models import ReliabilityLabel, SourceCategory
from backend.sources.source_analyzer import analyze_source, analyze_sources


def test_analyze_source_news_article():
    """Verify end-to-end analysis of a news article Evidence item."""
    ev = Evidence(
        evidence_id="ev_news_1",
        claim_id="claim_001",
        title="RBI keeps repo rate unchanged at 6.5%",
        url="https://www.thehindu.com/business/rbi-rate-decision.html",
        canonical_url="https://thehindu.com/business/rbi-rate-decision.html",
        publisher="The Hindu",
        domain="thehindu.com",
        author="Sanjay Kumar",
        published_at="2026-05-10T11:00:00Z",
        snippet='According to the RBI Governor, "Inflation risks have moderated."',
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="rbi repo rate",
    )

    sa = analyze_source(ev)

    assert sa.evidence_id == "ev_news_1"
    assert sa.domain == "thehindu.com"
    assert sa.publisher == "The Hindu"
    assert sa.source_category == SourceCategory.NEWS_MEDIA
    assert sa.reliability_score >= 70
    assert sa.attribution.present is True
    assert sa.attribution.has_quotes is True
    assert len(sa.signals) > 0


def test_analyze_source_government_portal():
    """Verify end-to-end analysis of a government notification."""
    ev = Evidence(
        evidence_id="ev_gov_1",
        claim_id="claim_002",
        title="Cabinet Approves National Quantum Mission",
        url="https://pib.gov.in/PressReleasePage.aspx?PRID=12345",
        canonical_url="https://pib.gov.in/PressReleasePage.aspx?PRID=12345",
        publisher="Press Information Bureau",
        domain="pib.gov.in",
        published_at="2026-04-12T14:30:00Z",
        snippet="In an official statement, the Union Cabinet chaired by the Prime Minister approved...",
        source_type=SourceType.OFFICIAL,
        provider="official_search",
        query_used="national quantum mission",
    )

    sa = analyze_source(ev)

    assert sa.source_category == SourceCategory.GOVERNMENT
    assert sa.reliability_label == ReliabilityLabel.HIGH
    assert any("official" in s.lower() for s in sa.signals)


def test_analyze_source_fact_checker():
    """Verify end-to-end analysis of a verified fact-checker."""
    ev = Evidence(
        evidence_id="ev_fc_1",
        claim_id="claim_003",
        title="Fact Check: Video showing currency recall is doctored",
        url="https://altnews.in/fact-check-currency-recall",
        canonical_url="https://altnews.in/fact-check-currency-recall",
        publisher="Alt News",
        domain="altnews.in",
        author="Pratik Sinha",
        published_at="2026-03-01T08:00:00Z",
        snippet="Our investigation revealed the viral video was clipped from 2016.",
        source_type=SourceType.FACT_CHECK,
        provider="factcheck_api",
        query_used="currency recall fact check",
    )

    sa = analyze_source(ev)

    assert sa.source_category == SourceCategory.FACT_CHECKER
    assert sa.reliability_label == ReliabilityLabel.HIGH
    assert sa.primary_reporting.present is True


def test_analyze_sources_batch():
    """Verify batch processing across multiple Evidence items."""
    ev1 = Evidence(
        evidence_id="ev_1",
        claim_id="c1",
        title="Report 1",
        url="https://bbc.com/news/1",
        domain="bbc.com",
        provider="gdelt",
        query_used="q",
    )
    ev2 = Evidence(
        evidence_id="ev_2",
        claim_id="c1",
        title="Report 2",
        url="https://reuters.com/news/2",
        domain="reuters.com",
        provider="gdelt",
        query_used="q",
    )

    results = analyze_sources([ev1, ev2])
    assert len(results) == 2
    assert results[0].evidence_id == "ev_1"
    assert results[1].evidence_id == "ev_2"


def test_source_analyzer_strict_boundary():
    """Verify that source analyzer NEVER outputs claim truth or verdict."""
    ev = Evidence(
        evidence_id="ev_bound",
        claim_id="c1",
        title="Allegations of policy change",
        url="https://blog.substack.com/post/1",
        domain="blog.substack.com",
        provider="web_search",
        query_used="q",
    )

    sa = analyze_source(ev)
    # Check that model attributes contain no truth judgment fields
    assert not hasattr(sa, "is_claim_true")
    assert not hasattr(sa, "claim_credibility")
    assert not hasattr(sa, "stance")
    assert not hasattr(sa, "verdict")
