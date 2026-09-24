import { describe, expect, it } from "vitest";
import { buildPdfExportPayload, generateVerificationPdf } from "@/lib/pdfExport";
import { SAMPLE_RESPONSE } from "@/lib/sampleReport";
import { pdfReportFilename } from "@/lib/reportUtils";
import type { ClaimResult, VerificationReport, VerificationResponse } from "@/lib/types";

function makeResponse(overrides: Partial<VerificationResponse> = {}): VerificationResponse {
  return {
    request_id: "req/unsafe id?",
    processed_at: "2026-09-23T10:00:00+00:00",
    input_type: "text",
    input_summary: {
      title: null,
      publisher: null,
      author: null,
      published_at: null,
      domain: null,
      url: null,
    },
    claims: [],
    overall_score: null,
    overall_classification: "INSUFFICIENT EVIDENCE",
    overall_summary: "Not enough evidence.",
    limitations: [],
    report: null,
    ...overrides,
  };
}

function makeClaim(overrides: Partial<ClaimResult> = {}): ClaimResult {
  return {
    claim_id: "c1",
    claim_text: "Claim text.",
    score: null,
    classification: "INSUFFICIENT EVIDENCE",
    summary: "Summary.",
    supporting_evidence: [],
    contradicting_evidence: [],
    neutral_evidence: [],
    fact_checks: [],
    source_analysis: [],
    duplicate_clusters: [],
    score_breakdown: [],
    verification_gaps: [],
    evidence_reasoning: null,
    independent_source_count: 0,
    total_evidence_count: 0,
    retrieved_evidence: [],
    ...overrides,
  };
}

describe("PDF export payload", () => {
  it("exposes an export action filename from actual report data", () => {
    expect(pdfReportFilename(SAMPLE_RESPONSE)).toBe("verifact-report-demo-report.pdf");
  });

  it("uses the live report object rather than recomputing scores", () => {
    const payload = buildPdfExportPayload(SAMPLE_RESPONSE);
    expect(payload.score).toBe("82 / 100");
    expect(payload.classification).toBe(SAMPLE_RESPONSE.overall_classification);
    expect(payload.summary).toBe(SAMPLE_RESPONSE.overall_summary);
    expect(payload.claims[0].claimText).toBe(SAMPLE_RESPONSE.claims[0].claim_text);
    expect(payload.claims[0].score).toBe("82 / 100");
  });

  it("includes backend citations and does not invent URLs", () => {
    const payload = buildPdfExportPayload(SAMPLE_RESPONSE);
    const urls = payload.citations.map((item) => item.url);
    expect(urls).toEqual([
      "https://example.com/sample/reuters-data",
      "https://example.com/sample/research-archive",
      "https://example.com/sample/factcheck-context",
    ]);
    expect(urls.every((url) => SAMPLE_RESPONSE.report?.citations.some((c) => c.url === url))).toBe(true);
  });

  it("supports insufficient-evidence reports without turning them into false", () => {
    const response = makeResponse();
    const payload = buildPdfExportPayload(response);
    expect(payload.classification).toBe("INSUFFICIENT EVIDENCE");
    expect(payload.score).toBeNull();
    expect(payload.citations).toEqual([]);
  });

  it("supports scored and multi-claim reports", () => {
    const claims = [
      makeClaim({
        claim_id: "c1",
        claim_text: "First claim",
        score: 80,
        classification: "Mostly Supported",
        supporting_evidence: [
          {
            evidence_id: "s1",
            title: "Support title",
            url: "https://news.example/a",
            publisher: "Paper",
            published_at: null,
            snippet: "snippet a",
            stance: "SUPPORTING",
            rationale: "r",
            is_primary_source: false,
            source_reliability: "high",
          },
        ],
      }),
      makeClaim({
        claim_id: "c2",
        claim_text: "Second claim",
        score: 20,
        classification: "Strongly Contradicted",
        contradicting_evidence: [
          {
            evidence_id: "c-ev",
            title: "Contra title",
            url: "https://news.example/b",
            publisher: "Outlet",
            published_at: null,
            snippet: "snippet b",
            stance: "CONTRADICTING",
            rationale: "r",
            is_primary_source: false,
            source_reliability: "medium",
          },
        ],
        fact_checks: [
          {
            fact_check_id: "fc1",
            claim_text: "Second claim",
            verdict: "False",
            rating_label: "False",
            fact_checker: "Checker",
            url: "https://fact.example/c",
            published_at: null,
            explanation: "Rated false by the fact-checker.",
          },
        ],
      }),
    ];
    const response = makeResponse({
      overall_score: 50,
      overall_classification: "Mixed / Uncertain",
      overall_summary: "Mixed evidence across claims.",
      claims,
    });
    const payload = buildPdfExportPayload(response);
    expect(payload.claims).toHaveLength(2);
    expect(payload.claims[0].supporting[0].url).toBe("https://news.example/a");
    expect(payload.claims[1].factChecks[0].rating).toBe("False");
    expect(payload.citations.map((c) => c.url).sort()).toEqual([
      "https://fact.example/c",
      "https://news.example/a",
      "https://news.example/b",
    ]);
  });

  it("never fabricates citation URLs when none exist", () => {
    const payload = buildPdfExportPayload(makeResponse({ claims: [makeClaim()] }));
    expect(payload.citations).toEqual([]);
  });
});

describe("PDF binary", () => {
  it("generates a PDF containing the actual report fields", () => {
    const doc = generateVerificationPdf(SAMPLE_RESPONSE);
    const text = doc.output("arraybuffer");
    const header = new TextDecoder("latin1").decode(text.slice(0, 8));
    expect(header.startsWith("%PDF")).toBe(true);
    const body = new TextDecoder("latin1").decode(text);
    expect(body).toContain("VERIFACT");
    expect(body).toContain("demo-report");
    expect(body).toContain("https://example.com/sample/reuters-data");
  });

  it("keeps report-level methodology and insufficient classification intact", () => {
    const report = {
      ...(SAMPLE_RESPONSE.report as VerificationReport),
      report_id: "insufficient-1",
      overall_result: {
        score: null,
        classification: "INSUFFICIENT EVIDENCE",
        summary: "Not enough independent evidence.",
      },
    };
    const response = makeResponse({
      report,
      overall_classification: "INSUFFICIENT EVIDENCE",
      overall_summary: "Not enough independent evidence.",
    });
    const payload = buildPdfExportPayload(response);
    expect(payload.methodologyVersion).toBe("v1.0");
    expect(payload.classification).toBe("INSUFFICIENT EVIDENCE");
    expect(payload.score).toBeNull();
    const doc = generateVerificationPdf(response);
    expect(doc.getNumberOfPages()).toBeGreaterThan(0);
  });
});
