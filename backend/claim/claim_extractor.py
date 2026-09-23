"""Core claim extraction engine.

Extracts candidate claims from normalized articles or texts using:
1. Headline prioritization
2. Sentence segmentation via spaCy
3. Candidate filtering via rules
4. Quote and attribution decomposition
5. Multi-claim conjunction splitting
6. Entity extraction and classification
7. Importance heuristic scoring
8. Duplicate/equivalence grouping with stable deterministic IDs
"""

import hashlib
import re
from typing import List, Optional, Tuple

from backend.claim.claim_normalizer import normalize_claim_text
from backend.claim.entity_extractor import extract_entities_from_doc, get_nlp
from backend.claim.models import (
    AttributedSpeaker,
    Claim,
    ClaimImportance,
    ClaimType,
)
from backend.claim.rules import (
    ATTRIBUTION_VERBS,
    contains_factual_signals,
    is_candidate_sentence,
)
from backend.ingestion.models import NormalizedArticle
from backend.logging_config import logger

# Attribution regex pattern: e.g. "The minister said that inflation had fallen"
ATTRIBUTION_REGEX = re.compile(
    r"^(?P<speaker>[A-Z][a-zA-Z\s\.\-]{2,40}?)\s+(?P<verb>"
    + "|".join(ATTRIBUTION_VERBS)
    + r")(?:\s+(?:that|on|in|during|at|yesterday|today|recently))?\s*[:,\s]\s*(?P<statement>.+)$",
    re.IGNORECASE,
)

# Conjunction split pattern for multi-claim sentences (e.g. "...on Monday and the law will...")
CONJUNCTION_SPLIT_PATTERN = re.compile(
    r"\s+and\s+(?=[a-z\s]+(?:will|is|are|was|were|has|have|had|announced|approved|banned|scheduled)\b)",
    re.IGNORECASE,
)


def generate_claim_id(claim_text: str, index: int) -> str:
    """Generate a stable, deterministic claim ID based on normalized content."""
    clean = re.sub(r"\W+", "", claim_text.lower())
    digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:10]
    return f"claim_{digest}_{index}"


def classify_claim_type(
    text: str,
    entities: dict,
    has_attribution: bool,
) -> ClaimType:
    """Determine the descriptive claim category."""
    text_lower = text.lower()

    if has_attribution:
        return ClaimType.QUOTE

    # Financial / Statistical
    if any(m in text_lower for m in ("repo rate", "inflation", "gdp", "profit", "revenue", "loss", "budget", "tax", "emi", "inr", "usd", "$", "₹")):
        return ClaimType.FINANCIAL
    if entities.get("numbers") or any(p in text_lower for p in ("percent", "%", "crore", "lakh", "billion", "million")):
        return ClaimType.STATISTIC

    # Policy / Announcement
    if any(p in text_lower for p in ("approved", "bill", "law", "policy", "cabinet", "ban", "guidelines", "decree", "rule")):
        return ClaimType.POLICY
    if any(p in text_lower for p in ("announced", "unveiled", "launched", "introduced", "scheduled")):
        return ClaimType.ANNOUNCEMENT

    # Scientific / Research
    if any(p in text_lower for p in ("study", "research", "scientists", "vaccine", "clinical", "discovery", "published")):
        return ClaimType.SCIENTIFIC

    # Actions
    if entities.get("persons"):
        return ClaimType.PERSON_ACTION
    if entities.get("organizations"):
        return ClaimType.ORGANIZATION_ACTION

    # Event
    if entities.get("dates") or entities.get("locations") or any(e in text_lower for e in ("struck", "earthquake", "crash", "flood", "fire", "killed")):
        return ClaimType.EVENT

    return ClaimType.OTHER


def calculate_claim_importance(
    is_headline: bool,
    sentence_idx: int,
    entities: dict,
    claim_type: ClaimType,
) -> ClaimImportance:
    """Assign importance based on structural prominence and factual density."""
    if is_headline or sentence_idx == 0:
        return ClaimImportance.HIGH

    score = 0
    if sentence_idx <= 2:
        score += 2
    if entities.get("numbers"):
        score += 1
    if entities.get("organizations") or entities.get("persons"):
        score += 1
    if entities.get("dates"):
        score += 1
    if claim_type in (ClaimType.POLICY, ClaimType.EVENT, ClaimType.ANNOUNCEMENT, ClaimType.FINANCIAL):
        score += 1

    if score >= 4:
        return ClaimImportance.HIGH
    elif score >= 2:
        return ClaimImportance.MEDIUM
    else:
        return ClaimImportance.LOW


def check_claim_similarity(text1: str, text2: str) -> float:
    """Compute token Jaccard similarity between two normalized claims."""
    words1 = set(re.findall(r"\b\w{3,}\b", text1.lower()))
    words2 = set(re.findall(r"\b\w{3,}\b", text2.lower()))
    if not words1 or not words2:
        return 0.0
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return intersection / float(union)


def split_multi_claim_sentence(sentence: str) -> List[str]:
    """Split sentences that contain two coordinate factual clauses joined by 'and'."""
    parts = CONJUNCTION_SPLIT_PATTERN.split(sentence)
    if len(parts) > 1:
        valid_parts = []
        for p in parts:
            p_strip = p.strip()
            if len(p_strip.split()) >= 4 and contains_factual_signals(p_strip):
                if p_strip and p_strip[-1] not in (".", "!", "?"):
                    p_strip += "."
                valid_parts.append(p_strip)
        if len(valid_parts) > 1:
            return valid_parts
    return [sentence]


