"""Unit tests for text, title, and n-gram similarity utilities."""

from backend.verification.similarity import (
    compute_content_similarity,
    compute_title_similarity,
    extract_distinctive_phrases,
    jaccard_similarity,
    ngram_overlap_similarity,
    normalize_text_for_similarity,
)


def test_normalize_text_for_similarity():
    """Verify punctuation removal and lowercasing."""
    raw = "Breaking News: Government Approves ₹10,000 Cr Plan!"
    normalized = normalize_text_for_similarity(raw)
    assert "breaking news" in normalized
    assert "₹" not in normalized
    assert ":" not in normalized
    assert "!" not in normalized


def test_jaccard_similarity_tokens():
    """Verify token Jaccard similarity across identical, partial, and disjoint sets."""
    tokens_a = ["government", "approves", "semiconductor", "subsidy"]
    tokens_b = ["government", "approves", "semiconductor", "subsidy"]
    assert jaccard_similarity(tokens_a, tokens_b) == 1.0

    tokens_c = ["rbi", "raises", "interest", "rates"]
    assert jaccard_similarity(tokens_a, tokens_c) == 0.0

    tokens_d = ["government", "announces", "semiconductor", "scheme"]
    sim = jaccard_similarity(tokens_a, tokens_d)
    assert 0.3 < sim < 0.8


def test_ngram_overlap_similarity():
    """Verify tri-gram overlap between related texts."""
    text_a = "The government approved a new semiconductor manufacturing facility in Gujarat."
    text_b = "The government approved a new semiconductor manufacturing plant in Gujarat today."
    overlap = ngram_overlap_similarity(text_a, text_b, n=3)
    assert overlap > 0.40


def test_compute_title_similarity():
    """Verify blended title similarity."""
    t1 = "Cabinet approves ₹10000 crore semiconductor incentive scheme"
    t2 = "Cabinet approves 10000 crore semiconductor scheme"
    sim = compute_title_similarity(t1, t2)
    assert sim >= 0.80

    t3 = "Stock market closes lower amid global tensions"
    low_sim = compute_title_similarity(t1, t3)
    assert low_sim < 0.20


def test_compute_content_similarity():
    """Verify content similarity across identical and differing paragraphs."""
    c1 = "The Reserve Bank of India has maintained the key repo rate at 6.5% during its MPC meeting."
    c2 = "The Reserve Bank of India decided to hold the key repo rate steady at 6.5% in the MPC meeting."
    sim = compute_content_similarity(c1, c2)
    assert sim >= 0.55


def test_extract_distinctive_phrases():
    """Verify extraction of shared verbatim 5-word or 6-word sequences."""
    text_a = "Officials said that the new manufacturing facility will commence operations in early January."
    text_b = "Sources confirmed that the new manufacturing facility will commence operations in early January next year."
    phrases = extract_distinctive_phrases(text_a, text_b, min_words=5)
    assert len(phrases) >= 1
    assert any("the new manufacturing facility will" in p for p in phrases)

