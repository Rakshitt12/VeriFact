/**
 * Pure presentation helpers for rendering backend verification data.
 *
 * No verification logic: every helper reads values the backend already
 * computed (Parts 5–10) and only formats them for display.
 */
import type {
  ClaimResult,
  ClaimVerificationReport,
  EvidenceCard,
  EvidenceItem,
  VerificationResponse,
} from "./types";

export const INSUFFICIENT_LABEL = "INSUFFICIENT EVIDENCE";

export function isInsufficientClassification(classification: string): boolean {
  return classification.trim().toUpperCase() === INSUFFICIENT_LABEL;
}

/** A response/score is insufficient when the backend returned score=null. */
export function isInsufficientScore(score: number | null | undefined): boolean {
  return score === null || score === undefined;
}

/** "82 / 100", or null when the backend returned no score (never "0 / 100"). */
export function scoreDisplay(score: number | null | undefined): string | null {
  if (isInsufficientScore(score)) return null;
  return `${score} / 100`;
}

/** Short report identifier for the breadcrumb, e.g. request_id prefix. */
export function shortReportId(requestId: string): string {
  const compact = requestId.replace(/-/g, "");
  return `VF-${compact.slice(0, 4).toUpperCase()}`;
}

/** Locale-formatted timestamp; falls back to the raw value when unparseable. */
export function formatReportDate(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/**
 * Independent vs retrieved evidence counts.
 * NEVER equate article count with independent confirmations — the backend's
 * `independent_source_count` (post dedup/syndication clustering) is authoritative.
 */
export function evidenceCounts(response: VerificationResponse): {
  retrieved: number;
  independent: number;
} {
  const retrieved = response.claims.reduce(
    (sum, claim) => sum + (claim.total_evidence_count || 0),
    0,
  );
  const independent = response.claims.reduce(
    (sum, claim) => sum + (claim.independent_source_count || 0),
    0,
  );
  const reportTotal = response.report?.evidence_summary.total_retrieved;
  const reportIndependent = response.report?.evidence_summary.independent_source_count;
  return {
    retrieved: reportTotal ?? retrieved,
    independent: reportIndependent ?? independent,
  };
}

export function verificationGapCount(response: VerificationResponse): number {
  return allVerificationGaps(response).length;
}

/** Flatten all verification-gap descriptions for the gap callout. */
export function allVerificationGaps(response: VerificationResponse): string[] {
  const gaps: string[] = [];
  for (const claim of response.claims) {
    for (const gap of claim.verification_gaps ?? []) gaps.push(gap.description);
  }
  if (response.report) {
    for (const claim of response.report.claims) {
      for (const gap of claim.verification_gaps ?? []) {
        if (!gaps.includes(gap)) gaps.push(gap);
      }
    }
  }
  return gaps;
}

export interface EvidenceGroups {
  supporting: EvidenceItem[];
  contradicting: EvidenceItem[];
  neutral: EvidenceItem[];
}

export function groupClaimEvidence(claim: ClaimResult): EvidenceGroups {
  return {
    supporting: claim.supporting_evidence ?? [],
    contradicting: claim.contradicting_evidence ?? [],
    neutral: claim.neutral_evidence ?? [],
  };
}

export interface ReportEvidenceGroups {
  supporting: EvidenceCard[];
  contradicting: EvidenceCard[];
  neutral: EvidenceCard[];
  insufficient: EvidenceCard[];
}

export function groupReportClaimEvidence(claim: ClaimVerificationReport): ReportEvidenceGroups {
  return {
    supporting: claim.supporting_evidence ?? [],
    contradicting: claim.contradicting_evidence ?? [],
    neutral: claim.neutral_evidence ?? [],
    insufficient: claim.insufficient_evidence ?? [],
  };
}

/** Score-breakdown rows rendered directly from backend contributions. */
export function breakdownRows(claim: ClaimResult): { label: string; value: number }[] {
  return (claim.score_breakdown ?? []).map((item) => ({
    label: item.label,
    value: item.contribution,
  }));
}

/** Report-level breakdown rows (weighted contributions) for a report claim. */
export function reportBreakdownRows(claim: ClaimVerificationReport): {
  label: string;
  value: number;
  detail: string;
}[] {
  const rows =
    claim.score_breakdown?.components.map((c) => ({
      label: c.label,
      value: c.weighted_contribution,
      detail: c.explanation,
    })) ?? [];
  const penalties =
    claim.score_breakdown?.penalties.map((p) => ({
      label: `Penalty — ${p.penalty_type}`,
      value: -Math.abs(p.amount),
      detail: p.explanation,
    })) ?? [];
  return [...rows, ...penalties];
}

/** Bar width helper: scale contributions to a 0–100% bar without inventing data. */
export function contributionBarWidth(value: number, maxAbs: number): number {
  if (maxAbs <= 0) return 0;
  return Math.min(100, Math.max(0, (Math.abs(value) / maxAbs) * 100));
}

/** Tone bucket for badges, derived from backend classification text only. */
export function classificationTone(classification: string): "supported" | "contested" | "insufficient" {
  if (isInsufficientClassification(classification)) return "insufficient";
  const lower = classification.toLowerCase();
  if (lower.includes("supported")) return "supported";
  return "contested";
}

/** Primary headline for a report: first claim text, else the overall summary. */
export function reportHeadline(response: VerificationResponse): string {
  const first = response.report?.claims[0]?.claim_text ?? response.claims[0]?.claim_text;
  return first || response.overall_summary || "Verification report";
}
