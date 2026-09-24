/**
 * Client-side PDF presentation of an existing VerificationResponse.
 * Copies backend fields only — never recomputes scores, ratings, or URLs.
 */
import { jsPDF } from "jspdf";
import {
  formatReportDate,
  groupClaimEvidence,
  pdfReportFilename,
  scoreDisplay,
} from "./reportUtils";
import type {
  ClaimResult,
  ClaimVerificationReport,
  FactCheckCard,
  FactCheckItem,
  VerificationResponse,
} from "./types";

export interface PdfCitation {
  title: string;
  publisher: string;
  url: string;
}

export interface PdfFactCheck {
  publisher: string;
  rating: string;
  claimText: string;
  explanation: string;
  url: string;
}

export interface PdfEvidenceLine {
  title: string;
  publisher: string;
  snippet: string;
  url: string;
}

export interface PdfClaimSection {
  claimText: string;
  classification: string;
  score: string | null;
  summary: string;
  supporting: PdfEvidenceLine[];
  contradicting: PdfEvidenceLine[];
  neutral: PdfEvidenceLine[];
  factChecks: PdfFactCheck[];
  discrepancies: string[];
  verificationGaps: string[];
}

export interface PdfSourceLine {
  publisher: string;
  domain: string;
  reliability: string;
  transparency: string;
  independence: string;
}

export interface PdfExportPayload {
  reportId: string;
  generatedAt: string;
  methodologyVersion: string;
  score: string | null;
  classification: string;
  summary: string;
  claims: PdfClaimSection[];
  sources: PdfSourceLine[];
  aiSummary: string | null;
  aiUncertainty: string | null;
  aiFindings: string[];
  aiGaps: string[];
  aiProvenance: string | null;
  citations: PdfCitation[];
}

function evidenceLine(item: {
  title: string;
  publisher?: string | null;
  snippet?: string | null;
  url?: string | null;
}): PdfEvidenceLine {
  return {
    title: item.title,
    publisher: item.publisher || "",
    snippet: item.snippet || "",
    url: item.url || "",
  };
}

function factCheckFromItem(item: FactCheckItem): PdfFactCheck {
  return {
    publisher: item.fact_checker,
    rating: item.rating_label || item.verdict,
    claimText: item.claim_text,
    explanation: item.explanation,
    url: item.url || "",
  };
}

function factCheckFromCard(item: FactCheckCard): PdfFactCheck {
  return {
    publisher: item.publisher,
    rating: item.normalized_rating || item.original_rating,
    claimText: item.title || "",
    explanation: item.explanation,
    url: item.url || "",
  };
}

function claimFromResult(claim: ClaimResult): PdfClaimSection {
  const groups = groupClaimEvidence(claim);
  return {
    claimText: claim.claim_text,
    classification: claim.classification,
    score: scoreDisplay(claim.score),
    summary: claim.summary,
    supporting: groups.supporting.map(evidenceLine),
    contradicting: groups.contradicting.map(evidenceLine),
    neutral: groups.neutral.map(evidenceLine),
    factChecks: (claim.fact_checks ?? []).map(factCheckFromItem),
    discrepancies: [],
    verificationGaps: (claim.verification_gaps ?? []).map((gap) => gap.description),
  };
}

function claimFromReport(claim: ClaimVerificationReport): PdfClaimSection {
  return {
    claimText: claim.claim_text,
    classification: claim.classification,
    score: scoreDisplay(claim.score),
    summary: claim.summary,
    supporting: (claim.supporting_evidence ?? []).map(evidenceLine),
    contradicting: (claim.contradicting_evidence ?? []).map(evidenceLine),
    neutral: [...(claim.neutral_evidence ?? []), ...(claim.insufficient_evidence ?? [])].map(evidenceLine),
    factChecks: (claim.fact_checks ?? []).map(factCheckFromCard),
    discrepancies: (claim.discrepancies ?? []).map((item) => item.description),
    verificationGaps: claim.verification_gaps ?? [],
  };
}

