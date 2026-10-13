# Part 10 — Verification Reports Completion Report

> **Part 10 does not independently verify claims or recalculate credibility.
> It presents and explains the structured results produced by Parts 3–9.**

---

## 1. Report architecture

```text
backend/report/
├── __init__.py            # Side-effect-free exports (ReportGenerator, VerificationReportService)
├── models.py              # Pydantic report schema (VerificationReport + cards)
├── report_generator.py    # Orchestrator: Parts 3–9 outputs -> VerificationReport
├── evidence_formatter.py  # Stance routing, fact-check/discrepancy/source/independence/score cards
├── summary_generator.py   # Deterministic templates (claim + executive summaries)
├── citation_manager.py    # Whitelist-validated, deduplicated citation registry
└── service.py             # VerificationReportService facade used by the API layer
```

Pipeline position: Scoring (Part 9) -> **Report (Part 10)** -> Frontend (Part 11).
`backend/api/routes.py` (`POST /api/analyze`, `POST /api/verify`) collects
per-claim pipeline artefacts, calls `VerificationReportService.generate_report(...)`,
and returns it as `VerificationResponse.report` alongside all pre-existing fields.

## 2. Report schema

`VerificationReport`: `report_id` (UUID4), `generated_at` (tz-aware UTC ISO-8601),
`methodology_version` (carried from `SCORING_METHODOLOGY_VERSION`, currently `v1.0`),
`input_summary`, `overall_result`, `executive_summary`, `claims[]`,
`evidence_summary`, `citations[]`, `limitations[]`.
Fully JSON-serializable via `model_dump()` / `model_validate()`.

## 3. Claim-level structure

Each `ClaimVerificationReport` carries: `claim_id`, `claim_text`, `claim_type`,
`importance` (HIGH/MEDIUM/LOW, preserved from Part 3), `score`, `classification`,
`is_insufficient_evidence`, `summary`, `evidence_summary`, supporting /
contradicting / neutral / insufficient evidence cards, `fact_checks`,
`discrepancies`, `verification_gaps`, `source_analysis`, `independence_analysis`,
`score_breakdown`, `ai_reasoning`, `limitations`.
Claims are ordered deterministically: HIGH importance first, then MEDIUM, then
LOW; original extraction order breaks ties within a tier.

## 4. Evidence presentation

`EvidenceCard` exposes only pre-existing fields (`evidence_id`, `title`,
`publisher`, `url`, `publication_date`, `snippet`, `stance`, `relevance`,
`cluster_id`, `independence_status`, `source_category`, `source_reliability`);
missing values become `null`, never invented. Stance routing comes verbatim from
Part 7; within each stance, cards sort by relevance desc, then `evidence_id`.
Display order for consumers: relevant -> supporting -> contradicting ->
fact-checks -> neutral. `EvidenceSummary` keeps `total_retrieved` strictly
separate from `independent_source_count`.

## 5. Source presentation

`SourceAnalysisCard` surfaces Part 5 observables (`publisher`, `domain`,
`source_category`, `reliability_label`, `reliability_score`, `transparency`,
`metadata_quality`, `attribution_signal`, `primary_reporting_signal`,
`limitations`). Descriptive only — never a ranking. The methodology/limitations
text states explicitly: source reliability describes observable source
characteristics; claim credibility describes evidence strength for the specific
claim; high reliability does not make a claim true.

## 6. Independence presentation

`IndependenceSummary` re-exports Part 6 (`independent_source_count`,
`cluster_count`, `syndication_clusters`, `duplicate_clusters`,
`independence_limitations`, per-cluster cards with type/member
count/representative). Syndication clusters carry an explicit caveat so the UI
can state: N syndicated articles = 1 independent confirmation. Part 10 never
recalculates independence.

## 7. Fact-check presentation

`FactCheckCard` preserves `fact_check_id`, `publisher`, `title`, `url`,
`review_date`, **both** `original_rating` (verbatim publisher wording, e.g.
"Mostly False") and `normalized_rating`, plus `stance`/`explanation`. Ratings
are never rewritten; fact-checks are not presented as infallible.

## 8. Discrepancy presentation

`DiscrepancyCard` mirrors Part 7 (`type` NUMERIC/TEMPORAL/POLARITY/ENTITY/STATUS,
`description`, `claim_value`, `evidence_value`, `evidence_ids`, `severity`).

## 9. Score presentation

