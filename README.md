# AI-Powered News Credibility & Verification System

> **A transparent, evidence-first news verification backend that retrieves, clusters, and analyzes multi-source evidence to generate explainable credibility assessments — without relying on an LLM's pretrained opinion.**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Core Design Principles](#2-core-design-principles)
3. [What This System Does NOT Do](#3-what-this-system-does-not-do)
4. [Key Concepts & Terminology](#4-key-concepts--terminology)
5. [System Architecture](#5-system-architecture)
6. [Processing Pipeline](#6-processing-pipeline)
7. [Module Reference](#7-module-reference)
   - [api/](#71-api)
   - [ingestion/](#72-ingestion)
   - [claim/](#73-claim)
   - [retrieval/](#74-retrieval)
   - [sources/](#75-sources)
   - [verification/](#76-verification)
   - [scoring/](#77-scoring)
   - [report/](#78-report)
   - [config/](#79-config)
8. [Input Specification](#8-input-specification)
9. [Claim Extraction](#9-claim-extraction)
10. [Evidence Retrieval](#10-evidence-retrieval)
11. [Fact-Check Integration](#11-fact-check-integration)
12. [Source Analysis](#12-source-analysis)
13. [Duplicate & Syndication Detection](#13-duplicate--syndication-detection)
14. [Evidence Classification](#14-evidence-classification)
15. [Credibility Scoring](#15-credibility-scoring)
16. [Result Classification](#16-result-classification)
17. [Explainability & Score Breakdown](#17-explainability--score-breakdown)
18. [Verification Gaps](#18-verification-gaps)
19. [API Reference](#19-api-reference)
20. [Configuration Reference](#20-configuration-reference)
21. [Limitations & Caveats](#21-limitations--caveats)
22. [Development Roadmap](#22-development-roadmap)
23. [Contributing Guidelines](#23-contributing-guidelines)
24. [License](#24-license)

---

## 1. Project Overview

The **AI-Powered News Credibility & Verification System** is a backend service that accepts a news claim (plain text) or a URL to a news article and produces a structured, explainable credibility report.

Unlike a simple "ask-the-AI" approach, this system:

- **Retrieves real, external evidence** before forming any judgment.
- **Separates distinct analytical dimensions**: claim credibility, source reliability, evidence strength, fact-check results, independent source agreement, supporting evidence, contradicting evidence, and missing evidence.
- **Identifies and deduplicates syndicated reporting** so that twenty outlets republishing the same wire story count as one independent source — not twenty.
- **Supports an `INSUFFICIENT EVIDENCE` state**, clearly distinguishing *"we could not find evidence"* from *"evidence says this is false."*
- **Keeps scoring configurable and transparent**, with each point on the credibility scale explained by a concrete reason tied to retrieved evidence.

The LLM (large language model) is used exclusively as a **reasoning and language component** operating over retrieved evidence — never as a primary knowledge oracle for current events.

---

## 2. Core Design Principles

| # | Principle | Implication |
|---|-----------|-------------|
| 1 | **Evidence before AI opinion** | Every factual conclusion must be grounded in retrieved, cited sources. The LLM may reason over evidence but must not substitute its pretrained knowledge for retrieval. |
| 2 | **Modular retrieval layer** | News, web, and fact-check search providers are independently swappable. Adding or removing a provider must not require changes to the verification engine. |
| 3 | **Syndication awareness** | Articles that re-publish the same original report are not independent confirmations. Clustering must occur before counting independent sources. |
| 4 | **Insufficient evidence ≠ false** | When evidence is sparse or absent, the system must explicitly say so. Absence of evidence must never be treated as evidence of absence. |
| 5 | **Source reliability ≠ political leaning** | Political bias and factual accuracy are tracked as separate, independent dimensions. A politically biased source that accurately reports a fact is not penalized for that fact. |
| 6 | **Transparent scoring** | Every point on the credibility scale must map to a specific, human-readable explanation tied to real evidence. |
| 7 | **Caching** | Repeated lookups for the same claim, URL, or domain should be served from cache to reduce latency and API costs. |
| 8 | **Extensibility** | The architecture must allow additional APIs, sources, classifiers, and scoring factors to be added without large-scale refactoring. |

---

## 3. What This System Does NOT Do

- ❌ Ask an LLM "is this news true?" and return its answer.
- ❌ Treat the LLM's internal training data as a source of current facts.
- ❌ Count ten outlets repeating the same wire story as ten independent sources.
- ❌ Equate political bias or ideological leaning with factual unreliability.
- ❌ Return a binary TRUE/FALSE verdict — the system produces a graded, evidence-based assessment.
- ❌ Claim certainty. All outputs carry explicit uncertainty disclosures.
- ❌ Penalize claims simply because they are controversial, political, or recent.

---

## 4. Key Concepts & Terminology

| Term | Definition |
|------|-----------|
| **Claim** | A single, independently verifiable factual statement extracted from the submitted input. |
| **Evidence** | A retrieved article, document, or dataset that relates to a claim. |
| **Fact-check** | An evaluation published by a recognized fact-checking organization that specifically addresses a claim. |
| **Independent source** | A source that reports on a claim using its own original reporting — not a copy, reprint, or minor rewrite of another article. |
| **Source cluster** | A group of articles that are identified as reporting the same original story (i.e., syndicated or copied). |
| **Credibility score** | A 0–100 numerical representation of the strength of available evidence for a claim. |
| **Classification** | A human-readable category derived from the credibility score (e.g., "Mostly Supported"). |
| **Verification gap** | A specific aspect of a claim for which sufficient evidence could not be found. |
| **Primary source** | A government, institutional, or first-party document that directly asserts or denies a fact (e.g., an official press release, legislation, peer-reviewed study). |
| **Score breakdown** | An itemized list of score contributions and deductions, each explained in plain language. |

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT / FRONTEND                           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  POST /api/verify
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          API LAYER (FastAPI)                        │
│   routes.py  ·  schemas.py                                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                              │
│   text_processor.py  ·  url_extractor.py                           │
│                                                                     │
│   • Validates input type (text vs URL)                              │
│   • Extracts full article body, title, author, date, domain        │
│   • Normalizes encoding, strips ads/boilerplate                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        CLAIM LAYER                                  │
│   claim_extractor.py  ·  claim_normalizer.py                       │
│                                                                     │
│   • Breaks input text into individual verifiable claims            │
│   • Normalizes entities, dates, numbers, locations                 │
│   • Deduplicates claims that express the same fact                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  (one pipeline branch per claim)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       RETRIEVAL LAYER                               │
│   news_search.py  ·  web_search.py  ·  factcheck_search.py        │
│                                                                     │
│   • Queries news APIs, web search, and fact-check databases        │
│   • Returns raw evidence documents with metadata                   │
│   • Provider-agnostic interface; providers are plug-in modules     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCES LAYER                                │
│   source_analyzer.py  ·  source_registry.py  ·  source_scoring.py │
│                                                                     │
│   • Looks up source metadata from registry                        │
│   • Identifies primary vs secondary vs aggregator sources         │
│   • Scores each source on reliability (separate from bias)        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     VERIFICATION LAYER                              │
│   evidence_analyzer.py  ·  contradiction_detector.py               │
│   duplicate_detector.py  ·  consensus_analyzer.py                  │
│                                                                     │
│   • Classifies each piece of evidence as SUPPORTING / CONTRA-      │
│     DICTING / NEUTRAL / INSUFFICIENT                               │
│   • Detects and clusters duplicate/syndicated articles             │
│   • Detects explicit contradictions between sources                │
│   • Measures consensus across independent sources                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SCORING LAYER                                │
│   credibility_score.py  ·  score_explanation.py                    │
│                                                                     │
│   • Applies configurable weights to evidence dimensions            │
│   • Produces 0–100 score + itemized breakdown                      │
│   • Detects INSUFFICIENT EVIDENCE state                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        REPORT LAYER                                 │
│   report_generator.py  ·  citation_manager.py                      │
│                                                                     │
│   • Compiles all evidence, scores, and breakdowns into a           │
│     structured JSON response                                       │
│   • Formats citations with URLs, titles, publishers, dates        │
│   • Lists verification gaps and system limitations                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
                      Structured JSON Response
```

---

## 6. Processing Pipeline

The following steps execute sequentially for each verification request:

```
USER INPUT
    │
    ▼
[1] INPUT VALIDATION
    Validate that input is non-empty, well-formed text or a reachable URL.
    Reject clearly invalid requests early.
    │
    ▼
[2] TEXT / URL INGESTION
    • Text input → pass through text_processor.py for cleaning/normalization.
    • URL input  → url_extractor.py fetches and parses the article.
                   Extracts: title, publisher, author, date, body, domain.
    │
    ▼
[3] CLAIM EXTRACTION
    LLM-assisted extraction of individual, independently verifiable claims
    from the input text or article body.
    Each claim is a discrete, atomic factual assertion.
    │
    ▼
[4] CLAIM NORMALIZATION
    Normalize entities (people, organizations, locations), dates, currencies,
    and numbers within each claim for consistent search query construction.
    │
    ▼
[5] NEWS / WEB EVIDENCE RETRIEVAL   ←── runs per claim
    Query news APIs and web search for relevant articles.
    Collect title, snippet, URL, publisher, date, and full body where available.
    │
    ▼
[6] FACT-CHECK RETRIEVAL   ←── runs per claim
    Query fact-check databases (e.g., Google Fact Check Tools API, ClaimBuster,
    Snopes, PolitiFact feeds, Full Fact, AFP Fact Check) for existing evaluations.
    Collect verdict, publisher, URL, and explanation.
    │
    ▼
[7] SOURCE CREDIBILITY ANALYSIS   ←── runs per retrieved article
    Look up each source domain in source_registry.
    Assign reliability score, transparency signals, type classification.
    Identify likely primary sources.
    │
    ▼
[8] DUPLICATE / SYNDICATION DETECTION
    Compare retrieved articles for textual similarity.
    Cluster near-duplicates into source clusters.
    Identify the earliest/most likely original report within each cluster.
    Count only unique cluster origins as independent sources.
    │
    ▼
[9] EVIDENCE CLASSIFICATION
    For each unique, non-duplicated article, classify its stance relative to
    the claim: SUPPORTING / CONTRADICTING / NEUTRAL / INSUFFICIENT.
    │
    ▼
[10] EVIDENCE SYNTHESIS
    Aggregate classified evidence across all claims.
    Measure agreement, contradiction, and source independence.
    │
    ▼
[11] CREDIBILITY SCORING
    Apply configurable weights to evidence dimensions.
    Compute 0–100 score. Detect INSUFFICIENT EVIDENCE state.
    │
    ▼
[12] EXPLAINABLE REPORT GENERATION
    Produce itemized score breakdown.
    Identify verification gaps.
    Compile citations and source analysis.
    │
    ▼
[13] FRONTEND RESPONSE
    Return structured JSON to the API caller.
```

---

## 7. Module Reference

### 7.1 `api/`

#### `api/routes.py`

Defines all HTTP endpoints using **FastAPI**.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/verify` | `POST` | Main verification endpoint. Accepts text or URL, returns full verification report. |
| `/api/health` | `GET` | Health check. Returns service status. |
| `/api/config` | `GET` | Returns current (non-sensitive) scoring configuration. |

- Handles request deserialization using `schemas.py`.
- Delegates processing to the pipeline orchestrator in `main.py`.
- Returns structured JSON conforming to the response schema.

#### `api/schemas.py`

Pydantic models for request and response validation.

**Key models:**
- `VerificationRequest` — input payload (text or URL + optional metadata).
- `VerificationResponse` — full structured report (see [Section 19](#19-api-reference)).
- `ClaimResult` — per-claim evidence summary.
- `EvidenceItem` — a single retrieved evidence article.
- `FactCheckItem` — a single fact-check result.
- `SourceAnalysis` — per-source metadata and reliability score.
- `DuplicateCluster` — a grouped set of syndicated articles.
- `ScoreBreakdown` — itemized scoring contributions.
- `VerificationGap` — a specific missing piece of evidence.

---

### 7.2 `ingestion/`

#### `ingestion/text_processor.py`

Handles plain-text input submitted directly by the user.

**Responsibilities:**
- Strip leading/trailing whitespace and normalize Unicode.
- Detect and handle non-English text (flag for future translation support).
- Estimate rough word count and reject inputs below a minimum threshold.
- Return a normalized string ready for claim extraction.

#### `ingestion/url_extractor.py`

Fetches and parses a news article from a submitted URL.

**Responsibilities:**
- Send an HTTP GET request with browser-like headers to avoid bot-blocking.
- Use `newspaper3k`, `trafilatura`, or a similar library to extract the main article body, stripping navigation, ads, and boilerplate.
- Extract metadata: `title`, `author`, `publish_date`, `publisher`, `domain`, `url`.
- Fall back to `og:` meta tags and JSON-LD structured data when the parser fails.
- Handle paywalled or inaccessible URLs gracefully with a clear error signal.
- Cache extracted articles by URL to avoid re-fetching within a session window.

---

### 7.3 `claim/`

#### `claim/claim_extractor.py`

Breaks an article or text input into individual, independently verifiable factual claims.

**Approach:**
- Uses the LLM with a structured prompt that instructs it to extract *only* concrete, verifiable factual assertions — not opinions, interpretations, or predictions.
- Each extracted claim is returned as a self-contained sentence (context-complete).
- Assigns a `claim_id` to each extracted claim for downstream tracking.

**Example:**

| Input | Extracted Claims |
|-------|-----------------|
| "The RBI cut interest rates by 0.25% on Monday, affecting home loan EMIs." | 1. "The RBI cut interest rates by 0.25%." 2. "The rate cut was announced on Monday." 3. "The rate cut will affect home loan EMIs." |

**Important constraints:**
- The LLM must be instructed *not* to judge whether the claims are true — only to extract them.
- Subjective statements and editorializing must be excluded from extracted claims.

#### `claim/claim_normalizer.py`

Normalizes claims to improve retrieval accuracy.

**Responsibilities:**
- Expand abbreviations (e.g., "RBI" → "Reserve Bank of India").
- Standardize date formats.
- Normalize currency notations.
- Resolve co-references (e.g., "it," "they," "the organization").
- Generate one or more search-ready query strings per claim.

---

### 7.4 `retrieval/`

The retrieval layer is the most critical external-facing component. All providers must implement a **common interface** so that swapping providers requires no changes to the verification engine.

**Provider Interface (conceptual):**

```python
class BaseProvider:
    def search(self, query: str, max_results: int) -> list[RawEvidenceDocument]:
        ...
```

Each `RawEvidenceDocument` must include:
- `url`
- `title`
- `snippet` (short excerpt)
- `body` (full text if available)
- `publisher`
- `domain`
- `published_at` (datetime or None)
- `provider` (the retrieval provider that found it)

#### `retrieval/news_search.py`

Queries news search APIs.

**Potential providers (configurable):**
- [NewsAPI.org](https://newsapi.org/)
- [GDELT Project](https://www.gdeltproject.org/)
- [MediaStack](https://mediastack.com/)
- [The GDELT News API](https://api.gdeltproject.org/api/v2/doc/doc)
- [Bing News Search API](https://www.microsoft.com/en-us/bing/apis/bing-news-search-api)

**Behavior:**
- Accepts a normalized claim query string.
- Returns a list of `RawEvidenceDocument` objects sorted by date (newest first).
- Respects configurable `max_results_per_provider` limits.
- Merges and deduplicates results across multiple providers.

#### `retrieval/web_search.py`

Queries general web search for broader evidence, including government sites, institutional documents, and primary sources.

**Potential providers (configurable):**
- [Google Custom Search JSON API](https://developers.google.com/custom-search/v1/introduction)
- [Brave Search API](https://api.search.brave.com/)
- [SerpAPI](https://serpapi.com/)
- [Tavily](https://tavily.com/)

**Behavior:**
- Prioritizes official domains (`.gov`, `.edu`, `.org`, `.int`) where possible.
- Optionally applies domain-allowlisting to reduce low-quality results.
- Returns `RawEvidenceDocument` list.

#### `retrieval/factcheck_search.py`

Queries fact-check-specific sources and databases.

**Potential providers (configurable):**
- [Google Fact Check Tools API](https://developers.google.com/fact-check/tools/api) — searches across many fact-checkers simultaneously.
- [ClaimBuster API](https://idir.uta.edu/claimbuster/) — claim detection and search.
- Direct RSS/feed parsers for: Snopes, PolitiFact, Full Fact, AFP Fact Check, Boom Live, Alt News, The Quint Webqoof.

**Behavior:**
- Returns `FactCheckDocument` objects (distinct from `RawEvidenceDocument`).
- Each `FactCheckDocument` includes: `claim_text`, `verdict`, `rating_label`, `fact_checker`, `url`, `published_at`, `explanation`.
- Fact-checks are treated as a **separate evidence category**, never merged with ordinary news coverage.

---

### 7.5 `sources/`

#### `sources/source_registry.py`

A domain-indexed database of source metadata.

**Data stored per domain:**
- `name` — human-readable publisher name.
- `domain` — base domain (e.g., `reuters.com`).
- `type` — one of: `major_news`, `regional_news`, `government`, `institution`, `academic`, `fact_checker`, `aggregator`, `social_media`, `unknown`.
- `country` — country of origin.
- `reliability_tier` — `high` / `medium` / `low` / `unknown`.
- `transparency_score` — numerical 0–10 rating of editorial transparency.
- `is_primary_source_candidate` — boolean, whether this domain typically publishes primary documents.
- `notes` — free-text annotation.

**Important design notes:**
- Political leaning/bias is **not stored** as a reliability factor. It is a separate, optional metadata field.
- Reliability tier reflects historical accuracy and editorial standards, not political alignment.
- The registry is a YAML or JSON file (not hardcoded in Python) so it can be updated without code changes.

#### `sources/source_analyzer.py`

Analyzes each retrieved article's source.

**Responsibilities:**
- Look up the article's domain in `source_registry`.
- Detect signals that suggest the article is a copy/reprint (e.g., "Originally published by...", matching agency bylines like AP/Reuters/AFP).
- Detect signals of primary-source status (official press release language, `.gov` domain, institutional authorship).
- Flag sources not found in the registry as `UNKNOWN` — do not assume reliability.

#### `sources/source_scoring.py`

Converts source metadata into a numerical reliability contribution for the credibility score.

**Scoring factors:**
- Registry reliability tier.
- Transparency score.
- Whether the source appears to be a primary source.
- Whether the source is identified as an aggregator or copy.
- Domain age and HTTPS usage as lightweight heuristics.

---

### 7.6 `verification/`

#### `verification/evidence_analyzer.py`

For each retrieved, non-duplicate article, classifies its stance relative to the claim.

**Classification labels:**

| Label | Meaning |
|-------|---------|
| `SUPPORTING` | The article explicitly confirms or strongly corroborates the claim. |
| `CONTRADICTING` | The article explicitly denies, refutes, or contradicts the claim. |
| `NEUTRAL` | The article is topically related but takes no clear stance on the claim. |
| `INSUFFICIENT` | The article does not provide enough information to classify. |

**Classification approach:**
- A structured LLM prompt receives the claim + the article snippet/body and returns a classification with a brief rationale.
- The LLM is given explicit instructions to classify *only* based on what the article says — not its pretrained knowledge.
- Extracted numbers, dates, entities, and quotes from the article are used to ground the classification.

#### `verification/contradiction_detector.py`

Identifies explicit contradictions between sources.

**Responsibilities:**
- Compare supporting and contradicting evidence to surface the most significant conflicts.
- Detect numerical discrepancies (e.g., "₹10 reduction" vs "₹15 reduction").
- Detect date conflicts.
- Summarize each contradiction for inclusion in the report.

#### `verification/duplicate_detector.py`

Detects and clusters syndicated or near-duplicate articles.

**Approach:**
- Compute semantic similarity between article bodies/snippets (e.g., using sentence embeddings + cosine similarity).
- Apply a configurable similarity threshold (default: `0.85`) to group articles into clusters.
- Within each cluster, identify the most likely original source (typically the earliest publication date and the highest-reliability source).
- Only the **original source** within each cluster counts as an independent confirmation.

**Why this matters:**
> When a major wire service like Reuters or AP breaks a story, dozens of outlets republish it verbatim or with minor edits. Without deduplication, a system could incorrectly interpret 30 outlets as 30 independent sources. This module prevents that inflation.

#### `verification/consensus_analyzer.py`

Aggregates the output of all verification sub-modules.

**Responsibilities:**
- Count independent supporting sources (after deduplication).
- Count independent contradicting sources (after deduplication).
- Detect the `INSUFFICIENT_EVIDENCE` state:
  - Fewer than N independent sources found (configurable threshold).
  - Retrieved articles are mostly `NEUTRAL` or `INSUFFICIENT`.
  - No fact-check results found.
- Compute an agreement ratio across independent sources.
- Summarize the overall evidence picture for the scoring layer.

---

### 7.7 `scoring/`

#### `scoring/credibility_score.py`

Applies configurable weights to evidence dimensions to produce the final 0–100 credibility score.

**Scoring dimensions and default weights:**

| Dimension | Default Weight | Description |
|-----------|---------------|-------------|
| `evidence_agreement` | 25% | Ratio of supporting to total classified evidence across independent sources. |
| `source_quality` | 15% | Weighted average reliability of supporting independent sources. |
| `independent_sources` | 20% | Number of independent (non-duplicate) supporting sources, scaled. |
| `fact_checks` | 15% | Fact-check results: positive verdicts boost, negative verdicts penalize. |
| `official_evidence` | 20% | Presence of primary/official source confirmation. |
| `transparency` | 5% | Transparency signals of the submitted article/source. |

- All weights are defined in `config/scoring_config.py` and can be changed without modifying this module.
- The module detects `INSUFFICIENT_EVIDENCE` when total independent source count falls below a configurable minimum (default: 2).
- In `INSUFFICIENT_EVIDENCE` state, the score is returned as `null` and the classification is overridden to `"INSUFFICIENT EVIDENCE"`.

#### `scoring/score_explanation.py`

Generates the human-readable `score_breakdown` list.

**Format of each breakdown item:**

```json
{
  "factor": "independent_sources",
  "label": "Multiple independent reputable sources",
  "contribution": +18,
  "detail": "3 independent sources (Reuters, BBC, AP) corroborate the main claim."
}
```

- Positive contributions are scored with `+` values.
- Negative contributions (contradicting evidence, low-quality sources, etc.) use `−` values.
- The breakdown items are sorted by absolute magnitude (largest impact first).

---

### 7.8 `report/`

#### `report/report_generator.py`

Compiles all module outputs into the final structured report.

**Responsibilities:**
- Assemble: claim text, score, classification, summary, supporting/contradicting evidence, fact-checks, source analysis, duplicate clusters, score breakdown, verification gaps, and limitations.
- Generate a plain-language summary paragraph that describes the overall evidence picture (LLM-assisted, grounded in retrieved evidence only).
- Ensure every evidence item has a citation.

#### `report/citation_manager.py`

Manages citations and ensures every evidence item is traceable.

**Responsibilities:**
- Assign a citation ID to every evidence document and fact-check.
- Store: `url`, `title`, `publisher`, `author`, `published_at`, `retrieved_at`.
- Generate a deduplicated, sorted citations list for the final response.
- Flag broken or inaccessible URLs.

---

### 7.9 `config/`

#### `config/scoring_config.py`

The single source of truth for all configurable parameters.

**Configuration categories:**

```python
# --- Scoring weights (must sum to 1.0) ---
SCORING_WEIGHTS = {
    "evidence_agreement": 0.25,
    "source_quality": 0.15,
    "independent_sources": 0.20,
    "fact_checks": 0.15,
    "official_evidence": 0.20,
    "transparency": 0.05,
}

# --- Classification thresholds ---
CLASSIFICATION_THRESHOLDS = {
    "strongly_supported": 90,
    "mostly_supported": 75,
    "mixed_uncertain": 50,
    "weakly_supported": 25,
    # below 25 → "Strongly Contradicted"
}

# --- Insufficient evidence detection ---
MIN_INDEPENDENT_SOURCES = 2
MIN_CLASSIFIED_EVIDENCE_ITEMS = 2

# --- Duplicate detection ---
DUPLICATE_SIMILARITY_THRESHOLD = 0.85

# --- Retrieval limits ---
MAX_RESULTS_PER_NEWS_PROVIDER = 10
MAX_RESULTS_PER_WEB_PROVIDER = 10
MAX_FACTCHECK_RESULTS = 5

# --- Caching ---
CACHE_TTL_SECONDS = 3600
```

---

## 8. Input Specification

### Text Input

A user-submitted string containing one or more factual claims.

```json
{
  "input_type": "text",
  "content": "India has introduced a new law banning all cryptocurrency transactions."
}
```

**Constraints:**
- Minimum length: 20 characters.
- Maximum length: 10,000 characters (configurable).
- Must contain at least one verifiable factual assertion.

### URL Input

A URL pointing to a publicly accessible news article.

```json
{
  "input_type": "url",
  "content": "https://example.com/news/article-title"
}
```

**Extracted article metadata (attempted):**

| Field | Source Priority |
|-------|----------------|
| `title` | `<title>` tag → `og:title` → `<h1>` |
| `author` | JSON-LD → `<meta name="author">` → byline heuristics |
| `published_at` | JSON-LD → `<meta property="article:published_time">` → date heuristics |
| `publisher` | `og:site_name` → domain name |
| `body` | Trafilatura / Newspaper3k main content extraction |
| `domain` | Parsed from URL |
| `url` | Original submitted URL (canonical if available) |

---

## 9. Claim Extraction

The system uses a structured LLM prompt to extract discrete, independently verifiable factual claims.

**Extraction rules (enforced via prompt):**
1. Only extract concrete factual assertions — not opinions, predictions, or interpretations.
2. Each claim must be self-contained (contain all necessary context).
3. Each claim must be independently searchable.
4. Duplicate claims (same fact expressed differently) must be merged.
5. Very broad or vague statements that cannot be independently verified should be flagged but still passed through.

**Example:**

```
Input text:
"The central government announced a ₹10 reduction in petrol prices effective
October 1, 2024. The decision follows a decline in global crude oil prices.
The opposition party criticized the decision as insufficient."

Extracted claims:
1. The central government announced a ₹10 reduction in petrol prices.
2. The petrol price reduction will take effect on October 1, 2024.
3. Global crude oil prices have declined recently.
[Note: "The opposition party criticized the decision" is an opinion and is excluded.]
```

---

## 10. Evidence Retrieval

For each normalized claim, the retrieval layer executes parallel searches across configured providers.

**Search query construction:**
- The normalized claim text is used as the primary query.
- Entity-focused variants may be generated (e.g., querying specific organizations or numbers mentioned).
- Date-bounded queries may be added when a publication date is known.

**Evidence metadata collected per item:**

| Field | Description |
|-------|-------------|
| `url` | Article URL |
| `title` | Article headline |
| `snippet` | Short excerpt from article |
| `body` | Full article text (when available) |
| `publisher` | Publication name |
| `domain` | Domain of the URL |
| `published_at` | Publication date/time |
| `retrieved_at` | When the system fetched this item |
| `provider` | Which retrieval provider returned this |
| `is_fact_check` | Boolean |

**Coverage categories targeted:**
- Major international and national news organizations.
- Regional and local outlets (for geographic specificity).
- Government websites and official press releases.
- Institutional and organizational publications.
- Academic and research publications.
- Fact-checking organizations.
- Public primary source documents.

---

## 11. Fact-Check Integration

Fact-checks are retrieved separately from general news and displayed as their own evidence category.

**Why separate?**
Fact-checks represent an expert's pre-existing evaluation of a claim. They carry more informational weight than ordinary news coverage and must be reported transparently, including when they conflict with each other.

**Fact-check result schema:**

```json
{
  "fact_check_id": "fc_001",
  "claim_text": "...",
  "verdict": "False",
  "rating_label": "False",
  "fact_checker": "PolitiFact",
  "url": "https://www.politifact.com/...",
  "published_at": "2024-09-10",
  "explanation": "...",
  "claim_id": "claim_001"
}
```

**Positive verdicts** (e.g., "True", "Mostly True", "Confirmed") boost the credibility score.  
**Negative verdicts** (e.g., "False", "Misleading", "Pants on Fire") reduce the score.  
**Ambiguous verdicts** (e.g., "Mixture", "Unverified") are noted but do not strongly move the score.

---

## 12. Source Analysis

Every retrieved article is analyzed for source quality **independently of its stance** on the claim.

**Source reliability signals:**

| Signal | Description |
|--------|-------------|
| Registry tier | Pre-assessed reliability tier from the source registry. |
| Transparency score | Editorial standards, corrections policy, author attribution. |
| Domain type | `.gov`, `.edu`, `.org`, `.com` — as a weak heuristic only. |
| HTTPS | Whether the site uses HTTPS. |
| Author attribution | Whether the article credits a named author. |
| Date presence | Whether a publication date is present. |
| Agency syndication | Whether the article is syndicated from AP/Reuters/AFP. |
| Primary source signals | Official press release language, institutional authorship. |

**Important:** Political leaning is tracked as a separate optional metadata field and is **never used** as a direct input to the reliability score.

---

## 13. Duplicate & Syndication Detection

Wire service stories (AP, Reuters, AFP, PTI, ANI, etc.) are routinely republished verbatim or near-verbatim by hundreds of outlets. Without detection, this inflates the apparent independent source count.

**Detection pipeline:**

1. Generate text embeddings for each retrieved article's body/snippet.
2. Compute pairwise cosine similarity across all articles retrieved for a claim.
3. Group articles above the similarity threshold (`DUPLICATE_SIMILARITY_THRESHOLD = 0.85` by default) into clusters.
4. Within each cluster:
   - Identify the original source (earliest publication date + highest-reliability source).
   - Mark all others as `DUPLICATE` with a reference to the cluster's origin.
5. When counting independent sources, only cluster origins are counted.

**Cluster output example:**

```json
{
  "cluster_id": "cluster_001",
  "origin": {
    "url": "https://www.reuters.com/article/...",
    "publisher": "Reuters",
    "published_at": "2024-09-22T08:00:00Z"
  },
  "duplicates": [
    {"url": "https://www.hindustantimes.com/...", "publisher": "Hindustan Times"},
    {"url": "https://www.ndtv.com/...", "publisher": "NDTV"}
  ],
  "cluster_size": 3,
  "counted_as_independent": 1
}
```

---

## 14. Evidence Classification

Each non-duplicate evidence article is classified relative to each claim.

**Classification prompt contract with LLM:**
- Input: `[claim text]` + `[article title + snippet/body]`
- Task: "Based only on what this article says — not your own knowledge — does this article support, contradict, or neither support nor contradict the following claim?"
- Output: `SUPPORTING` | `CONTRADICTING` | `NEUTRAL` | `INSUFFICIENT` + brief rationale.

**Grounding rules enforced in the prompt:**
- The LLM must reference specific text from the article in its rationale.
- The LLM must not use its pretrained knowledge to supplement gaps in the article.
- Numerical discrepancies must be flagged explicitly.

---

## 15. Credibility Scoring

The credibility score is a **0–100 integer** representing the strength of available evidence.

> ⚠️ **Important:** The score is NOT a probability that the claim is true. It is a measure of how strongly the retrieved evidence, across independent sources, supports or contradicts the claim.

### Scoring formula (conceptual)

```
score = sum(weight[dimension] * raw_score[dimension]) for each dimension
      × 100
```

Each dimension's raw score is normalized to [0, 1] before weighting.

### Dimension calculations

| Dimension | Calculation |
|-----------|------------|
| `evidence_agreement` | `supporting_independent / (supporting_independent + contradicting_independent)` |
| `source_quality` | Weighted average reliability score of supporting independent sources. |
| `independent_sources` | `min(independent_supporting_count / SCALE_FACTOR, 1.0)` |
| `fact_checks` | Weighted positive/negative verdicts from fact-checks. |
| `official_evidence` | 1.0 if a primary/official source supports the claim; 0.0 otherwise. Partial credit for primary-source neutrality. |
| `transparency` | Transparency signals of the submitted article (author present, date present, publisher identifiable). |

### INSUFFICIENT EVIDENCE state

Triggered when:
- Total independent classified evidence count < `MIN_INDEPENDENT_SOURCES` (default: 2), **or**
- Fewer than `MIN_CLASSIFIED_EVIDENCE_ITEMS` items are classified as SUPPORTING or CONTRADICTING.

In this state:
- `score` is returned as `null`.
- `classification` is set to `"INSUFFICIENT EVIDENCE"`.
- The score breakdown explains why evidence was insufficient.

---

## 16. Result Classification

| Score Range | Classification |
|-------------|---------------|
| 90–100 | ✅ Strongly Supported |
| 75–89 | 🟢 Mostly Supported |
| 50–74 | 🟡 Mixed / Uncertain |
| 25–49 | 🟠 Weakly Supported |
| 0–24 | 🔴 Strongly Contradicted |
| N/A | ⬜ Insufficient Evidence |

All thresholds are defined in `config/scoring_config.py` and can be adjusted.

---

## 17. Explainability & Score Breakdown

Every score must be explained. The `score_breakdown` field contains one item per scoring factor.

**Example breakdown:**

```json
"score_breakdown": [
  {
    "factor": "independent_sources",
    "label": "Multiple independent reputable sources support the claim",
    "contribution": +18,
    "detail": "Reuters, BBC, and The Hindu independently reported the petrol price reduction of ₹10."
  },
  {
    "factor": "official_evidence",
    "label": "Official government source confirms a key detail",
    "contribution": +15,
    "detail": "The Ministry of Petroleum's official press release confirms the price change."
  },
  {
    "factor": "fact_checks",
    "label": "Existing fact-check supports the claim",
    "contribution": +12,
    "detail": "Boom Live fact-check (2024-09-21) rated the claim 'True'."
  },
  {
    "factor": "evidence_agreement",
    "label": "One credible source reports a conflicting figure",
    "contribution": -8,
    "detail": "The Financial Express reports a ₹8 reduction, not ₹10."
  },
  {
    "factor": "transparency",
    "label": "Submitted article lacks author attribution",
    "contribution": -5,
    "detail": "The submitted article does not credit a named author."
  }
]
```

---

## 18. Verification Gaps

The report includes a `verification_gaps` list that transparently communicates what could not be verified.

**Example gap types:**

```json
"verification_gaps": [
  {
    "gap_type": "no_official_source",
    "description": "No official government or institutional source was found to independently confirm this claim."
  },
  {
    "gap_type": "low_independent_source_count",
    "description": "Only 2 independent sources were found. More independent reporting would increase confidence."
  },
  {
    "gap_type": "no_fact_check",
    "description": "No existing fact-check for this claim was found in available databases."
  },
  {
    "gap_type": "original_source_unclear",
    "description": "The original source of this report could not be identified. All retrieved articles may be secondary."
  },
  {
    "gap_type": "source_disagreement",
    "description": "Sources disagree on a key numerical detail (₹8 vs ₹10 price reduction)."
  },
  {
    "gap_type": "article_no_date",
    "description": "The submitted article does not include a publication date."
  },
  {
    "gap_type": "article_no_author",
    "description": "The submitted article does not include author information."
  }
]
```

---

## 19. API Reference

### `POST /api/verify`

**Request body:**

```json
{
  "input_type": "text" | "url",
  "content": "string"
}
```

**Response body (200 OK):**

```json
{
  "request_id": "uuid",
  "processed_at": "ISO-8601 datetime",
  "input_type": "text" | "url",
  "input_summary": {
    "title": "string | null",
    "publisher": "string | null",
    "author": "string | null",
    "published_at": "string | null",
    "domain": "string | null",
    "url": "string | null"
  },
  "claims": [
    {
      "claim_id": "claim_001",
      "claim_text": "string",
      "score": 82,
      "classification": "Mostly Supported",
      "summary": "string",
      "supporting_evidence": [
        {
          "evidence_id": "ev_001",
          "title": "string",
          "url": "string",
          "publisher": "string",
          "published_at": "string | null",
          "snippet": "string",
          "stance": "SUPPORTING",
          "rationale": "string",
          "is_primary_source": false,
          "source_reliability": "high"
        }
      ],
      "contradicting_evidence": [],
      "neutral_evidence": [],
      "fact_checks": [
        {
          "fact_check_id": "fc_001",
          "claim_text": "string",
          "verdict": "True",
          "rating_label": "True",
          "fact_checker": "Boom Live",
          "url": "string",
          "published_at": "string",
          "explanation": "string"
        }
      ],
      "source_analysis": [
        {
          "domain": "reuters.com",
          "publisher": "Reuters",
          "reliability_tier": "high",
          "transparency_score": 9,
          "type": "major_news",
          "is_primary_source": false,
          "is_duplicate": false,
          "cluster_id": "cluster_001 | null"
        }
      ],
      "duplicate_clusters": [
        {
          "cluster_id": "cluster_001",
          "origin": {},
          "duplicates": [],
          "cluster_size": 3,
          "counted_as_independent": 1
        }
      ],
      "score_breakdown": [],
      "verification_gaps": [],
      "independent_source_count": 3,
      "total_evidence_count": 8
    }
  ],
  "overall_score": 82,
  "overall_classification": "Mostly Supported",
  "overall_summary": "string",
  "limitations": [
    "This system cannot access paywalled content.",
    "Evidence retrieval is limited to sources indexed by configured providers.",
    "The credibility score represents evidence strength, not a guaranteed truth determination."
  ]
}
```

**Error responses:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_INPUT` | Input is malformed, too short, or unsupported format. |
| 422 | `NO_CLAIMS_EXTRACTED` | No verifiable claims could be extracted from the input. |
| 503 | `RETRIEVAL_UNAVAILABLE` | All retrieval providers are currently unavailable. |
| 504 | `TIMEOUT` | Processing exceeded the configured timeout. |

---

## 20. Configuration Reference

All tunable parameters reside in `config/scoring_config.py`. The `GET /api/config` endpoint exposes non-sensitive configuration values.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SCORING_WEIGHTS` | See above | Per-dimension score weights (must sum to 1.0). |
| `CLASSIFICATION_THRESHOLDS` | See above | Score boundaries for each classification label. |
| `MIN_INDEPENDENT_SOURCES` | `2` | Minimum independent sources before `INSUFFICIENT_EVIDENCE` is declared. |
| `DUPLICATE_SIMILARITY_THRESHOLD` | `0.85` | Cosine similarity above which two articles are considered duplicates. |
| `MAX_RESULTS_PER_NEWS_PROVIDER` | `10` | Max articles fetched per news provider per claim. |
| `MAX_RESULTS_PER_WEB_PROVIDER` | `10` | Max articles fetched per web search provider per claim. |
| `MAX_FACTCHECK_RESULTS` | `5` | Max fact-check results per claim. |
| `CACHE_TTL_SECONDS` | `3600` | Time-to-live for cached search results and article extractions. |
| `MAX_INPUT_LENGTH` | `10000` | Maximum characters accepted in a text input. |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Maximum time for a single verification request. |

---

## 21. Limitations & Caveats

The system is designed to be honest about what it cannot do.

1. **Paywalled content:** The system cannot access articles behind paywalls. It will note when retrieved evidence appears to be truncated.

2. **Real-time events:** The system is bounded by the coverage of its retrieval providers. Very recent events (last few hours) may have limited coverage.

3. **Non-English content:** Initial implementation targets English-language content. Non-English claims may produce degraded results.

4. **Dark web / private communication:** The system cannot access private or unlisted sources.

5. **Deepfake / multimedia claims:** The system does not analyze images, audio, or video. Claims about visual content are processed as text only.

6. **Score is not a probability:** A score of 80 does not mean there is an 80% chance the claim is true. It means the retrieved evidence is broadly supportive, subject to the system's retrieval and analysis limitations.

7. **Provider dependency:** The system's quality is directly tied to the quality and coverage of its configured retrieval providers.

8. **LLM classification errors:** The evidence classification step uses an LLM and can make errors, particularly on ambiguous, nuanced, or culturally specific text.

9. **Source registry coverage:** Domains not in the source registry are treated as `UNKNOWN` reliability — neither trusted nor distrusted.

10. **Syndication detection limits:** Very heavily rewritten articles may not be caught by the similarity-based duplicate detector.

---

## 22. Development Roadmap

### Phase 1 — Core Backend (MVP)
- [ ] FastAPI project scaffold and schema definitions.
- [ ] URL extraction with `trafilatura` / `newspaper3k`.
- [ ] Text ingestion and normalization.
- [ ] LLM-based claim extraction (OpenAI / Gemini).
- [ ] NewsAPI + Google Custom Search integration.
- [ ] Google Fact Check Tools API integration.
- [ ] Basic source registry (50+ major domains).
- [ ] Evidence classification via LLM.
- [ ] Basic duplicate detection (TF-IDF cosine similarity).
- [ ] Credibility scoring with configurable weights.
- [ ] Score explanation generation.
- [ ] Verification gaps generation.
- [ ] Structured JSON API response.

### Phase 2 — Retrieval Expansion
- [ ] Add GDELT as a news provider.
- [ ] Add Brave/Tavily web search providers.
- [ ] Add additional fact-checker feeds (Snopes, PolitiFact, Full Fact, AFP, Alt News, Boom Live).
- [ ] Implement caching layer (Redis or in-memory).
- [ ] Expand source registry to 500+ domains.
- [ ] Add ClaimBuster for claim check-worthiness scoring.

### Phase 3 — Analysis Improvements
- [ ] Sentence-embedding-based duplicate detection (replace TF-IDF).
- [ ] Structured entity extraction to improve claim normalization.
- [ ] Date and number normalization in claims.
- [ ] Primary-source detection heuristics.
- [ ] Author credibility signals.

### Phase 4 — Frontend Integration
- [ ] REST API documentation (OpenAPI / Swagger UI).
- [ ] React or Next.js frontend.
- [ ] Real-time progress updates via WebSocket or SSE.
- [ ] Per-claim drill-down UI.
- [ ] Interactive score breakdown visualization.
- [ ] Citation hover-cards with article previews.

### Phase 5 — Scale & Reliability
- [ ] Async pipeline with Celery or native `asyncio`.
- [ ] Rate limiting and request queuing.
- [ ] Provider failover: if Provider A is unavailable, automatically fall back to Provider B.
- [ ] Monitoring and alerting (Prometheus / Grafana).
- [ ] Structured logging (ELK stack or similar).

### Phase 6 — Advanced Features
- [ ] Multilingual support (claim translation before retrieval).
- [ ] Claim-level user feedback loop (thumbs up/down on evidence classification).
- [ ] Historical claim database: cache past verifications for trending claims.
- [ ] Browser extension integration.
- [ ] Webhook support for batch processing.

---

## 23. Contributing Guidelines

> _To be expanded once the project moves to open contribution._

**Branch naming:**
- `feature/short-description`
- `fix/short-description`
- `docs/short-description`

**Code standards:**
- Python 3.11+.
- Type hints on all public functions.
- Docstrings on all public classes and functions.
- `ruff` for linting; `black` for formatting.
- Unit tests required for all new modules (`pytest`).

**Pull request requirements:**
- All existing tests must pass.
- New features must include unit tests.
- Configuration changes must be reflected in `config/scoring_config.py` and documented in this README.
- Do not hardcode weights, thresholds, or provider keys in module code.

---

## 24. License

_To be determined._

---

> **Note to AI coding agents:** This README is the authoritative project specification. When implementing any module, verify your implementation decisions against the design principles in [Section 2](#2-core-design-principles) and the module responsibilities in [Section 7](#7-module-reference). Never implement the LLM as a direct truth oracle for current events — it is a reasoning component over retrieved evidence only. All configurable parameters must live in `config/scoring_config.py`, not scattered through module code.
