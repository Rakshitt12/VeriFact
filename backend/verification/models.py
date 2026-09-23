"""Data models for duplicate detection, syndication identification, and source independence.

Evaluates relationships between pairs and clusters of retrieved evidence to prevent
reprinted or syndicated stories from inflating the independent confirmation count.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Categorical classification of relationship between two evidence items."""
    EXACT_DUPLICATE    = "EXACT_DUPLICATE"      # Same canonical URL or identical text
    NEAR_DUPLICATE     = "NEAR_DUPLICATE"       # Substantially identical text/title with minor edits
    SYNDICATED         = "SYNDICATED"           # Same wire service / syndicated copy across different outlets
    LIKELY_DERIVED     = "LIKELY_DERIVED"       # Content clearly cites or rewrites another primary report
    LIKELY_INDEPENDENT = "LIKELY_INDEPENDENT"   # Separate reporting with independent text and angles
    UNKNOWN            = "UNKNOWN"              # Insufficient text/metadata to establish relationship


class ClusterType(str, Enum):
    """Classification of an evidence cluster's formation."""
    DUPLICATE   = "DUPLICATE"    # Exact or near duplicates
    SYNDICATION = "SYNDICATION"  # Syndicated wire / cross-published reports
    MIXED       = "MIXED"        # Contains duplicates and syndicated variants
    INDEPENDENT = "INDEPENDENT"  # Single or distinct independent reporting source
    UNKNOWN     = "UNKNOWN"


class IndependenceStatus(str, Enum):
    """Analytical assessment of an evidence item's reporting independence."""
    LIKELY_INDEPENDENT = "LIKELY_INDEPENDENT"
    LIKELY_DERIVED     = "LIKELY_DERIVED"
    POSSIBLY_DERIVED   = "POSSIBLY_DERIVED"
    UNKNOWN            = "UNKNOWN"


class EvidenceRelationship(BaseModel):
    """Pairwise relationship analysis between two evidence items."""
    evidence_id_a:     str              = Field(..., description="ID of first evidence item")
    evidence_id_b:     str              = Field(..., description="ID of second evidence item")
    relationship_type: RelationshipType = Field(..., description="Nature of the connection")
    similarity_score:  float            = Field(..., ge=0.0, le=1.0, description="Measured similarity (0.0 to 1.0)")
    confidence:        float            = Field(..., ge=0.0, le=1.0, description="Confidence in relationship classification")
    signals:           List[str]        = Field(default_factory=list, description="Observable cues supporting classification")
    limitations:       List[str]        = Field(default_factory=list, description="Diagnostic caveats or uncertainties")


class EvidenceCluster(BaseModel):
    """A group of evidence items derived from the same underlying reporting source."""
    cluster_id:                 str                = Field(..., description="Unique deterministic cluster ID")
    evidence_ids:               List[str]          = Field(default_factory=list, description="All evidence IDs in cluster")
    cluster_type:               ClusterType        = Field(ClusterType.UNKNOWN, description="Structural type of cluster")
    representative_evidence_id: Optional[str]      = Field(None, description="Best representative item (origin/earliest/fullest)")
    independence_status:        IndependenceStatus = Field(IndependenceStatus.UNKNOWN)
    confidence:                 float              = Field(0.0, ge=0.0, le=1.0)
    signals:                    List[str]          = Field(default_factory=list)
    limitations:                List[str]          = Field(default_factory=list)


class IndependenceAnalysis(BaseModel):
    """Source independence evaluation for a single evidence item."""
    evidence_id:             str                = Field(..., description="ID of evaluated evidence item")
    cluster_id:              str                = Field(..., description="Assigned cluster ID")
    independence_status:     IndependenceStatus = Field(..., description="Assessment of independence")
    independence_confidence: float              = Field(..., ge=0.0, le=1.0)
    related_evidence_ids:    List[str]          = Field(default_factory=list, description="IDs of related/syndicated items")
    signals:                 List[str]          = Field(default_factory=list)
    limitations:             List[str]          = Field(default_factory=list)


class ClaimIndependenceResult(BaseModel):
    """Complete Part 6 result for all evidence retrieved for a claim."""
    claim_id:                 str                         = Field(..., description="Claim ID")
    total_evidence_count:     int                         = Field(0, description="Raw total evidence items")
    independent_source_count: int                         = Field(0, description="Effective count of independent source clusters")
    clusters:                 List[EvidenceCluster]       = Field(default_factory=list)
    relationships:            List[EvidenceRelationship]  = Field(default_factory=list)
    analyses:                 List[IndependenceAnalysis]  = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Part 7: Evidence Comparison & Stance Detection Models
# ---------------------------------------------------------------------------

class EvidenceStance(str, Enum):
    """Categorical stance of a single evidence item relative to a specific factual claim."""
    SUPPORTING    = "SUPPORTING"     # Corroborates or confirms the claim materially
    CONTRADICTING = "CONTRADICTING"  # Conficts with, denies, or refutes a material aspect of claim
    NEUTRAL       = "NEUTRAL"        # On topic, but neither materially supports nor refutes
    INSUFFICIENT  = "INSUFFICIENT"   # Too vague, indirect, or brief to establish stance


