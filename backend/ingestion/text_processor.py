"""Text normalization and preprocessing module."""

import re
import unicodedata
from backend.config.settings import settings
from backend.ingestion.errors import EmptyContent
from backend.ingestion.models import NormalizedArticle, NormalizedText


# Regex patterns for normalization
# Matches zero-width spaces, joiners, directional marks, and control characters (excluding tab and newline)
INVISIBLE_CHARS_PATTERN = re.compile(
    r"[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"
)
# Matches multiple consecutive spaces or tabs on a single line
HORIZONTAL_WHITESPACE_PATTERN = re.compile(r"[^\S\r\n]+")
# Matches 3 or more consecutive newlines to compress excessive paragraph breaks
EXCESSIVE_NEWLINES_PATTERN = re.compile(r"\n{3,}")


def normalize_text_content(text: str) -> NormalizedText:
    """Normalize raw user text input.

    Performs:
    - Unicode NFKC normalization
    - Removal of invisible/control characters
    - Standardized line breaks (\\r\\n -> \\n, \\r -> \\n)
    - Compression of consecutive horizontal spaces
    - Compression of excessive newlines (>2 down to 2)
    - Stripping leading and trailing whitespace
    """
    if not text:
        raise EmptyContent("Input text is empty.")

    original_text = text

    # Step 1: Unicode Normalization (NFKC compatibility decomposition + canonical composition)
    normalized = unicodedata.normalize("NFKC", original_text)

    # Step 2: Strip invisible control characters
    normalized = INVISIBLE_CHARS_PATTERN.sub("", normalized)

    # Step 3: Normalize line endings
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # Step 4: Normalize horizontal whitespace (spaces/tabs) on each line
    normalized = HORIZONTAL_WHITESPACE_PATTERN.sub(" ", normalized)

    # Step 5: Clean individual lines
    lines = [line.strip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    # Step 6: Compress excessive newlines
    normalized = EXCESSIVE_NEWLINES_PATTERN.sub("\n\n", normalized).strip()

    if not normalized:
        raise EmptyContent("Input text contains only whitespace or invisible characters.")

    char_count = len(normalized)
    word_count = len(normalized.split())

    return NormalizedText(
        original_text=original_text,
        normalized_text=normalized,
        character_count=char_count,
        word_count=word_count,
    )


def process_text_input(raw_text: str) -> NormalizedArticle:
    """Convert raw text input into a NormalizedArticle representation ready for pipeline processing."""
    norm = normalize_text_content(raw_text)

    return NormalizedArticle(
        source_type="text",
        original_input=raw_text,
        url=None,
        canonical_url=None,
        title=None,
        body=norm.normalized_text,
        publisher=None,
        author=None,
        published_at=None,
        domain=None,
        description=None,
        extraction_method="direct_text",
        metadata={
            "character_count": norm.character_count,
            "word_count": norm.word_count,
        },
    )
