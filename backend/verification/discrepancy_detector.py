"""Numeric, temporal, and polarity discrepancy detection between claims and evidence.

Identifies explicit conflicts such as conflicting monetary values (e.g. ₹500 crore vs ₹300 crore),
conflicting dates, and explicit polarity denials (e.g. resignation announced vs denial/staying).
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from backend.claim.models import Claim
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.verification.models import Discrepancy, DiscrepancyType


# Common denial and refutation patterns
_DENIAL_PATTERNS = [
    r"\bdeni(?:es|ed|al)\b",
    r"\breject(?:s|ed|ing|ion)\b",
    r"\brefut(?:es|ed|ing|ation)\b",
    r"\bdismiss(?:es|ed|ing)\b",
    r"\brul(?:es|ed)\s+out\b",
    r"\bdid\s+not\s+(?:resign|step\s+down|quit|approve|announce|agree|happen|occur)\b",
    r"\bhas\s+not\s+(?:resigned|stepped\s+down|quit|approved|announced)\b",
    r"\bnot\s+true\b",
    r"\bno\s+truth\b",
    r"\bfake\s+(?:news|claim|report)\b",
    r"\buntrue\b",
    r"\bbaseless\b",
    r"\bremains?\s+(?:in|as|the)\b",
    r"\bno\s+evidence\b",
]

_NUMERIC_UNIT_PATTERNS = [
    # ₹5,000 crore / 5000 crore / ₹500 cr / 500 cr
    r"(?:(?:₹|rs\.?|inr|\$|usd)\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(crore|cr|lakh|million|mn|billion|bn|trillion|percent|%|rupees?|dollars?|jobs?|workers?|employees?|bps|basis\s+points?)\b",
    # Bare numbers with symbols: ₹10 / 10 rupee
    r"(?:(?:₹|rs\.?|inr|\$)\s*)(\d+(?:,\d+)*(?:\.\d+)?)",
    r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:rupees?|dollars?|per\s+cent|percent|%)",
]

# Months pattern for temporal comparison
_MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"
]


def _normalize_number_string(val_str: str) -> float:
    """Convert number string with optional commas to float."""
    try:
        return float(val_str.replace(",", "").strip())
    except ValueError:
        return 0.0


def extract_quantities(text: str) -> List[Tuple[float, str, str]]:
    """Extract (numeric_value, unit, full_phrase) tuples from text.

    Examples:
        "₹500 crore" -> (500.0, "crore", "₹500 crore")
        "₹10 reduction" -> (10.0, "rupee", "₹10")
        "25 bps" -> (25.0, "bps", "25 bps")
    """
    results: List[Tuple[float, str, str]] = []
    seen_spans = set()

    for pat in _NUMERIC_UNIT_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            span = m.span()
            if any(span[0] >= s[0] and span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)

            groups = m.groups()
            if len(groups) == 2:
                num_part, unit_part = groups
                unit = (unit_part or "unit").lower()
            elif len(groups) == 1:
                num_part = groups[0]
                unit = "currency"
            else:
                continue

            num_val = _normalize_number_string(num_part)
            full_match = m.group(0).strip()
            results.append((num_val, unit, full_match))

    return results


def _extract_snippet_around(text: str, target: str, window: int = 100) -> Optional[str]:
    """Extract a contextual snippet around a target string in text."""
    idx = text.lower().find(target.lower())
    if idx == -1:
        return None
    start = max(0, idx - window)
    end = min(len(text), idx + len(target) + window)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def detect_discrepancies(claim: Claim, evidence: Evidence) -> List[Discrepancy]:
    """Examine evidence text against claim for numerical, temporal, and polarity discrepancies."""
    discrepancies: List[Discrepancy] = []
    
    # Aggregate available evidence text
    evidence_text = f"{evidence.title} {evidence.snippet or ''} {evidence.content or ''}".strip()
    if not evidence_text:
        return discrepancies

    claim_text = claim.normalized_text or claim.original_text

    # -------------------------------------------------------------------------
    # 1. Polarity / Direct Denial Detection
    # -------------------------------------------------------------------------
    for pat in _DENIAL_PATTERNS:
        m = re.search(pat, evidence_text, re.IGNORECASE)
        if m:
            denial_word = m.group(0)
            # Check if evidence mentions key entities or subjects of claim
            overlap_entities = [
                e.text.lower() for e in claim.entities
                if len(e.text) > 2 and e.text.lower() in evidence_text.lower()
            ]
            key_words = [w.lower() for w in claim.persons + claim.organizations]
            has_subject = any(kw in evidence_text.lower() for kw in key_words) or len(overlap_entities) >= 1

            if has_subject:
                snippet = _extract_snippet_around(evidence_text, denial_word, window=80)
                discrepancies.append(
                    Discrepancy(
                        discrepancy_type=DiscrepancyType.POLARITY,
                        aspect="claim_action_or_status",
                        claim_value=claim.original_text[:100],
                        evidence_value=f"Evidence contains explicit denial/refutation: '{denial_word}'",
                        snippet=snippet,
                        severity="CRITICAL",
                    )
                )
                # One critical denial is sufficient
                break

    # -------------------------------------------------------------------------
    # 2. Numerical / Amount Discrepancies
    # -------------------------------------------------------------------------
    claim_quantities = extract_quantities(claim_text)
    evidence_quantities = extract_quantities(evidence_text)

    # Standardize common units
    unit_map = {
        "cr": "crore",
        "mn": "million",
        "bn": "billion",
        "%": "percent",
        "per cent": "percent",
        "rs": "currency",
        "rupee": "currency",
        "rupees": "currency",
        "dollars": "currency",
        "dollar": "currency",
    }

    if claim_quantities and evidence_quantities:
        for c_val, c_unit, c_phrase in claim_quantities:
            norm_c_unit = unit_map.get(c_unit, c_unit)
            
            # Find evidence quantities sharing compatible unit
            compatible_ev = [
                (e_val, e_unit, e_phrase) for e_val, e_unit, e_phrase in evidence_quantities
                if unit_map.get(e_unit, e_unit) == norm_c_unit or norm_c_unit == "currency"
            ]

            if compatible_ev:
                # Check if exact match exists
                exact_match = any(abs(e_val - c_val) < 1e-4 for e_val, _, _ in compatible_ev)
                if not exact_match:
                    # Check if there is an opposing number mentioned in same context
                    # Take the closest or most prominent contrasting number
                    diff_ev = [ev for ev in compatible_ev if abs(ev[0] - c_val) >= 1e-4]
                    if diff_ev:
                        e_val, e_unit, e_phrase = diff_ev[0]
                        snippet = _extract_snippet_around(evidence_text, e_phrase, window=70)
                        discrepancies.append(
                            Discrepancy(
                                discrepancy_type=DiscrepancyType.NUMERIC,
                                aspect=f"amount_{norm_c_unit}",
                                claim_value=c_phrase,
                                evidence_value=e_phrase,
                                snippet=snippet,
                                severity="MAJOR",
                            )
                        )

    # -------------------------------------------------------------------------
    # 3. Temporal / Date Discrepancies
    # -------------------------------------------------------------------------
    if claim.dates:
        # Check if evidence mentions a distinct month or date for the same announcement/event
        claim_months = [m for m in _MONTHS if any(m in d.lower() for d in claim.dates)]
        if claim_months:
            ev_months = [m for m in _MONTHS if m in evidence_text.lower()]
            # If evidence mentions different month and does not mention claim month
            contradicting_months = [m for m in ev_months if m not in claim_months]
            if contradicting_months and not any(m in ev_months for m in claim_months):
                snippet = _extract_snippet_around(evidence_text, contradicting_months[0], window=60)
                discrepancies.append(
                    Discrepancy(
                        discrepancy_type=DiscrepancyType.TEMPORAL,
                        aspect="timeframe_month",
                        claim_value=", ".join(claim.dates),
                        evidence_value=contradicting_months[0].capitalize(),
                        snippet=snippet,
                        severity="MINOR",
                    )
                )

    return discrepancies
