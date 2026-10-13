"""Pydantic models for Part 8 AI Evidence Reasoning.

Defines structured data structures for evidence packets, findings, discrepancies,
and grounded reasoning results.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FindingImportance(str, Enum):
    """Significance of a factual finding within the evidence reasoning."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class UncertaintyLevel(str, Enum):
    """Assessment of epistemic uncertainty in the retrieved evidence situation."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvidenceFinding(BaseModel):
    """An individual grounded factual finding referencing specific evidence IDs."""
    text:         str               = Field(..., description="Factually grounded reasoning statement")
    evidence_ids: List[str]         = Field(default_factory=list, description="IDs of evidence supporting this finding")
    stance:       Optional[str]     = Field(None, description="SUPPORTING, CONTRADICTING, or NEUTRAL")
    importance:   FindingImportance = Field(FindingImportance.MEDIUM, description="Importance of this finding")
    confidence:   float             = Field(0.8, ge=0.0, le=1.0, description="Confidence in the reasoning statement itself")


class AIReasoningResult(BaseModel):
    """Complete, validated output from the AI Evidence Reasoning engine."""
    claim_id:                  Optional[str]         = Field(None, description="Claim ID")
    claim_text:                Optional[str]         = Field(None, description="Factual claim text")
    summary:                   str                   = Field(..., description="Concise evidence-grounded summary")
    key_findings:              List[EvidenceFinding] = Field(default_factory=list, description="Top essential findings")
    supporting_findings:       List[EvidenceFinding] = Field(default_factory=list, description="Corroborating observations with citations")
    contradicting_findings:    List[EvidenceFinding] = Field(default_factory=list, description="Refuting observations or conflicts with citations")
    important_discrepancies:   List[str]             = Field(default_factory=list, description="Explanations of numeric/temporal/status conflicts")
    source_observations:       List[str]             = Field(default_factory=list, description="Observations on source characteristics and reliability")
    independence_observations: List[str]             = Field(default_factory=list, description="Observations on syndication clusters and original reporting")
    fact_check_observations:   List[str]             = Field(default_factory=list, description="Observations on available fact-checks and ratings")
    verification_gaps:         List[str]             = Field(default_factory=list, description="Explicitly missing or unresolved evidence points")
    uncertainty:               UncertaintyLevel      = Field(UncertaintyLevel.MEDIUM, description="Assessed evidence uncertainty")
    reasoning_steps:           List[str]             = Field(default_factory=list, description="Auditable reasoning trace")
    limitations:               List[str]             = Field(default_factory=list, description="Specific retrieval or analysis caveats")
    ai_used:                   bool                  = Field(False, description="True if generated via external LLM; False if fallback")
    provider:                  Optional[str]         = Field(None, description="LLM provider name (e.g. gemini, openai)")
    model:                     Optional[str]         = Field(None, description="Model identifier used")
    fallback_used:             bool                  = Field(False, description="True if deterministic fallback was triggered")


class EvidencePacketItem(BaseModel):
    """Sanitized and character-bounded evidence item prepared for LLM consumption."""
    evidence_id:                str           = Field(..., description="Unique ID of evidence item")
    title:                      str           = Field(..., description="Article title")
    publisher:                  str           = Field(..., description="Publisher name")
    domain:                     Optional[str] = Field(None, description="Source domain")
    url:                        str           = Field(..., description="Real source URL")
    publication_date:           Optional[str] = Field(None, description="Publication timestamp")
    snippet:                    str           = Field(..., description="Relevant excerpt (bounded length)")
    source_category:            str           = Field("unknown")
    source_reliability:         str           = Field("unknown")
    cluster_id:                 Optional[str] = Field(None)
    independence_status:        str           = Field("unknown")
    stance:                     str           = Field("NEUTRAL")
    stance_confidence:          float         = Field(0.8)
    relevance:                  float         = Field(0.8)
    supporting_points:          List[str]     = Field(default_factory=list)
    contradicting_points:       List[str]     = Field(default_factory=list)
    discrepancies:              List[str]     = Field(default_factory=list)
    is_fact_check:              bool          = Field(False)
    fact_check_rating:          Optional[str] = Field(None)


class EvidencePacket(BaseModel):
    """Bounded, privacy-sanitized evidence packet supplied to the reasoner."""
    claim_id:                 str                      = Field(..., description="Claim ID")
    claim_text:               str                      = Field(..., description="Factual claim text")
    claim_aspects:            Dict[str, Any]           = Field(default_factory=dict, description="Key dimensions (who, what, amount, etc.)")
    independent_source_count: int                      = Field(0, description="True count of independent clusters")
    evidence:                 List[EvidencePacketItem] = Field(default_factory=list, description="Ordered evidence items")
    fact_checks:              List[Dict[str, Any]]     = Field(default_factory=list, description="Fact-checks summary")
    discrepancies:            List[Dict[str, Any]]     = Field(default_factory=list, description="Surface conflicts")
    clusters_summary:         List[Dict[str, Any]]     = Field(default_factory=list, description="Cluster breakdown")
