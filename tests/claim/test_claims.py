"""Unit tests for Part 3 - Claim Extraction, Normalization, Entities, Rules, and Importance."""

import pytest
from backend.claim.claim_extractor import (
    calculate_claim_importance,
    check_claim_similarity,
    classify_claim_type,
    extract_claims,
    extract_claims_from_text,
    generate_claim_id,
    split_multi_claim_sentence,
)
from backend.claim.claim_normalizer import normalize_claim_text
from backend.claim.entity_extractor import extract_entities_from_doc, get_nlp
from backend.claim.models import Claim, ClaimImportance, ClaimType
from backend.claim.rules import contains_factual_signals, is_candidate_sentence
from backend.ingestion.models import NormalizedArticle


# =====================================================================
# 1. Basic Extraction Tests
# =====================================================================

def test_extract_single_factual_sentence():
    """Test extracting a single clear factual sentence."""
    text = "The Reserve Bank increased the repo rate to 6.5% on Wednesday."
    claims = extract_claims_from_text(text)
    assert len(claims) == 1
    c = claims[0]
    assert "Reserve Bank" in c.original_text
    assert c.claim_type in (ClaimType.FINANCIAL, ClaimType.STATISTIC)
    assert len(c.numbers) >= 1
    assert "6.5%" in c.numbers


def test_extract_multiple_factual_sentences():
    """Test extracting multiple discrete factual claims across paragraphs."""
    text = (
        "India's population exceeded 1.4 billion people in 2024. "
        "The central government unveiled a ₹5000 subsidy for rooftop solar power. "
        "Commercial banks agreed to lower processing fees."
    )
    claims = extract_claims_from_text(text)
    assert len(claims) >= 2
    claims_text = [c.original_text for c in claims]
    assert any("population" in t for t in claims_text)
    assert any("subsidy" in t or "5000" in t for t in claims_text)


def test_extract_multi_claim_single_sentence():
    """Test coordinate factual clauses joined by 'and' are split into discrete claims."""
    sentence = "The government approved the bill on Monday and the law will take effect in January."
    split = split_multi_claim_sentence(sentence)
    assert len(split) == 2
    assert "approved the bill" in split[0]
    assert "take effect in January" in split[1]


def test_extract_article_with_headline_and_body():
    """Test headline claim extraction combined with article body claims."""
    article = NormalizedArticle(
        source_type="url",
        original_input="https://example.com/news",
        url="https://example.com/news",
        title="India Approves New Semiconductor Manufacturing Plant",
        body=(
            "The Union Cabinet approved a 10 billion dollar incentive program for chipmakers. "
            "Construction will commence in Gujarat next quarter."
        ),
        publisher="Tech Wire",
        author="Sanjay Verma",
        published_at="2026-09-23",
        domain="example.com",
    )
    claims = extract_claims(article)
    assert len(claims) >= 2
    # Verify headline claim was extracted
    headline_claim = next((c for c in claims if c.is_headline_claim), None)
    assert headline_claim is not None
    assert "Semiconductor" in headline_claim.original_text
    assert headline_claim.importance == ClaimImportance.HIGH


# =====================================================================
# 2. Filtering Tests (Non-Claims & Noise)
# =====================================================================

@pytest.mark.parametrize("non_claim_text", [
    "Could India become the world's next technology hub?",
    "Is this the beginning of a new economic era?",
    "What will happen to retail investors next week?",
    "Hello and welcome back to our daily news show.",
    "Click here to subscribe to our daily newsletter for updates.",
    "Sign up for the newsletter to receive regular alerts.",
    "In my opinion, this policy is completely misguided and flawed.",
    "I believe things will probably turn out better soon.",
    "All rights reserved.",
    "Short.",
])
def test_filter_out_non_claims(non_claim_text):
    """Test questions, opinions, ads, greetings, and boilerplate are rejected."""
    assert not is_candidate_sentence(non_claim_text)


def test_empty_or_whitespace_extraction():
    """Test that empty or whitespace-only body yields empty list of claims."""
    assert extract_claims_from_text("") == []
    assert extract_claims_from_text("   \n\t  ") == []


# =====================================================================
# 3. Normalization Tests
# =====================================================================

def test_normalize_claim_abbreviations():
    """Test expansion of common standardized abbreviations."""
    raw = "The RBI announced new guidelines in consultation with MoF and Govt."
    norm = normalize_claim_text(raw)
    assert "Reserve Bank of India" in norm
    assert "Ministry of Finance" in norm
    assert "Government" in norm


