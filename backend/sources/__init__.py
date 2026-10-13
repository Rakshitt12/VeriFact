"""Source analysis and reliability assessment package exports."""

from backend.sources.domain_classifier import classify_domain
from backend.sources.metadata_analyzer import (
    evaluate_metadata_quality,
    evaluate_transparency,
)
from backend.sources.models import (
    AttributionSignal,
    MetadataQuality,
    PrimaryReportingSignal,
    ReliabilityLabel,
    SourceAge,
    SourceAnalysis,
    SourceCategory,
    TransparencyLevel,
)
from backend.sources.source_analyzer import analyze_source, analyze_sources
from backend.sources.source_registry import (
    RegistryEntry,
    lookup_registered_source,
    register_source,
)
from backend.sources.source_scoring import calculate_source_reliability

__all__ = [
    "SourceCategory",
    "TransparencyLevel",
    "ReliabilityLabel",
    "SourceAge",
    "AttributionSignal",
    "PrimaryReportingSignal",
    "MetadataQuality",
    "SourceAnalysis",
    "RegistryEntry",
    "lookup_registered_source",
    "register_source",
    "classify_domain",
    "evaluate_metadata_quality",
    "evaluate_transparency",
    "calculate_source_reliability",
    "analyze_source",
    "analyze_sources",
]
