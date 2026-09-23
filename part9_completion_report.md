# Part 9 — Credibility Scoring Engine Completion Report

---

## 1. Executive Summary

**Part 9: Credibility Scoring Engine** is complete and fully integrated into the **AI-Powered News Credibility & Verification System**.

The engine adheres strictly to the core architectural principles:
> **"Deterministic, explainable, configurable, and reproducible."**
- **No LLM scoring**: Credibility scores are strictly derived from structured evidence signals produced by Parts 3–8 using transparent arithmetic formulas. An LLM is never permitted to guess or output a numerical credibility score.
- **Evidence strength, NOT truth probability**: The 0–100 score reflects the strength, diversity, and consistency of retrieved evidence, not an ontological certainty of absolute truth.
- **Cluster-aware & syndication-safe**: Prevents syndicated wire reprints or duplicate articles from inflating the independent confirmation count.
- **Explicit Insufficient Evidence State**: Returns `score = None` and `classification = "INSUFFICIENT EVIDENCE"` whenever independent source clusters < 2 or decisive evidence items < 2.

All **245 tests** (219 existing from Parts 1–8 + 26 new Part 9 tests) pass with a **100% success rate** in ~50 seconds.

---

## 2. Key Modules Implemented

```text
backend/scoring/
├── __init__.py                # Package facade and public exports
├── models.py                  # Pydantic data models (ScoreFactor, ScoreComponent, ScorePenalty,
│                              # ClaimCredibilityScore, DocumentCredibilityScore)
├── component_calculator.py    # Normalized [0.0, 1.0] evaluation across the 6 scoring dimensions
├── penalties.py               # Grounded deductions (discrepancies, reputable refutations, unindexed sources)
├── score_explanation.py       # Transparent ranking of signed ScoreContribution items and summaries
├── credibility_score.py       # Orchestrator computing raw weighted score, subtracting penalties,
│                              # enforcing insufficient evidence, and classifying into 0-100 scale
└── service.py                 # High-level service facade for claim-level and multi-claim document scoring
```

---

## 3. Architecture & Functional Capabilities

### A. Dimensional Component Scoring (`component_calculator.py`)
Implements the 6 dimensions defined in `backend/config/scoring_config.py` totaling a weight of 1.00:
1. **Evidence Agreement (30%)**:
   - Computes ratio of independent supporting clusters to total decisive (supporting + contradicting) clusters.
   - Neutral/contextual-only fallback returns a neutral 0.5 baseline.
2. **Source Quality (20%)**:
   - Computes the average source reliability heuristic score (0–100) across all supporting publisher sources.
3. **Independent Sources (20%)**:
   - Measures distinct independent source clusters corroborating the claim against target threshold (`INDEPENDENT_SOURCES_TARGET = 3`).
4. **Fact-Checks (15%)**:
   - Maps verified fact-checker ratings: True/Supporting = 1.0, False/Contradicting = 0.0, Mixed/Neutral = 0.5.
   - Neutral baseline (0.5) when no fact-checks exist in verified databases.
5. **Official / Primary Evidence (10%)**:
   - Direct confirmation by government, regulatory, academic, or international organization = 1.0.
   - Firsthand primary journalistic reporting = 0.8.
   - Secondary reporting = 0.0.
6. **Source Transparency (5%)**:
   - Evaluates metadata completeness (disclosures of publisher, author, timestamp, canonical URL).

### B. Grounded Penalty Deductions (`penalties.py`)
Transparent, explainable point deductions applied to the raw weighted score:
- **Discrepancy Penalties**:
  - `CRITICAL` discrepancy (e.g. numeric difference > 20% or opposite polarity/temporal claims): **-20.0 points**
  - `MAJOR` discrepancy (e.g. numeric difference 5–20% or timeframe mismatch): **-10.0 points**
  - Deduplication across identical aspect keys prevents compounding penalties on repeated citations of the same conflict.
- **Reputable Source / Fact-Check Refutations**:
  - Direct contradiction by verified fact-checker (e.g. rated "False" or "Pants on Fire") or authoritative institutional source: **-25.0 points**
- **Anonymous / Low-Transparency Sources**:
  - Supporting evidence originating exclusively from anonymous, unindexed, or low-reliability sources: **-10.0 points**

### C. Insufficient Evidence Detection (`credibility_score.py`)
Enforces strict epistemic honesty:
- When `independent_source_count < MIN_INDEPENDENT_SOURCES` (2) OR `(supporting + contradicting) < MIN_CLASSIFIED_EVIDENCE_ITEMS` (2):
  - Returns `score = None`
  - Returns `classification = "INSUFFICIENT EVIDENCE"`
  - Sets `is_insufficient_evidence = True`
  - Generates diagnostic limitations highlighting the corroboration gap.

### D. Score Classification
For verifiable claims, final score is clamped to `[0, 100]` and mapped deterministically to:
- **90 – 100**: `"Strongly Supported"`
- **75 – 89**: `"Mostly Supported"`
- **50 – 74**: `"Mixed / Uncertain"`
- **25 – 49**: `"Weakly Supported"`
- **0 – 24**: `"Strongly Contradicted"`

### E. Multi-Claim Document Aggregation (`service.py`)
- Aggregates per-claim credibility scores across an article or document.
- Applies importance weighting based on claim priority (`HIGH` = 1.0, `MEDIUM` = 0.7, `LOW` = 0.4).
- Ignores claims with insufficient evidence in weighted average calculation.
- Produces document-level `overall_score`, `overall_classification`, and multi-claim synthesis `summary`.

---

## 4. API Route Integration (`backend/api/routes.py`)

Integrated seamlessly into `/api/analyze` and `/api/verify`:
- **Per-Claim**:
  - `ClaimResult.score`: Final integer 0–100 (or `None` if insufficient evidence)
  - `ClaimResult.classification`: Standard classification label string
  - `ClaimResult.score_breakdown`: List of `ScoreContribution` items (factor, label, contribution, detail) sorted by absolute impact descending
- **Per-Document**:
  - `VerificationResponse.overall_score`: Document-level score
  - `VerificationResponse.overall_classification`: Document classification label
  - `VerificationResponse.overall_summary`: Grounded multi-claim synthesis
  - `VerificationResponse.limitations`: Methodological caveats

---

## 5. Verification & Test Results

The test suite was executed via `py -3.14 -m pytest`:

```text
====================== 245 passed, 3 warnings in 50.89s =======================
```

---

## 6. Pipeline Progression

```text
User Input
   ↓
Part 2 — Ingestion                    [COMPLETE]
   ↓
Part 3 — Claim Extraction             [COMPLETE]
   ↓
Part 4 — Evidence Retrieval           [COMPLETE]
   ↓
Part 5 — Source Analysis              [COMPLETE]
   ↓
Part 6 — Duplicate / Independence     [COMPLETE]
   ↓
Part 7 — Evidence Comparison / Stance [COMPLETE]
   ↓
Part 8 — AI Evidence Reasoning        [COMPLETE]
   ↓
Part 9 — Credibility Scoring Engine   [COMPLETE] ✅
   ↓
Part 10 — Report Generation           [NEXT]
   ↓
Frontend
```
