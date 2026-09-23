"""Data models for explainable verification report generation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScoreContribution(BaseModel):
    """User-facing score impact item (local copy to avoid circular import with api.schemas)."""
    factor: str = Field(..., description="Scoring factor identifier")
    label: str = Field(..., description="Human-readable factor title")
    contribution: float = Field(..., description="Signed point contribution")
    detail: str = Field(..., description="Grounded explanation")


class ReportInputSummary(BaseModel):
    """Metadata describing the user's submitted input."""
    input_type:             str           = Field(..., description="text or url")
    headline:               Optional[str] = Field(None, description="Extracted headline/title if present")
    source_url:             Optional[str] = Field(None, description="Original submission URL if applicable")
    text_length:            int           = Field(0, description="Character length of verified body")
    claim_count:            int           = Field(0, description="Total factual claims extracted")
    verification_timestamp: str           = Field(..., description="ISO 8601 UTC timestamp of verification")


class ReportOverallResult(BaseModel):
    """Aggregated document-level credibility assessment."""
    score:          Optional[int] = Field(None, ge=0, le=100, description="Overall score 0-100 or None if insufficient")
    classification: str           = Field(..., description="Official human-readable classification label")
    summary:        str           = Field(..., description="Executive synthesis of document credibility")


class EvidenceCard(BaseModel):
    """Normalized evidence presentation card."""
    evidence_id:         str            = Field(..., description="Evidence ID")
    title:               str            = Field(..., description="Article title")
    publisher:           Optional[str]  = Field(None, description="Publishing outlet")
    url:                 str            = Field(..., description="Source URL")
    publication_date:    Optional[str]  = Field(None, description="Publication timestamp")
    snippet:             Optional[str]  = Field(None, description="Extracted textual excerpt")
    stance:              str            = Field(..., description="SUPPORTING, CONTRADICTING, NEUTRAL, or INSUFFICIENT")
    relevance:           Optional[float]= Field(None, ge=0.0, le=1.0, description="Relevance score to claim")
    cluster_id:          Optional[str]  = Field(None, description="Duplicate or syndication cluster ID")
    independence_status: Optional[str]  = Field(None, description="LIKELY_INDEPENDENT, LIKELY_DERIVED, etc.")
    source_category:     Optional[str]  = Field(None, description="e.g. news_media, government, academic")
    source_reliability:  Optional[str]  = Field(None, description="high, medium, low, unknown")


class EvidenceSummary(BaseModel):
    """Compact metrics summarizing evidence distribution."""
    total_retrieved:          int = Field(0, description="Total raw evidence items retrieved")
    supporting_count:         int = Field(0, description="Number of supporting evidence items")
    contradicting_count:      int = Field(0, description="Number of contradicting evidence items")
    neutral_count:            int = Field(0, description="Number of neutral/contextual items")
    insufficient_count:       int = Field(0, description="Number of items with insufficient stance clarity")
    independent_source_count: int = Field(0, description="Distinct independent reporting source clusters")
    duplicate_count:          int = Field(0, description="Duplicate items identified")
    syndicated_count:         int = Field(0, description="Syndicated wire copies identified")
    fact_check_count:         int = Field(0, description="Verified fact-check reviews retrieved")


class FactCheckCard(BaseModel):
    """Structured review card from a verified fact-checking organization."""
    fact_check_id:     str           = Field(..., description="Fact-check identifier or URL")
    publisher:         str           = Field(..., description="Name of fact-checker (e.g. Reuters Fact Check)")
    title:             Optional[str] = Field(None, description="Fact-check review headline")
    url:               str           = Field(..., description="URL to the full fact-check report")
    review_date:       Optional[str] = Field(None, description="Date fact-check was published")
    original_rating:   str           = Field(..., description="Original rating label from publisher (e.g. Pants on Fire)")
    normalized_rating: str           = Field(..., description="Normalized rating (True, False, Misleading, etc.)")
    stance:            str           = Field(..., description="SUPPORTING, CONTRADICTING, or NEUTRAL")
    explanation:       str           = Field(..., description="Summary explanation of the verdict")
    evidence_ids:      List[str]     = Field(default_factory=list, description="Associated evidence IDs")


