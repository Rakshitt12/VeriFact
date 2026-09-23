"""Claim normalization without altering factual meaning.

Normalizes:
- Common abbreviations (e.g. RBI -> Reserve Bank of India, govt -> government)
- Currency notations (e.g. Rs. -> INR, ₹ -> INR, $ -> USD)
- Percentages (e.g. bps / basis points -> %)
- Whitespace and punctuation
- Entity representations for search consistency
"""

import re

# Abbreviation dictionary
ABBREVIATIONS = {
    r"\bRBI\b": "Reserve Bank of India",
    r"\bSBI\b": "State Bank of India",
    r"\bGovt\.?\b": "Government",
    r"\bdept\.?\b": "department",
    r"\bapprox\.?\b": "approximately",
    r"\bPMO\b": "Prime Minister's Office",
    r"\bMoF\b": "Ministry of Finance",
    r"\bWHO\b": "World Health Organization",
    r"\bUN\b": "United Nations",
    r"\bIMF\b": "International Monetary Fund",
    r"\bUS\b": "United States",
    r"\bUK\b": "United Kingdom",
    r"\bEU\b": "European Union",
}

# Currency normalization patterns
CURRENCY_REPLACEMENTS = [
    (re.compile(r"₹\s*([\d,]+(?:\.\d+)?)"), r"\1 INR"),
    (re.compile(r"\bRs\.?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE), r"\1 INR"),
    (re.compile(r"\$\s*([\d,]+(?:\.\d+)?)"), r"\1 USD"),
    (re.compile(r"€\s*([\d,]+(?:\.\d+)?)"), r"\1 EUR"),
    (re.compile(r"£\s*([\d,]+(?:\.\d+)?)"), r"\1 GBP"),
]

# Percent and basis point normalization
BASIS_POINTS_PATTERN = re.compile(r"\b(\d+)\s*(?:bps|basis points)\b", re.IGNORECASE)


def normalize_claim_text(original_text: str) -> str:
    """Produce a normalized, search-ready version of a claim.

    Does NOT infer missing facts or alter factual meaning.
    """
    if not original_text:
        return ""

    text = original_text.strip()

    # 1. Expand standard well-known abbreviations
    for pattern, expansion in ABBREVIATIONS.items():
        text = re.sub(pattern, expansion, text)

    # 2. Normalize currency symbols to ISO codes
    for pattern, replacement in CURRENCY_REPLACEMENTS:
        text = pattern.sub(replacement, text)

    # 3. Normalize basis points (e.g. 25bps -> 0.25 percent)
    def _bps_repl(m):
        bps_val = int(m.group(1))
        pct_val = bps_val / 100.0
        return f"{pct_val}%"

    text = BASIS_POINTS_PATTERN.sub(_bps_repl, text)

    # 4. Standardize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # 5. Ensure trailing punctuation is clean
    if text and text[-1] not in (".", "!", "?"):
        text += "."

    return text
