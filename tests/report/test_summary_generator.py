"""Summary-generator determinism tests (spec sections 33-35)."""

from backend.report.summary_generator import SummaryGenerator
from tests.report.conftest import make_claim_score


def test_insufficient_summary_respects_score_state():
    """Spec 34 — score=None must not claim 'scored poorly'."""
    text = SummaryGenerator.generate_claim_summary(
        classification="INSUFFICIENT EVIDENCE", score=None,
        is_insufficient_evidence=True, independent_sources=0,
        supporting_count=0, contradicting_count=0)
    assert "not enough independent evidence" in text.lower()
    assert "scored poorly" not in text.lower()


def test_classification_templates_are_deterministic():
    s1 = SummaryGenerator.generate_claim_summary(
        classification="Strongly Supported", score=95,
        is_insufficient_evidence=False, independent_sources=3,
        supporting_count=3, contradicting_count=0)
    s2 = SummaryGenerator.generate_claim_summary(
        classification="Strongly Supported", score=95,
        is_insufficient_evidence=False, independent_sources=3,
        supporting_count=3, contradicting_count=0)
    assert s1 == s2
    assert "supportive" in s1.lower()

    mixed = SummaryGenerator.generate_claim_summary(
        classification="Mixed / Uncertain", score=60,
        is_insufficient_evidence=False, independent_sources=3,
        supporting_count=1, contradicting_count=1)
    assert "mixed" in mixed.lower()

    contra = SummaryGenerator.generate_claim_summary(
        classification="Strongly Contradicted", score=10,
        is_insufficient_evidence=False, independent_sources=2,
        supporting_count=0, contradicting_count=2)
    assert "contradiction" in contra.lower()


def test_executive_summary_multi_claim_distribution():
    from backend.report.models import ClaimVerificationReport, EvidenceSummary
    reports = [
        ClaimVerificationReport(
            claim_id="c1", claim_text="t1", claim_type="EVENT", importance="HIGH",
            score=80, classification="Mostly Supported",
            summary="s", evidence_summary=EvidenceSummary()),
        ClaimVerificationReport(
            claim_id="c2", claim_text="t2", claim_type="EVENT", importance="LOW",
            score=None, classification="INSUFFICIENT EVIDENCE",
            is_insufficient_evidence=True, summary="s",
            evidence_summary=EvidenceSummary()),
    ]
    text = SummaryGenerator.generate_executive_summary(
        claim_reports=reports, overall_score=80,
        overall_classification="Mostly Supported")
    assert "2 material" in text
    assert "insufficient" in text.lower()
    # Must carry the anti-probability disclaimer, not a probability claim
    assert "should not be interpreted" in text.lower()
