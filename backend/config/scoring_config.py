"""Scoring weights, thresholds, and limits as defined in README.md."""

from typing import Dict

# Scoring weights (must sum to 1.0)
SCORING_WEIGHTS: Dict[str, float] = {
    "evidence_agreement": 0.25,
    "source_quality": 0.15,
    "independent_sources": 0.20,
    "fact_checks": 0.15,
    "official_evidence": 0.20,
    "transparency": 0.05,
}

# Part 5: Source Reliability Heuristic Weights (must sum to 1.0)
SOURCE_RELIABILITY_WEIGHTS: Dict[str, float] = {
    "transparency": 0.25,
    "metadata_completeness": 0.20,
    "attribution_quality": 0.20,
    "domain_reputation": 0.20,
    "primary_reporting": 0.15,
}

SOURCE_RELIABILITY_THRESHOLDS: Dict[str, int] = {
    "high": 75,
    "medium": 50,
}

# Classification thresholds
CLASSIFICATION_THRESHOLDS: Dict[str, int] = {
    "strongly_supported": 90,
    "mostly_supported": 75,
    "mixed_uncertain": 50,
    "weakly_supported": 25,
    # Below 25 is categorized as "Strongly Contradicted"
}

# Insufficient evidence detection
MIN_INDEPENDENT_SOURCES: int = 2
MIN_CLASSIFIED_EVIDENCE_ITEMS: int = 2

# Duplicate detection thresholds
DUPLICATE_SIMILARITY_THRESHOLD: float = 0.85
EXACT_DUPLICATE_THRESHOLD: float = 0.95
NEAR_DUPLICATE_THRESHOLD: float = 0.82
SYNDICATION_TEXT_THRESHOLD: float = 0.60
SYNDICATION_TITLE_THRESHOLD: float = 0.70

# Recognized news agencies / wire syndicators
WIRE_SERVICE_NAMES = {
    "reuters",
    "associated press",
    "ap",
    "pti",
    "press trust of india",
    "afp",
    "agence france-presse",
    "ani",
    "asian news international",
    "bloomberg",
    "united press international",
    "upi",
}

# Retrieval limits
MAX_RESULTS_PER_NEWS_PROVIDER: int = 10
MAX_RESULTS_PER_WEB_PROVIDER: int = 10
MAX_FACTCHECK_RESULTS: int = 5

# Caching
CACHE_TTL_SECONDS: int = 3600

# Part 7: Evidence Comparison & Stance Detection Thresholds
STANCE_RELEVANCE_THRESHOLD: float = 0.20
STANCE_CONFIDENCE_DEFAULT: float = 0.85

# Normalized mapping for known fact-check ratings (lowercased key -> (normalized_verdict, stance))
FACT_CHECK_RATING_MAP: Dict[str, tuple[str, str]] = {
    # Supporting verdicts
    "true": ("True", "SUPPORTING"),
    "correct": ("True", "SUPPORTING"),
    "accurate": ("True", "SUPPORTING"),
    "verified": ("True", "SUPPORTING"),
    "mostly true": ("Mostly True", "SUPPORTING"),
    "mostly correct": ("Mostly True", "SUPPORTING"),
    "mostly accurate": ("Mostly True", "SUPPORTING"),
    "confirmed": ("True", "SUPPORTING"),
    
    # Contradicting verdicts
    "false": ("False", "CONTRADICTING"),
    "incorrect": ("False", "CONTRADICTING"),
    "fake": ("False", "CONTRADICTING"),
    "pants on fire": ("Pants on Fire", "CONTRADICTING"),
    "misleading": ("Misleading", "CONTRADICTING"),
    "fabricated": ("Fabricated", "CONTRADICTING"),
    "hoax": ("Hoax", "CONTRADICTING"),
    "debunked": ("Debunked", "CONTRADICTING"),
    "distorts the facts": ("Distorts Facts", "CONTRADICTING"),
    "mostly false": ("Mostly False", "CONTRADICTING"),
    "mostly incorrect": ("Mostly False", "CONTRADICTING"),
    "untrue": ("False", "CONTRADICTING"),
    "bust": ("False", "CONTRADICTING"),
    "unfounded": ("False", "CONTRADICTING"),
    
    # Neutral / Mixed / Inconclusive verdicts
    "half true": ("Half True", "NEUTRAL"),
    "partly true": ("Partly True", "NEUTRAL"),
    "partly false": ("Partly False", "NEUTRAL"),
    "mixture": ("Mixture", "NEUTRAL"),
    "mixed": ("Mixed", "NEUTRAL"),
    "inconclusive": ("Inconclusive", "NEUTRAL"),
    "unproven": ("Unproven", "NEUTRAL"),
    "unverified": ("Unverified", "NEUTRAL"),
    "needs context": ("Needs Context", "NEUTRAL"),
    "missing context": ("Missing Context", "NEUTRAL"),
    "disputed": ("Disputed", "NEUTRAL"),
}

# Part 8: Evidence Packet Limits for AI Reasoning
MAX_EVIDENCE_ITEMS_FOR_REASONING: int = 10
MAX_CHARS_PER_EVIDENCE: int = 1200
MAX_TOTAL_EVIDENCE_CHARS: int = 10000
MAX_FACT_CHECKS_FOR_REASONING: int = 5

# Part 9: Credibility Scoring Engine
INDEPENDENT_SOURCES_TARGET: int = 3
PENALTY_CRITICAL_DISCREPANCY: float = 20.0
PENALTY_MAJOR_DISCREPANCY: float = 10.0
PENALTY_REPUTABLE_CONTRADICTION: float = 25.0
PENALTY_ANONYMOUS_UNINDEXED: float = 10.0
SCORING_METHODOLOGY_VERSION: str = "v1.0"