function collectCitations(response: VerificationResponse): PdfCitation[] {
  const seen = new Set<string>();
  const out: PdfCitation[] = [];
  const push = (title: string, publisher: string, url: string) => {
    if (!url) return;
    if (seen.has(url)) return;
    seen.add(url);
    out.push({ title, publisher, url });
  };
  for (const item of response.report?.citations ?? []) {
    push(item.title, item.publisher, item.url);
  }
  for (const claim of response.claims) {
    for (const item of [
      ...(claim.supporting_evidence ?? []),
      ...(claim.contradicting_evidence ?? []),
      ...(claim.neutral_evidence ?? []),
      ...(claim.retrieved_evidence ?? []),
    ]) {
      push(item.title, item.publisher || "", item.url);
    }
    for (const fc of claim.fact_checks ?? []) push(fc.claim_text, fc.fact_checker, fc.url);
  }
  if (response.report) {
    for (const claim of response.report.claims) {
      for (const item of [
        ...(claim.supporting_evidence ?? []),
        ...(claim.contradicting_evidence ?? []),
        ...(claim.neutral_evidence ?? []),
        ...(claim.insufficient_evidence ?? []),
      ]) {
        push(item.title, item.publisher || "", item.url);
      }
      for (const fc of claim.fact_checks ?? []) push(fc.title || fc.publisher, fc.publisher, fc.url);
    }
  }
  return out;
}

function collectSources(response: VerificationResponse): PdfSourceLine[] {
  const out: PdfSourceLine[] = [];
  const seen = new Set<string>();
  for (const claim of response.claims) {
    for (const source of claim.source_analysis ?? []) {
      const key = source.domain || source.publisher;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        publisher: source.publisher,
        domain: source.domain,
        reliability: source.reliability_tier,
        transparency: source.transparency_level || String(source.transparency_score),
        independence: source.is_duplicate ? "Grouped duplicate" : "Counted independently",
      });
    }
  }
  if (out.length === 0 && response.report) {
    for (const claim of response.report.claims) {
      for (const source of claim.source_analysis ?? []) {
        const key = source.domain || source.publisher;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({
          publisher: source.publisher,
          domain: source.domain,
          reliability: source.reliability_label,
          transparency: source.transparency,
          independence: source.primary_reporting_signal ? "Primary reporting signal" : "Not marked primary",
        });
      }
    }
  }
  return out;
}

function collectAi(response: VerificationResponse): Pick<
  PdfExportPayload,
  "aiSummary" | "aiUncertainty" | "aiFindings" | "aiGaps" | "aiProvenance"
> {
  const reportAi = response.report?.claims[0]?.ai_reasoning;
  const claimAi = response.claims[0]?.evidence_reasoning;
  if (reportAi) {
    return {
      aiSummary: reportAi.summary || null,
      aiUncertainty: reportAi.uncertainty || null,
      aiFindings: [
        ...reportAi.supporting_findings,
        ...reportAi.contradicting_findings,
        ...reportAi.important_discrepancies,
      ],
      aiGaps: reportAi.verification_gaps,
      aiProvenance: [
        reportAi.fallback_used ? "Fallback reasoning" : null,
        reportAi.ai_used ? "AI-assisted" : "Deterministic",
        reportAi.provider,
        reportAi.model,
      ]
        .filter(Boolean)
        .join(" · ") || null,
    };
  }
  if (claimAi) {
    return {
      aiSummary: claimAi.summary || null,
      aiUncertainty: claimAi.uncertainty || null,
      aiFindings: [
        ...claimAi.supporting_findings.map((item) => item.text),
        ...claimAi.contradicting_findings.map((item) => item.text),
        ...claimAi.important_discrepancies,
      ],
      aiGaps: claimAi.verification_gaps,
      aiProvenance: [
        claimAi.fallback_used ? "Fallback reasoning" : null,
        claimAi.ai_used ? "AI-assisted" : "Deterministic",
        claimAi.provider,
        claimAi.model,
      ]
        .filter(Boolean)
        .join(" · ") || null,
    };
  }
  return { aiSummary: null, aiUncertainty: null, aiFindings: [], aiGaps: [], aiProvenance: null };
}

