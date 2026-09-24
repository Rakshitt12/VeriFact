"""Regression tests: causal-attribution phrases without indicator verbs.

"RAM price hike is due to Artificial intelligence." carries no word from
FACTUAL_INDICATOR_VERBS, so the verb-set check alone misses it. The
phrase-level check in contains_factual_signals() must catch "due to",
"because of", and sibling constructions — while opinion/greeting/boilerplate
filters in is_candidate_sentence() keep firing first.
"""

import pytest

from backend.claim.claim_extractor import extract_claims_from_text
from backend.claim.rules import contains_factual_signals, is_candidate_sentence


@pytest.mark.parametrize("text", [
    "RAM price hike is due to Artificial intelligence.",
    "Prices rose because of increased demand.",
    "The outage was owing to a failed deployment.",
    "Delays were attributed to staff shortages.",
    "The shortfall was blamed on weak exports.",
    "Growth was driven by consumer spending.",
    "Demand was fueled by subsidies.",
    "Rallies were spurred by rate cuts.",
    "The debate was sparked by new data.",
    "The outage stems from a failed update.",
    "The outage stemmed from a failed update.",
    "The loss was a result of poor planning.",
    "Rates are tied to inflation expectations.",
    "Markets fell amid rising tensions.",
    "RAM PRICE HIKE IS DUE TO ARTIFICIAL INTELLIGENCE.",
])
def test_causal_attribution_phrases_are_signals(text):
    assert contains_factual_signals(text) is True, text


@pytest.mark.parametrize("text", [
    "RAM price hike is due to Artificial intelligence.",
    "Prices rose because of increased demand.",
])
def test_causal_attribution_claims_extract_end_to_end(text):
    claims = extract_claims_from_text(text)
    assert len(claims) == 1
    assert claims[0].original_text == text


def test_opinion_filter_still_runs_first():
    # Causal phrase present, but opinion framing must reject it anyway.
    assert is_candidate_sentence("In my opinion, prices rose because of greed.") is False
    assert is_candidate_sentence("I believe the hike is due to manipulation.") is False


@pytest.mark.parametrize("non_claim", [
    "Hello and welcome back to our daily news show.",
    "Click here to subscribe to our daily newsletter for updates.",
    "Sign up for the newsletter to receive regular alerts.",
    "All rights reserved.",
    "Short.",
])
def test_existing_rejections_unaffected(non_claim):
    assert is_candidate_sentence(non_claim) is False, non_claim