class DiscrepancyCard(BaseModel):
    """Grounded factual contradiction or conflict."""
    type:           str           = Field(..., description="NUMERIC, TEMPORAL, POLARITY, etc.")
    description:    str           = Field(..., description="Plain-language description of conflict")
    claim_value:    str           = Field(..., description="Value asserted in the claim")
    evidence_value: str           = Field(..., description="Value reported by the evidence")
    evidence_ids:   List[str]     = Field(default_factory=list, description="IDs of evidence containing conflict")
    severity:       str           = Field("MAJOR", description="CRITICAL, MAJOR, or MINOR")


class SourceAnalysisCard(BaseModel):
    """Evaluation of an evidence publisher's observable characteristics."""
    publisher:                str           = Field(..., description="Publisher name")
    domain:                   str           = Field(..., description="Domain name")
    source_category:          str           = Field(..., description="Category (news_media, government, etc.)")
    reliability_label:        str           = Field(..., description="HIGH, MEDIUM, LOW, or UNKNOWN")
    reliability_score:        int           = Field(..., ge=0, le=100, description="Heuristic score (0-100)")
    transparency:             str           = Field(..., description="HIGH, MEDIUM, LOW")
    metadata_quality:         float         = Field(..., ge=0.0, le=1.0, description="Metadata completeness score")
    attribution_signal:       bool          = Field(False, description="Quotes or official attribution detected")
    primary_reporting_signal: bool          = Field(False, description="Original reporting detected")
    limitations:              List[str]     = Field(default_factory=list, description="Diagnostic caveats")


class ClusterCard(BaseModel):
    """Evidence cluster card illustrating syndication or duplication."""
    cluster_id:                 str           = Field(..., description="Cluster identifier")
    cluster_type:               str           = Field(..., description="SYNDICATION, DUPLICATE, INDEPENDENT, etc.")
    member_count:               int           = Field(1, description="Number of evidence items in cluster")
    representative_evidence_id: Optional[str] = Field(None, description="Representative / earliest item ID")
    evidence_ids:               List[str]     = Field(default_factory=list, description="All item IDs in cluster")


class IndependenceSummary(BaseModel):
    """Synthesized view of reporting independence."""
    independent_source_count: int               = Field(0, description="Effective count of independent clusters")
    cluster_count:            int               = Field(0, description="Total clusters formed")
    syndication_clusters:     int               = Field(0, description="Clusters containing syndicated wire copies")
    duplicate_clusters:       int               = Field(0, description="Clusters containing exact/near duplicates")
    independence_limitations: List[str]         = Field(default_factory=list, description="Caveats on independence")
    clusters:                 List[ClusterCard] = Field(default_factory=list, description="Detailed cluster list")


class ScoreComponentCard(BaseModel):
    """Score component visualization card."""
    factor:                str       = Field(..., description="Factor key")
    label:                 str       = Field(..., description="Human-readable title")
    raw_score:             float     = Field(..., description="Raw normalized score (0.0 - 1.0)")
    weight:                float     = Field(..., description="Factor weight (e.g. 0.30)")
    weighted_contribution: float     = Field(..., description="Calculated point contribution")
    explanation:           str       = Field(..., description="Deterministic justification")
    evidence_ids:          List[str] = Field(default_factory=list, description="Referenced evidence citations")


class ScorePenaltyCard(BaseModel):
    """Score penalty deduction card."""
    penalty_type: str       = Field(..., description="Category of deduction")
    amount:       float     = Field(..., description="Points deducted")
    explanation:  str       = Field(..., description="Grounded justification for deduction")
    evidence_ids: List[str] = Field(default_factory=list, description="Associated evidence IDs")


class ScoreBreakdownReport(BaseModel):
    """Full transparent score calculation audit."""
    components:             List[ScoreComponentCard] = Field(default_factory=list)
    penalties:              List[ScorePenaltyCard]   = Field(default_factory=list)
    total_before_penalties: float                    = Field(0.0)
    penalties_total:        float                    = Field(0.0)
    final_score:            Optional[int]            = Field(None)
    score_contributions:    List[ScoreContribution]  = Field(default_factory=list)


