"""Strongly typed internal data models for factual claims and entities."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    """Controlled vocabulary of factual claim categories."""

    EVENT = "EVENT"
    STATISTIC = "STATISTIC"
    POLICY = "POLICY"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    PERSON_ACTION = "PERSON_ACTION"
    ORGANIZATION_ACTION = "ORGANIZATION_ACTION"
    QUOTE = "QUOTE"
    FINANCIAL = "FINANCIAL"
    SCIENTIFIC = "SCIENTIFIC"
    OTHER = "OTHER"


class ClaimImportance(str, Enum):
    """Assessment of claim significance within the input text or article."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExtractedEntity(BaseModel):
    """A named or numerical entity detected in a claim."""

    text: str = Field(..., description="Exact entity text as it appears in source")
    label: str = Field(..., description="Category label (e.g. PERSON, ORG, GPE, DATE, MONEY, PERCENT)")


class AttributedSpeaker(BaseModel):
    """Attribution metadata for statements, quotes, or claims made by a specific actor."""

    speaker: str = Field(..., description="Identified person or entity who made the statement")
    role_or_affiliation: Optional[str] = Field(default=None, description="Title, role, or organization if mentioned")
    attribution_verb: Optional[str] = Field(default=None, description="Reporting verb (e.g. said, announced, stated)")


class Claim(BaseModel):
    """An atomic, independently verifiable factual assertion extracted from text."""

    claim_id: str = Field(..., description="Unique deterministic identifier for the claim")
    original_text: str = Field(..., description="Exact unaltered wording from source")
    normalized_text: str = Field(..., description="Normalized, search-ready representation")

    claim_type: ClaimType = Field(default=ClaimType.OTHER, description="Descriptive classification of claim")
    importance: ClaimImportance = Field(default=ClaimImportance.MEDIUM, description="Significance of claim in document")

    entities: List[ExtractedEntity] = Field(default_factory=list, description="All detected entities")
    dates: List[str] = Field(default_factory=list, description="Extracted dates or time references")
    numbers: List[str] = Field(default_factory=list, description="Extracted numerical figures or cardinal numbers")
    locations: List[str] = Field(default_factory=list, description="Extracted locations, countries, cities (GPE/LOC)")
    organizations: List[str] = Field(default_factory=list, description="Extracted corporate or institutional names (ORG)")
    persons: List[str] = Field(default_factory=list, description="Extracted individual person names (PERSON)")

    source_sentence: str = Field(..., description="Full context sentence from which claim was derived")
    is_headline_claim: bool = Field(default=False, description="True if derived directly from an article title/headline")
    attribution: Optional[AttributedSpeaker] = Field(default=None, description="Quote or reported speech attribution")

    duplicate_of: Optional[str] = Field(default=None, description="claim_id of primary claim if this is a duplicate")
    equivalent_claims: List[str] = Field(default_factory=list, description="Alternative wordings found in document")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplementary parsing heuristics")
