"""Shared lemma + WordNet verb-family expansion (generalization layer).

Hand-curated verb lists (``FACTUAL_INDICATOR_VERBS`` in ``backend/claim/rules.py``
and ``_ACTION_AFFIRMATIONS`` in ``backend/verification/stance_detector.py``) can
never enumerate every conjugation or synonym ("hike"/"surged"/"skyrocketed" all
missed them, misclassifying genuinely on-topic evidence). This module generalizes
those checks: spaCy lemmatizes a verb to its root form and WordNet supplies the
verb-sense synonym neighborhood, so new verbs and tenses match without manual
list updates.

Design rules:
- Static lists stay the fast first pass; this module is fallback-only, so every
  previously-covered verb behaves exactly as before.
- Empirical WordNet gap (verified against the bundled corpus): related verbs do
  NOT always share a synset ("hike" <-> "surge" share none; they meet at the
  hypernym "lift"). Relatedness is therefore pairwise per lemma: identical,
  synonym, direct/shared/two-hop hypernym links — with ultra-generic lemmas
  ("run", "hit") restricted to identical matches and hyponym-fringe bridges
  excluded outright (they linked "walked" to static verbs spuriously).
- Phrase-level causal constructions ("due to", "as a result of") still need
  their own regex patterns — WordNet covers single words, not phrases.

Known limitation (documented, not fixable deterministically): verb-level
relatedness cannot separate same-shaped pairs whose arguments differ.
"plummet" reaches "fall" through drop.v.02 exactly the way "ate" reaches
"acquire" through absorb.v.02, and "rain" IS-A "fall" ("rain falls") no less
than prices do. Only the sentence arguments ("oil prices" vs "dinner",
"August" vs "afternoon") tell them apart, and single-word synonymy has no
access to arguments. Consequence: the SIGNALS fallback (extraction gating)
may admit ordinary action sentences ("They walked...", "We ate dinner").
That is contained by design — extraction still requires candidate structure
plus opinion/boilerplate filtering, and a verdict still requires retrieved
evidence plus aspect support (absence of evidence yields INSUFFICIENT, never
FALSE). The STANCE path additionally pairs the bridge against the claim's
own predicate, where the surface is tiny and all probed pairs behave.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional, Set, Tuple

from backend.logging_config import logger

_WORDNET_WARNED = False

# Loud, greppable production message shared by the startup self-check and the
# lazy degraded path. Deliberately ERROR-level and explicit about impact and
# remediation: a quiet warning here once shipped a silently degraded deploy.
_WORDNET_MISSING_MSG = (
    "WORDNET CORPORA MISSING OR UNUSABLE. Lexical expansion is degraded to "
    "lemma-only matching: the verb-synonym fallback contributes nothing and "
    "deverbal-noun ACTION detection is disabled, so genuinely related "
    "predicates (e.g. hike/surge) will NOT match. Fix the deploy by ensuring "
    "render-build.sh runs 'python -m nltk.downloader -e -q wordnet omw-1.4' "
    "successfully at build time."
)


@dataclass
class WordNetStatus:
    """Testable result of the WordNet availability self-check."""
    available: bool
    detail: str


def _probe_wordnet() -> int:
    """Return verb-synset count for the probe word; raises if corpus unusable."""
    from nltk.corpus import wordnet as wn
    return len(wn.synsets("test", pos=wn.VERB))


def check_wordnet() -> WordNetStatus:
    """Startup self-check for the NLTK corpora. Loud, testable, never raises.

    Called once at app startup (backend/main.py); returns failure state
    instead of raising so a missing corpus degrades the service loudly
    rather than taking it down.
    """
    try:
        count = _probe_wordnet()
    except Exception as exc:
        logger.error("%s (%s)", _WORDNET_MISSING_MSG, exc)
        return WordNetStatus(False, f"wordnet probe raised: {exc}")
    if count == 0:
        logger.error("%s (probe returned zero synsets)", _WORDNET_MISSING_MSG)
        return WordNetStatus(False, "wordnet probe returned zero synsets")
    logger.info("WordNet corpora available (%d verb synsets for probe word).", count)
    return WordNetStatus(True, f"wordnet OK ({count} probe synsets)")


def _wordnet():
    """Lazily import the NLTK WordNet corpus, degrading gracefully when absent."""
    global _WORDNET_WARNED
    try:
        if _probe_wordnet() == 0:
            raise LookupError("wordnet returned no synsets for probe word")
        from nltk.corpus import wordnet as wn
        return wn
    except (ImportError, LookupError, Exception) as exc:
        if not _WORDNET_WARNED:
            logger.error("%s (%s)", _WORDNET_MISSING_MSG, exc)
            _WORDNET_WARNED = True
        return None


def _spacy_lemma(word: str) -> str:
    """Lemmatize a single word with spaCy; fall back to the raw word."""
    try:
        from backend.claim.entity_extractor import get_nlp
        doc = get_nlp()(word)
        for token in doc:
            if token.text:
                return token.lemma_.lower()
    except Exception:
        pass
    return word.lower()


@lru_cache(maxsize=4096)
def get_verb_lemma_and_synonyms(word: str) -> Tuple[str, Set[str]]:
    """Lemmatize ``word`` and expand it to its verb-sense synonym set.

    Returns (lemma, synonyms) where synonyms holds WordNet verb-sense lemma
    names (underscores normalized to spaces). When the corpus is missing or
    the lookup fails, returns (lemma_or_word, empty set) instead of raising,
    so claim processing never crashes on lexical expansion.
    """
    lemma = _spacy_lemma(word)
    wn = _wordnet()
    if wn is None:
        return lemma, set()
    try:
        synonyms: Set[str] = {lemma}
        # Three most frequent verb senses (see _verb_sets for rationale).
        for synset in list(wn.synsets(lemma, pos=wn.VERB))[:3]:
            for name in synset.lemma_names():
                synonyms.add(name.replace("_", " ").lower())
        return lemma, synonyms
    except (LookupError, Exception) as exc:
        global _WORDNET_WARNED
        if not _WORDNET_WARNED:
            logger.warning("WordNet lookup failed (%s); using lemma only.", exc)
            _WORDNET_WARNED = True
        return lemma, set()


# Ultra-generic verbs excluded from relatedness bridges. Verified against the
# bundled corpus: without these, near-universal hubs ("go", "hit" as a
# hypernym of "walk", "operate" shared by "run"/"drive") bridge unrelated
# predicates. Multi-word members never bridge (phrases like "pass over" are
# equally promiscuous). Never contains static-list verbs as bridge blockers —
# static verbs still match verbatim/lemma equality, which bypasses this list.
GENERIC_VERBS = frozenset({
    "be", "have", "do", "does", "get", "make", "take", "go", "goes",
    "come", "put", "set", "give", "run", "turn", "become", "seem",
    "keep", "leave", "hold", "bring", "flow", "course", "feed",
    "move", "travel", "change", "alter", "modify", "hit", "operate",
    "work", "displace", "locomote", "pull", "express",
    # Empirically-observed spurious bridge hubs (verified against the bundled
    # corpus): "tally"/"score" funnel "walked" to "win"; "show" funnels
    # "smiled" to "confirmed"; "ingest" funnels "ate" to "acquire". Each was
    # observed joining unrelated predicates while no required pair routes
    # through them. They gate intermediate/bridge use only — verbatim and
    # lemma-equality matches bypass this list, so e.g. "show" still matches
    # "showed" and static "hit" still matches directly.
    "tally", "score", "show", "ingest",
})


def _content_verb_lemmas(text: str, nlp=None) -> Set[str]:
    """Lemmas of VERB-tagged tokens (len > 2); empty set without a tagger."""
    try:
        if nlp is None:
            from backend.claim.entity_extractor import get_nlp
            nlp = get_nlp()
        if "tagger" not in getattr(nlp, "pipe_names", []):
            return set()
        doc = nlp(text or "")
        return {t.lemma_.lower() for t in doc if t.pos_ == "VERB" and len(t.lemma_) > 2}
    except Exception:
        return set()


def _word_in_text(word: str, text_lower: str) -> bool:
    return re.search(r"\b" + re.escape(word) + r"\b", text_lower) is not None


def _clean_lemmas(names: Iterable[str]) -> Set[str]:
    """Normalize WordNet lemma names; drop empties and ultra-short tokens."""
    out: Set[str] = set()
    for name in names:
        clean = name.replace("_", " ").lower().strip()
        if clean and (len(clean) > 2 or " " in clean):
            out.add(clean)
    return out


@lru_cache(maxsize=4096)
def _verb_sets(lemma: str) -> Tuple[frozenset, frozenset, frozenset]:
    """(synonyms, hypernyms, hyponyms) for a verb lemma; empty on failure.

    Only the three most frequent verb senses are expanded. WordNet orders
    synsets by frequency, and rare senses ("hit the road" readings of common
    verbs) are the main source of spurious bridges between unrelated
    predicates — this most-frequent-sense cap removes most of them while
    keeping the dominant, intended readings.
    """
    wn = _wordnet()
    if wn is None or not lemma:
        return frozenset(), frozenset(), frozenset()
    synonyms: Set[str] = {lemma}
    hypernyms: Set[str] = set()
    hyponyms: Set[str] = set()
    try:
        for synset in list(wn.synsets(lemma, pos=wn.VERB))[:3]:
            synonyms |= _clean_lemmas(l.name() for l in synset.lemmas())
            for hyper in synset.hypernyms():
                hypernyms |= _clean_lemmas(l.name() for l in hyper.lemmas())
            for hypo in synset.hyponyms():
                hyponyms |= _clean_lemmas(l.name() for l in hypo.lemmas())
    except (LookupError, Exception):
        return frozenset(), frozenset(), frozenset()
    return frozenset(synonyms), frozenset(hypernyms), frozenset(hyponyms)


def _specific_single(members: Set[str]) -> Set[str]:
    """Single-token members minus generic verbs (multi-word never bridges)."""
    return {w for w in members if " " not in w and w not in GENERIC_VERBS}


@lru_cache(maxsize=4096)
def _hypernyms2(lemma: str) -> frozenset:
    """Two-hop hypernyms: hypernyms of hypernyms (single tokens)."""
    _, hyper, _ = _verb_sets(lemma)
    closure: Set[str] = set(_specific_single(hyper))
    for parent in hyper:
        if " " in parent or parent in GENERIC_VERBS:
            continue
        closure |= _specific_single(_verb_sets(parent)[1])
    return frozenset(closure)


def verbs_related(lemma_a: str, lemma_b: str) -> bool:
    """Decide whether two verb lemmas assert a related predicate.

    True on: identical lemmas; synonymy either direction; a direct hypernym
    either direction ("surge" -> "rise"); a shared hypernym ("hike" and
    "surge" meet at "lift"); or a two-hop hypernym link ("plummet" up
    through "drop" to "fall"). Ultra-generic lemmas ("run", "hit", "give")
    match identical lemmas only — their neighborhoods are too polysemous
    to bridge ("run" as motion vs operation, "hit" as strike vs reach).
    Hyponym bridges of any kind are excluded: they connect unrelated
    predicates through high-fanout fringe nodes ("walked" matched static
    verbs; "rain" met "resign").
    """
    if lemma_a == lemma_b:
        return True
    if lemma_a in GENERIC_VERBS or lemma_b in GENERIC_VERBS:
        return False
    syn_a, hyper_a, _ = _verb_sets(lemma_a)
    syn_b, hyper_b, _ = _verb_sets(lemma_b)
    if lemma_a in syn_b or lemma_b in syn_a:
        return True
    if lemma_a in hyper_b or lemma_b in hyper_a:
        return True
    if _specific_single(hyper_a) & _specific_single(hyper_b):
        return True
    closure_a = _hypernyms2(lemma_a) | {lemma_a}
    closure_b = _hypernyms2(lemma_b) | {lemma_b}
    if lemma_b in closure_a or lemma_a in closure_b:
        return True
    return False


def action_matches_evidence(
    claim_lemma: str,
    evidence_text: str,
    nlp=None,
) -> bool:
    """Check a claim predicate lemma against evidence text (fallback matcher).

    Ordered tiers — pure synonym appearance first, then pairwise relatedness:
    1. Claim lemma appears verbatim (word boundary) in the evidence text.
    2. A verb-sense synonym of the claim lemma appears among the evidence's
       lemmatized verbs.
    3. ``verbs_related`` against an evidence verb (synonym, direct/shared
       hypernym, or lemma-targeted two-hop link).
    Ultra-generic claim lemmas ("run", "make") match verbatim only.
    """
    ev_lower = (evidence_text or "").lower()
    if _word_in_text(claim_lemma, ev_lower):
        return True

    ev_verbs = _content_verb_lemmas(evidence_text, nlp)
    if not ev_verbs:
        return False

    _, synonyms = get_verb_lemma_and_synonyms(claim_lemma)
    if synonyms & ev_verbs:
        return True

    if claim_lemma not in GENERIC_VERBS and any(
        verbs_related(claim_lemma, ev_verb) for ev_verb in ev_verbs
    ):
        return True

    for phrase in synonyms - {claim_lemma}:
        if " " in phrase and phrase in ev_lower:
            return True
    return False


def text_has_verb_family_match(text: str, reference_words: Iterable[str]) -> bool:
    """Fallback signal check: does any verb in ``text`` relate to ``reference_words``?

    ``reference_words`` are the static verb lists (surface forms). Each side is
    lemmatized, so conjugations ("surged") match their roots. Matching is
    deliberately asymmetric: the observed text verb expands (synonyms,
    hypernyms, lemma-targeted two-hop), while the reference side contributes
    only lemmas and synonyms. Expanding 150 reference verbs through
    hypernyms is what linked unrelated predicates ("walked" met "win" and
    "correlate" through hub words); the intended side is taken at face value
    instead. Returns False when nothing relates.
    """
    words = re.findall(r"\b[A-Za-z]+\b", text or "")
    if not words:
        return False
    try:
        from backend.claim.entity_extractor import get_nlp
        nlp = get_nlp()
    except Exception:
        return False
    ref_lemmas: Set[str] = set()
    for raw in reference_words:
        lemma, _ = get_verb_lemma_and_synonyms(raw)
        if len(lemma) > 2:
            ref_lemmas.add(lemma)
    if not ref_lemmas:
        return False
    ref_surface: Set[str] = set(ref_lemmas)
    for ref in ref_lemmas:
        _, synonyms = get_verb_lemma_and_synonyms(ref)
        ref_surface |= synonyms
    try:
        doc = nlp(text)
        text_verbs = {t.lemma_.lower() for t in doc if t.pos_ == "VERB" and len(t.lemma_) > 2}
    except Exception:
        return False
    if not text_verbs:
        return False
    if text_verbs & ref_surface:
        return True
    for verb in text_verbs:
        _, synonyms = get_verb_lemma_and_synonyms(verb)
        _, hyper, _ = _verb_sets(verb)
        expansion = {
            w for w in (synonyms | hyper | _hypernyms2(verb))
            if " " not in w and w not in GENERIC_VERBS
        }
        if expansion & ref_surface:
            return True
    return False


def fallback_claim_action(text: str) -> Optional[str]:
    """Derive a predicate lemma for claims the static verb tables miss.

    Prefers the ROOT verb, then a copular subject with verb senses
    ("price hike is ..." -> "hike"), then any verb, then any deverbal noun.
    Returns None when nothing predicate-like exists.
    """
    try:
        from backend.claim.entity_extractor import get_nlp
        nlp = get_nlp()
        if "parser" not in getattr(nlp, "pipe_names", []):
            return None
        doc = nlp(text or "")
    except Exception:
        return None

    def _lemma(token) -> str:
        return token.lemma_.lower()

    roots = [t for t in doc if t.dep_ == "ROOT"]
    root = roots[0] if roots else None
    if root is not None and root.pos_ == "VERB" and len(root.lemma_) > 2:
        return _lemma(root)
    if root is not None and root.pos_ in ("AUX", "VERB"):
        for child in root.children:
            if child.dep_ in ("nsubj", "nsubjpass", "attr") and child.pos_ in ("NOUN", "PROPN"):
                if _has_verb_sense(child.lemma_.lower()):
                    return _lemma(child)
    for token in doc:
        if token.pos_ == "VERB" and len(token.lemma_) > 2:
            return _lemma(token)
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and _has_verb_sense(token.lemma_.lower()):
            return _lemma(token)
    return None


def _has_verb_sense(lemma: str) -> bool:
    """True when WordNet knows verb senses for ``lemma`` (deverbal-noun test)."""
    wn = _wordnet()
    if wn is None or not lemma or len(lemma) <= 2:
        return False
    try:
        return bool(wn.synsets(lemma, pos=wn.VERB))
    except (LookupError, Exception):
        return False
