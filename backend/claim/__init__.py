"""Claim package public exports."""

from backend.claim.ai_claim_extractor import (
    AIClaimExtractionResult,
    AIExtractedClaim,
    ai_extract_claims,
    build_claims_from_ai_result,
    extract_claims_ai_first,
    extract_claims_with_ai,
    validate_ai_claims,
)
from backend.claim.claim_extractor import extract_claims, extract_claims_from_text
from backend.claim.claim_normalizer import normalize_claim_text
from backend.claim.entity_extractor import extract_entities_from_doc, get_nlp
from backend.claim.models import (
    AttributedSpeaker,
    Claim,
    ClaimImportance,
    ClaimType,
    ExtractedEntity,
)
from backend.claim.rules import (
    contains_factual_signals,
    is_candidate_sentence,
)

__all__ = [
    "Claim",
    "ClaimType",
    "ClaimImportance",
    "ExtractedEntity",
    "AttributedSpeaker",
    "extract_claims",
    "extract_claims_from_text",
    "extract_claims_with_ai",
    "extract_claims_ai_first",
    "ai_extract_claims",
    "validate_ai_claims",
    "build_claims_from_ai_result",
    "AIExtractedClaim",
    "AIClaimExtractionResult",
    "normalize_claim_text",
    "extract_entities_from_doc",
    "get_nlp",
    "is_candidate_sentence",
    "contains_factual_signals",
]
