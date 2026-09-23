"""Ingestion package exports."""

from backend.ingestion.errors import (
    ArticleExtractionFailed,
    BlockedURL,
    EmptyContent,
    FetchFailed,
    FetchTimeout,
    HTTPError,
    IngestionError,
    InvalidURL,
    SSRFViolation,
    UnsupportedContentType,
)
from backend.ingestion.models import NormalizedArticle, NormalizedText
from backend.ingestion.service import ingest_input
from backend.ingestion.text_processor import normalize_text_content, process_text_input
from backend.ingestion.url_extractor import (
    extract_article_body,
    extract_article_from_url,
    extract_metadata,
    fetch_article_html,
    validate_url,
    verify_ip_security,
)

__all__ = [
    "IngestionError",
    "InvalidURL",
    "SSRFViolation",
    "BlockedURL",
    "FetchTimeout",
    "FetchFailed",
    "HTTPError",
    "UnsupportedContentType",
    "EmptyContent",
    "ArticleExtractionFailed",
    "NormalizedText",
    "NormalizedArticle",
    "normalize_text_content",
    "process_text_input",
    "validate_url",
    "verify_ip_security",
    "fetch_article_html",
    "extract_metadata",
    "extract_article_body",
    "extract_article_from_url",
    "ingest_input",
]
