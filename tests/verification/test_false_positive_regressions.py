"""Regression tests for false-positive contradiction penalties.

Bug 1 (fact-check mismatch): a fact-check reviewing a DIFFERENT assertion that
shares keywords/entities must not stamp its rating onto the submitted claim.
Bug 2 (polarity overreach): denials unrelated to the claim's assertion —
including the supportive phrase "remains the ..." — must not yield CRITICAL
polarity discrepancies, while genuine adjacent denials must still be caught.
"""

from backend.claim.models import Claim, ClaimType, ExtractedEntity
from backend.retrieval.models import Evidence, SourceType
from backend.scoring.penalties import PenaltyCalculator
from backend.verification.discrepancy_detector import detect_discrepancies
from backend.verification.factcheck_mapper import map_fact_check_comparison
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    DiscrepancyType,
    EvidenceStance,
)


def _eiffel_claim() -> Claim:
    return Claim(
        claim_id="cl_eiffel",
        original_text="The Eiffel Tower was completed in 1889 for the World's Fair in Paris.",
        normalized_text="The Eiffel Tower was completed in 1889 for the World's Fair in Paris.",
        claim_type=ClaimType.EVENT,
        entities=[
            ExtractedEntity(text="Eiffel Tower", label="FAC"),
            ExtractedEntity(text="1889", label="DATE"),
            ExtractedEntity(text="Paris", label="GPE"),
        ],
        dates=["1889"],
        organizations=["Eiffel Tower"],
        locations=["Paris"],
        source_sentence="The Eiffel Tower was completed in 1889 for the World's Fair in Paris.",
    )


def _mismatched_fact_check() -> Evidence:
    """Fact-check about a different Eiffel Tower assertion sharing keywords."""
    reviewed = (
        "Viral photo claims to show the Eiffel Tower collapsing "
        "after a massive earthquake in Paris"
    )
    return Evidence(
        evidence_id="ev_fc_mismatch",
        claim_id="cl_eiffel",
        title="Fact Check: Eiffel Tower collapse photo is digitally altered",
        url="https://www.example-factcheck.org/eiffel-photo",
        publisher="Example Fact Checker",
        domain="example-factcheck.org",
        snippet=f"Claim reviewed: '{reviewed}'. Rating: False",
        source_type=SourceType.FACT_CHECK,
        provider="google_factcheck",
        query_used="Eiffel Tower fact check",
        metadata={
            "claim_reviewed": reviewed,
            "verdict": "False",
            "rating": "False",
        },
    )


def test_mismatched_fact_check_does_not_contradict():
    """Eiffel Tower case: unrelated False rating must not become CONTRADICTING."""
    claim = _eiffel_claim()
    fc_comp, ev_comp = map_fact_check_comparison(
        _mismatched_fact_check(), claim.claim_id, claim=claim
    )
    # Publisher rating wording is preserved, never reinterpreted ...
    assert fc_comp.verdict_normalized == "False"
    assert fc_comp.raw_rating == "False"
    # ... but the stance must not contradict the submitted claim.
    assert fc_comp.stance != EvidenceStance.CONTRADICTING
    assert ev_comp.stance != EvidenceStance.CONTRADICTING
    assert any(
        "match" in lim.lower() for lim in ev_comp.limitations
    ), f"expected mismatch limitation, got {ev_comp.limitations}"


def test_mismatched_fact_check_triggers_no_refutation_penalty():
    """The -25 fact_check_refutation penalty must not fire on a mismatch."""
    claim = _eiffel_claim()
    fc_comp, ev_comp = map_fact_check_comparison(
        _mismatched_fact_check(), claim.claim_id, claim=claim
    )
    comparison = ClaimEvidenceComparisonResult(
        claim_id=claim.claim_id,
        comparisons=[ev_comp],
        fact_checks=[fc_comp],
    )
    penalties = PenaltyCalculator().calculate_penalties(
        comparison_result=comparison, source_analyses=[], evidence_items=[]
    )
    assert [
        p for p in penalties if p.penalty_type == "fact_check_refutation"
    ] == []


