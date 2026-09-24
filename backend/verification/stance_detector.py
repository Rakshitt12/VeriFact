"""Evidence stance detection and claim aspect comparison.

Determines the deterministic stance (SUPPORTING, CONTRADICTING, NEUTRAL, INSUFFICIENT)
of a single evidence document relative to a factual claim by analyzing aspect alignment,
negation/denial signals, and numerical/temporal discrepancies.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

from backend.claim.models import Claim
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.verification.discrepancy_detector import detect_discrepancies, extract_quantities
from backend.verification.lexical_expansion import (
    action_matches_evidence,
    fallback_claim_action,
)
from backend.verification.models import (
    AspectMatch,
    AspectType,
    Discrepancy,
    EvidenceComparison,
    EvidenceStance,
)
from backend.verification.similarity import (
    get_words,
    jaccard_similarity,
    normalize_text_for_similarity,
)


# Common action confirmation verbs and their variants
_ACTION_AFFIRMATIONS = {
    "cut": ["cut", "reduced", "lowered", "slashed", "reduction", "decrease"],
    "reduce": ["reduced", "cut", "lowered", "slashed", "reduction", "decrease"],
    "announce": ["announced", "unveiled", "declared", "introduced", "rolled out"],
    "approve": ["approved", "cleared", "greenlit", "sanctioned", "okayed", "passed"],
    "resign": ["resigned", "resignation", "stepped down", "quit", "vacated"],
    "invest": ["invested", "investment", "investing", "pledged", "committed"],
    "ban": ["banned", "prohibited", "outlawed", "illegal", "prohibition"],
    "lose": ["lost", "loss", "losses", "deficit", "incurred"],
    "acquire": ["acquired", "bought", "purchased", "takeover", "acquisition"],
    "launch": ["launched", "rolled out", "introduced", "started", "unveiled"],
    "hire": ["hired", "recruited", "onboarded", "appointed", "hiring"],
    "layoff": ["laid off", "layoffs", "sacked", "fired", "terminated", "job cuts"],
}


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences cleanly."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 5]


def _find_best_matching_sentence(sentences: List[str], claim_tokens: Set[str]) -> Optional[str]:
    """Find the sentence in evidence that has highest token overlap with claim."""
    best_score = 0.0
    best_sent = None

    for sent in sentences:
        sent_tokens = set(re.findall(r"\b\w{3,}\b", sent.lower()))
        if not sent_tokens:
            continue
        overlap = len(claim_tokens & sent_tokens)
        score = overlap / max(len(claim_tokens), 1)
        if score > best_score and overlap >= 2:
            best_score = score
            best_sent = sent

    return best_sent


def _extract_claim_aspects(claim: Claim) -> List[Tuple[AspectType, str]]:
    """Extract key factual aspects from Claim."""
    aspects: List[Tuple[AspectType, str]] = []

    # WHO
    for p in claim.persons:
        aspects.append((AspectType.WHO, p))
    for org in claim.organizations:
        aspects.append((AspectType.WHO, org))
    if claim.attribution and claim.attribution.speaker:
        if claim.attribution.speaker not in claim.persons and claim.attribution.speaker not in claim.organizations:
            aspects.append((AspectType.ATTRIBUTION, claim.attribution.speaker))

    # WHERE
    for loc in claim.locations:
        aspects.append((AspectType.WHERE, loc))

    # WHEN
    for d in claim.dates:
        aspects.append((AspectType.WHEN, d))

    # AMOUNT / COUNT
    for n in claim.numbers:
        aspects.append((AspectType.AMOUNT, n))

    # Detect primary action verb from normalized text
    claim_text = (claim.normalized_text or claim.original_text).lower()
    for base_action, variants in _ACTION_AFFIRMATIONS.items():
        all_variants = [base_action] + variants
        if any(re.search(r"\b" + re.escape(v) + r"\b", claim_text) for v in all_variants):
            aspects.append((AspectType.ACTION, base_action))
            break

    # Generalization fallback: claims whose predicate is missing from the
    # static table still get an ACTION aspect from the dependency parse
    # ("RAM price hike ..." -> "hike"), so unlisted verbs stay verifiable.
    if not any(aspect_type == AspectType.ACTION for aspect_type, _ in aspects):
        fallback_action = fallback_claim_action(claim.normalized_text or claim.original_text)
        if fallback_action:
            aspects.append((AspectType.ACTION, fallback_action))

    return aspects


def classify_evidence_stance(
    claim: Claim,
    evidence: Evidence,
) -> EvidenceComparison:
    """Classify the stance of an Evidence item relative to a specific Claim."""
    evidence_text = f"{evidence.title}. {evidence.snippet or ''} {evidence.content or ''}".strip()
    claim_text = (claim.normalized_text or claim.original_text).strip()

    # 1. Relevance calculation via token overlap
    claim_words_list = get_words(claim_text, remove_stopwords=True)
    ev_words_list = get_words(evidence_text, remove_stopwords=True)
    jaccard = jaccard_similarity(claim_words_list, ev_words_list)
    claim_words = set(claim_words_list)
    ev_words = set(ev_words_list)
    common_words = claim_words & ev_words

    # Relevance score normalized
    relevance = min(1.0, max(0.0, jaccard * 2.5 + (len(common_words) / max(len(claim_words), 1)) * 0.5))

    # 2. Extract and match claim aspects
    aspects = _extract_claim_aspects(claim)
    aspect_matches: List[AspectMatch] = []
    supported_aspects_count = 0
    contradicted_aspects_count = 0

    # 3. Detect factual discrepancies (numeric, temporal, polarity)
    discrepancies = detect_discrepancies(claim, evidence)

    # Map discrepancies to aspect matches
    discrepancy_types = {d.discrepancy_type for d in discrepancies}
    has_critical_denial = any(d.severity == "CRITICAL" for d in discrepancies)
    has_numeric_discrepancy = any(d.discrepancy_type.value == "NUMERIC" for d in discrepancies)

    for aspect_type, val in aspects:
        val_clean = val.lower()
        if aspect_type == AspectType.ACTION:
            if val_clean in _ACTION_AFFIRMATIONS:
                synonyms = _ACTION_AFFIRMATIONS[val_clean]
                found = any(re.search(r"\b" + re.escape(syn) + r"\b", evidence_text.lower()) for syn in synonyms)
            else:
                # Generalization fallback for unlisted predicates: lemma +
                # verb-family expansion instead of another static entry.
                found = action_matches_evidence(val_clean, evidence_text)
            if has_critical_denial:
                status = "CONTRADICTED"
                contradicted_aspects_count += 1
            elif found:
                status = "SUPPORTED"
                supported_aspects_count += 1
            else:
                status = "UNMENTIONED"
        elif aspect_type in (AspectType.AMOUNT, AspectType.COUNT):
            if has_numeric_discrepancy:
                # Find matching numeric discrepancy
                m_disc = [d for d in discrepancies if d.discrepancy_type.value == "NUMERIC"]
                ev_val = m_disc[0].evidence_value if m_disc else None
                status = "CONTRADICTED"
                contradicted_aspects_count += 1
            elif val_clean in evidence_text.lower():
                ev_val = val
                status = "SUPPORTED"
                supported_aspects_count += 1
            else:
                ev_val = None
                status = "UNMENTIONED"
            aspect_matches.append(AspectMatch(aspect_type=aspect_type, claim_value=val, evidence_value=ev_val, status=status))
            continue
        else:
            if val_clean in evidence_text.lower():
                status = "SUPPORTED"
                supported_aspects_count += 1
            else:
                status = "UNMENTIONED"

        aspect_matches.append(
            AspectMatch(
                aspect_type=aspect_type,
                claim_value=val,
                evidence_value=val if status == "SUPPORTED" else None,
                status=status,
            )
        )

    # Sentences for grounded quotations
    sentences = _split_into_sentences(evidence_text)
    best_quote = _find_best_matching_sentence(sentences, claim_words)

    # 4. Determine Stance
    has_action_aspect = any(m.aspect_type == AspectType.ACTION for m in aspect_matches)
    action_supported = any(m.aspect_type == AspectType.ACTION and m.status == "SUPPORTED" for m in aspect_matches)

    supporting_points: List[str] = []
    contradicting_points: List[str] = []
    neutral_points: List[str] = []
    signals: List[str] = []
    limitations: List[str] = []

    # Case A: Explicit Polarity Denial or Major Discrepancy -> CONTRADICTING
    if has_critical_denial:
        stance = EvidenceStance.CONTRADICTING
        confidence = 0.90
        for d in discrepancies:
            if d.discrepancy_type.value == "POLARITY":
                contradicting_points.append(f"Explicit denial/refutation found: {d.evidence_value}")
                signals.append("polarity_denial_detected")
        reasoning = (
            f"Evidence explicitly contradicts the claim. "
            f"Source reports denial/rejection of asserted action: '{best_quote or evidence.title}'."
        )

    elif has_numeric_discrepancy:
        stance = EvidenceStance.CONTRADICTING
        confidence = 0.88
        for d in discrepancies:
            if d.discrepancy_type.value == "NUMERIC":
                contradicting_points.append(
                    f"Numerical conflict on {d.aspect}: claim asserts '{d.claim_value}', but evidence reports '{d.evidence_value}'."
                )
                signals.append(f"numeric_discrepancy:{d.claim_value}_vs_{d.evidence_value}")

        # Check partial support
        if supported_aspects_count > 0:
            supporting_points.append(
                f"Corroborates surrounding context ({supported_aspects_count} aspect(s) matched)."
            )
            reasoning = (
                f"Partial support with material contradiction: Evidence confirms the event/subject, "
                f"but contradicts the numerical figure (reports '{contradicting_points[0]}')."
            )
        else:
            reasoning = f"Evidence reports conflicting numerical figures: {contradicting_points[0]}."

    # Case B: Very low relevance / superficial text -> INSUFFICIENT
    elif relevance < 0.18 or len(evidence_text) < 40 or len(common_words) < 2:
        stance = EvidenceStance.INSUFFICIENT
        confidence = 0.70
        neutral_points.append("Insufficient overlap or detail to corroborate or refute claim.")
        reasoning = "Evidence text is too brief, general, or indirect to establish a definitive stance on the claim."
        limitations.append("Minimal textual content available for verification")

    # Case C: Key subject/entities present, but action/outcome unconfirmed -> NEUTRAL
    elif (has_action_aspect and not action_supported) or (supported_aspects_count < 2 and not action_supported):
        # Mentions subject or entity, but doesn't corroborate the predicate action
        stance = EvidenceStance.NEUTRAL
        confidence = 0.80
        neutral_points.append(
            "Mentions subject/entities from claim, but does not confirm or refute the specific action or event."
        )
        signals.append("topic_related_no_stance")
        reasoning = (
            f"Evidence discusses the subject or entities ('{', '.join(list(common_words)[:3])}'), "
            f"but does not confirm or refute the specific claim assertion."
        )

    # Case D: Affirmative Corroboration -> SUPPORTING
    else:
        stance = EvidenceStance.SUPPORTING
        confidence = min(0.95, 0.75 + (supported_aspects_count * 0.06))
        supporting_points.append(
            f"Corroborates {supported_aspects_count} claim aspect(s) including action and core entities."
        )
        if best_quote:
            supporting_points.append(f"Matching excerpt: \"{best_quote}\"")
        signals.append(f"aspects_supported:{supported_aspects_count}")
        reasoning = (
            f"Evidence corroborates the factual claim without material discrepancies. "
            f"Grounded excerpt: \"{best_quote or evidence.title}\"."
        )

    return EvidenceComparison(
        evidence_id=evidence.evidence_id,
        claim_id=claim.claim_id,
        stance=stance,
        confidence=round(confidence, 2),
        relevance=round(relevance, 2),
        matched_claim_aspects=aspect_matches,
        supporting_points=supporting_points,
        contradicting_points=contradicting_points,
        neutral_points=neutral_points,
        discrepancies=discrepancies,
        fact_check_rating=None,
        reasoning=reasoning,
        signals=signals,
        limitations=limitations,
    )