/** Flatten the live report object into printable fields. No derived verdicts. */
export function buildPdfExportPayload(response: VerificationResponse): PdfExportPayload {
  const report = response.report;
  const claims = report?.claims.length
    ? report.claims.map(claimFromReport)
    : response.claims.map(claimFromResult);
  const overall = report?.overall_result;
  return {
    reportId: report?.report_id || response.request_id,
    generatedAt: formatReportDate(report?.generated_at || response.processed_at),
    methodologyVersion: report?.methodology_version || "not provided",
    score: scoreDisplay(overall?.score ?? response.overall_score),
    classification: overall?.classification || response.overall_classification,
    summary: overall?.summary || response.overall_summary,
    claims,
    sources: collectSources(response),
    ...collectAi(response),
    citations: collectCitations(response),
  };
}

const ACCENT: [number, number, number] = [182, 81, 102];
const INK: [number, number, number] = [28, 24, 26];
const MUTED: [number, number, number] = [90, 82, 86];

class PdfWriter {
  doc: jsPDF;
  y = 22;
  readonly margin = 18;
  readonly pageWidth: number;
  readonly pageHeight: number;
  readonly maxWidth: number;

  constructor() {
    this.doc = new jsPDF({ unit: "mm", format: "a4" });
    this.pageWidth = this.doc.internal.pageSize.getWidth();
    this.pageHeight = this.doc.internal.pageSize.getHeight();
    this.maxWidth = this.pageWidth - this.margin * 2;
  }

  ensure(space: number) {
    if (this.y + space > this.pageHeight - 18) {
      this.doc.addPage();
      this.y = 20;
    }
  }

  text(value: string, size: number, color: [number, number, number], style: "normal" | "bold" = "normal") {
    const lines = this.doc.splitTextToSize(value, this.maxWidth) as string[];
    this.ensure(lines.length * (size * 0.42) + 2);
    this.doc.setFont("helvetica", style);
    this.doc.setFontSize(size);
    this.doc.setTextColor(...color);
    this.doc.text(lines, this.margin, this.y);
    this.y += lines.length * (size * 0.42) + 1.4;
  }

  heading(value: string) {
    this.y += 4;
    this.text(value, 13, ACCENT, "bold");
    this.doc.setDrawColor(...ACCENT);
    this.doc.setLineWidth(0.3);
    this.doc.line(this.margin, this.y - 1, this.pageWidth - this.margin, this.y - 1);
    this.y += 3;
  }

  field(label: string, value: string | null | undefined) {
    if (value == null || value === "") return;
    this.text(`${label}: ${value}`, 10, INK);
  }

  list(title: string, items: PdfEvidenceLine[]) {
    this.text(title, 11, ACCENT, "bold");
    if (!items.length) {
      this.text("None reported.", 10, MUTED);
      return;
    }
    for (const item of items) {
      this.text(item.title, 10, INK, "bold");
      if (item.publisher) this.text(item.publisher, 9, MUTED);
      if (item.snippet) this.text(item.snippet, 9, INK);
      if (item.url) this.text(item.url, 8, ACCENT);
    }
  }

  footer() {
    const pages = this.doc.getNumberOfPages();
    for (let i = 1; i <= pages; i += 1) {
      this.doc.setPage(i);
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(8);
      this.doc.setTextColor(...MUTED);
      this.doc.text("VeriFact · Evidence-based verification", this.margin, this.pageHeight - 8);
      this.doc.text(`Page ${i} of ${pages}`, this.pageWidth - this.margin, this.pageHeight - 8, { align: "right" });
    }
  }
}

