"""Main entry point for Source Analysis & Reliability assessment.

Inspects Evidence items retrieved in Part 4 and builds comprehensive,
explainable SourceAnalysis profiles without evaluating claim truth.
"""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.sources.domain_classifier import classify_domain
from backend.sources.heuristics import (
    detect_attribution,
    detect_primary_reporting,
    parse_source_age,
)
from backend.sources.metadata_analyzer import (
    evaluate_metadata_quality,
    evaluate_transparency,
)
from backend.sources.models import SourceAnalysis
from backend.sources.source_scoring import calculate_source_reliability


def _extract_domain_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        dom = netloc.lower().strip()
        if dom.startswith("www."):
            dom = dom[4:]
        return dom
    except Exception:
        return ""


def analyze_source(evidence: Evidence) -> SourceAnalysis:
    """Analyze observable characteristics of a single Evidence item.

    Does NOT determine claim truth or verify evidence veracity.
    """
    domain = evidence.domain or _extract_domain_from_url(evidence.url)
    source_type_val = (
        evidence.source_type.value
        if hasattr(evidence.source_type, "value")
        else str(evidence.source_type)
    )

    # 1. Structural Domain Classification
    category = classify_domain(domain, source_type_hint=source_type_val)

    # 2. Metadata completeness and disclosure
    metadata_quality = evaluate_metadata_quality(evidence)
    transparency = evaluate_transparency(metadata_quality)

    # 3. Text excerpt signals (quotes, attribution, firsthand reporting)
    text_content = evidence.content or evidence.snippet or evidence.title or ""
    attribution = detect_attribution(text_content)
    primary_reporting = detect_primary_reporting(text_content)

    # 4. Publication age
    source_age, _ = parse_source_age(evidence.published_at)

    # 5. Reliability scoring and explainable signals
    score, label, signals, limitations = calculate_source_reliability(
        evidence=evidence,
        category=category,
        transparency=transparency,
        attribution=attribution,
        primary_reporting=primary_reporting,
        metadata_quality=metadata_quality,
        source_age=source_age,
    )

    logger.debug(
        "Analyzed source for evidence %s (domain=%s, cat=%s, score=%d, label=%s)",
        evidence.evidence_id,
        domain,
        category.value,
        score,
        label.value,
    )

    return SourceAnalysis(
        evidence_id=evidence.evidence_id,
        domain=domain,
        publisher=evidence.publisher or domain,
        source_type=source_type_val,
        source_category=category,
        reliability_score=score,
        reliability_label=label,
        transparency=transparency,
        attribution=attribution,
        primary_reporting=primary_reporting,
        metadata_quality=metadata_quality,
        source_age=source_age,
        signals=signals,
        limitations=limitations,
    )


def analyze_sources(evidence_items: List[Evidence]) -> List[SourceAnalysis]:
    """Batch analyze source characteristics across a collection of Evidence items."""
    return [analyze_source(ev) for ev in evidence_items]
