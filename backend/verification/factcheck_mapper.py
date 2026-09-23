"""Fact-check rating normalization and stance mapping.

Translates diverse verdicts from fact-checking organizations (e.g., Google Fact Check,
Boom Live, PolitiFact, Snopes, AFP, Full Fact) into normalized verdicts and
deterministic EvidenceStance classifications.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple
from urllib.parse import urlparse

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


def map_fact_check_comparison(
    evidence: Evidence,
    claim_id: str,
) -> Tuple[FactCheckComparison, EvidenceComparison]:
    """Convert a fact-check Evidence item into FactCheckComparison and EvidenceComparison."""
    raw_rating = _extract_raw_rating(evidence)
    verdict_normalized, stance = map_raw_rating_to_verdict_and_stance(raw_rating)

    publisher_name = evidence.publisher or evidence.domain or "Fact Checker"
    explanation = (
        evidence.metadata.get("explanation")
        or evidence.snippet
        or f"Fact check by {publisher_name} concluded: '{raw_rating}'."
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
        confidence=0.92,
        relevance=0.95,
        matched_claim_aspects=[
            AspectMatch(
                aspect_type=AspectType.STATUS,
                claim_value="asserted_fact",
                evidence_value=verdict_normalized,
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
        signals=[f"fact_check_rating:{raw_rating}", f"normalized_verdict:{verdict_normalized}"],
        limitations=[] if raw_rating != "Unknown" else ["Fact check rating could not be parsed with high certainty"],
    )

    return fact_check_comp, evidence_comp