class AIReasoningReport(BaseModel):
    """Synthesized AI evidence reasoning."""
    summary:                   str       = Field("", description="Evidence reasoning summary")
    supporting_findings:       List[str] = Field(default_factory=list)
    contradicting_findings:    List[str] = Field(default_factory=list)
    important_discrepancies:   List[str] = Field(default_factory=list)
    source_observations:       List[str] = Field(default_factory=list)
    independence_observations: List[str] = Field(default_factory=list)
    fact_check_observations:   List[str] = Field(default_factory=list)
    verification_gaps:         List[str] = Field(default_factory=list)
    uncertainty:               str       = Field("MEDIUM")
    limitations:               List[str] = Field(default_factory=list)
    ai_used:                   bool      = Field(False)
    fallback_used:             bool      = Field(False)
    provider:                  Optional[str] = Field(None)
    model:                     Optional[str] = Field(None)


class CitationItem(BaseModel):
    """Auditable citation entry directly traceable to retrieved source evidence."""
    evidence_id:      str           = Field(..., description="Unique evidence ID")
    title:            str           = Field(..., description="Article title")
    publisher:        str           = Field(..., description="Publishing organization")
    url:              str           = Field(..., description="Full URL to original source")
    publication_date: Optional[str] = Field(None, description="Publication date if available")
    domain:           Optional[str] = Field(None, description="Normalized source domain")


class ClaimVerificationReport(BaseModel):
    """Comprehensive explainability section for a single factual claim."""
    claim_id:                 str                         = Field(..., description="Claim ID")
    claim_text:               str                         = Field(..., description="Extracted claim text")
    claim_type:               str                         = Field(..., description="STATISTIC, EVENT, POLICY, etc.")
    importance:               str                         = Field("HIGH", description="HIGH, MEDIUM, or LOW")
    score:                    Optional[int]               = Field(None, ge=0, le=100)
    classification:           str                         = Field(...)
    is_insufficient_evidence: bool                        = Field(False)
    summary:                  str                         = Field(...)
    evidence_summary:         EvidenceSummary             = Field(default_factory=EvidenceSummary)
    supporting_evidence:      List[EvidenceCard]          = Field(default_factory=list)
    contradicting_evidence:   List[EvidenceCard]          = Field(default_factory=list)
    neutral_evidence:         List[EvidenceCard]          = Field(default_factory=list)
    insufficient_evidence:    List[EvidenceCard]          = Field(default_factory=list)
    fact_checks:              List[FactCheckCard]         = Field(default_factory=list)
    discrepancies:            List[DiscrepancyCard]       = Field(default_factory=list)
    verification_gaps:        List[str]                   = Field(default_factory=list)
    source_analysis:          List[SourceAnalysisCard]    = Field(default_factory=list)
    independence_analysis:    Optional[IndependenceSummary]= Field(None)
    score_breakdown:          Optional[ScoreBreakdownReport]= Field(None)
    ai_reasoning:             Optional[AIReasoningReport] = Field(None)
    limitations:              List[str]                   = Field(default_factory=list)


class VerificationReport(BaseModel):
    """Complete root verification report document for UI and API consumers."""
    report_id:           str                           = Field(..., description="Unique report UUID4")
    generated_at:        str                           = Field(..., description="ISO 8601 UTC timestamp")
    methodology_version: str                           = Field("v1.0", description="Methodology version")
    input_summary:       ReportInputSummary            = Field(...)
    overall_result:      ReportOverallResult           = Field(...)
    executive_summary:   str                           = Field(..., description="Concise executive synthesis")
    claims:              List[ClaimVerificationReport] = Field(default_factory=list)
    evidence_summary:    EvidenceSummary               = Field(default_factory=EvidenceSummary)
    citations:           List[CitationItem]            = Field(default_factory=list)
    limitations:         List[str]                     = Field(default_factory=list)
