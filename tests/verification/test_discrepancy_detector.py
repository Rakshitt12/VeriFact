"""Unit tests for numeric, temporal, and polarity discrepancy detection."""

from backend.claim.models import Claim, ClaimType, ExtractedEntity
from backend.retrieval.models import Evidence, SourceType
from backend.verification.discrepancy_detector import (
    detect_discrepancies,
    extract_quantities,
)
from backend.verification.models import DiscrepancyType


def test_extract_quantities():
    """Verify quantity and unit extraction across currency, crore, and percentages."""
    q1 = extract_quantities("Company A announced a ₹500 crore investment in Gujarat.")
    assert len(q1) >= 1
    val, unit, phrase = q1[0]
    assert val == 500.0
    assert "crore" in unit or unit == "cr"

    q2 = extract_quantities("The government announced a ₹10 reduction in petrol prices.")
    assert len(q2) >= 1
    val, unit, phrase = q2[0]
    assert val == 10.0


def test_numeric_discrepancy_crore_investment():
    """Verify ₹500 crore vs ₹300 crore triggers NUMERIC discrepancy."""
    claim = Claim(
        claim_id="cl_inv_01",
        original_text="Company A announced a ₹500 crore investment in Gujarat.",
        normalized_text="Company A announced a ₹500 crore investment in Gujarat.",
        claim_type=ClaimType.ANNOUNCEMENT,
        numbers=["500 crore"],
        organizations=["Company A"],
        locations=["Gujarat"],
        source_sentence="Company A announced a ₹500 crore investment in Gujarat.",
    )

    ev_conflicting = Evidence(
        evidence_id="ev_01",
        claim_id="cl_inv_01",
        title="Company A announces ₹300 crore plant in Gujarat",
        url="https://example.com/inv",
        snippet="Company A announced a ₹300 crore investment in Gujarat today.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Company A Gujarat investment",
    )

    discrepancies = detect_discrepancies(claim, ev_conflicting)
    assert len(discrepancies) >= 1
    num_disc = [d for d in discrepancies if d.discrepancy_type == DiscrepancyType.NUMERIC]
    assert len(num_disc) == 1
    assert "500" in num_disc[0].claim_value
    assert "300" in num_disc[0].evidence_value


def test_numeric_discrepancy_petrol_cut():
    """Verify ₹10 cut vs ₹8 cut triggers NUMERIC discrepancy."""
    claim = Claim(
        claim_id="cl_fuel_01",
        original_text="The central government announced a ₹10 reduction in petrol prices.",
        normalized_text="The central government announced a ₹10 reduction in petrol prices.",
        claim_type=ClaimType.POLICY,
        numbers=["10"],
        organizations=["central government"],
        source_sentence="The central government announced a ₹10 reduction in petrol prices.",
    )

    ev = Evidence(
        evidence_id="ev_fuel_8",
        claim_id="cl_fuel_01",
        title="Fuel relief: Government slashes petrol price by ₹8",
        url="https://example.com/fuel",
        snippet="The ministry announced that petrol prices will be cut by ₹8 per litre.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="petrol price reduction",
    )

    discrepancies = detect_discrepancies(claim, ev)
    num_disc = [d for d in discrepancies if d.discrepancy_type == DiscrepancyType.NUMERIC]
    assert len(num_disc) == 1
    assert "10" in num_disc[0].claim_value
    assert "8" in num_disc[0].evidence_value


def test_polarity_denial_detection():
    """Verify explicit resignation denial triggers POLARITY discrepancy."""
    claim = Claim(
        claim_id="cl_res_01",
        original_text="Person A resigned from Organization B.",
        normalized_text="Person A resigned from Organization B.",
        claim_type=ClaimType.PERSON_ACTION,
        persons=["Person A"],
        organizations=["Organization B"],
        source_sentence="Person A resigned from Organization B.",
    )

    ev_denial = Evidence(
        evidence_id="ev_denial",
        claim_id="cl_res_01",
        title="Organization B denies reports of Person A resignation",
        url="https://example.com/denial",
        snippet="Organization B confirmed that Person A remains in the position and dismissed reports of resignation as baseless.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Person A Organization B resignation",
    )

    discrepancies = detect_discrepancies(claim, ev_denial)
    pol_disc = [d for d in discrepancies if d.discrepancy_type == DiscrepancyType.POLARITY]
    assert len(pol_disc) >= 1
    assert pol_disc[0].severity == "CRITICAL"


def test_no_discrepancy_when_matching():
    """Verify no discrepancy flagged when numbers and polarity match."""
    claim = Claim(
        claim_id="cl_match_01",
        original_text="The government approved a ₹500 crore project in Gujarat.",
        normalized_text="The government approved a ₹500 crore project in Gujarat.",
        claim_type=ClaimType.POLICY,
        numbers=["500 crore"],
        locations=["Gujarat"],
        source_sentence="The government approved a ₹500 crore project in Gujarat.",
    )

    ev_matching = Evidence(
        evidence_id="ev_match",
        claim_id="cl_match_01",
        title="Cabinet clears ₹500 crore project in Gujarat",
        url="https://example.com/match",
        snippet="The cabinet has approved a ₹500 crore infrastructure project in Gujarat.",
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="Gujarat project 500 crore",
    )

    discrepancies = detect_discrepancies(claim, ev_matching)
    assert len(discrepancies) == 0
