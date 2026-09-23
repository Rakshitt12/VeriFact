import { describe, expect, it } from "vitest";
import {
  allVerificationGaps,
  breakdownRows,
  classificationTone,
  contributionBarWidth,
  evidenceCounts,
  groupClaimEvidence,
  isInsufficientClassification,
  isInsufficientScore,
  reportHeadline,
  scoreDisplay,
  shortReportId,
  verificationGapCount,
} from "@/lib/reportUtils";
import { SAMPLE_RESPONSE } from "@/lib/sampleReport";
import type { ClaimResult, VerificationResponse } from "@/lib/types";

function makeResponse(overrides: Partial<VerificationResponse> = {}): VerificationResponse {
  return {
    request_id: "11111111-2222-3333-4444-555555555555",
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
    score: 76,
    classification: "Mostly Supported",
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

describe("insufficient evidence handling", () => {
  it("detects null scores without converting to zero/false", () => {
    expect(isInsufficientScore(null)).toBe(true);
    expect(isInsufficientScore(undefined)).toBe(true);
    expect(isInsufficientScore(0)).toBe(false);
    expect(scoreDisplay(null)).toBeNull();
    expect(scoreDisplay(82)).toBe("82 / 100");
    expect(scoreDisplay(0)).toBe("0 / 100");
  });

  it("detects the INSUFFICIENT EVIDENCE classification", () => {
    expect(isInsufficientClassification("INSUFFICIENT EVIDENCE")).toBe(true);
    expect(isInsufficientClassification("insufficient evidence")).toBe(true);
    expect(isInsufficientClassification("Mostly Supported")).toBe(false);
  });
});

describe("independent vs retrieved counts (syndication honesty)", () => {
  it("never equates article count with independent confirmations", () => {
    const response = makeResponse({
      overall_score: 70,
      overall_classification: "Mixed / Uncertain",
      claims: [makeClaim({ total_evidence_count: 10, independent_source_count: 2 })],
    });
    const counts = evidenceCounts(response);
    expect(counts.retrieved).toBe(10);
    expect(counts.independent).toBe(2);
  });

  it("prefers report-level evidence summaries when present", () => {
    const counts = evidenceCounts(SAMPLE_RESPONSE);
    expect(counts.retrieved).toBe(3);
    expect(counts.independent).toBe(4);
  });
});

describe("verification gaps", () => {
  it("flattens and deduplicates gaps across claims and report", () => {
    const gaps = allVerificationGaps(SAMPLE_RESPONSE);
    expect(gaps.length).toBeGreaterThan(0);
    expect(new Set(gaps).size).toBe(gaps.length);
    expect(verificationGapCount(SAMPLE_RESPONSE)).toBe(gaps.length);
  });

  it("returns an empty list when no gaps exist", () => {
    expect(allVerificationGaps(makeResponse())).toEqual([]);
  });
});

describe("score breakdown passthrough", () => {
  it("renders backend contributions verbatim", () => {
    const claim = SAMPLE_RESPONSE.claims[0];
    const rows = breakdownRows(claim);
    expect(rows[0]).toEqual({ label: "Evidence agreement", value: 24 });
    expect(rows).toHaveLength(claim.score_breakdown.length);
  });

  it("scales bars without inventing data", () => {
    expect(contributionBarWidth(24, 24)).toBe(100);
    expect(contributionBarWidth(12, 24)).toBe(50);
    expect(contributionBarWidth(5, 0)).toBe(0);
  });
});

describe("classifications and multi-claim", () => {
  it("buckets tones from backend text only", () => {
    expect(classificationTone("Strongly Supported")).toBe("supported");
    expect(classificationTone("Mostly Supported")).toBe("supported");
    expect(classificationTone("Mixed / Uncertain")).toBe("contested");
    expect(classificationTone("Strongly Contradicted")).toBe("contested");
    expect(classificationTone("INSUFFICIENT EVIDENCE")).toBe("insufficient");
  });

  it("supports 1, 3, and many claims without assuming a single claim", () => {
    for (const n of [1, 3, 8]) {
      const claims = Array.from({ length: n }, (_, i) =>
        makeClaim({ claim_id: `c${i}`, claim_text: `Claim ${i}` }),
      );
      const response = makeResponse({
        claims,
        overall_score: 70,
        overall_classification: "Mixed / Uncertain",
      });
      expect(response.claims).toHaveLength(n);
      expect(reportHeadline(response)).toBe("Claim 0");
    }
  });

  it("groups supporting/contradicting/neutral distinctly", () => {
    const claim = makeClaim({
      supporting_evidence: [
        {
          evidence_id: "s1",
          title: "t",
          url: "https://x.example/1",
          publisher: "P",
          published_at: null,
          snippet: "s",
          stance: "SUPPORTING",
          rationale: "r",
          is_primary_source: false,
          source_reliability: "high",
        },
      ],
      contradicting_evidence: [
        {
          evidence_id: "c1",
          title: "t",
          url: "https://x.example/2",
          publisher: "P",
          published_at: null,
          snippet: "s",
          stance: "CONTRADICTING",
          rationale: "r",
          is_primary_source: false,
          source_reliability: "high",
        },
      ],
    });
    const groups = groupClaimEvidence(claim);
    expect(groups.supporting.map((e) => e.evidence_id)).toEqual(["s1"]);
    expect(groups.contradicting.map((e) => e.evidence_id)).toEqual(["c1"]);
    expect(groups.neutral).toEqual([]);
  });
});

describe("report metadata", () => {
  it("shortens request ids deterministically", () => {
    expect(shortReportId("11111111-2222-3333-4444-555555555555")).toBe("VF-1111");
  });

  it("uses the first claim as headline", () => {
    expect(reportHeadline(SAMPLE_RESPONSE)).toContain("urban green spaces");
  });
});
