"""Pydantic schemas for request and response validation.

Conforms strictly to the API design defined in README.md Section 19.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class InputType(str, Enum):
    TEXT = "text"
    URL = "url"


class EvidenceStance(str, Enum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    NEUTRAL = "NEUTRAL"
    INSUFFICIENT = "INSUFFICIENT"


class ClassificationLabel(str, Enum):
    STRONGLY_SUPPORTED = "Strongly Supported"
    MOSTLY_SUPPORTED = "Mostly Supported"
    MIXED_UNCERTAIN = "Mixed / Uncertain"
    WEAKLY_SUPPORTED = "Weakly Supported"
    STRONGLY_CONTRADICTED = "Strongly Contradicted"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT EVIDENCE"


# Request Models
class VerificationRequest(BaseModel):
    input_type: InputType = Field(..., description="Whether input is raw text or a URL")
    content: str = Field(..., min_length=5, description="News text or URL to verify")

    model_config = {
        "json_schema_extra": {
            "example": {
                "input_type": "text",
                "content": "India has introduced a new law banning all cryptocurrency transactions."
            }
        }
    }


# Response sub-models
class InputSummary(BaseModel):
    title: Optional[str] = None
    publisher: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None
    domain: Optional[str] = None
    url: Optional[str] = None


class EvidenceItem(BaseModel):
    evidence_id: str
    title: str
    url: str
    publisher: str
    published_at: Optional[str] = None
    snippet: str
    stance: EvidenceStance
    rationale: str
    is_primary_source: bool = False
    source_reliability: str = "unknown"  # high, medium, low, unknown


class FactCheckItem(BaseModel):
    fact_check_id: str
    claim_text: str
    verdict: str
    rating_label: str
    fact_checker: str
    url: str
    published_at: Optional[str] = None
    explanation: str


class SourceAnalysisItem(BaseModel):
    domain: str
    publisher: str
    reliability_tier: str  # high, medium, low, unknown
    transparency_score: float = 0.0
    type: str = "unknown"  # major_news, regional_news, government, institution, academic, fact_checker, aggregator, social_media, unknown
    is_primary_source: bool = False
    is_duplicate: bool = False
    cluster_id: Optional[str] = None
    evidence_id: Optional[str] = None
    reliability_score: Optional[int] = None
    transparency_level: Optional[str] = None
    source_category: Optional[str] = None
    source_age: Optional[str] = None
    signals: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class DuplicateCluster(BaseModel):
    cluster_id: str
    origin: Dict[str, Any] = Field(default_factory=dict)
    duplicates: List[Dict[str, Any]] = Field(default_factory=list)
    cluster_size: int = 1
    counted_as_independent: int = 1


class ScoreContribution(BaseModel):
    factor: str
    label: str
    contribution: float
    detail: str


class VerificationGap(BaseModel):
    gap_type: str
    description: str


class EvidenceFindingItem(BaseModel):
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    stance: Optional[str] = None
    importance: str = "MEDIUM"
    confidence: float = 0.8


class AIReasoningResponse(BaseModel):
    summary: str
    key_findings: List[EvidenceFindingItem] = Field(default_factory=list)
    supporting_findings: List[EvidenceFindingItem] = Field(default_factory=list)
    contradicting_findings: List[EvidenceFindingItem] = Field(default_factory=list)
    important_discrepancies: List[str] = Field(default_factory=list)
    source_observations: List[str] = Field(default_factory=list)
    independence_observations: List[str] = Field(default_factory=list)
    fact_check_observations: List[str] = Field(default_factory=list)
    verification_gaps: List[str] = Field(default_factory=list)
    uncertainty: str = "MEDIUM"
    reasoning_steps: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    ai_used: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_used: bool = False


class RetrievedEvidenceItem(BaseModel):
    evidence_id: str
    title: str
    url: str
    publisher: Optional[str] = None
    domain: Optional[str] = None
    snippet: Optional[str] = None
    source_type: str
    provider: str
    published_at: Optional[str] = None
    query_used: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClaimResult(BaseModel):
    claim_id: str
    claim_text: str
    score: Optional[int] = None
    classification: str
    summary: str
    supporting_evidence: List[EvidenceItem] = Field(default_factory=list)
    contradicting_evidence: List[EvidenceItem] = Field(default_factory=list)
    neutral_evidence: List[EvidenceItem] = Field(default_factory=list)
    fact_checks: List[FactCheckItem] = Field(default_factory=list)
    source_analysis: List[SourceAnalysisItem] = Field(default_factory=list)
    duplicate_clusters: List[DuplicateCluster] = Field(default_factory=list)
    score_breakdown: List[ScoreContribution] = Field(default_factory=list)
    verification_gaps: List[VerificationGap] = Field(default_factory=list)
    evidence_reasoning: Optional[AIReasoningResponse] = None
    independent_source_count: int = 0
    total_evidence_count: int = 0
    retrieved_evidence: List[RetrievedEvidenceItem] = Field(default_factory=list)


# Full Structured API Response
class VerificationResponse(BaseModel):
    request_id: str
    processed_at: datetime
    input_type: InputType
    input_summary: InputSummary
    claims: List[ClaimResult] = Field(default_factory=list)
    overall_score: Optional[int] = None
    overall_classification: str
    overall_summary: str
    limitations: List[str] = Field(default_factory=list)
    # Part 10 — Explainable Report. Typed as Any to avoid a runtime circular
    # import (backend.report.* imports claim/retrieval/sources models, and
    # routes imports the report service). The value is a VerificationReport
    # instance serialized by FastAPI's jsonable_encoder.
    report: Optional[Any] = None



# Health Check Response
class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