`overall_result` and per-claim `score`/`classification` are copied exactly from
Part 9 (`None` + `INSUFFICIENT EVIDENCE` preserved; never manufactured).
Display rule: `Credibility Score: 78/100`, or `Not available` when `None`.
Never rendered as a probability ("78% true"). `ScoreBreakdownReport` lists every
component (`factor`, `label`, `raw_score`, `weight`, `weighted_contribution`,
`explanation`, `evidence_ids`) and every penalty (`penalty_type`, `amount`,
`explanation`, `evidence_ids`).

## 10. Citation management

`CitationManager` keeps a whitelist of evidence URLs/IDs, rejects fabricated
URLs (`add_citation` returns `False` and logs a warning), and deduplicates by
`evidence_id` so multi-section references yield one record. Distinct records on
the same domain are never merged. Source URLs are preserved verbatim for
clickable frontend titles.

## 11. AI reasoning presentation

`AIReasoningReport` carries the Part 8 synthesis (summary, supporting /
contradicting findings, discrepancies, source/independence/fact-check
observations, gaps, uncertainty, limitations) plus provenance (`ai_used`,
`fallback_used`, `provider`, `model`). The report states AI reasoning
summarizes retrieved evidence and does not determine the score; fallback usage
is disclosed (`AI model unavailable; deterministic evidence reasoning was used.`)
and repeated in claim limitations. No chain-of-thought or secrets are exposed.

## 12. Verification gaps

Gaps surface verbatim from Part 8 (e.g. missing primary document, single-source
numeric assertion, unresolved date). Never invented.

## 13. Limitations

Document + claim limitations are grounded in the actual result (insufficient
corroboration, AI fallback, paywall/retrieval bounds, score-is-evidence-strength
disclaimer). No generic disclaimer wall.

## 14. API response structure

`VerificationResponse` gains one optional field — `report` (a serialized
`VerificationReport`; typed `Any` to avoid a runtime circular import, validated
by the report test-suite). All pre-existing fields are untouched. Example:

```json
{
  "request_id": "...",
  "overall_score": 76,
  "overall_classification": "Mostly Supported",
  "report": {
    "report_id": "...",
    "generated_at": "2026-09-23T00:00:00+00:00",
    "methodology_version": "v1.0",
    "input_summary": {"input_type": "text", "claim_count": 1, "...": "..."},
    "overall_result": {"score": 76, "classification": "Mostly Supported", "summary": "..."},
    "executive_summary": "...",
    "claims": [],
    "evidence_summary": {"total_retrieved": 5, "independent_source_count": 2, "...": "..."},
    "citations": [],
    "limitations": []
  }
}
```

---

## Compatibility fixes (minimal, Part 10 only unless noted)

1. `backend/api/__init__.py` — removed eager `from backend.api.routes import router`
   (side-effect-free package init). Importing `backend.api.schemas` no longer
   pulls in routes/scoring/report, eliminating import-order-dependent cycles.
   No caller used `from backend.api import router` (verified by grep); all
   imports go via `backend.api.routes` / `backend.main`.
2. `backend/report/models.py` — local `ScoreContribution` model instead of
   importing `backend.api.schemas` at runtime (identical fields).
3. `backend/report/summary_generator.py` — local classification string constants
   instead of importing `ClassificationLabel` at runtime.
4. `backend/report/evidence_formatter.py` — converts `api.schemas`
   `ScoreContribution` instances to the report-local class when building
   `ScoreBreakdownReport`.
5. `backend/api/schemas.py` — `VerificationResponse.report: Optional[Any]`
   (was an unresolvable `TYPE_CHECKING`-only `VerificationReport` reference).

---

## Test results

`py -3.14 -m pytest -q` — **271 passed, 3 warnings, 0 failures** (~53 s).

| Suite | Count |
|---|---|
| Foundation (`tests/test_foundation.py`) | 8 |
| Ingestion | 38 |
| Claim | 25 |
| Retrieval | 40 |
| Source | 33 |
| Verification | 52 |
| AI | 23 |
| Scoring | 26 |
| Reporting (`tests/report/`, new Part 10) | 26 |
| **Total** | **271** |
| Warnings | 3 (pre-existing: httpx/starlette deprecations, HTTP_422 alias) |
| Failures | 0 |

All 25 required Part 10 behaviors are covered (model validation, optional-field
tolerance, citation integrity/fabrication/dedup, stance routing x3,
insufficient-evidence, score/classification/breakdown/penalty preservation,
syndication honesty, fact-check ratings, discrepancies, gaps, AI fallback,
multi-claim, ordering, empty evidence, hallucination guard, timestamp,
methodology version, API integration), plus summary-determinism and
serialization tests.
