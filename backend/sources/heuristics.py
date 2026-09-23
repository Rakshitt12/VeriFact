"""Pattern-based heuristics for attribution, primary reporting, and publication recency."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import List, Optional, Tuple
from backend.sources.models import AttributionSignal, PrimaryReportingSignal, SourceAge


# Attribution detection patterns
_ATTRIBUTION_VERBS_PATTERN = re.compile(
    r"\b(according to|cited by|reported by|spokesperson said|told reporters|"
    r"stated that|announced by|confirmed by|in an official statement|"
    r"in a press release|in a regulatory filing|court documents? states?|"
    r"ministry said|government confirmed|cabinet approved|revealed that|"
    r"found that|showed that|spoke on condition of anonymity)\b",
    re.IGNORECASE,
)

_ATTRIBUTED_ACTORS_PATTERN = re.compile(
    r"\b(spokesperson|minister|prime minister|secretary|governor|commissioner|director|"
    r"researchers|scientists|investigators|officials|regulators|analysts)\b",
    re.IGNORECASE,
)

# Primary / firsthand reporting indicator patterns
_PRIMARY_REPORTING_PATTERNS = [
    (re.compile(r"\b(exclusive(:|report)?|first reported by)\b", re.IGNORECASE), "exclusive_reporting"),
    (re.compile(r"\b(in an interview with|told this publication|speaking exclusively)\b", re.IGNORECASE), "direct_interview"),
    (re.compile(r"\b(documents? (obtained|reviewed|seen) by)\b", re.IGNORECASE), "documentary_evidence"),
    (re.compile(r"\b(in an official statement|official release|cabinet approved|press release)\b", re.IGNORECASE), "official_statement"),
    (re.compile(r"\b(investigation (revealed|found|showed)|fact[- ]check (revealed|found|showed))\b", re.IGNORECASE), "fact_check_investigation"),
    (re.compile(r"\b(in a press conference|at a press briefing)\b", re.IGNORECASE), "press_briefing"),
    (re.compile(r"\b(our correspondent|our reporter|field report)\b", re.IGNORECASE), "firsthand_reporting"),
    (re.compile(r"\b(regulatory filing|exchange filing|court filing|affidavit)\b", re.IGNORECASE), "official_filing"),
    (re.compile(r"\b(study published in|peer-reviewed journal)\b", re.IGNORECASE), "academic_publication"),
]


def detect_attribution(text: Optional[str]) -> AttributionSignal:
    """Analyze article snippet or content for explicit attribution and quotes."""
    if not text or not text.strip():
        return AttributionSignal(present=False, has_quotes=False, named_sources=[], statement_type=None)

    has_quotes = bool(re.search(r'["“][^"”]{5,}["”]', text))
    has_attrib_verb = bool(_ATTRIBUTION_VERBS_PATTERN.search(text))

    named_sources: List[str] = []
    actor_matches = _ATTRIBUTED_ACTORS_PATTERN.findall(text)
    for m in actor_matches:
        if m.lower() not in [s.lower() for s in named_sources]:
            named_sources.append(m.capitalize())

    statement_type = None
    if "press release" in text.lower():
        statement_type = "press_release"
    elif "statement" in text.lower():
        statement_type = "official_statement"
    elif "filing" in text.lower():
        statement_type = "regulatory_filing"
    elif has_quotes:
        statement_type = "direct_quote"

    present = has_attrib_verb or has_quotes or len(named_sources) > 0

    return AttributionSignal(
        present=present,
        has_quotes=has_quotes,
        named_sources=named_sources[:3],
        statement_type=statement_type,
    )


def detect_primary_reporting(text: Optional[str]) -> PrimaryReportingSignal:
    """Detect observable signals that a report contains original firsthand reporting."""
    if not text or not text.strip():
        return PrimaryReportingSignal(present=False, signals=[])

    detected_signals: List[str] = []
    for pattern, signal_name in _PRIMARY_REPORTING_PATTERNS:
        if pattern.search(text):
            detected_signals.append(signal_name)

    return PrimaryReportingSignal(
        present=len(detected_signals) > 0,
        signals=detected_signals,
    )


def parse_source_age(published_at_raw: Optional[str]) -> Tuple[SourceAge, Optional[int]]:
    """Parse raw publication timestamp string and categorize age relative to current UTC time.

    Returns:
        (SourceAge, age_in_days_or_None)
    """
    if not published_at_raw:
        return SourceAge.UNKNOWN, None

    raw = published_at_raw.strip()
    pub_dt: Optional[datetime] = None

    # Try standard ISO-8601 variations
    # 1. 2026-04-05T12:00:00Z
    try:
        pub_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        pass

    # 2. GDELT format: 20260405T120000Z or 20260405
    if pub_dt is None:
        try:
            if "T" in raw:
                clean_raw = raw.replace("Z", "")
                pub_dt = datetime.strptime(clean_raw, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
            elif len(raw) == 8 and raw.isdigit():
                pub_dt = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass

    # 3. YYYY-MM-DD
    if pub_dt is None:
        try:
            pub_dt = datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass

    if pub_dt is None:
        return SourceAge.UNKNOWN, None

    # Calculate days difference
    now = datetime.now(timezone.utc)
    if pub_dt.tzinfo is None:
        pub_dt = pub_dt.replace(tzinfo=timezone.utc)

    delta_days = (now - pub_dt).days

    if delta_days < 0:
        # Clocks slightly out of sync / future timestamp
        return SourceAge.VERY_RECENT, 0
    elif delta_days <= 30:
        return SourceAge.VERY_RECENT, delta_days
    elif delta_days <= 365:
        return SourceAge.RECENT, delta_days
    else:
        return SourceAge.OLDER, delta_days
