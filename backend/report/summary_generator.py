"""Deterministic summary generation for executive overviews and claim-level reports."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.report.models import ClaimVerificationReport

# Local classification constants to avoid circular import with backend.api.schemas.
# Must stay in sync with ClassificationLabel values in backend/api/schemas.py.
_STRONGLY_SUPPORTED = "Strongly Supported"
_MOSTLY_SUPPORTED = "Mostly Supported"
_MIXED_UNCERTAIN = "Mixed / Uncertain"
_WEAKLY_SUPPORTED = "Weakly Supported"
_STRONGLY_CONTRADICTED = "Strongly Contradicted"


class SummaryGenerator:
    """Generates consistent, evidence-grounded textual summaries without hallucination."""

    @staticmethod
    def generate_claim_summary(
        classification: str,
        score: Optional[int],
        is_insufficient_evidence: bool,
        independent_sources: int,
        supporting_count: int,
        contradicting_count: int,
        discrepancy_count: int = 0,
        fact_check_count: int = 0,
    ) -> str:
        """Produce deterministic claim summary strictly adhering to classification and score state."""
        if is_insufficient_evidence or score is None:
            return (
                "There is not enough independent evidence in the retrieved material to produce a reliable "
                f"credibility assessment ({independent_sources} independent source cluster(s) found; "
                "minimum threshold is 2)."
            )

        parts: List[str] = []

        if classification == _STRONGLY_SUPPORTED:
            parts.append(
                f"Evidence is predominantly supportive across {independent_sources} independent source cluster(s) analyzed."
            )
        elif classification == _MOSTLY_SUPPORTED:
            parts.append(
                f"Evidence largely corroborates the core assertion across {independent_sources} independent reporting cluster(s)."
            )
        elif classification == _MIXED_UNCERTAIN:
            parts.append(
                "The retrieved evidence is mixed, with independent sources supporting and contradicting different aspects of the claim."
            )
        elif classification == _WEAKLY_SUPPORTED:
            parts.append(
                "Limited corroborating evidence was found, accompanied by material unverified aspects or contrary accounts."
            )
        elif classification == _STRONGLY_CONTRADICTED:
            parts.append(
                "Relevant independent evidence contains substantial contradictions to the material claim."
            )
        else:
            parts.append(f"Claim evaluated under '{classification}' with score {score}/100.")

        if fact_check_count > 0:
            parts.append(f"{fact_check_count} verified fact-check review(s) were analyzed.")

        if discrepancy_count > 0:
            parts.append(f"{discrepancy_count} factual discrepancy(ies) were identified against reporting.")

        return " ".join(parts)

    @staticmethod
    def generate_executive_summary(
        claim_reports: List["ClaimVerificationReport"],
        overall_score: Optional[int],
        overall_classification: str,
    ) -> str:
        """Produce document-level executive summary synthesizing multi-claim distributions."""
        if not claim_reports:
            return (
                "No discrete factual assertions were detected in the submitted content for verification. "
                "The verification engine requires factual claims to retrieve and evaluate evidence."
            )

        total_claims = len(claim_reports)
        sufficient_claims = [c for c in claim_reports if not c.is_insufficient_evidence and c.score is not None]
        insufficient_claims = [c for c in claim_reports if c.is_insufficient_evidence or c.score is None]

        lines: List[str] = [
            f"The submitted content contains {total_claims} material factual claim(s)."
        ]

        if sufficient_claims:
            supp_count = sum(
                1 for c in sufficient_claims
                if c.classification in (_STRONGLY_SUPPORTED, _MOSTLY_SUPPORTED)
            )
            contra_count = sum(
                1 for c in sufficient_claims
                if c.classification in (_STRONGLY_CONTRADICTED, _WEAKLY_SUPPORTED)
            )
            mixed_count = sum(
                1 for c in sufficient_claims
                if c.classification == _MIXED_UNCERTAIN
            )

            status_fragments: List[str] = []
            if supp_count > 0:
                status_fragments.append(f"{supp_count} supported by independent evidence")
            if contra_count > 0:
                status_fragments.append(f"{contra_count} contradicted or contested")
            if mixed_count > 0:
                status_fragments.append(f"{mixed_count} with mixed evidence")
            if insufficient_claims:
                status_fragments.append(f"{len(insufficient_claims)} with insufficient corroboration")

            lines.append("Analysis indicates: " + ", ".join(status_fragments) + ".")

            if overall_score is not None:
                lines.append(
                    f"The overall document credibility is evaluated as '{overall_classification}' ({overall_score}/100)."
                )
            else:
                lines.append(f"Overall document assessment is '{overall_classification}'.")
        else:
            lines.append(
                "All extracted factual assertions fell below the minimum independent corroboration threshold "
                "to form a reliable credibility assessment."
            )

        # Methodology caveat
        lines.append(
            "This assessment represents evidence strength and consistency at the time of retrieval, "
            "and should not be interpreted as an ontological probability of truth."
        )

        return " ".join(lines)
