"""Source reliability heuristic scoring and explainable signal generation.

Computes a 0-100 heuristic reliability score based purely on observable source
characteristics, transparency, metadata completeness, and attribution.

DISCLAIMER:
Source Reliability is an internal heuristic based on metadata completeness,
transparency, attribution, and reporting characteristics. It is not a guarantee
of factual accuracy.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from backend.config.scoring_config import (
    SOURCE_RELIABILITY_THRESHOLDS,
    SOURCE_RELIABILITY_WEIGHTS,
)
from backend.retrieval.models import Evidence
from backend.sources.models import (
    AttributionSignal,
    MetadataQuality,
    PrimaryReportingSignal,
    ReliabilityLabel,
    SourceAge,
    SourceCategory,
    TransparencyLevel,
)
from backend.sources.source_registry import lookup_registered_source


def _score_transparency(transparency: TransparencyLevel) -> float:
    mapping = {
        TransparencyLevel.HIGH: 100.0,
        TransparencyLevel.MEDIUM: 65.0,
        TransparencyLevel.LOW: 30.0,
        TransparencyLevel.UNKNOWN: 10.0,
    }
    return mapping.get(transparency, 10.0)


def _score_attribution(attrib: AttributionSignal) -> float:
    if not attrib.present:
        return 30.0  # Neutral baseline for short search snippets
    score = 60.0
    if attrib.has_quotes:
        score += 20.0
    if attrib.named_sources:
        score += 20.0
    return min(score, 100.0)


def _score_primary_reporting(primary: PrimaryReportingSignal) -> float:
    if not primary.present:
        return 40.0  # Base neutral baseline (secondary reporting is normal in journalism)
    # Scaled by number of detected firsthand indicators
    return min(70.0 + len(primary.signals) * 15.0, 100.0)


def _score_domain_reputation(domain: str, category: SourceCategory) -> float:
    entry = lookup_registered_source(domain)
    if entry:
        return float(entry.reputation_score)

    category_baselines = {
        SourceCategory.GOVERNMENT: 90.0,
        SourceCategory.REGULATORY: 90.0,
        SourceCategory.INTERNATIONAL_ORGANIZATION: 88.0,
        SourceCategory.ACADEMIC: 85.0,
        SourceCategory.FACT_CHECKER: 85.0,
        SourceCategory.NEWS_MEDIA: 75.0,
        SourceCategory.ORGANIZATION: 60.0,
        SourceCategory.PERSONAL_BLOG: 35.0,
        SourceCategory.UNKNOWN: 45.0,
    }
    return category_baselines.get(category, 45.0)


def calculate_source_reliability(
    evidence: Evidence,
    category: SourceCategory,
    transparency: TransparencyLevel,
    attribution: AttributionSignal,
    primary_reporting: PrimaryReportingSignal,
    metadata_quality: MetadataQuality,
    source_age: SourceAge,
) -> Tuple[int, ReliabilityLabel, List[str], List[str]]:
    """Compute 0-100 source reliability score and generate explainable signals/limitations.

    Returns:
        (reliability_score, reliability_label, positive_signals, limitations)
    """
    weights = SOURCE_RELIABILITY_WEIGHTS

    # Sub-component scores (0.0 - 100.0)
    score_trans = _score_transparency(transparency)
    score_meta = metadata_quality.score * 100.0
    score_attrib = _score_attribution(attribution)
    score_domain = _score_domain_reputation(evidence.domain or "", category)
    score_primary = _score_primary_reporting(primary_reporting)

    raw_weighted = (
        score_trans * weights["transparency"]
        + score_meta * weights["metadata_completeness"]
        + score_attrib * weights["attribution_quality"]
        + score_domain * weights["domain_reputation"]
        + score_primary * weights["primary_reporting"]
    )

    final_score = max(0, min(100, int(round(raw_weighted))))

    # Map to qualitative label
    high_threshold = SOURCE_RELIABILITY_THRESHOLDS.get("high", 75)
    medium_threshold = SOURCE_RELIABILITY_THRESHOLDS.get("medium", 50)

    if final_score >= high_threshold:
        label = ReliabilityLabel.HIGH
    elif final_score >= medium_threshold:
        label = ReliabilityLabel.MEDIUM
    elif metadata_quality.score <= 0.2 and category == SourceCategory.UNKNOWN:
        label = ReliabilityLabel.UNKNOWN
    else:
        label = ReliabilityLabel.LOW

    # Build explainable positive signals
    signals: List[str] = []
    limitations: List[str] = []

    # Publisher & Domain signals
    if evidence.publisher:
        signals.append(f"Publisher clearly identified ({evidence.publisher})")
    else:
        limitations.append("Publisher identity not clearly disclosed")

    if category in (SourceCategory.GOVERNMENT, SourceCategory.REGULATORY):
        signals.append("Official institutional or regulatory source")
    elif category == SourceCategory.FACT_CHECKER:
        signals.append("Identified independent fact-checking desk")
    elif category == SourceCategory.ACADEMIC:
        signals.append("Accredited academic or higher education domain")
    elif category == SourceCategory.PERSONAL_BLOG:
        limitations.append("Self-publishing or personal blog platform; independent corroboration advised")

    # Author & Date signals
    if metadata_quality.has_author:
        signals.append(f"Named author byline ({evidence.author})")
    else:
        limitations.append("Author byline missing or uncredited")

    if metadata_quality.has_published_at:
        signals.append("Publication timestamp clearly recorded")
        if source_age == SourceAge.VERY_RECENT:
            signals.append("Recent publication date (within last 30 days)")
    else:
        limitations.append("Publication date is missing or unparseable")

    # Attribution & Quotes
    if attribution.present:
        if attribution.has_quotes:
            signals.append("Contains direct quoted statements")
        if attribution.named_sources:
            sources_str = ", ".join(attribution.named_sources)
            signals.append(f"Attributes claims to cited sources ({sources_str})")
    else:
        limitations.append("No explicit external attribution or quotes detected in excerpt")

    # Primary reporting
    if primary_reporting.present:
        reps = ", ".join(primary_reporting.signals)
        signals.append(f"Firsthand reporting indicators detected ({reps})")

    if not metadata_quality.has_content:
        limitations.append("Full article content unavailable; evaluated based on snippet only")

    return final_score, label, signals, limitations
