/**
 * TypeScript mirrors of the FastAPI backend response schema.
 *
 * Sources of truth (do not guess field names — verified against):
 * - backend/api/schemas.py        (VerificationRequest/Response, ClaimResult, EvidenceItem, ...)
 * - backend/report/models.py      (VerificationReport and all report cards)
 * - backend/scoring/models.py     (ScoreComponent, ScorePenalty, claim/document scores)
 * - backend/verification/models.py (stances, clusters, comparisons, discrepancies, fact-checks)
 * - backend/ai/models.py          (AIReasoningResult, EvidenceFinding)
 * - backend/sources/models.py     (SourceAnalysis)
 * - backend/retrieval/models.py   (Evidence)
 *
 * The frontend performs NO verification logic — these types are presentation-only.
 */

/** Backend `InputType` (backend/api/schemas.py). Only text|url exist server-side. */
export type BackendInputType = "text" | "url";

/** Frontend input tabs. `claim` maps to backend `text` (see buildVerificationPayload). */
export type FrontendInputMode = "claim" | "url" | "text";

export interface VerificationRequest {
  input_type: BackendInputType;
  content: string;
}

export type EvidenceStance = "SUPPORTING" | "CONTRADICTING" | "NEUTRAL" | "INSUFFICIENT";

/** Backend classifications (backend/api/schemas.py ClassificationLabel + Part 10 passthrough). */
export type ClassificationLabel =
  | "Strongly Supported"
  | "Mostly Supported"
  | "Mixed / Uncertain"
  | "Weakly Supported"
  | "Strongly Contradicted"
  | "INSUFFICIENT EVIDENCE"
  | string;

export interface InputSummary {
  title: string | null;
  publisher: string | null;
  author: string | null;
  published_at: string | null;
  domain: string | null;
  url: string | null;
}

export interface EvidenceItem {
  evidence_id: string;
  title: string;
  url: string;
  publisher: string;
  published_at: string | null;
  snippet: string;
  stance: EvidenceStance;
  rationale: string;
  is_primary_source: boolean;
  source_reliability: string;
}

export interface FactCheckItem {
  fact_check_id: string;
  claim_text: string;
  verdict: string;
  rating_label: string;
  fact_checker: string;
  url: string;
  published_at: string | null;
  explanation: string;
}

export interface SourceAnalysisItem {
  domain: string;
  publisher: string;
  reliability_tier: string;
  transparency_score: number;
  type: string;
  is_primary_source: boolean;
  is_duplicate: boolean;
  cluster_id: string | null;
  evidence_id: string | null;
  reliability_score: number | null;
  transparency_level: string | null;
  source_category: string | null;
  source_age: string | null;
  signals: string[];
  limitations: string[];
}

export interface DuplicateCluster {
  cluster_id: string;
  origin: Record<string, unknown>;
  duplicates: Record<string, unknown>[];
  cluster_size: number;
  counted_as_independent: number;
}

export interface ScoreContribution {
  factor: string;
  label: string;
  contribution: number;
  detail: string;
}

export interface VerificationGap {
  gap_type: string;
  description: string;
}

export interface EvidenceFindingItem {
  text: string;
  evidence_ids: string[];
  stance: string | null;
  importance: string;
  confidence: number;
}

export interface AIReasoningResponse {
  summary: string;
  key_findings: EvidenceFindingItem[];
  supporting_findings: EvidenceFindingItem[];
  contradicting_findings: EvidenceFindingItem[];
  important_discrepancies: string[];
  source_observations: string[];
  independence_observations: string[];
  fact_check_observations: string[];
  verification_gaps: string[];
  uncertainty: string;
  reasoning_steps: string[];
  limitations: string[];
  ai_used: boolean;
  provider: string | null;
  model: string | null;
  fallback_used: boolean;
}

export interface RetrievedEvidenceItem {
  evidence_id: string;
  title: string;
  url: string;
  publisher: string | null;
  domain: string | null;
  snippet: string | null;
  source_type: string;
  provider: string;
  published_at: string | null;
  query_used: string;
  metadata: Record<string, unknown>;
}

export interface ClaimResult {
  claim_id: string;
  claim_text: string;
  score: number | null;
  classification: string;
  summary: string;
  supporting_evidence: EvidenceItem[];
  contradicting_evidence: EvidenceItem[];
  neutral_evidence: EvidenceItem[];
  fact_checks: FactCheckItem[];
  source_analysis: SourceAnalysisItem[];
  duplicate_clusters: DuplicateCluster[];
  score_breakdown: ScoreContribution[];
  verification_gaps: VerificationGap[];
  evidence_reasoning: AIReasoningResponse | null;
  independent_source_count: number;
  total_evidence_count: number;
  retrieved_evidence: RetrievedEvidenceItem[];
}

