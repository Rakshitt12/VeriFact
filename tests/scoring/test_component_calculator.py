"""Unit tests for ComponentCalculator across all 6 dimensions."""

import pytest

from backend.config.scoring_config import SCORING_WEIGHTS
from backend.retrieval.models import Evidence, SourceType
from backend.scoring.component_calculator import ComponentCalculator
from backend.scoring.models import ScoreFactor
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
    ClaimIndependenceResult,
    EvidenceCluster,
    EvidenceComparison,
    EvidenceStance,
    FactCheckComparison,
)


def _make_evidence(eid: str, stype: SourceType = SourceType.NEWS) -> Evidence:
    return Evidence(
        evidence_id=eid,
        claim_id="cl_test",
        title=f"Title for {eid}",
        url=f"https://example.com/{eid}",
        publisher="Example News",
        domain="example.com",
        snippet=f"Snippet for {eid}",
        source_type=stype,
        provider="gdelt",
        query_used="test query",
    )


def _make_source_analysis(
    eid: str,
    rel_score: int = 80,
    category: SourceCategory = SourceCategory.NEWS_MEDIA,
    transparency: TransparencyLevel = TransparencyLevel.HIGH,
    is_primary: bool = False,
) -> SourceAnalysis:
    return SourceAnalysis(
        evidence_id=eid,
        domain="example.com",
        publisher="Example News",
        source_type="NEWS",
        source_category=category,
        reliability_score=rel_score,
        reliability_label=ReliabilityLabel.HIGH if rel_score >= 75 else ReliabilityLabel.MEDIUM,
        transparency=transparency,
        primary_reporting=PrimaryReportingSignal(present=is_primary),
        metadata_quality=MetadataQuality(score=0.85),
        source_age=SourceAge.RECENT,
    )


def test_component_calculator_weight_validation():
    """Verify weights sum to 1.0 and normalization works if uneven."""
    calc = ComponentCalculator()
    assert sum(calc.weights.values()) == pytest.approx(1.0)

    # Test normalization of uneven weights
    uneven = {"evidence_agreement": 0.60, "source_quality": 0.60}
    calc_custom = ComponentCalculator(weights=uneven)
    assert sum(calc_custom.weights.values()) == pytest.approx(1.0)


def test_evidence_agreement_dimension():
    """Verify evidence agreement calculation under supporting and contradicting stances."""
    calc = ComponentCalculator()

    # 1. 2 independent supporting vs 0 contradicting -> 1.0 ratio
    comp_result = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        supporting_count=2,
        contradicting_count=0,
        independent_supporting_count=2,
        independent_contradicting_count=0,
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_1",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.9,
                relevance=0.8,
                reasoning="Agrees",
            ),
            EvidenceComparison(
                evidence_id="ev_2",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.9,
                relevance=0.8,
                reasoning="Agrees",
            ),
        ],
    )
    comp = calc._calc_evidence_agreement(comp_result)
    assert comp.factor == ScoreFactor.EVIDENCE_AGREEMENT
    assert comp.raw_score == 1.0
    assert comp.weighted_contribution == 30.0  # 1.0 * 0.30 * 100

    # 2. 1 supporting vs 1 contradicting -> 0.5 ratio
    comp_result.independent_contradicting_count = 2
    comp = calc._calc_evidence_agreement(comp_result)
    assert comp.raw_score == 0.5
    assert comp.weighted_contribution == 15.0


def test_source_quality_dimension():
    """Verify source quality averages the reliability of supporting sources."""
    calc = ComponentCalculator()
    ev1 = _make_evidence("ev_1")
    ev2 = _make_evidence("ev_2")

    sa1 = _make_source_analysis("ev_1", rel_score=90)
    sa2 = _make_source_analysis("ev_2", rel_score=70)

    comp_result = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_1",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.9,
                relevance=0.8,
                reasoning="Agrees",
            ),
            EvidenceComparison(
                evidence_id="ev_2",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.9,
                relevance=0.8,
                reasoning="Agrees",
            ),
        ],
    )

    comp = calc._calc_source_quality([ev1, ev2], [sa1, sa2], comp_result)
    assert comp.factor == ScoreFactor.SOURCE_QUALITY
    # Avg reliability: (90 + 70) / 2 = 80 -> 0.80 raw
    assert comp.raw_score == 0.80
    assert comp.weighted_contribution == 16.0  # 0.80 * 0.20 * 100


def test_independent_sources_dimension():
    """Verify independent sources scaling up to target 3."""
    calc = ComponentCalculator()

    # 1 independent source -> 1/3
    comp_result = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        independent_supporting_count=1,
    )
    comp = calc._calc_independent_sources(None, comp_result)
    assert comp.factor == ScoreFactor.INDEPENDENT_SOURCES
    assert comp.raw_score == pytest.approx(1 / 3, 0.001)

    # 3 independent sources -> 1.0 (capped)
    comp_result.independent_supporting_count = 3
    comp = calc._calc_independent_sources(None, comp_result)
    assert comp.raw_score == 1.0
    assert comp.weighted_contribution == 20.0


def test_fact_checks_dimension():
    """Verify fact-checks scoring under True, False, and no fact check."""
    calc = ComponentCalculator()

    # Baseline when no fact-check exists -> neutral 0.5
    comp = calc._calc_fact_checks(None)
    assert comp.factor == ScoreFactor.FACT_CHECKS
    assert comp.raw_score == 0.5
    assert comp.weighted_contribution == 7.5

    # With contradicting fact check -> 0.0
    fc = FactCheckComparison(
        fact_check_id="fc_1",
        claim_id="cl_test",
        verdict_normalized="False",
        raw_rating="False",
        fact_checker="Snopes",
        url="https://snopes.com/test",
        stance=EvidenceStance.CONTRADICTING,
        explanation="Debunked as false.",
    )
    comp_res = ClaimEvidenceComparisonResult(claim_id="cl_test", fact_checks=[fc])
    comp = calc._calc_fact_checks(comp_res)
    assert comp.raw_score == 0.0
    assert comp.weighted_contribution == 0.0


def test_official_evidence_dimension():
    """Verify official / primary documentation bonus."""
    calc = ComponentCalculator()

    ev_gov = _make_evidence("ev_gov", stype=SourceType.OFFICIAL)
    sa_gov = _make_source_analysis("ev_gov", category=SourceCategory.GOVERNMENT)

    comp_res = ClaimEvidenceComparisonResult(
        claim_id="cl_test",
        comparisons=[
            EvidenceComparison(
                evidence_id="ev_gov",
                claim_id="cl_test",
                stance=EvidenceStance.SUPPORTING,
                confidence=0.9,
                relevance=0.8,
                reasoning="Official notice",
            )
        ],
    )

    comp = calc._calc_official_evidence([ev_gov], [sa_gov], comp_res)
    assert comp.factor == ScoreFactor.OFFICIAL_EVIDENCE
    assert comp.raw_score == 1.0
    assert comp.weighted_contribution == 10.0


def test_transparency_dimension():
    """Verify transparency calculation based on metadata completeness."""
    calc = ComponentCalculator()
    sa = _make_source_analysis("ev_1")
    sa.metadata_quality.score = 0.80

    comp = calc._calc_transparency([sa])
    assert comp.factor == ScoreFactor.TRANSPARENCY
    assert comp.raw_score == 0.80
    assert comp.weighted_contribution == 4.0  # 0.80 * 0.05 * 100