class AspectType(str, Enum):
    """Specific factual dimension of a claim evaluated against evidence."""
    WHO         = "WHO"          # Subject, actor, organization, person
    WHAT        = "WHAT"         # The core event, action, or subject matter
    WHEN        = "WHEN"         # Date, timestamp, timeframe
    WHERE       = "WHERE"        # Geographical location, jurisdiction
    AMOUNT      = "AMOUNT"       # Monetary figure, percentage, rate
    COUNT       = "COUNT"        # Quantity, cardinal number, headcount
    ACTION      = "ACTION"       # Specific policy or action verb
    STATUS      = "STATUS"       # Final state (e.g. approved vs rejected, resigned vs stayed)
    ATTRIBUTION = "ATTRIBUTION"  # Attribution speaker or source cited


class AspectMatch(BaseModel):
    """Comparison result for a single aspect of a claim."""
    aspect_type:    AspectType       = Field(..., description="Aspect category being compared")
    claim_value:    str              = Field(..., description="Value asserted in the claim")
    evidence_value: Optional[str]    = Field(None, description="Value found in evidence, if any")
    status:         str              = Field(..., description="SUPPORTED, CONTRADICTED, or UNMENTIONED")


class DiscrepancyType(str, Enum):
    """Nature of a factual discrepancy between claim and evidence."""
    NUMERIC  = "NUMERIC"   # Discrepancy in monetary figures, numbers, or percentages
    TEMPORAL = "TEMPORAL"  # Discrepancy in dates, months, or years
    POLARITY = "POLARITY"  # Affirmative assertion vs explicit denial/rejection
    ENTITY   = "ENTITY"    # Mismatch in identified person, org, or location
    STATUS   = "STATUS"    # Mismatch in outcome (e.g., approved vs pending/rejected)
    OTHER    = "OTHER"     # General qualitative contradiction


class Discrepancy(BaseModel):
    """Detailed record of a factual conflict between claim and evidence."""
    discrepancy_type: DiscrepancyType = Field(..., description="Category of conflict")
    aspect:           str             = Field(..., description="Aspect or field with conflict")
    claim_value:      str             = Field(..., description="What the claim asserts")
    evidence_value:   str             = Field(..., description="What the evidence reports")
    snippet:          Optional[str]   = Field(None, description="Verbatim excerpt highlighting conflict")
    severity:         str             = Field("MAJOR", description="CRITICAL, MAJOR, or MINOR")


class EvidenceComparison(BaseModel):
    """Structured stance evaluation of a single evidence document against a claim."""
    evidence_id:           str                 = Field(..., description="ID of evaluated evidence item")
    claim_id:              str                 = Field(..., description="ID of claim being evaluated")
    stance:                EvidenceStance      = Field(..., description="Assigned stance")
    confidence:            float               = Field(..., ge=0.0, le=1.0, description="Confidence in stance determination")
    relevance:             float               = Field(..., ge=0.0, le=1.0, description="How directly evidence addresses claim")
    matched_claim_aspects: List[AspectMatch]   = Field(default_factory=list, description="Aspect-by-aspect matches")
    supporting_points:     List[str]           = Field(default_factory=list, description="Specific assertions corroborating claim")
    contradicting_points:  List[str]           = Field(default_factory=list, description="Specific assertions refuting claim")
    neutral_points:        List[str]           = Field(default_factory=list, description="Contextual points neither supporting nor refuting")
    discrepancies:         List[Discrepancy]   = Field(default_factory=list, description="Specific factual conflicts found")
    fact_check_rating:     Optional[str]       = Field(None, description="Original rating if this is a fact-check item")
    reasoning:             str                 = Field(..., description="Plain-language explanation grounded in evidence text")
    signals:               List[str]           = Field(default_factory=list, description="Observable cues used in classification")
    limitations:           List[str]           = Field(default_factory=list, description="Caveats, truncations, or ambiguities")


class FactCheckComparison(BaseModel):
    """Normalized fact-check review for a claim."""
    fact_check_id:      str            = Field(..., description="ID or URL of fact-check")
    claim_id:           str            = Field(..., description="ID of claim reviewed")
    verdict_normalized: str            = Field(..., description="Normalized rating: True, False, Misleading, etc.")
    raw_rating:         str            = Field(..., description="Original verbatim rating label from publisher")
    fact_checker:       str            = Field(..., description="Name of fact-checking organization")
    url:                str            = Field(..., description="URL to full fact-check article")
    published_at:       Optional[str]  = Field(None, description="Fact-check publication date")
    stance:             EvidenceStance = Field(..., description="Mapped stance relative to claim")
    explanation:        str            = Field(..., description="Fact-checker's summary explanation")


class ClaimEvidenceComparisonResult(BaseModel):
    """Consolidated Part 7 comparison result across all evidence retrieved for a claim."""
    claim_id:                         str                      = Field(..., description="Claim ID")
    comparisons:                      List[EvidenceComparison] = Field(default_factory=list, description="All evidence comparisons")
    fact_checks:                      List[FactCheckComparison]= Field(default_factory=list, description="All normalized fact checks")
    supporting_count:                 int                      = Field(0, description="Total evidence items supporting")
    contradicting_count:              int                      = Field(0, description="Total evidence items contradicting")
    neutral_count:                    int                      = Field(0, description="Total evidence items neutral")
    insufficient_count:               int                      = Field(0, description="Total evidence items insufficient")
    independent_supporting_count:     int                      = Field(0, description="Distinct independent clusters supporting")
    independent_contradicting_count:  int                      = Field(0, description="Distinct independent clusters contradicting")
    agreement_ratio:                  float                    = Field(0.0, ge=0.0, le=1.0, description="Ratio of supporting to total opposing/supporting")
    key_discrepancies:                List[Discrepancy]        = Field(default_factory=list, description="Material discrepancies across evidence")
    summary:                          str                      = Field("", description="Human-readable synthesis of stance distribution")
