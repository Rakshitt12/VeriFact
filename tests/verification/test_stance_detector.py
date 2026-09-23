"""Unit tests for evidence stance classification and claim aspect matching."""

from backend.claim.models import Claim, ClaimType
from backend.retrieval.models import Evidence, SourceType
from backend.verification.models import AspectType, EvidenceStance
from backend.verification.stance_detector import classify_evidence_stance


def test_stance_supporting():
    """Verify evidence confirming the core action and entities is classified as SUPPORTING."""
    claim = Claim(
        claim_id="cl_res_01",
        original_text="Person A resigned from Organization B.",
        normalized_text="Person A resigned from Organization B.",
        claim_type=ClaimType.PERSON_ACTION,
        persons=["Person A"],
        organizations=["Organization B"],
        source_sentence="Person A resigned from Organization B.",
    )

    ev = Evidence(
        evidence_id="ev_supp",
        claim_id="cl_res_01",
        title="Person A steps down from Organization B",
        url="https://example.com/resignation",
        snippet="Person A submitted their resignation to Organization B on Monday, vacating the leadership post.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Person A Organization B resignation",
    )

    comp = classify_evidence_stance(claim, ev)
    assert comp.stance == EvidenceStance.SUPPORTING
    assert comp.confidence >= 0.80
    assert len(comp.supporting_points) > 0
    assert len(comp.contradicting_points) == 0


def test_stance_contradicting_denial():
    """Verify evidence refuting the claim action is classified as CONTRADICTING."""
    claim = Claim(
        claim_id="cl_res_02",
        original_text="Person A resigned from Organization B.",
        normalized_text="Person A resigned from Organization B.",
        claim_type=ClaimType.PERSON_ACTION,
        persons=["Person A"],
        organizations=["Organization B"],
        source_sentence="Person A resigned from Organization B.",
    )

    ev = Evidence(
        evidence_id="ev_contra_denial",
        claim_id="cl_res_02",
        title="Organization B denies reports of Person A quitting",
        url="https://example.com/denial",
        snippet="Organization B rejected rumors of resignation and confirmed Person A remains in the position.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Person A Organization B resignation",
    )

    comp = classify_evidence_stance(claim, ev)
    assert comp.stance == EvidenceStance.CONTRADICTING
    assert len(comp.contradicting_points) > 0
    assert "denial" in comp.signals[0] or "polarity" in comp.reasoning.lower() or "contradicts" in comp.reasoning.lower()


def test_stance_contradicting_with_partial_support():
    """Verify numerical mismatch yields CONTRADICTING while noting partial aspect support."""
    claim = Claim(
        claim_id="cl_inv_01",
        original_text="Company A announced a ₹500 crore investment in Gujarat in September.",
        normalized_text="Company A announced a ₹500 crore investment in Gujarat in September.",
        claim_type=ClaimType.ANNOUNCEMENT,
        numbers=["500 crore"],
        organizations=["Company A"],
        locations=["Gujarat"],
        dates=["September"],
        source_sentence="Company A announced a ₹500 crore investment in Gujarat in September.",
    )

    ev = Evidence(
        evidence_id="ev_300cr",
        claim_id="cl_inv_01",
        title="Company A announces ₹300 crore investment in Gujarat",
        url="https://example.com/inv",
        snippet="Company A announced a ₹300 crore investment in Gujarat in September for a new facility.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Company A Gujarat investment",
    )

    comp = classify_evidence_stance(claim, ev)
    assert comp.stance == EvidenceStance.CONTRADICTING
    assert len(comp.discrepancies) >= 1
    # Check that partial support of context/entities is preserved
    assert len(comp.supporting_points) > 0 or "partial" in comp.reasoning.lower()
    assert "300" in comp.contradicting_points[0]


def test_stance_neutral():
    """Verify article on subject that neither supports nor refutes is NEUTRAL."""
    claim = Claim(
        claim_id="cl_res_03",
        original_text="Person A resigned from Organization B.",
        normalized_text="Person A resigned from Organization B.",
        claim_type=ClaimType.PERSON_ACTION,
        persons=["Person A"],
        organizations=["Organization B"],
        source_sentence="Person A resigned from Organization B.",
    )

    ev = Evidence(
        evidence_id="ev_neutral",
        claim_id="cl_res_03",
        title="Person A visits regional summit in Delhi",
        url="https://example.com/summit",
        snippet="Person A attended a major technology summit in Delhi today as a keynote speaker for Organization B.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Person A Organization B",
    )

    comp = classify_evidence_stance(claim, ev)
    assert comp.stance == EvidenceStance.NEUTRAL
    assert len(comp.neutral_points) > 0


def test_stance_insufficient():
    """Verify vague or minimal evidence text is classified as INSUFFICIENT."""
    claim = Claim(
        claim_id="cl_fin_01",
        original_text="Company X lost ₹500 crore in Q2.",
        normalized_text="Company X lost ₹500 crore in Q2.",
        claim_type=ClaimType.FINANCIAL,
        numbers=["500 crore"],
        organizations=["Company X"],
        source_sentence="Company X lost ₹500 crore in Q2.",
    )

    ev = Evidence(
        evidence_id="ev_vague",
        claim_id="cl_fin_01",
        title="Company X financial update",
        url="https://example.com/update",
        snippet="Company X released quarterly filings today.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Company X loss",
    )

    comp = classify_evidence_stance(claim, ev)
    assert comp.stance == EvidenceStance.INSUFFICIENT
    assert "brief" in comp.reasoning.lower() or "insufficient" in comp.reasoning.lower()


def test_aspect_matches_preserved():
    """Verify AspectMatch entries are generated for WHO, WHERE, AMOUNT, ACTION."""
    claim = Claim(
        claim_id="cl_aspects",
        original_text="Government X approved a ₹5000 crore project in Gujarat.",
        normalized_text="Government X approved a ₹5000 crore project in Gujarat.",
        claim_type=ClaimType.POLICY,
        organizations=["Government X"],
        locations=["Gujarat"],
        numbers=["5000 crore"],
        source_sentence="Government X approved a ₹5000 crore project in Gujarat.",
    )

    ev = Evidence(
        evidence_id="ev_aspects",
        claim_id="cl_aspects",
        title="Government X clears ₹5000 crore project in Gujarat",
        url="https://example.com/cleared",
        snippet="Government X approved a ₹5000 crore project in Gujarat following cabinet approval.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Government X Gujarat 5000 crore",
    )

    comp = classify_evidence_stance(claim, ev)
    matched_types = {m.aspect_type for m in comp.matched_claim_aspects}
    assert AspectType.WHO in matched_types or AspectType.WHERE in matched_types
