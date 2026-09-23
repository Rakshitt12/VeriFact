"""Data models for explainable credibility scoring, component contributions, and penalties."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.api.schemas import ClassificationLabel, ScoreContribution


class ScoreFactor(str, Enum):
    """Controlled vocabulary of scoring dimensions."""
    EVIDENCE_AGREEMENT  = "evidence_agreement"
    SOURCE_QUALITY      = "source_quality"
    INDEPENDENT_SOURCES = "independent_sources"
    FACT_CHECKS         = "fact_checks"
    OFFICIAL_EVIDENCE   = "official_evidence"
    TRANSPARENCY        = "transparency"


class ScoreComponent(BaseModel):
    """Individual scoring dimension evaluation."""
    factor:                ScoreFactor = Field(..., description="Scoring factor identifier")
    label:                 str         = Field(..., description="Human-readable factor title")
    raw_score:             float       = Field(..., ge=0.0, le=1.0, description="Normalized score [0.0, 1.0]")
    weight:                float       = Field(..., ge=0.0, le=1.0, description="Configured factor weight")
    weighted_contribution: float       = Field(..., description="Point contribution (+/- on 0-100 scale)")
    explanation:           str         = Field(..., description="Deterministic grounding rationale")
    evidence_ids:          List[str]   = Field(default_factory=list, description="Citations grounding this component")


class ScorePenalty(BaseModel):
    """Specific grounded deduction applied to the credibility score."""
    penalty_type: str       = Field(..., description="Category: numeric_discrepancy, contradiction, unindexed")
    amount:       float     = Field(..., ge=0.0, description="Points deducted from raw total")
    explanation:  str       = Field(..., description="Plain-language reason for penalty")
    evidence_ids: List[str] = Field(default_factory=list, description="Citations associated with penalty")


class ClaimCredibilityScore(BaseModel):
    """Complete credibility assessment for a single factual claim."""
    claim_id:                 str                     = Field(..., description="Claim ID")
    claim_text:               str                     = Field(..., description="Claim statement")
    score:                    Optional[int]           = Field(None, ge=0, le=100, description="Credibility score 0-100 or None if insufficient")
    classification:           str                     = Field(..., description="Human-readable classification label")
    is_insufficient_evidence: bool                    = Field(False, description="True if evidence fell below minimum thresholds")
    total_before_penalties:   float                   = Field(0.0, description="Sum of weighted components (0-100)")
    penalties_total:          float                   = Field(0.0, description="Total points deducted via penalties")
    final_score_raw:          float                   = Field(0.0, description="Score before integer rounding and clamping")
    components:               List[ScoreComponent]    = Field(default_factory=list, description="Dimensional component breakdown")
    penalties:                List[ScorePenalty]      = Field(default_factory=list, description="Deductions applied")
    score_breakdown:          List[ScoreContribution] = Field(default_factory=list, description="User-facing sorted impact items")
    summary:                  str                     = Field("", description="Grounded explanation of score result")
    limitations:              List[str]               = Field(default_factory=list, description="Evaluation caveats")
    methodology_version:      str                     = Field("v1.0", description="Scoring methodology version")


class DocumentCredibilityScore(BaseModel):
    """Aggregated credibility assessment across an entire input text or article."""
    overall_score:          Optional[int]               = Field(None, ge=0, le=100, description="Overall weighted score across claims")
    overall_classification: str                         = Field(..., description="Document-level classification")
    claim_scores:           List[ClaimCredibilityScore] = Field(default_factory=list, description="Per-claim scoring results")
    summary:                str                         = Field("", description="Overall document synthesis")
    methodology_version:    str                         = Field("v1.0")