def test_normalize_claim_currencies_and_basis_points():
    """Test currency standardization (₹ -> INR, $ -> USD) and basis points to %."""
    raw = "The central bank announced a ₹5000 rebate and cut the rate by 25bps."
    norm = normalize_claim_text(raw)
    assert "5000 INR" in norm
    assert "0.25%" in norm


def test_normalize_claim_whitespace_and_punctuation():
    """Test whitespace compression and punctuation completion."""
    raw = "  The   company    cut   500   jobs  "
    norm = normalize_claim_text(raw)
    assert norm == "The company cut 500 jobs."


# =====================================================================
# 4. Entity Extraction Tests (spaCy + Regex)
# =====================================================================

def test_entity_extraction_types():
    """Test extraction of persons, organizations, locations, dates, currencies, and numbers."""
    nlp = get_nlp()
    doc = nlp("Prime Minister Narendra Modi visited Paris on Friday and announced a €2 billion investment.")
    ents = extract_entities_from_doc(doc)

    assert "Narendra Modi" in ents["persons"] or any("Modi" in p for p in ents["persons"])
    assert "Paris" in ents["locations"]
    assert "Friday" in ents["dates"]
    assert any("2 billion" in n or "€" in n for n in ents["numbers"])


def test_indian_entities_and_rupees():
    """Test Indian currency notation, crore/lakh numbers, and regional organizations."""
    nlp = get_nlp()
    doc = nlp("State Bank of India approved ₹10,000 crore in infrastructure bonds across Maharashtra.")
    ents = extract_entities_from_doc(doc)

    assert any("State Bank" in org for org in ents["organizations"]) or len(ents["organizations"]) >= 1
    assert any("Maharashtra" in loc for loc in ents["locations"])
    assert any("10,000" in n or "crore" in n or "₹" in n for n in ents["numbers"])


# =====================================================================
# 5. Quotes and Attribution Tests
# =====================================================================

def test_extract_attributed_quote():
    """Test attributed statements extract speaker and statement cleanly."""
    text = "Governor Das stated that inflation had fallen to 4.2% in August."
    claims = extract_claims_from_text(text)
    assert len(claims) >= 1
    c = claims[0]
    assert c.attribution is not None
    assert "Governor Das" in c.attribution.speaker
    assert c.attribution.attribution_verb.lower() == "stated"
    assert "inflation had fallen to 4.2%" in c.original_text


# =====================================================================
# 6. Duplicate and Similar Claims Grouping
# =====================================================================

def test_duplicate_claims_grouping():
    """Test that two differently phrased sentences expressing the same underlying claim are grouped."""
    text = (
        "The tech company announced layoffs affecting 500 employees on Tuesday. "
        "The tech company said it would cut 500 employees on Tuesday."
    )
    claims = extract_claims_from_text(text)
    # The second sentence should be detected as equivalent and merged into equivalent_claims of the primary
    assert len(claims) == 1
    primary = claims[0]
    assert len(primary.equivalent_claims) >= 1
    assert "500 employees" in primary.original_text


# =====================================================================
# 7. Importance and Category Assignment
# =====================================================================

def test_claim_importance_assignment():
    """Test that headline and early high-density factual claims receive HIGH importance."""
    headline_imp = calculate_claim_importance(
        is_headline=True,
        sentence_idx=0,
        entities={"numbers": ["10"], "organizations": ["Govt"]},
        claim_type=ClaimType.POLICY,
    )
    assert headline_imp == ClaimImportance.HIGH

    minor_detail_imp = calculate_claim_importance(
        is_headline=False,
        sentence_idx=8,
        entities={},
        claim_type=ClaimType.OTHER,
    )
    assert minor_detail_imp == ClaimImportance.LOW


def test_classify_claim_types():
    """Test claim classification logic."""
    assert classify_claim_type("The RBI raised repo rate to 6.5%", {"numbers": ["6.5%"]}, False) == ClaimType.FINANCIAL
    assert classify_claim_type("Parliament approved the telecom bill", {}, False) == ClaimType.POLICY
    assert classify_claim_type("Scientists published a study on climate change", {}, False) == ClaimType.SCIENTIFIC
    assert classify_claim_type("He said that rates were too high", {}, True) == ClaimType.QUOTE


# =====================================================================
# 8. Deterministic Claim ID Stability
# =====================================================================

def test_stable_claim_ids():
    """Test that identical claim text yields the exact same deterministic ID."""
    text = "The government announced a ₹10 reduction in petrol prices."
    id1 = generate_claim_id(text, 1)
    id2 = generate_claim_id(text, 1)
    assert id1 == id2
    assert id1.startswith("claim_")
