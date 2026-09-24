"""Regression tests: lemma + synonym generalization (not verb-list additions).

"RAM price hike" + "memory prices surged" must connect without "surge"
appearing in any static list; skyrocket/plummet/soar must generalize the
same way. Static-list behavior for already-covered verbs must be identical
(the full suite proves it; the ordering test below pins the mechanism).
"""

from backend.claim.models import Claim, ClaimType
from backend.claim.rules import (
    ATTRIBUTION_VERBS,
    FACTUAL_INDICATOR_VERBS,
    contains_factual_signals,
)
from backend.retrieval.models import Evidence, SourceType
from backend.verification.lexical_expansion import (
    fallback_claim_action,
    get_verb_lemma_and_synonyms,
)
from backend.verification.models import AspectType, EvidenceStance
from backend.verification.stance_detector import (
    _ACTION_AFFIRMATIONS,
    _extract_claim_aspects,
    classify_evidence_stance,
)


def _claim(text: str, **kwargs) -> Claim:
    return Claim(
        claim_id="cl_lex",
        original_text=text,
        normalized_text=text,
        claim_type=ClaimType.OTHER,
        source_sentence=text,
        **kwargs,
    )


def _evidence(text: str, evidence_id: str = "ev_lex") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        claim_id="cl_lex",
        title=text,
        url="https://example.com/lex",
        snippet=text,
        source_type=SourceType.NEWS,
        provider="gdelt",
        query_used="lexical test",
    )


def test_module_api_lemmatizes_and_expands():
    lemma, synonyms = get_verb_lemma_and_synonyms("surged")
    assert lemma == "surge"
    assert "soar" in synonyms  # shared synset soar.v.01


def test_module_api_degrades_gracefully_on_unknown_word():
    lemma, synonyms = get_verb_lemma_and_synonyms("xyzzy")
    assert lemma == "xyzzy"
    assert isinstance(synonyms, set)  # no crash, no expansion


def test_new_verbs_not_in_static_lists():
    """Generalization proof must not smuggle words into the static lists."""
    for verb in ["surge", "surged", "skyrocket", "skyrocketed", "plummet",
                 "plummeted", "soar", "soared", "hike"]:
        assert verb not in FACTUAL_INDICATOR_VERBS, verb
        assert verb not in ATTRIBUTION_VERBS, verb
    assert "hike" not in _ACTION_AFFIRMATIONS
    for variants in _ACTION_AFFIRMATIONS.values():
        assert "surge" not in variants
        assert "hike" not in variants


def test_ram_hike_matches_surged_evidence():
    """Headline case: hike (claim) <-> surge (evidence) via hypernym lift."""
    claim = _claim(
        "RAM price hike is due to Artificial intelligence.",
        organizations=["Artificial Intelligence"],
    )
    assert fallback_claim_action(claim.normalized_text) == "hike"
    comp = classify_evidence_stance(
        claim,
        _evidence("RAM prices surged as Artificial intelligence demand grew."),
    )
    assert comp.stance == EvidenceStance.SUPPORTING


def test_skyrocket_matches_rise():
    claim = _claim(
        "Steel prices skyrocketed in March.",
        dates=["March"],
        numbers=[],
    )
    comp = classify_evidence_stance(
        claim, _evidence("Steel prices rose sharply in March.")
    )
    assert comp.stance == EvidenceStance.SUPPORTING


def test_plummet_matches_fall():
    claim = _claim("Oil prices plummeted yesterday.", numbers=[])
    comp = classify_evidence_stance(
        claim, _evidence("Oil prices fell sharply.", evidence_id="ev_plum")
    )
    assert comp.stance == EvidenceStance.SUPPORTING


def test_soar_matches_surge():
    claim = _claim("Stocks soared on Monday.", dates=["Monday"])
    comp = classify_evidence_stance(
        claim, _evidence("Stocks surged on Monday.", evidence_id="ev_soar")
    )
    assert comp.stance == EvidenceStance.SUPPORTING


def test_static_table_still_wins_first_pass():
    """Covered verbs keep the exact static ACTION base (fallback untouched)."""
    aspects = _extract_claim_aspects(
        _claim("The ministry announced new guidelines.")
    )
    action_aspects = [v for t, v in aspects if t == AspectType.ACTION]
    assert action_aspects == ["announce"]


def test_fallback_action_none_without_predicate():
    assert fallback_claim_action("He is happy.") is None
    assert fallback_claim_action("What a day!") is None


def test_unlisted_verbs_signal_without_static_membership():
    for text in [
        "Memory prices surged.",
        "Steel prices skyrocketed in March.",
        "Oil prices plummeted yesterday.",
        "Stocks soared on Monday.",
    ]:
        assert contains_factual_signals(text) is True, text
