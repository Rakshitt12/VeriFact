"""Regression tests: short/causal factual claims must not be silently discarded.

"Vaccines cause autism." is a complete 3-word SVO assertion and must survive
candidate filtering and extraction, while greetings, fragments, boilerplate,
opinions, and unverifiable statives ("He is happy.") must still be rejected.
"""

from backend.claim.claim_extractor import extract_claims_from_text
from backend.claim.rules import (
    contains_factual_signals,
    has_subject_verb_structure,
    is_candidate_sentence,
)


def test_three_word_svo_has_subject_verb_structure():
    assert has_subject_verb_structure("Vaccines cause autism.") is True
    assert has_subject_verb_structure("Smoking causes cancer.") is True
    # Verbless fragment has no subject-verb structure.
    assert has_subject_verb_structure("What a day!") is False


def test_three_word_causal_claims_are_candidates():
    assert is_candidate_sentence("Vaccines cause autism.") is True
    assert is_candidate_sentence("Smoking causes cancer.") is True


def test_causal_verbs_are_factual_signals():
    assert contains_factual_signals("Vaccines cause autism.") is True
    assert contains_factual_signals("Smoking causes cancer.") is True


def test_short_causal_claims_extract_end_to_end():
    claims = extract_claims_from_text("Vaccines cause autism.")
    assert len(claims) == 1
    assert claims[0].original_text == "Vaccines cause autism."
    claims = extract_claims_from_text("Smoking causes cancer.")
    assert len(claims) == 1


def test_stative_verifiable_property_is_signal():
    text = "The Great Wall of China is visible from space."
    assert is_candidate_sentence(text) is True
    assert contains_factual_signals(text) is True
    assert len(extract_claims_from_text(text)) == 1


def test_short_non_claims_still_rejected():
    for non_claim in [
        "Short.",
        "All rights reserved.",
        "Hello and welcome back to our daily news show.",
        "Click here to subscribe to our daily newsletter for updates.",
        "What a day!",
        "In my opinion, this policy is completely misguided and flawed.",
    ]:
        assert is_candidate_sentence(non_claim) is False, non_claim


def test_unverifiable_stative_never_extracted():
    # Structurally complete but no verifiable signal: must not become a claim.
    assert contains_factual_signals("He is happy.") is False
    assert extract_claims_from_text("He is happy.") == []
