"""Internal data models for the evidence retrieval layer.

These models are the normalised, provider-agnostic representation of
everything retrieved from external sources.  The rest of the backend
must not need to know which provider produced a result.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    """Category of the source that produced an Evidence item."""
    NEWS             = "NEWS"
    FACT_CHECK       = "FACT_CHECK"
    OFFICIAL         = "OFFICIAL"
    PRIMARY_DOCUMENT = "PRIMARY_DOCUMENT"
    ACADEMIC         = "ACADEMIC"
    WEB              = "WEB"
    OTHER            = "OTHER"


class QueryType(str, Enum):
    """Classification of how a search query was generated."""
    DIRECT         = "DIRECT"          # normalized claim text, trimmed
    ENTITY_FOCUSED = "ENTITY_FOCUSED"  # key named entities + topic
    NUMERIC        = "NUMERIC"         # numbers + org/location
    DATE_FOCUSED   = "DATE_FOCUSED"    # date + org/event anchor
    FACT_CHECK     = "FACT_CHECK"      # claim phrase + "fact check"
    OFFICIAL       = "OFFICIAL"        # org + "official statement" + topic


class ProviderStatusCode(str, Enum):
    SUCCESS     = "success"
    UNAVAILABLE = "unavailable"   # key missing / provider disabled
    ERROR       = "error"         # transient failure
    TIMEOUT     = "timeout"


# ---------------------------------------------------------------------------
# Query model
# ---------------------------------------------------------------------------

class SearchQuery(BaseModel):
    """A single typed query to be dispatched to one or more providers."""
    query:      str       = Field(..., description="Query string to send to provider")
    query_type: QueryType = Field(..., description="Semantic category of the query")
    claim_id:   str       = Field(..., description="ID of the claim this query belongs to")


# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """A single normalised piece of evidence retrieved from an external source.

    Every field that carries a URL must contain a real URL returned by the
    provider.  The system must never generate or guess URLs.
    """

    evidence_id:    str = Field(..., description="Unique deterministic ID for this evidence item")

    # Link back to the claim that triggered retrieval
    claim_id: str = Field(..., description="ID of the claim this evidence was retrieved for")

    # Content
    title:    str           = Field(..., description="Article or page title")
    url:      str           = Field(..., description="URL as returned by provider — never generated")
    canonical_url: Optional[str] = Field(None, description="Normalised URL after stripping tracking params")

    publisher:    Optional[str] = Field(None, description="Publisher or outlet name")
    domain:       Optional[str] = Field(None, description="Registered domain (e.g. bbc.com)")
    author:       Optional[str] = Field(None, description="Author if available")
    published_at: Optional[str] = Field(None, description="Publication date/time (ISO-8601 string or raw)")

    snippet:  Optional[str] = Field(None, description="Short excerpt returned by provider")
    content:  Optional[str] = Field(None, description="Full body text if extracted; None if only snippet available")

    # Classification
    source_type: SourceType = Field(SourceType.OTHER, description="Category of source")
    provider:    str        = Field(..., description="Name of the provider that returned this result")

    # Provenance
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    query_used:   str      = Field(..., description="Exact query string that produced this result")

    # Flexible metadata — carries provider-specific extras (e.g. fact-check rating)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider status
# ---------------------------------------------------------------------------

class ProviderStatus(BaseModel):
    """Operational status for a single provider within a retrieval run."""
    provider:      str                = Field(..., description="Provider identifier")
    status:        ProviderStatusCode = Field(...)
    results_count: int                = Field(0)
    error:         Optional[str]      = Field(None, description="Human-readable error (no credentials exposed)")
    duration_ms:   Optional[float]    = Field(None, description="Wall-clock time for provider call")


# ---------------------------------------------------------------------------
# Grouped per-claim result
# ---------------------------------------------------------------------------

class ClaimEvidence(BaseModel):
    """All evidence retrieved for a single claim, with provider diagnostics."""
    claim_id:          str                 = Field(...)
    evidence:          List[Evidence]       = Field(default_factory=list)
    queries_used:      List[SearchQuery]    = Field(default_factory=list)
    provider_statuses: List[ProviderStatus] = Field(default_factory=list)
    total_retrieved:   int                 = Field(0, description="Before deduplication / limiting")


# ---------------------------------------------------------------------------
# Top-level retrieval result
# ---------------------------------------------------------------------------

class RetrievalResult(BaseModel):
    """Complete output of the evidence retrieval stage."""
    claims:               List[ClaimEvidence] = Field(default_factory=list)
    total_evidence_count: int                 = Field(0)
    retrieval_duration_ms: float              = Field(0.0)
