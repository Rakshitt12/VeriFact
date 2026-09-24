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
    # Causal / scientific-claim verbs (cause, prevent, cure, correlate, ...)
    "cause", "causes", "caused", "causing",
    "prevent", "prevents", "prevented", "preventing",
    "cure", "cures", "cured", "curing",
    "treat", "treats", "treated", "treating",
    "trigger", "triggers", "triggered", "triggering",
    "link", "links", "linked", "linking",
    "correlate", "correlates", "correlated",
    "contribute", "contributes", "contributed",
    "result", "results", "resulted", "resulting",
    "lead", "leads", "led", "leading",
    "worsen", "worsens",
    "improve", "improves",
    "associated",
}



# Copular stative/descriptive claims ("X is/was [verifiable property]") carry no
# action verb, so they need their own narrow pattern. The complement lexicon is
# deliberately restricted to objectively checkable properties (superlatives,
# ranks, origins, locations, visibility) — a bare "is/was" match would admit
# opinion and narrative text ("He is happy", "It was a dark day").
COPULAR_VERIFIABLE_PROPERTIES = frozenset({
    "tallest", "longest", "largest", "biggest", "smallest", "shortest",
    "oldest", "newest", "first", "last", "only",
    "visible", "located", "situated", "invented", "discovered",
    "founded", "headquartered",
})

_COPULAR_PROPERTY_PATTERN = re.compile(
    r"\b(?:is|are|was|were)\b[^.?!]{0,60}\b(?:"
    + "|".join(sorted(COPULAR_VERIFIABLE_PROPERTIES))
    + r")\b",
    re.IGNORECASE,
)

# Causal-attribution phrases: causal constructions with no indicator verb
# ("is due to", "rose because of", "driven by demand"). Matched alongside —
# never instead of — the verb-set check. In the extraction pipeline
# is_candidate_sentence() (opinion/greeting/boilerplate filters) always runs
# first, so opinion sentences containing these phrases are still rejected
# before this signal is ever consulted.
_CAUSAL_ATTRIBUTION_PATTERN = re.compile(
    r"\b(?:due\s+to|because\s+of|owing\s+to|attributed\s+to|blamed\s+on|"
    r"driven\s+by|fueled\s+by|fuelled\s+by|spurred\s+by|sparked\s+by|"
    r"stem(?:med|s)?\s+from|a\s+result\s+of|tied\s+to|amid)\b",
    re.IGNORECASE,
)

# Dependency labels / POS tags constituting a genuine subject-verb structure.
_SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "csubj", "csubjpass"})
_VERB_POS = frozenset({"VERB", "AUX"})

# Verb lexicon for degraded pipelines without a parser (spacy.blank fallback).
_FALLBACK_VERB_LEXICON = frozenset(
    set(FACTUAL_INDICATOR_VERBS)
    | {"is", "are", "was", "were", "be", "been", "has", "have", "had", "do", "does", "did"}
)


def has_subject_verb_structure(text: str) -> bool:
    """Confirm genuine subject-verb structure via spaCy dependency parse.

    A short sentence is accepted as a candidate claim only if the parse yields
    both a subject dependency (nsubj/nsubjpass/csubj/csubjpass) and a verb
    (VERB/AUX). In degraded environments where the pipeline has no parser
    (spacy.blank fallback), falls back to a conservative verb-lexicon check.
    """
    try:
        from backend.claim.entity_extractor import get_nlp
        nlp = get_nlp()
        doc = nlp(text)
    except Exception:
        return False
    if "parser" in getattr(nlp, "pipe_names", []):
        deps = {t.dep_ for t in doc}
        poses = {t.pos_ for t in doc}
        return bool(deps & _SUBJECT_DEPS) and bool(poses & _VERB_POS)
    words = {w.lower() for w in re.findall(r"\b[A-Za-z]+\b", text)}
    return len(text.split()) >= 3 and bool(words & _FALLBACK_VERB_LEXICON)



def is_candidate_sentence(text: str) -> bool:
    """Filter out questions, opinions, ads, greetings, and short non-substantive text.

    Returns True if the sentence is worth analyzing for factual claims.
    """
    clean = text.strip()

    # Length bounds: fragments below 3 words cannot carry a verifiable assertion.
    # The old 4-word bar survives only as a trigger: sub-4-word sentences must
    # additionally prove genuine subject-verb structure (dependency parse)
    # instead of being admitted on length alone.
    if len(clean) < 8 or len(clean.split()) < 3:
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

    # Short sentences below the old 4-word bar must prove subject-verb shape;
    # this admits complete 3-word assertions ("Vaccines cause autism.") while
    # still rejecting verbless fragments.
    if len(clean.split()) < 4 and not has_subject_verb_structure(clean):
        return False

    return True


def contains_factual_signals(text: str) -> bool:
    """Check if the sentence contains at least one concrete factual indicator.

    Signals include:
    - Digits or numbers (e.g. 10, 6.5%, ₹5000, 2026, 1.4 billion)
    - Action verbs of policy, announcement, physical event, or causation
    - Causal-attribution phrases (due to, because of, driven by, ...)
    - Currency symbols or percentage markers ($, €, £, ₹, %)
    - Copular stative claims with verifiable properties
      (e.g. "X is the tallest ...", "X is visible from ...")
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

    # Contains verifiable action verbs (including causal/scientific claims)
    words = {w.lower() for w in re.findall(r"\b[A-Za-z]+\b", text)}
    if words.intersection(FACTUAL_INDICATOR_VERBS) or words.intersection(ATTRIBUTION_VERBS):
        return True

    # Contains a copular stative claim with a verifiable property
    # ("The Great Wall of China is visible from space"). Bare is/was alone
    # is not enough — the complement must be objectively checkable.
    if _COPULAR_PROPERTY_PATTERN.search(text):
        return True

    # Contains a causal-attribution phrase ("due to", "because of", ...).
    if _CAUSAL_ATTRIBUTION_PATTERN.search(text):
        return True

    return False