def extract_claims_from_text(
    text: str,
    headline: Optional[str] = None,
) -> List[Claim]:
    """Extract, filter, normalize, and deduplicate claims from input text and optional headline."""
    nlp = get_nlp()
    raw_claims: List[Claim] = []
    claim_counter = 1

    # 1. Headline factual claim extraction
    if headline and is_candidate_sentence(headline) and contains_factual_signals(headline):
        doc = nlp(headline)
        entities = extract_entities_from_doc(doc)
        normalized = normalize_claim_text(headline)
        claim_type = classify_claim_type(headline, entities, has_attribution=False)

        claim_id = generate_claim_id(headline, claim_counter)
        claim_counter += 1

        raw_claims.append(
            Claim(
                claim_id=claim_id,
                original_text=headline.strip(),
                normalized_text=normalized,
                claim_type=claim_type,
                importance=ClaimImportance.HIGH,
                entities=entities["all_entities"],
                dates=entities["dates"],
                numbers=entities["numbers"],
                locations=entities["locations"],
                organizations=entities["organizations"],
                persons=entities["persons"],
                source_sentence=headline.strip(),
                is_headline_claim=True,
                attribution=None,
            )
        )

    # 2. Body processing via spaCy sentence segmentation
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    for s_idx, sentence in enumerate(sentences):
        if not is_candidate_sentence(sentence):
            continue

        if not contains_factual_signals(sentence):
            continue

        # Check for quote / reported speech attribution
        attribution_match = ATTRIBUTION_REGEX.match(sentence)
        attribution: Optional[AttributedSpeaker] = None
        statement_text = sentence

        if attribution_match:
            speaker = attribution_match.group("speaker").strip()
            verb = attribution_match.group("verb").strip()
            statement = attribution_match.group("statement").strip()

            # Ensure speaker looks like a plausible person or organization name
            if len(speaker.split()) <= 5:
                attribution = AttributedSpeaker(speaker=speaker, attribution_verb=verb)
                statement_text = statement

        # Handle multi-claim clauses
        sub_clauses = split_multi_claim_sentence(statement_text)

        for clause in sub_clauses:
            clause_doc = nlp(clause)
            entities = extract_entities_from_doc(clause_doc)
            normalized = normalize_claim_text(clause)
            claim_type = classify_claim_type(clause, entities, has_attribution=attribution is not None)
            importance = calculate_claim_importance(
                is_headline=False,
                sentence_idx=s_idx,
                entities=entities,
                claim_type=claim_type,
            )

            claim_id = generate_claim_id(clause, claim_counter)
            claim_counter += 1

            raw_claims.append(
                Claim(
                    claim_id=claim_id,
                    original_text=clause.strip(),
                    normalized_text=normalized,
                    claim_type=claim_type,
                    importance=importance,
                    entities=entities["all_entities"],
                    dates=entities["dates"],
                    numbers=entities["numbers"],
                    locations=entities["locations"],
                    organizations=entities["organizations"],
                    persons=entities["persons"],
                    source_sentence=sentence,
                    is_headline_claim=False,
                    attribution=attribution,
                )
            )

    # 3. Duplicate detection and grouping
    deduplicated_claims: List[Claim] = []
    for candidate in raw_claims:
        is_dup = False
        for primary in deduplicated_claims:
            # Primary similarity check on normalized (stripped) statement text
            similarity = check_claim_similarity(candidate.normalized_text, primary.normalized_text)

            # Secondary check: compare full source sentences — catches attribution rewording
            # (e.g. "announced layoffs" vs "said it would cut"), where the source sentences
            # share substantially the same factual content (same numbers, dates, location).
            if similarity < 0.75:
                source_sim = check_claim_similarity(candidate.source_sentence, primary.source_sentence)
                # Promote to duplicate if source sentences are close AND the claims share
                # the same key numeric + date entities (same quantitative facts).
                shared_numbers = set(candidate.numbers) & set(primary.numbers)
                shared_dates = set(candidate.dates) & set(primary.dates)
                if source_sim >= 0.5 and (shared_numbers or shared_dates):
                    similarity = source_sim  # use the higher measure

            if similarity >= 0.75 or (
                similarity >= 0.5
                and set(candidate.numbers) & set(primary.numbers)
                and set(candidate.dates) & set(primary.dates)
            ):
                # Mark as duplicate and link to primary
                candidate.duplicate_of = primary.claim_id
                if candidate.original_text not in primary.equivalent_claims:
                    primary.equivalent_claims.append(candidate.original_text)
                is_dup = True
                break

        if not is_dup:
            deduplicated_claims.append(candidate)

    logger.info("Extracted %d unique claims from %d candidate statements.", len(deduplicated_claims), len(raw_claims))
    return deduplicated_claims


def extract_claims(article: NormalizedArticle) -> List[Claim]:
    """Clean service interface: transform a NormalizedArticle into a list of factual Claims."""
    return extract_claims_from_text(
        text=article.body,
        headline=article.title,
    )