/* ---------------- Part 10 report models (backend/report/models.py) ---------------- */

export interface ReportInputSummary {
  input_type: string;
  headline: string | null;
  source_url: string | null;
  text_length: number;
  claim_count: number;
  verification_timestamp: string;
}

export interface ReportOverallResult {
  score: number | null;
  classification: string;
  summary: string;
}

export interface EvidenceCard {
  evidence_id: string;
  title: string;
  publisher: string | null;
  url: string;
  publication_date: string | null;
  snippet: string | null;
  stance: string;
  relevance: number | null;
  cluster_id: string | null;
  independence_status: string | null;
  source_category: string | null;
  source_reliability: string | null;
}

export interface EvidenceSummary {
  total_retrieved: number;
  supporting_count: number;
  contradicting_count: number;
  neutral_count: number;
  insufficient_count: number;
  independent_source_count: number;
  duplicate_count: number;
  syndicated_count: number;
  fact_check_count: number;
}

export interface FactCheckCard {
  fact_check_id: string;
  publisher: string;
  title: string | null;
  url: string;
  review_date: string | null;
  original_rating: string;
  normalized_rating: string;
  stance: string;
  explanation: string;
  evidence_ids: string[];
}

export interface DiscrepancyCard {
  type: string;
  description: string;
  claim_value: string;
  evidence_value: string;
  evidence_ids: string[];
  severity: string;
}

export interface SourceAnalysisCard {
  publisher: string;
  domain: string;
  source_category: string;
  reliability_label: string;
  reliability_score: number;
  transparency: string;
  metadata_quality: number;
  attribution_signal: boolean;
  primary_reporting_signal: boolean;
  limitations: string[];
}

export interface ClusterCard {
  cluster_id: string;
  cluster_type: string;
  member_count: number;
  representative_evidence_id: string | null;
  evidence_ids: string[];
}

export interface IndependenceSummary {
  independent_source_count: number;
  cluster_count: number;
  syndication_clusters: number;
  duplicate_clusters: number;
  independence_limitations: string[];
  clusters: ClusterCard[];
}

export interface ScoreComponentCard {
  factor: string;
  label: string;
  raw_score: number;
  weight: number;
  weighted_contribution: number;
  explanation: string;
  evidence_ids: string[];
}

export interface ScorePenaltyCard {
  penalty_type: string;
  amount: number;
  explanation: string;
  evidence_ids: string[];
}

export interface ScoreBreakdownReport {
  components: ScoreComponentCard[];
  penalties: ScorePenaltyCard[];
  total_before_penalties: number;
  penalties_total: number;
  final_score: number | null;
  score_contributions: ScoreContribution[];
}

export interface AIReasoningReport {
  summary: string;
  supporting_findings: string[];
  contradicting_findings: string[];
  important_discrepancies: string[];
  source_observations: string[];
  independence_observations: string[];
  fact_check_observations: string[];
  verification_gaps: string[];
  uncertainty: string;
  limitations: string[];
  ai_used: boolean;
  fallback_used: boolean;
  provider: string | null;
  model: string | null;
}

export interface CitationItem {
  evidence_id: string;
  title: string;
  publisher: string;
  url: string;
  publication_date: string | null;
  domain: string | null;
}

export interface ClaimVerificationReport {
  claim_id: string;
  claim_text: string;
  claim_type: string;
  importance: string;
  score: number | null;
  classification: string;
  is_insufficient_evidence: boolean;
  summary: string;
  evidence_summary: EvidenceSummary;
  supporting_evidence: EvidenceCard[];
  contradicting_evidence: EvidenceCard[];
  neutral_evidence: EvidenceCard[];
  insufficient_evidence: EvidenceCard[];
  fact_checks: FactCheckCard[];
  discrepancies: DiscrepancyCard[];
  verification_gaps: string[];
  source_analysis: SourceAnalysisCard[];
  independence_analysis: IndependenceSummary | null;
  score_breakdown: ScoreBreakdownReport | null;
  ai_reasoning: AIReasoningReport | null;
  limitations: string[];
}

export interface VerificationReport {
  report_id: string;
  generated_at: string;
  methodology_version: string;
  input_summary: ReportInputSummary;
  overall_result: ReportOverallResult;
  executive_summary: string;
  claims: ClaimVerificationReport[];
  evidence_summary: EvidenceSummary;
  citations: CitationItem[];
  limitations: string[];
}

export interface VerificationResponse {
  request_id: string;
  processed_at: string;
  input_type: BackendInputType;
  input_summary: InputSummary;
  claims: ClaimResult[];
  overall_score: number | null;
  overall_classification: string;
  overall_summary: string;
  limitations: string[];
  report: VerificationReport | null;
}
