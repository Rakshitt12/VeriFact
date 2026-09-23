"""Unit tests for the search query generator."""

from backend.claim.models import AttributedSpeaker, Claim, ClaimImportance, ClaimType
from backend.retrieval.models import QueryType
from backend.retrieval.query_generator import generate_queries


def _make_claim(
    text: str,
    orgs=None,
    persons=None,
    locations=None,
    dates=None,
    numbers=None,
    speaker=None,
) -> Claim:
    return Claim(
        claim_id="claim_test_01",
        original_text=text,
        normalized_text=text,
        claim_type=ClaimType.EVENT,
        importance=ClaimImportance.HIGH,
        entities=[],
        organizations=orgs or [],
        persons=persons or [],
        locations=locations or [],
        dates=dates or [],
        numbers=numbers or [],
        source_sentence=text,
        attribution=AttributedSpeaker(speaker=speaker, attribution_verb="said") if speaker else None,
    )


def test_query_generator_basic():
    """Verify that a basic claim produces DIRECT and FACT_CHECK queries."""
    claim = _make_claim("The central bank raised interest rates yesterday.")
    queries = generate_queries(claim, max_queries=5)

    assert len(queries) >= 2
    types = [q.query_type for q in queries]
    assert QueryType.DIRECT in types
    assert QueryType.FACT_CHECK in types
    for q in queries:
        assert q.claim_id == "claim_test_01"
        assert len(q.query.split()) >= 2


def test_query_generator_with_entities():
    """Verify that ENTITY_FOCUSED query includes orgs, persons, or locations."""
    claim = _make_claim(
        "Tesla will open a new manufacturing hub in Pune next year.",
        orgs=["Tesla"],
        locations=["Pune"],
    )
    queries = generate_queries(claim, max_queries=6)
    entity_queries = [q for q in queries if q.query_type == QueryType.ENTITY_FOCUSED]

    assert len(entity_queries) >= 1
    q_str = entity_queries[0].query
    assert "Tesla" in q_str
    assert "Pune" in q_str


def test_query_generator_with_numbers():
    """Verify that NUMERIC query includes numerical facts."""
    claim = _make_claim(
        "Company X laid off 5000 employees in Bengaluru.",
        orgs=["Company X"],
        locations=["Bengaluru"],
        numbers=["5000"],
    )
    queries = generate_queries(claim, max_queries=6)
    num_queries = [q for q in queries if q.query_type == QueryType.NUMERIC]

    assert len(num_queries) >= 1
    assert "5000" in num_queries[0].query


def test_query_generator_with_dates():
    """Verify that DATE_FOCUSED query includes temporal references."""
    claim = _make_claim(
        "The Cabinet approved the semiconductor scheme on Tuesday.",
        orgs=["Cabinet"],
        dates=["Tuesday"],
    )
    queries = generate_queries(claim, max_queries=6)
    date_queries = [q for q in queries if q.query_type == QueryType.DATE_FOCUSED]

    assert len(date_queries) >= 1
    assert "Tuesday" in date_queries[0].query


def test_query_generator_with_speaker_attribution():
    """Verify that attributed speaker is integrated into official/entity queries."""
    claim = _make_claim(
        "Inflation has declined to four percent.",
        speaker="Finance Minister",
        orgs=["Finance Ministry"],
    )
    queries = generate_queries(claim, max_queries=6)
    official_queries = [q for q in queries if q.query_type == QueryType.OFFICIAL]

    assert len(official_queries) >= 1
    assert "official statement" in official_queries[0].query.lower()


def test_query_generator_respects_max_limit():
    """Verify that returned queries do not exceed max_queries ceiling."""
    claim = _make_claim(
        "Infosys announces 10000 new tech jobs in Karnataka starting next month.",
        orgs=["Infosys"],
        locations=["Karnataka"],
        numbers=["10000"],
        dates=["next month"],
    )
    queries = generate_queries(claim, max_queries=3)
    assert len(queries) <= 3


def test_query_generator_short_claim():
    """Verify short input fallback produces at least one clean query."""
    claim = _make_claim("Gold prices fall.")
    queries = generate_queries(claim, max_queries=5)
    assert len(queries) >= 1
    assert "Gold" in queries[0].query or "prices" in queries[0].query
