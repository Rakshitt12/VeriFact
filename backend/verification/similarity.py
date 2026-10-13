"""Deterministic text, title, and n-gram similarity utilities for verification.

Supports token Jaccard similarity, character SequenceMatcher / RapidFuzz ratio,
n-gram overlap, and distinctive phrase matching.
"""

from __future__ import annotations

import difflib
import re
from typing import List, Set, Tuple

# Optional RapidFuzz import with standard library difflib fallback
try:
    from rapidfuzz import fuzz

    def sequence_similarity(s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        return fuzz.ratio(s1, s2) / 100.0

except ImportError:
    def sequence_similarity(s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        return difflib.SequenceMatcher(None, s1, s2).ratio()


_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "that", "which", "who", "whom", "this", "these", "those", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "must", "can", "could",
    "and", "but", "or", "nor", "so", "yet", "as", "if", "into", "through",
    "during", "before", "after", "above", "below", "up", "down", "out", "off",
}


def normalize_text_for_similarity(text: str) -> str:
    """Lowercase and remove non-alphanumeric noise characters."""
    if not text:
        return ""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(clean.split())


def get_words(text: str, remove_stopwords: bool = False) -> List[str]:
    """Tokenize normalized string into words."""
    norm = normalize_text_for_similarity(text)
    words = norm.split()
    if remove_stopwords:
        words = [w for w in words if w not in _STOPWORDS and len(w) > 1]
    return words


def jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Compute token Jaccard similarity between two lists of tokens."""
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return float(intersection) / float(union)


def get_ngrams(words: List[str], n: int = 3) -> Set[Tuple[str, ...]]:
    """Generate n-gram tuples from a word list."""
    if len(words) < n:
        return set()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def ngram_overlap_similarity(text_a: str, text_b: str, n: int = 3) -> float:
    """Compute n-gram Jaccard overlap between two texts."""
    words_a = get_words(text_a, remove_stopwords=False)
    words_b = get_words(text_b, remove_stopwords=False)
    ngrams_a = get_ngrams(words_a, n)
    ngrams_b = get_ngrams(words_b, n)
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection = len(ngrams_a.intersection(ngrams_b))
    union = len(ngrams_a.union(ngrams_b))
    return float(intersection) / float(union)


def compute_title_similarity(title_a: str, title_b: str) -> float:
    """Compute blended title similarity using token Jaccard and sequence matching."""
    norm_a = normalize_text_for_similarity(title_a)
    norm_b = normalize_text_for_similarity(title_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    words_a = get_words(norm_a, remove_stopwords=True)
    words_b = get_words(norm_b, remove_stopwords=True)

    jaccard = jaccard_similarity(words_a, words_b)
    seq = sequence_similarity(norm_a, norm_b)

    # Blend: 60% token overlap + 40% sequence alignment
    return round(0.60 * jaccard + 0.40 * seq, 3)


def compute_content_similarity(text_a: str, text_b: str) -> float:
    """Compute multi-factor content similarity across tokens, tri-grams, and sequence."""
    norm_a = normalize_text_for_similarity(text_a)
    norm_b = normalize_text_for_similarity(text_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    words_a = get_words(norm_a, remove_stopwords=True)
    words_b = get_words(norm_b, remove_stopwords=True)

    token_jaccard = jaccard_similarity(words_a, words_b)
    tri_gram_sim = ngram_overlap_similarity(text_a, text_b, n=3)
    seq = sequence_similarity(norm_a[:500], norm_b[:500])

    # Blended similarity score: token overlap, sequence alignment, and n-gram overlap
    return round(0.45 * token_jaccard + 0.35 * seq + 0.20 * tri_gram_sim, 3)


def extract_distinctive_phrases(text_a: str, text_b: str, min_words: int = 5) -> List[str]:
    """Find shared consecutive word sequences of length >= min_words appearing in both texts."""
    words_a = get_words(text_a, remove_stopwords=False)
    words_b = get_words(text_b, remove_stopwords=False)

    if len(words_a) < min_words or len(words_b) < min_words:
        return []

    # Check 5-grams and 6-grams
    phrases = []
    seen = set()
    for n in (6, 5):
        set_b = get_ngrams(words_b, n)
        for i in range(len(words_a) - n + 1):
            gram = tuple(words_a[i : i + n])
            if gram in set_b:
                phrase = " ".join(gram)
                if phrase not in seen:
                    seen.add(phrase)
                    phrases.append(phrase)
    return phrases[:5]
