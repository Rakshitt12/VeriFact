"""Fact-check rating normalization and stance mapping.

Translates diverse verdicts from fact-checking organizations (e.g., Google Fact Check,
Boom Live, PolitiFact, Snopes, AFP, Full Fact) into normalized verdicts and
deterministic EvidenceStance classifications.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from backend.claim.models import Claim
from backend.config.scoring_config import FACT_CHECK_RATING_MAP
from backend.logging_config import logger
from backend.retrieval.models import Evidence, SourceType
from backend.verification.models import (
    AspectMatch,
    AspectType,
    EvidenceComparison,
    EvidenceStance,
    FactCheckComparison,
)
from backend.verification.similarity import get_words, jaccard_similarity
from backend.verification.stance_detector import classify_evidence_stance


def _extract_raw_rating(evidence: Evidence) -> str:
    """Extract raw verdict/rating label from evidence metadata or snippet."""
    if evidence.metadata:
        for key in ("rating", "verdict", "textual_rating", "rating_label"):
            val = evidence.metadata.get(key)
            if val and isinstance(val, str) and val.strip():
                return val.strip()

    # Fallback to snippet regex: "Rating: <rating>"
    if evidence.snippet:
        m = re.search(r"Rating:\s*([^.\n]+)", evidence.snippet, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return "Unknown"


def map_raw_rating_to_verdict_and_stance(raw_rating: str) -> Tuple[str, EvidenceStance]:
    """Map a raw rating string to (normalized_verdict, EvidenceStance).

    Examples:
        "False" -> ("False", EvidenceStance.CONTRADICTING)
        "Pants on Fire" -> ("Pants on Fire", EvidenceStance.CONTRADICTING)
        "True" -> ("True", EvidenceStance.SUPPORTING)
        "Mostly True" -> ("Mostly True", EvidenceStance.SUPPORTING)
        "Half True" -> ("Half True", EvidenceStance.NEUTRAL)
    """
    clean = raw_rating.strip().lower()

    # 1. Exact match in configured rating dictionary
    if clean in FACT_CHECK_RATING_MAP:
        verdict, stance_str = FACT_CHECK_RATING_MAP[clean]
        return verdict, EvidenceStance(stance_str)

    # 2. Substring & semantic heuristics
    # Negative / Contradicting indicators
    if any(k in clean for k in ["pants on fire", "fake", "fabricated", "hoax", "debunked", "untrue", "unfounded", "bust", "disproven"]):
        return "False", EvidenceStance.CONTRADICTING

    if "misleading" in clean or "distort" in clean:
        return "Misleading", EvidenceStance.CONTRADICTING

    if "mostly false" in clean or "mostly incorrect" in clean:
        return "Mostly False", EvidenceStance.CONTRADICTING

    if "false" in clean or "incorrect" in clean:
        # ensure not "partly false" or "half false"
        if any(prefix in clean for prefix in ["half", "partly", "mixture", "partially"]):
            return "Partly False", EvidenceStance.NEUTRAL
        return "False", EvidenceStance.CONTRADICTING

    # Positive / Supporting indicators
    if "mostly true" in clean or "mostly correct" in clean or "mostly accurate" in clean:
        return "Mostly True", EvidenceStance.SUPPORTING

    if any(k in clean for k in ["true", "correct", "accurate", "verified", "confirmed"]):
        if any(prefix in clean for prefix in ["half", "partly", "mixture", "partially"]):
            return "Partly True", EvidenceStance.NEUTRAL
        return "True", EvidenceStance.SUPPORTING

    # Neutral / Inconclusive indicators
    if any(k in clean for k in ["half", "mixture", "mixed", "unproven", "unverified", "inconclusive", "context", "disputed"]):
        return "Needs Context", EvidenceStance.NEUTRAL

    logger.debug("Unrecognized fact check rating: '%s'. Defaulting to Unverified/NEUTRAL", raw_rating)
    return "Unverified", EvidenceStance.NEUTRAL


def is_fact_check_evidence(evidence: Evidence) -> bool:
    """Determine whether an Evidence item represents a formal fact-check evaluation."""
    if evidence.source_type == SourceType.FACT_CHECK:
        return True

    if evidence.provider in ("factcheck_api", "google_factcheck"):
        return True

    if evidence.metadata and any(k in evidence.metadata for k in ("verdict", "claim_reviewed", "rating")):
        return True

    # Check publisher / domain for known fact-checking outlets
    domain = (evidence.domain or "").lower()
    publisher = (evidence.publisher or "").lower()
    for fc_kw in ["politifact", "snopes", "factcheck", "boomlive", "altnews", "fullfact", "afp fact check", "lead stories"]:
        if fc_kw in domain or fc_kw in publisher:
            return True

    return False


# ---------------------------------------------------------------------------
# Fact-check / submitted-claim alignment.
#
# Retrieval providers (e.g. Google Fact Check API) match by keyword/entity,
# not by exact assertion, so a returned review may address a DIFFERENT claim
# that merely shares topic words. Applying its rating blindly stamps false
# contradictions onto true claims (and false confirmations onto false ones).
# ---------------------------------------------------------------------------

# Metadata keys that may carry the exact assertion the fact-checker reviewed.
_REVIEWED_TEXT_METADATA_KEYS = (
    "claim_reviewed",
    "reviewed_claim",
    "claim_text",
    "reviewed_text",
)

# Snippet/title patterns carrying the reviewed assertion. The Google Fact
# Check provider emits: "Claim reviewed: '<text>'. Rating: <rating>".
_SNIPPET_REVIEW_PATTERNS = (
    re.compile(r"Claim reviewed:\s*['\"](.+?)['\"]", re.IGNORECASE | re.DOTALL),
    re.compile(r"Claim:\s*(.+?)(?:\.?\s*Rating:|$)", re.IGNORECASE | re.DOTALL),
)

# Alignment gates (heuristic, deterministic). A review is trusted only when
# the submitted claim's discriminating aspects (dates/numbers) appear in the
# reviewed text AND there is topical overlap (token Jaccard or aspect
# coverage). Shared entities alone are not sufficient: "Eiffel Tower ...
# 1889" and "Eiffel Tower ... collapsing photo" share entities but assert
# different facts.
_ALIGNMENT_JACCARD_THRESHOLD = 0.15
_ALIGNMENT_COVERAGE_THRESHOLD = 0.5
_MISALIGNED_SCORE = 0.15


def _extract_reviewed_claim_text(evidence: Evidence) -> Optional[str]:
    """Return the exact assertion the fact-checker reviewed, if recoverable."""
    if evidence.metadata:
        for key in _REVIEWED_TEXT_METADATA_KEYS:
            val = evidence.metadata.get(key)
            if val and isinstance(val, str) and val.strip():
                return val.strip()
    for text in (evidence.snippet, evidence.title, evidence.content):
        if not text:
            continue
        for pat in _SNIPPET_REVIEW_PATTERNS:
            m = pat.search(text)
            if m and m.group(1).strip():
                return m.group(1).strip().rstrip(".")
    return None


def _claim_key_terms(claim: Claim) -> List[str]:
    """Collect distinctive entity terms (persons, orgs, locations, entities)."""
    terms: List[str] = []
    for coll in (claim.persons, claim.organizations, claim.locations):
        for term in coll or []:
            if term and len(term) > 2 and term not in terms:
                terms.append(term)
    for entity in claim.entities or []:
        if entity.text and len(entity.text) > 2 and entity.text not in terms:
            terms.append(entity.text)
    return terms


def _digit_sequence(text: str) -> str:
    """Extract bare digit sequence for lenient number comparison (Rs 10 vs 10)."""
    return re.sub(r"\D", "", text or "")


def assess_fact_check_alignment(
    claim: Claim, reviewed_text: str
) -> Tuple[float, bool, str]:
    """Score whether a fact-check review addresses the submitted claim.

    Returns (alignment_score 0..1, aligned bool, human-readable detail).
    """
    claim_text = claim.normalized_text or claim.original_text
    jaccard = jaccard_similarity(
        get_words(claim_text, remove_stopwords=True),
        get_words(reviewed_text, remove_stopwords=True),
    )
    rev_lower = reviewed_text.lower()
    rev_digits = _digit_sequence(reviewed_text)

    discriminating = [
        d.strip()
        for d in list(claim.dates or []) + list(claim.numbers or [])
        if d and d.strip()
    ]

    def _discrim_present(disc: str) -> bool:
        if disc.lower() in rev_lower:
            return True
        digits = _digit_sequence(disc)
        return len(digits) >= 2 and digits in rev_digits

    # Discriminating aspects (dates/numbers) pin down WHICH assertion is
    # reviewed. If the claim carries any and none appear in the reviewed
    # text, the review addresses a different assertion.
    if discriminating and not any(_discrim_present(d) for d in discriminating):
        return (
            _MISALIGNED_SCORE,
            False,
            "claim dates/numbers absent from the reviewed assertion",
        )

    coverage_terms = list(dict.fromkeys(_claim_key_terms(claim) + discriminating))
    if coverage_terms:
        hits = 0
        for term in coverage_terms:
            if term.lower() in rev_lower:
                hits += 1
            elif term in discriminating and _discrim_present(term):
                hits += 1
        coverage = hits / len(coverage_terms)
    else:
        coverage = 1.0

    score = round(0.5 * jaccard + 0.5 * coverage, 2)
    aligned = jaccard >= _ALIGNMENT_JACCARD_THRESHOLD or coverage >= _ALIGNMENT_COVERAGE_THRESHOLD
    detail = (
        f"token overlap {jaccard:.2f}, key-aspect coverage {coverage:.2f}"
    )
    return score, aligned, detail


def map_fact_check_comparison(
    evidence: Evidence,
    claim_id: str,
    claim: Optional[Claim] = None,
) -> Tuple[FactCheckComparison, EvidenceComparison]:
    """Convert a fact-check Evidence item into FactCheckComparison and EvidenceComparison.

    When the submitted ``claim`` is provided, the review's stance is applied
    only if the fact-checker demonstrably reviewed the same assertion
    (alignment gate on the review's ``claim_reviewed`` text). A review that
    cannot be matched yields NEUTRAL stance on both comparisons plus a
    limitation — never a contradiction. Without ``claim`` (legacy callers),
    behavior is unchanged: the rating maps directly with fixed confidence.
    """
    raw_rating = _extract_raw_rating(evidence)
    verdict_normalized, mapped_stance = map_raw_rating_to_verdict_and_stance(raw_rating)

    publisher_name = evidence.publisher or evidence.domain or "Fact Checker"
    explanation = (
        evidence.metadata.get("explanation")
        if evidence.metadata and evidence.metadata.get("explanation")
        else None
    ) or evidence.snippet or (
        f"Fact check by {publisher_name} concluded: '{raw_rating}'."
    )

    if claim is None:
        # Legacy path: rating maps directly with fixed confidence. Preserved
        # for callers that cannot supply the submitted claim.
        stance = mapped_stance
        confidence = 0.92
        relevance = 0.95
        extra_limitations: List[str] = []
        extra_signals: List[str] = []
        aspect_evidence_value: Optional[str] = verdict_normalized
    else:
        reviewed_text = _extract_reviewed_claim_text(evidence)
        if reviewed_text is None:
            # No recoverable reviewed assertion: do not assume alignment.
            # Ground the stance in the review's own text via regular
            # aspect-matching/stance detection instead.
            return _comparison_from_review_text_match(
                evidence=evidence,
                claim_id=claim_id,
                claim=claim,
                raw_rating=raw_rating,
                verdict_normalized=verdict_normalized,
                publisher_name=publisher_name,
                base_explanation=explanation,
            )
        score, aligned, detail = assess_fact_check_alignment(claim, reviewed_text)
        if aligned:
            logger.info(
                "Fact-check %s aligned with claim %s (%s); applying rating '%s'.",
                evidence.evidence_id,
                claim_id,
                detail,
                raw_rating,
            )
            stance = mapped_stance
            confidence = 0.92
            relevance = 0.95
            extra_limitations = []
            extra_signals = [f"fact_check_claim_aligned:{detail}"]
            aspect_evidence_value = verdict_normalized
        else:
            logger.warning(
                "Fact-check %s NOT aligned with claim %s (%s); "
                "withholding '%s' rating as contradiction.",
                evidence.evidence_id,
                claim_id,
                detail,
                raw_rating,
            )
            stance = EvidenceStance.NEUTRAL
            # Confidence/relevance derive from measured match quality —
            # never the fixed high values reserved for aligned reviews.
            confidence = round(0.55 + 0.25 * score, 2)
            relevance = round(0.25 + 0.5 * score, 2)
            extra_limitations = [
                f"Fact-check review could not be confidently matched to the "
                f"submitted claim ({detail}); the '{raw_rating}' rating was "
                f"not applied as a contradiction."
            ]
            extra_signals = ["fact_check_claim_mismatch"]
            aspect_evidence_value = None
            explanation = (
                f"{explanation} Reviewed assertion: '{reviewed_text}'. "
                f"This review addresses a different assertion and was not "
                f"counted for or against the submitted claim."
            )

    fact_check_comp = FactCheckComparison(
        fact_check_id=evidence.evidence_id,
        claim_id=claim_id,
        verdict_normalized=verdict_normalized,
        raw_rating=raw_rating,
        fact_checker=publisher_name,
        url=evidence.url,
        published_at=evidence.published_at,
        stance=stance,
        explanation=explanation,
    )

    # Build corresponding EvidenceComparison
    supporting_points = []
    contradicting_points = []
    neutral_points = []

    if stance == EvidenceStance.SUPPORTING:
        supporting_points.append(
            f"{publisher_name} verified claim with rating '{raw_rating}' ({verdict_normalized})."
        )
        reasoning = f"Authoritative fact-check by {publisher_name} validated this claim as '{verdict_normalized}'."
    elif stance == EvidenceStance.CONTRADICTING:
        contradicting_points.append(
            f"{publisher_name} refuted claim with rating '{raw_rating}' ({verdict_normalized})."
        )
        reasoning = f"Authoritative fact-check by {publisher_name} concluded this claim is '{verdict_normalized}'."
    else:
        neutral_points.append(
            f"{publisher_name} evaluated claim with inconclusive rating '{raw_rating}'."
        )
        reasoning = f"Fact-check by {publisher_name} issued an inconclusive/mixed rating: '{verdict_normalized}'."

    evidence_comp = EvidenceComparison(
        evidence_id=evidence.evidence_id,
        claim_id=claim_id,
        stance=stance,
        confidence=confidence,
        relevance=relevance,
        matched_claim_aspects=[
            AspectMatch(
                aspect_type=AspectType.STATUS,
                claim_value="asserted_fact",
                evidence_value=aspect_evidence_value,
                status="SUPPORTED" if stance == EvidenceStance.SUPPORTING else (
                    "CONTRADICTED" if stance == EvidenceStance.CONTRADICTING else "UNMENTIONED"
                ),
            )
        ],
        supporting_points=supporting_points,
        contradicting_points=contradicting_points,
        neutral_points=neutral_points,
        discrepancies=[],
        fact_check_rating=raw_rating,
        reasoning=reasoning,
        signals=[f"fact_check_rating:{raw_rating}", f"normalized_verdict:{verdict_normalized}"] + extra_signals,
        limitations=([] if raw_rating != "Unknown" else ["Fact check rating could not be parsed with high certainty"]) + extra_limitations,
    )

    return fact_check_comp, evidence_comp


def _comparison_from_review_text_match(
    evidence: Evidence,
    claim_id: str,
    claim: Claim,
    raw_rating: str,
    verdict_normalized: str,
    publisher_name: str,
    base_explanation: str,
) -> Tuple[FactCheckComparison, EvidenceComparison]:
    """Ground an unmatchable fact-check via regular stance detection.

    Used when no ``claim_reviewed`` text can be recovered: the review's own
    title/snippet/content is run through the same aspect-matching logic as
    ordinary evidence instead of assuming the rating applies to the claim.
    """
    grounded = classify_evidence_stance(claim, evidence)
    grounded.fact_check_rating = raw_rating
    grounded.signals = list(grounded.signals) + [
        f"fact_check_rating:{raw_rating}",
        f"normalized_verdict:{verdict_normalized}",
        "fact_check_unmatched_review_text",
    ]
    grounded.limitations = list(grounded.limitations) + [
        "No claim_reviewed text available; stance derived from review text "
        "match rather than assumed rating alignment."
    ]
    grounded.reasoning = (
        f"{grounded.reasoning} (Fact-check rating '{raw_rating}' present, "
        f"but the reviewed assertion could not be recovered for comparison.)"
    )

    fc_stance = (
        grounded.stance
        if grounded.stance in (EvidenceStance.SUPPORTING, EvidenceStance.CONTRADICTING)
        else EvidenceStance.NEUTRAL
    )
    fact_check_comp = FactCheckComparison(
        fact_check_id=evidence.evidence_id,
        claim_id=claim_id,
        verdict_normalized=verdict_normalized,
        raw_rating=raw_rating,
        fact_checker=publisher_name,
        url=evidence.url,
        published_at=evidence.published_at,
        stance=fc_stance,
        explanation=(
            f"{base_explanation} Reviewed-assertion text unavailable; stance "
            f"derived from review text match."
        ),
    )
    return fact_check_comp, grounded