def test_aligned_fact_check_still_contradicts():
    """A fact-check reviewing the SAME assertion keeps its CONTRADICTING stance."""
    claim = Claim(
        claim_id="cl_fuel",
        original_text="The central government announced a 10 rupee reduction in petrol prices.",
        normalized_text="The central government announced a 10 rupee reduction in petrol prices.",
        claim_type=ClaimType.POLICY,
        numbers=["10"],
        organizations=["central government"],
        source_sentence="The central government announced a 10 rupee reduction in petrol prices.",
    )
    reviewed = "The central government cut petrol prices by Rs 10"
    ev = Evidence(
        evidence_id="ev_fc_aligned",
        claim_id="cl_fuel",
        title="Fact Check: No order issued for Rs 10 petrol cut",
        url="https://www.example-factcheck.org/fuel-cut",
        publisher="Example Fact Checker",
        domain="example-factcheck.org",
        snippet=f"Claim reviewed: '{reviewed}'. Rating: False",
        source_type=SourceType.FACT_CHECK,
        provider="google_factcheck",
        query_used="petrol cut fact check",
        metadata={"claim_reviewed": reviewed, "verdict": "False", "rating": "False"},
    )
    fc_comp, ev_comp = map_fact_check_comparison(ev, claim.claim_id, claim=claim)
    assert fc_comp.stance == EvidenceStance.CONTRADICTING
    assert ev_comp.stance == EvidenceStance.CONTRADICTING
    assert ev_comp.confidence >= 0.90


def _apple_claim() -> Claim:
    return Claim(
        claim_id="cl_apple",
        original_text=(
            "Apple became the first publicly traded U.S. company "
            "to reach a $1 trillion market cap in 2018"
        ),
        normalized_text=(
            "Apple became the first publicly traded U.S. company "
            "to reach a $1 trillion market cap in 2018"
        ),
        claim_type=ClaimType.FINANCIAL,
        entities=[
            ExtractedEntity(text="Apple", label="ORG"),
            ExtractedEntity(text="2018", label="DATE"),
        ],
        dates=["2018"],
        numbers=["1 trillion"],
        organizations=["Apple"],
        source_sentence=(
            "Apple became the first publicly traded U.S. company "
            "to reach a $1 trillion market cap in 2018"
        ),
    )


def test_supportive_remains_phrase_triggers_no_polarity():
    """'remains the most valuable company' is supportive, not a denial."""
    ev = Evidence(
        evidence_id="ev_apple_support",
        claim_id="cl_apple",
        title="Apple hits $1 trillion market value",
        url="https://example.com/apple-trillion",
        snippet=(
            "Apple became the first US public company to reach a $1 trillion "
            "market capitalization in August 2018, and remains the most valuable "
            "company in the world today."
        ),
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Apple trillion market cap",
    )
    discs = detect_discrepancies(_apple_claim(), ev)
    assert [d for d in discs if d.discrepancy_type == DiscrepancyType.POLARITY] == []


def test_unrelated_denial_elsewhere_triggers_no_polarity():
    """A denial in a sentence without the claim entity must not flag polarity."""
    ev = Evidence(
        evidence_id="ev_apple_noise",
        claim_id="cl_apple",
        title="Apple hits $1 trillion market value",
        url="https://example.com/apple-noise",
        snippet=(
            "Apple became the first US public company to reach a $1 trillion "
            "market capitalization in August 2018. In other news, the supplier "
            "denied rumors about a delayed component shipment."
        ),
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Apple trillion market cap",
    )
    discs = detect_discrepancies(_apple_claim(), ev)
    assert [d for d in discs if d.discrepancy_type == DiscrepancyType.POLARITY] == []


def test_genuine_adjacent_denial_still_flagged():
    """A denial in the same sentence as the claim entity must still be caught."""
    claim = Claim(
        claim_id="cl_res_adj",
        original_text="Person A resigned from Organization B.",
        normalized_text="Person A resigned from Organization B.",
        claim_type=ClaimType.PERSON_ACTION,
        entities=[
            ExtractedEntity(text="Person A", label="PERSON"),
            ExtractedEntity(text="Organization B", label="ORG"),
        ],
        persons=["Person A"],
        organizations=["Organization B"],
        source_sentence="Person A resigned from Organization B.",
    )
    ev = Evidence(
        evidence_id="ev_adj_denial",
        claim_id="cl_res_adj",
        title="Organization B responds to resignation reports",
        url="https://example.com/adjacent-denial",
        snippet="In a statement today, Person A denied resigning from Organization B.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Person A Organization B resignation",
    )
    discs = detect_discrepancies(claim, ev)
    pol = [d for d in discs if d.discrepancy_type == DiscrepancyType.POLARITY]
    assert len(pol) >= 1
    assert pol[0].severity == "CRITICAL"
