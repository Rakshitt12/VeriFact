"""Unit tests for grounded PenaltyCalculator deductions."""

import pytest

from backend.config.scoring_config import (
    PENALTY_ANONYMOUS_UNINDEXED,
    PENALTY_CRITICAL_DISCREPANCY,
    PENALTY_MAJOR_DISCREPANCY,
    PENALTY_REPUTABLE_CONTRADICTION,
)
from backend.scoring.penalties import PenaltyCalculator
from backend.sources.models import (
    MetadataQuality,
    PrimaryReportingSignal,
    ReliabilityLabel,
    SourceAge,
    SourceAnalysis,
    SourceCategory,
    TransparencyLevel,
)
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    Discrepancy,
    DiscrepancyType,
    EvidenceComparison,
    EvidenceStance,
    FactCheckComparison,
)


def _make_source_analysis(
    eid: str,
    rel_score: int = 80,
    category: SourceCategory = SourceCategory.NEWS_MEDIA,
    transparency_score: float = 0.8,
) -> SourceAnalysis:
    return SourceAnalysis(
        evidence_id=eid,
        domain="example.com",
        publisher="Example News",
        source_type="NEWS",
        source_category=category,
        reliability_score=rel_score,
        reliability_label=ReliabilityLabel.HIGH if rel_score >= 75 else ReliabilityLabel.MEDIUM,
        transparency=TransparencyLevel.HIGH,
        primary_reporting=PrimaryReportingSignal(present=False),
        metadata_quality=MetadataQuality(score=transparency_score),
        source_age=SourceAge.RECENT,
    )


def test_discrepancy_penalties():
    """Verify critical, major, and minor discrepancy penalties."""
    calc = PenaltyCalculator()

    disc_crit = Discrepancy(
        discrepancy_type=DiscrepancyType.NUMERIC,
        aspect="tax_rate",
        claim_value="50%",
        evidence_value="5%",
        severity="CRITICAL",
    )
    disc_maj = Discrepancy(
        discrepancy_type=DiscrepancyType.TEMPORAL,
        aspect="effective_year",
        claim_value="2024",
        evidence_value="2027",
        severity="MAJOR",
    )

    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        key_discrepancies=[disc_crit, disc_maj],
    )

    penalties = calc.calculate_penalties(comparison_result=comp_res)
    penalty_types = {p.penalty_type: p.amount for p in penalties}

    assert "numeric_discrepancy" in penalty_types
    assert penalty_types["numeric_discrepancy"] == PENALTY_CRITICAL_DISCREPANCY
    assert "temporal_discrepancy" in penalty_types
    assert penalty_types["temporal_discrepancy"] == PENALTY_MAJOR_DISCREPANCY


def test_reputable_refutation_penalty():
    """Verify penalty when a verified fact-checker contradicts the claim."""
    calc = PenaltyCalculator()

    fc = FactCheckComparison(
        fact_check_id="fc_snopes",
        claim_id="cl_test",
        verdict_normalized="False",
        raw_rating="Pants on Fire",
        fact_checker="PolitiFact",
        url="https://politifact.com/factcheck/123",
        stance=EvidenceStance.CONTRADICTING,
        explanation="Debunked by official records.",
    )

    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        fact_checks=[fc],
    )

    penalties = calc.calculate_penalties(comparison_result=comp_res)
    assert len(penalties) == 1
    assert penalties[0].penalty_type == "fact_check_refutation"
    assert penalties[0].amount == PENALTY_REPUTABLE_CONTRADICTION


def test_anonymous_unindexed_penalty():
    """Verify penalty when supporting evidence is exclusively from low-transparency sources."""
    calc = PenaltyCalculator()

    sa_low = _make_source_analysis("ev_anon", rel_score=35, transparency_score=0.1)

    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_anon",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.7,
                relevance=0.8,
                reasoning="Agrees",
            )
        ],
    )

    penalties = calc.calculate_penalties(
        comparison_result=comp_res,
        source_analyses=[sa_low],
    )

    assert any(p.penalty_type == "anonymous_unindexed_sources" for p in penalties)
    anon_p = next(p for p in penalties if p.penalty_type == "anonymous_unindexed_sources")
    assert anon_p.amount == PENALTY_ANONYMOUS_UNINDEXED
