"""Normalized internal models for ingestion."""

from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class NormalizedText(BaseModel):
    """Normalized plain text input representation."""

    original_text: str = Field(..., description="Original raw text submitted by the user")
    normalized_text: str = Field(..., description="Cleaned, Unicode-normalized text")
    character_count: int = Field(..., description="Character count of normalized text")
    word_count: int = Field(..., description="Word count of normalized text")


class NormalizedArticle(BaseModel):
    """Normalized internal representation of an ingested article or text input."""

    source_type: Literal["text", "url"] = Field(..., description="Source medium of the input")
    original_input: str = Field(..., description="Raw text or submitted URL")

    url: Optional[str] = Field(default=None, description="Actual URL if source_type is url")
    canonical_url: Optional[str] = Field(default=None, description="Canonical URL from HTML metadata")

    title: Optional[str] = Field(default=None, description="Extracted article headline/title")
    body: str = Field(..., description="Main text body of article or normalized user text")

    publisher: Optional[str] = Field(default=None, description="Identified publishing organization")
    author: Optional[str] = Field(default=None, description="Identified author byline")
    published_at: Optional[str] = Field(default=None, description="Publication timestamp or date string")

    domain: Optional[str] = Field(default=None, description="Domain name (e.g. reuters.com)")
    description: Optional[str] = Field(default=None, description="Meta description or summary excerpt")

    extraction_method: str = Field(
        default="direct_text",
        description="Method used to extract content (e.g., direct_text, semantic_html, json_ld, opengraph)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Auxiliary raw metadata (e.g., OG tags, twitter tags, raw schema.org)"
    )