export function generateVerificationPdf(response: VerificationResponse): jsPDF {
  const data = buildPdfExportPayload(response);
  const writer = new PdfWriter();
  writer.text("VERIFACT", 18, ACCENT, "bold");
  writer.text("Evidence-Based News Verification Report", 12, INK);
  writer.y += 2;
  writer.field("Report ID", data.reportId);
  writer.field("Generated", data.generatedAt);
  writer.field("Methodology version", data.methodologyVersion);

  writer.heading("Overall result");
  writer.field("Credibility score", data.score ?? "Not available (insufficient evidence)");
  writer.field("Classification", data.classification);
  writer.field("Summary", data.summary);

  data.claims.forEach((claim, index) => {
    writer.heading(`Claim ${index + 1}`);
    writer.text(claim.claimText, 11, INK, "bold");
    writer.field("Classification", claim.classification);
    writer.field("Score", claim.score ?? "Not available");
    writer.field("Summary", claim.summary);
    writer.list("Supporting evidence", claim.supporting);
    writer.list("Contradicting evidence", claim.contradicting);
    writer.list("Neutral / context evidence", claim.neutral);
    writer.text("Fact-checks", 11, ACCENT, "bold");
    if (!claim.factChecks.length) writer.text("None reported.", 10, MUTED);
    for (const fc of claim.factChecks) {
      writer.field("Publisher", fc.publisher);
      writer.field("Rating", fc.rating);
      writer.field("Claim reviewed", fc.claimText);
      writer.field("Explanation", fc.explanation);
      if (fc.url) writer.text(fc.url, 8, ACCENT);
    }
    writer.text("Discrepancies", 11, ACCENT, "bold");
    if (!claim.discrepancies.length) writer.text("None reported.", 10, MUTED);
    else claim.discrepancies.forEach((item) => writer.text(item, 10, INK));
    writer.text("Verification gaps", 11, ACCENT, "bold");
    if (!claim.verificationGaps.length) writer.text("None reported.", 10, MUTED);
    else claim.verificationGaps.forEach((item) => writer.text(item, 10, INK));
  });

  writer.heading("Source information");
  if (!data.sources.length) writer.text("No source-analysis records were included in this report.", 10, MUTED);
  for (const source of data.sources) {
    writer.text(source.publisher, 10, INK, "bold");
    writer.field("Domain", source.domain);
    writer.field("Reliability", source.reliability);
    writer.field("Transparency", source.transparency);
    writer.field("Independence", source.independence);
  }

  writer.heading("AI reasoning");
  if (!data.aiSummary && !data.aiFindings.length) {
    writer.text("No AI reasoning section was included in this report.", 10, MUTED);
  } else {
    writer.field("Grounded summary", data.aiSummary);
    writer.field("Uncertainty", data.aiUncertainty);
    writer.field("Provenance", data.aiProvenance);
    writer.text("Findings", 11, ACCENT, "bold");
    if (!data.aiFindings.length) writer.text("None reported.", 10, MUTED);
    else data.aiFindings.forEach((item) => writer.text(item, 10, INK));
    writer.text("Verification gaps", 11, ACCENT, "bold");
    if (!data.aiGaps.length) writer.text("None reported.", 10, MUTED);
    else data.aiGaps.forEach((item) => writer.text(item, 10, INK));
  }

  writer.heading("Citations");
  if (!data.citations.length) writer.text("No source URLs were supplied by the backend for this report.", 10, MUTED);
  for (const citation of data.citations) {
    writer.text(citation.title || citation.publisher || citation.url, 10, INK, "bold");
    if (citation.publisher) writer.text(citation.publisher, 9, MUTED);
    writer.text(citation.url, 8, ACCENT);
  }

  writer.footer();
  return writer.doc;
}

export function downloadVerificationPdf(response: VerificationResponse): string {
  const filename = pdfReportFilename(response);
  generateVerificationPdf(response).save(filename);
  return filename;
}
