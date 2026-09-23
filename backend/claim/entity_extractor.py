"""Entity extraction combining spaCy NER with deterministic regex rules.

Extracts structured named entities, currencies, percentages, dates, and numbers.
Supports global model caching so spaCy is loaded only once across the application lifecycle.
"""

import re
from typing import Dict, List, Optional
import spacy
from spacy.language import Language

from backend.claim.models import ExtractedEntity
from backend.logging_config import logger

# Global spaCy pipeline singleton
_NLP_INSTANCE: Optional[Language] = None


def get_nlp() -> Language:
    """Return the cached spaCy language model singleton."""
    global _NLP_INSTANCE
    if _NLP_INSTANCE is None:
        logger.info("Initializing spaCy 'en_core_web_sm' pipeline...")
        try:
            _NLP_INSTANCE = spacy.load("en_core_web_sm")
        except Exception as exc:
            logger.warning("Failed to load 'en_core_web_sm' directly, attempting spacy.blank('en'): %s", exc)
            _NLP_INSTANCE = spacy.blank("en")
    return _NLP_INSTANCE


# Deterministic fallback patterns for entities
INDIAN_CURRENCY_PATTERN = re.compile(
    r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:crore|lakh|thousand|million|billion))?",
    re.IGNORECASE,
)
INTERNATIONAL_CURRENCY_PATTERN = re.compile(
    r"[\$€£]\s*[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|trillion|thousand))?",
    re.IGNORECASE,
)
PERCENTAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent|bps|basis points)\b", re.IGNORECASE)
CARDINAL_NUMBER_PATTERN = re.compile(
    r"\b\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:billion|million|trillion|lakh|crore|thousand))?\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?\b|"
    r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b|"
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b|"
    r"\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)

# Indian states and major territories for deterministic location recognition
INDIAN_STATES_PATTERN = re.compile(
    r"\b(?:Maharashtra|Gujarat|Karnataka|Tamil Nadu|Delhi|Uttar Pradesh|Rajasthan|Kerala|"
    r"Punjab|Haryana|Bihar|West Bengal|Madhya Pradesh|Andhra Pradesh|Telangana|Odisha|"
    r"Assam|Jharkhand|Chhattisgarh|Himachal Pradesh|Uttarakhand|Goa|Jammu & Kashmir)\b",
    re.IGNORECASE,
)



def extract_entities_from_doc(doc) -> Dict[str, List[str]]:
    """Extract entities grouped by functional category."""
    entities: List[ExtractedEntity] = []
    seen_spans = set()

    # 1. spaCy NER annotations
    for ent in doc.ents:
        entities.append(ExtractedEntity(text=ent.text.strip(), label=ent.label_))
        seen_spans.add(ent.text.strip().lower())

    text = doc.text

    # 2. Deterministic Currency checks (e.g. ₹5000, Rs. 10 crore)
    for m in INDIAN_CURRENCY_PATTERN.finditer(text):
        match_str = m.group(0).strip()
        if match_str.lower() not in seen_spans:
            entities.append(ExtractedEntity(text=match_str, label="MONEY"))
            seen_spans.add(match_str.lower())

    for m in INTERNATIONAL_CURRENCY_PATTERN.finditer(text):
        match_str = m.group(0).strip()
        if match_str.lower() not in seen_spans:
            entities.append(ExtractedEntity(text=match_str, label="MONEY"))
            seen_spans.add(match_str.lower())

    # 3. Deterministic Percentages (e.g. 25bps, 6.5%)
    for m in PERCENTAGE_PATTERN.finditer(text):
        match_str = m.group(0).strip()
        if match_str.lower() not in seen_spans:
            entities.append(ExtractedEntity(text=match_str, label="PERCENT"))
            seen_spans.add(match_str.lower())

    # 4. Deterministic Dates
    for m in DATE_PATTERN.finditer(text):
        match_str = m.group(0).strip()
        if match_str.lower() not in seen_spans:
            entities.append(ExtractedEntity(text=match_str, label="DATE"))
            seen_spans.add(match_str.lower())

    # 5. Deterministic Indian locations (GPE)
    for m in INDIAN_STATES_PATTERN.finditer(text):
        match_str = m.group(0).strip()
        # Even if spaCy mislabeled as ORG, ensure GPE is present
        entities.append(ExtractedEntity(text=match_str, label="GPE"))
        seen_spans.add(match_str.lower())


    # Categorize into lists for high-level claim attributes
    dates = []
    numbers = []
    locations = []
    organizations = []
    persons = []

    for ent in entities:
        lbl = ent.label.upper()
        if lbl in ("DATE", "TIME"):
            if ent.text not in dates:
                dates.append(ent.text)
        elif lbl in ("MONEY", "PERCENT", "CARDINAL", "QUANTITY"):
            if ent.text not in numbers:
                numbers.append(ent.text)
        elif lbl in ("GPE", "LOC"):
            if ent.text not in locations:
                locations.append(ent.text)
        elif lbl == "ORG":
            if ent.text not in organizations:
                organizations.append(ent.text)
        elif lbl == "PERSON":
            if ent.text not in persons:
                persons.append(ent.text)

    return {
        "all_entities": entities,
        "dates": dates,
        "numbers": numbers,
        "locations": locations,
        "organizations": organizations,
        "persons": persons,
    }
