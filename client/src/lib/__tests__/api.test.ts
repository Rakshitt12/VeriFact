import { describe, expect, it, vi, afterEach } from "vitest";
import {
  analyzeVerification,
  buildVerificationPayload,
  isVerificationResponse,
  validateVerificationInput,
  VerificationApiError,
} from "@/lib/api";

const BASE_RESPONSE = {
  request_id: "req-1",
  processed_at: "2026-09-23T00:00:00+00:00",
  input_type: "text",
  input_summary: {},
  claims: [
    {
      claim_id: "c1",
      claim_text: "The ministry approved a project.",
      score: 76,
      classification: "Mostly Supported",
      summary: "Supported.",
      supporting_evidence: [],
      contradicting_evidence: [],
      neutral_evidence: [],
      fact_checks: [],
      source_analysis: [],
      duplicate_clusters: [],
      score_breakdown: [],
      verification_gaps: [],
      evidence_reasoning: null,
      independent_source_count: 2,
      total_evidence_count: 5,
      retrieved_evidence: [],
    },
  ],
  overall_score: 76,
  overall_classification: "Mostly Supported",
  overall_summary: "Supported overall.",
  limitations: [],
  report: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("input mode mapping (claim/url/text -> backend schema)", () => {
  it("maps claim input to backend text type", () => {
    expect(buildVerificationPayload("claim", "  Some claim text  ")).toEqual({
      input_type: "text",
      content: "Some claim text",
    });
  });

  it("maps url input to backend url type", () => {
    expect(
      buildVerificationPayload("url", "https://example.com/article"),
    ).toEqual({ input_type: "url", content: "https://example.com/article" });
  });

  it("maps article text to backend text type", () => {
    expect(buildVerificationPayload("text", "Long article body here")).toEqual({
      input_type: "text",
      content: "Long article body here",
    });
  });
});

describe("client-side input validation", () => {
  it("rejects empty input", () => {
    expect(validateVerificationInput("claim", "   ")).toMatch(/first/);
  });

  it("rejects malformed urls", () => {
    expect(validateVerificationInput("url", "not a url at all here")).toMatch(/URL/);
  });

  it("rejects non-http protocols", () => {
    expect(validateVerificationInput("url", "ftp://example.com/file")).toMatch(/http/);
  });

  it("rejects inputs below backend minimum length", () => {
    expect(validateVerificationInput("claim", "Too short")).toMatch(/20 characters/);
  });

  it("accepts valid claim, url, and article text", () => {
    expect(
      validateVerificationInput("claim", "The ministry approved a Rs 500 crore project."),
    ).toBeNull();
    expect(
      validateVerificationInput("url", "https://example.com/news/article-title-here"),
    ).toBeNull();
    expect(
      validateVerificationInput("text", "A sufficiently long article body for verification."),
    ).toBeNull();
  });
});

describe("response guard", () => {
  it("accepts a well-formed response", () => {
    expect(isVerificationResponse(BASE_RESPONSE)).toBe(true);
  });

  it("accepts insufficient-evidence responses (null score)", () => {
    expect(
      isVerificationResponse({ ...BASE_RESPONSE, overall_score: null }),
    ).toBe(true);
  });

  it("rejects malformed payloads", () => {
    expect(isVerificationResponse(null)).toBe(false);
    expect(isVerificationResponse({})).toBe(false);
    expect(isVerificationResponse({ ...BASE_RESPONSE, claims: "nope" })).toBe(false);
  });
});

function mockFetchOnce(response: Partial<Response> & { jsonBody?: unknown }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve(response.jsonBody ?? BASE_RESPONSE),
    ...response,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("analyze endpoint integration", () => {
  it("posts to /api/analyze and returns the typed response", async () => {
    const fetchMock = mockFetchOnce({});
    const result = await analyzeVerification(
      "claim",
      "The ministry approved a Rs 500 crore project.",
    );
    expect(result.request_id).toBe("req-1");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url.endsWith("/api/analyze")).toBe(true);
    expect(JSON.parse(init.body as string)).toEqual({
      input_type: "text",
      content: "The ministry approved a Rs 500 crore project.",
    });
  });

  it("surfaces validation errors without fabricating data", async () => {
    mockFetchOnce({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: "NO_CLAIMS_EXTRACTED" }),
    });
    await expect(
      analyzeVerification("claim", "The ministry approved a Rs 500 crore project here."),
    ).rejects.toMatchObject({ status: 422 });
  });

  it("maps provider outages to a graceful message", async () => {
    mockFetchOnce({ ok: false, status: 503, json: () => Promise.resolve({}) });
    const err = await analyzeVerification(
      "claim",
      "The ministry approved a Rs 500 crore project here.",
    ).catch((e) => e as VerificationApiError);
    expect(err).toBeInstanceOf(VerificationApiError);
    expect(err.message).toMatch(/unavailable/);
  });

  it("maps network failures without stack traces", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("fetch failed")),
    );
    const err = await analyzeVerification(
      "claim",
      "The ministry approved a Rs 500 crore project here.",
    ).catch((e) => e as VerificationApiError);
    expect(err.code).toBe("NETWORK_ERROR");
    expect(err.stack).toBeDefined();
  });

  it("rejects malformed success payloads", async () => {
    mockFetchOnce({ jsonBody: { unexpected: true } });
    await expect(
      analyzeVerification("claim", "The ministry approved a Rs 500 crore project here."),
    ).rejects.toMatchObject({ code: "MALFORMED_RESPONSE" });
  });
});
