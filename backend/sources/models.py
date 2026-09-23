"""Data models for source analysis, reliability assessment, and transparency.

Evaluates observable characteristics of retrieved sources (transparency, attribution,
primary reporting indicators, domain classification) independently from claim veracity.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceCategory(str, Enum):
    """Controlled vocabulary of source domain types."""
    GOVERNMENT                 = "GOVERNMENT"                  # .gov, .gov.in, .nic.in, ministries
    ACADEMIC                   = "ACADEMIC"                    # .edu, .ac.in, universities, journals
    INTERNATIONAL_ORGANIZATION = "INTERNATIONAL_ORGANIZATION"  # .int, UN, WHO, IMF, World Bank
    REGULATORY                 = "REGULATORY"                  # RBI, SEBI, SEC, FDA, etc.
    NEWS_MEDIA                 = "NEWS_MEDIA"                  # Professional news reporting outlets
    FACT_CHECKER               = "FACT_CHECKER"                # Independent verified fact-checkers
    ORGANIZATION               = "ORGANIZATION"                # Companies, NGOs, civil society
    PERSONAL_BLOG              = "PERSONAL_BLOG"               # Substack, Medium, Blogspot, personal sites
    UNKNOWN                    = "UNKNOWN"                     # Unclassified / generic domain


class TransparencyLevel(str, Enum):
    """Categorical assessment of publisher and author disclosure."""
    HIGH    = "HIGH"      # Publisher, author, publication date, and canonical URL present
    MEDIUM  = "MEDIUM"    # Publisher and at least one of (author, date) present
    LOW     = "LOW"       # Anonymous, missing publisher or publication date
    UNKNOWN = "UNKNOWN"   # Insufficient metadata to evaluate


class ReliabilityLabel(str, Enum):
    """Qualitative tier derived from the 0-100 source reliability heuristic."""
    HIGH    = "HIGH"      # >= 75
    MEDIUM  = "MEDIUM"    # 50 - 74
    LOW     = "LOW"       # < 50
    UNKNOWN = "UNKNOWN"   # Unverified / unindexed source


class SourceAge(str, Enum):
    """Recency of the source relative to the analysis date."""
    VERY_RECENT = "VERY_RECENT"  # Published within the last 30 days
    RECENT      = "RECENT"       # Published within the last year (30 - 365 days)
    OLDER       = "OLDER"        # Published more than 1 year ago
    UNKNOWN     = "UNKNOWN"      # Publication date missing or unparseable


class AttributionSignal(BaseModel):
    """Detection of cited quotes, spokespeople, filings, or institutional attribution."""
    present:        bool           = Field(False, description="True if text attributes claims to an external entity")
    has_quotes:     bool           = Field(False, description="True if direct quotation marks are present")
    named_sources:  List[str]      = Field(default_factory=list, description="Extracted cited entities or speakers")
    statement_type: Optional[str]  = Field(None, description="e.g. quote, official_statement, filing, study")


class PrimaryReportingSignal(BaseModel):
    """Signals that the source conducted original reporting rather than secondary aggregation."""
    present: bool      = Field(False, description="True if firsthand reporting signals detected")
    signals: List[str] = Field(default_factory=list, description="Observable clues (interview, filing, investigation)")


class MetadataQuality(BaseModel):
    """Completeness score and boolean flags for standard article metadata."""
    score:             float = Field(0.0, description="Completeness score between 0.0 and 1.0")
    has_title:         bool  = Field(False)
    has_publisher:     bool  = Field(False)
    has_author:        bool  = Field(False)
    has_published_at:  bool  = Field(False)
    has_canonical_url: bool  = Field(False)
    has_content:       bool  = Field(False)


class SourceAnalysis(BaseModel):
    """Normalized assessment of a single evidence source's reporting characteristics.

    IMPORTANT: This model represents the source's transparency and reporting
    characteristics, NOT the truth or credibility of the underlying claim.
    """

    evidence_id:       str                  = Field(..., description="ID of the evidence item analyzed")
    domain:            str                  = Field(..., description="Normalized domain name (e.g. reuters.com)")
    publisher:         Optional[str]        = Field(None, description="Reported or registered publisher name")
    source_type:       str                  = Field(..., description="Source type from Evidence (NEWS, FACT_CHECK, etc.)")
    source_category:   SourceCategory       = Field(SourceCategory.UNKNOWN, description="Structural category")

    # Reliability heuristic (0 - 100)
    reliability_score: int                  = Field(..., ge=0, le=100, description="Heuristic score (0-100)")
    reliability_label: ReliabilityLabel     = Field(..., description="Categorical label (HIGH, MEDIUM, LOW)")

    # Qualitative dimensions
    transparency:      TransparencyLevel    = Field(TransparencyLevel.UNKNOWN)
    attribution:       AttributionSignal    = Field(default_factory=AttributionSignal)
    primary_reporting: PrimaryReportingSignal = Field(default_factory=PrimaryReportingSignal)
    metadata_quality:  MetadataQuality      = Field(default_factory=MetadataQuality)
    source_age:        SourceAge            = Field(SourceAge.UNKNOWN)

    # Explainable breakdown
    signals:           List[str]            = Field(default_factory=list, description="Positive observable characteristics")
    limitations:       List[str]            = Field(default_factory=list, description="Observed weaknesses or missing data")
    heuristic_notes:   str                  = Field(
        "Source Reliability is an internal heuristic based on metadata completeness, "
        "transparency, attribution, and reporting characteristics. It is not a guarantee of factual accuracy."
    )
