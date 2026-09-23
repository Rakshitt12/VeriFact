"""Deterministic rules and heuristic patterns for claim detection and filtering.

Identifies what counts as a candidate factual assertion vs opinion, rhetorical statements,
advertisements, navigational noise, and generic text.
"""

import re
from typing import Set

# Patterns that definitively signal non-factual or excluded text
QUESTION_MARK_PATTERN = re.compile(r"\?\s*$")

# Rhetorical or clickbait headline question patterns
RHETORICAL_QUESTION_STARTERS = re.compile(
    r"^(could|is|are|will|can|should|what if|why|how)\s+.*\?", re.IGNORECASE
)

# Opinion, speculation, and subjective commentary markers
OPINION_MARKERS = [
    "in my opinion",
    "i think",
    "i feel",
    "i believe",
    "we believe",
    "experts believe this could",
    "could change everything",
    "is this the beginning",
    "many people say",
    "some may argue",
    "to be honest",
    "needless to say",
    "in my view",
    "personally speaking",
    "pure speculation",
]

# Advertising, subscription, and navigational boilerplate patterns
AD_BOILERPLATE_PATTERNS = [
    re.compile(r"click here to subscribe", re.IGNORECASE),
    re.compile(r"sign up for (our|the) newsletter", re.IGNORECASE),
    re.compile(r"read more:?", re.IGNORECASE),
    re.compile(r"follow us on (twitter|facebook|instagram|linkedin|telegram)", re.IGNORECASE),
    re.compile(r"copyright \d{4}", re.IGNORECASE),
    re.compile(r"all rights reserved", re.IGNORECASE),
    re.compile(r"advertisement", re.IGNORECASE),
    re.compile(r"sponsored content", re.IGNORECASE),
    re.compile(r"terms of service", re.IGNORECASE),
    re.compile(r"privacy policy", re.IGNORECASE),
    re.compile(r"share this article", re.IGNORECASE),
    re.compile(r"leave a comment", re.IGNORECASE),
]

# Greetings and conversational openers
GREETINGS_PATTERNS = [
    re.compile(r"^(hello|hi|good morning|good evening|welcome back|greetings)[\.,! ]", re.IGNORECASE),
]

# Reporting and announcement attribution verbs
ATTRIBUTION_VERBS: Set[str] = {
    "said",
    "announced",
    "stated",
    "declared",
    "reported",
    "confirmed",
    "claimed",
    "noted",
    "added",
    "revealed",
    "disclosed",
    "explained",
    "asserted",
    "warned",
    "expressed",
    "informed",
    "emphasized",
}

# Strong factual action verbs indicating verifiable occurrences (past, present, 3rd person)
FACTUAL_INDICATOR_VERBS: Set[str] = {
    "increase", "increases", "increased", "increasing",
    "decrease", "decreases", "decreased", "decreasing",
    "approve", "approves", "approved", "approving",
    "pass", "passes", "passed", "passing",
    "sign", "signs", "signed", "signing",
    "launch", "launches", "launched", "launching",
    "cut", "cuts", "cutting",
    "raise", "raises", "raised", "raising",
    "introduce", "introduces", "introduced", "introducing",
    "exceed", "exceeds", "exceeded", "exceeding",
    "fall", "falls", "fell", "fallen", "falling",
    "rise", "rises", "rose", "risen", "rising",
    "strike", "strikes", "struck", "striking",
    "kill", "kills", "killed", "killing",
    "injure", "injures", "injured", "injuring",
    "arrest", "arrests", "arrested", "arresting",
    "acquire", "acquires", "acquired", "acquiring",
    "invest", "invests", "invested", "investing",
    "vote", "votes", "voted", "voting",
    "unveil", "unveils", "unveiled", "unveiling",
    "ban", "bans", "banned", "banning",
    "reject", "rejects", "rejected", "rejecting",
    "win", "wins", "won", "winning",
    "lose", "loses", "lost", "losing",
    "appoint", "appoints", "appointed", "appointing",
    "resign", "resigns", "resigned", "resigning",
    "allocate", "allocates", "allocated", "allocating",
    "budget", "budgets", "budgeted", "budgeting",
    "hit", "hits", "hitting",
    "reach", "reaches", "reached", "reaching",
    "commence", "commences", "commenced", "commencing",
    "begin", "begins", "began", "begun", "beginning",
    "start", "starts", "started", "starting",
    "publish", "publishes", "published", "publishing",
    "agree", "agrees", "agreed", "agreeing",
    "complete", "completes", "completed", "completing",
    "open", "opens", "opened", "opening",
    "close", "closes", "closed", "closing",
    "build", "builds", "built", "building",
}



def is_candidate_sentence(text: str) -> bool:
    """Filter out questions, opinions, ads, greetings, and short non-substantive text.

    Returns True if the sentence is worth analyzing for factual claims.
    """
    clean = text.strip()

    # Length bounds: too short cannot be a verifiable factual assertion
    if len(clean) < 15 or len(clean.split()) < 4:
        return False

    # Exclude questions
    if clean.endswith("?") or RHETORICAL_QUESTION_STARTERS.match(clean):
        return False

    # Exclude greetings
    for gp in GREETINGS_PATTERNS:
        if gp.match(clean):
            return False

    # Exclude ads and web boilerplate
    for bp in AD_BOILERPLATE_PATTERNS:
        if bp.search(clean):
            return False

    clean_lower = clean.lower()

    # Exclude obvious pure subjective opinion/speculation openings
    for op in OPINION_MARKERS:
        if clean_lower.startswith(op) or f" {op} " in clean_lower:
            # If the entire premise is opinionated commentary
            if len(clean.split()) < 12:
                return False

    return True


def contains_factual_signals(text: str) -> bool:
    """Check if the sentence contains at least one concrete factual indicator.

    Signals include:
    - Digits or numbers (e.g. 10, 6.5%, ₹5000, 2026, 1.4 billion)
    - Action verbs of policy, announcement, or physical event
    - Currency symbols or percentage markers ($, €, £, ₹, %)
    """
    # Contains numerical digits
    if re.search(r"\d", text):
        return True

    # Contains currency or percentage
    if re.search(r"[\$€£₹%]|(?:percent|crore|lakh|billion|million|thousand)", text, re.IGNORECASE):
        return True

    # Contains temporal date references (months or days)
    if re.search(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", text, re.IGNORECASE):
        return True

    # Contains verifiable action verbs
    words = {w.lower() for w in re.findall(r"\b[A-Za-z]+\b", text)}
    if words.intersection(FACTUAL_INDICATOR_VERBS) or words.intersection(ATTRIBUTION_VERBS):
        return True

    return False

