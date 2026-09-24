import { useMemo, useState } from "react";
import { Link, useLocation, useParams } from "wouter";
import { toast } from "sonner";
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  ChevronDown,
  ExternalLink,
  FileCheck2,
  Fingerprint,
  Globe2,
  Info,
  Link2,
  Menu,
  MoreHorizontal,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { downloadVerificationPdf } from "@/lib/pdfExport";
import { readVerificationResponse } from "@/hooks/useVerification";
import { SAMPLE_REQUEST_ID, SAMPLE_RESPONSE } from "@/lib/sampleReport";
import {
  allVerificationGaps,
  breakdownRows,
  classificationTone,
  contributionBarWidth,
  evidenceCounts,
  formatReportDate,
  groupClaimEvidence,
  isInsufficientClassification,
  isInsufficientScore,
  reportHeadline,
  scoreDisplay,
  jsonReportFilename,
  shortReportId,
  verdictVisualTone,
  verificationGapCount,
} from "@/lib/reportUtils";
import type {
  ClaimResult,
  EvidenceItem,
  FactCheckItem,
  SourceAnalysisItem,
  VerificationResponse,
} from "@/lib/types";

function BrandMark() {
  return <Link href="/" className="brand-mark" aria-label="VeriFact home"><span className="brand-glyph"><span /></span><span>verifact</span></Link>;
}

function ReportHeader({ isSample, reportReady }: { isSample: boolean; reportReady: boolean }) {
  const [, navigate] = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  return <header className="site-header report-header"><div className="container nav-inner"><button className="back-button" onClick={() => navigate("/")}><ArrowLeft size={16} /> New verification</button><BrandMark /><div className="nav-actions"><span className="report-state"><span className="live-dot" /> {isSample ? "Sample report" : reportReady ? "Report ready" : "No report"}</span><button className="icon-button mobile-menu" onClick={() => setMenuOpen(!menuOpen)} aria-label="Open menu">{menuOpen ? <X size={19} /> : <Menu size={19} />}</button><button className="icon-button hide-mobile" onClick={() => toast.info("Report actions are coming soon.")}><MoreHorizontal size={19} /></button></div></div></header>;
}

function ScoreRing({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 66;
  const dash = circumference * score / 100;
  return <div className="score-ring" style={{ "--score-dash": `${dash}px`, "--score-gap": `${circumference - dash}px` } as React.CSSProperties}><svg viewBox="0 0 160 160" aria-hidden="true"><circle className="score-track" cx="80" cy="80" r="66" /><circle className="score-progress" cx="80" cy="80" r="66" /></svg><div className="score-value"><strong>{score}</strong><span>/ 100</span></div></div>;
}

function ScoreBreakdown({ claim }: { claim: ClaimResult }) {
  const rows = breakdownRows(claim);
  const maxAbs = Math.max(1, ...rows.map((row) => Math.abs(row.value)));
  return <div className="breakdown-card"><div className="card-heading"><div><span className="eyebrow">The signal behind the score</span><h2>Why this score?</h2></div><button className="info-button" aria-label="Score methodology" onClick={() => toast.info("Each contribution comes straight from the backend scoring engine.")}><Info size={16} /></button></div><div className="breakdown-rows">{rows.map((row) => <div className="breakdown-row" key={row.label}><span>{row.label}</span><strong>{row.value >= 0 ? `+${row.value}` : row.value}</strong><div className="breakdown-bar"><span style={{ width: `${contributionBarWidth(row.value, maxAbs)}%` }} /></div></div>)}</div><div className="breakdown-total"><span>Credibility score</span><strong>{scoreDisplay(claim.score) ?? "Not available"}</strong></div><p className="method-note"><ShieldCheck size={14} /> Based on retrieved evidence and configured verification factors. This is not a probability of truth.</p></div>;
}

interface EvidenceView {
  key: string;
  source: string;
  title: string;
  meta: string;
  url: string | null;
  snippet: string | null;
  tag: string;
  tone: "blue" | "green" | "orange";
  contradicting: boolean;
}

function toEvidenceView(item: EvidenceItem, tone: "blue" | "green" | "orange"): EvidenceView {
  const date = item.published_at ? formatReportDate(item.published_at) : "Date unavailable";
  const reliability = item.source_reliability && item.source_reliability !== "unknown"
    ? `${item.source_reliability} reliability · `
    : "";
  return {
    key: item.evidence_id,
    source: item.publisher || "Unknown source",
    title: item.title,
    meta: `${reliability}${date}`,
    url: item.url,
    snippet: item.snippet,
    tag: item.stance === "SUPPORTING" ? "Supports the claim" : item.stance === "CONTRADICTING" ? "Contradicts the claim" : "Related context",
    tone,
    contradicting: item.stance === "CONTRADICTING",
  };
}

function EvidenceCard({ item }: { item: EvidenceView }) {
  const body = (
    <>
      <div className="evidence-top">
        <span className={`source-avatar ${item.tone}`}>{item.source.slice(0, 1)}</span>
        <span className="source-name">{item.source}</span>
        <span className="evidence-link" aria-hidden="true"><ExternalLink size={14} /></span>
      </div>
      <h3>{item.title}</h3>
      <p>{item.meta}{item.snippet ? ` — ${item.snippet.slice(0, 180)}${item.snippet.length > 180 ? "…" : ""}` : ""}</p>
      <div className={`evidence-tag${item.contradicting ? " contra" : ""}`}><Check size={13} /> {item.tag}</div>
    </>
  );
  if (item.url) {
    return (
      <a className="evidence-card interactive-card" href={item.url} target="_blank" rel="noreferrer" aria-label={`Open source: ${item.title}`}>
        {body}
      </a>
    );
  }
  return <article className="evidence-card">{body}</article>;
}

function FactCheckCard({ item }: { item: FactCheckItem }) {
  const rating = item.rating_label || item.verdict;
  const tone = verdictVisualTone(rating);
  const inner = (
    <>
      <div className="evidence-top">
        <span className="source-avatar orange">{item.fact_checker.slice(0, 1)}</span>
        <span className="source-name">{item.fact_checker}</span>
        <span className="evidence-link" aria-hidden="true"><ExternalLink size={14} /></span>
      </div>
      <span className="eyebrow fact-check-kicker">Fact check</span>
      <div className="fact-check-field">
        <span className="fact-check-label">Claim reviewed</span>
        <p className="fact-check-value">“{item.claim_text}”</p>
      </div>
      <div className="fact-check-field">
        <span className="fact-check-label">Rating</span>
        <p className={`fact-check-rating tone-${tone}`}>{rating}</p>
      </div>
      <div className="fact-check-field">
        <span className="fact-check-label">Reviewed assertion</span>
        <p className="fact-check-value">“{item.claim_text}”</p>
      </div>
      {item.explanation ? (
        <div className="fact-check-field">
          <span className="fact-check-label">Explanation</span>
          <p className="fact-check-expl">{item.explanation}</p>
        </div>
      ) : null}
    </>
  );
  if (item.url) {
    return (
      <a className="evidence-card fact-check-card interactive-card" href={item.url} target="_blank" rel="noreferrer" aria-label={`Open fact-check by ${item.fact_checker}`}>
        {inner}
      </a>
    );
  }
  return <article className="evidence-card fact-check-card">{inner}</article>;
}

function SourceCard({ item }: { item: SourceAnalysisItem }) {
  return (
    <article className="evidence-card source-card">
      <div className="evidence-top">
        <span className="source-avatar blue">{item.publisher.slice(0, 1)}</span>
        <span className="source-name">{item.publisher}</span>
      </div>
      <h3>{item.domain || item.publisher}</h3>
      <p>
        Reliability: {item.reliability_tier}
        {item.reliability_score != null ? ` (${item.reliability_score})` : ""}
        {item.transparency_level ? ` · Transparency: ${item.transparency_level}` : ""}
        {item.is_duplicate ? " · Grouped as a duplicate" : " · Counted independently"}
      </p>
      {item.limitations.length > 0 ? <p>{item.limitations.join(" ")}</p> : null}
    </article>
  );
}

function shareReport() {
  const url = window.location.href;
  const copied = "Copied this page URL. Reports are not stored as a permanent public link.";
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(
      () => toast.success(copied),
      () => toast.error("Could not copy the link. Copy the address bar URL instead."),
    );
  } else {
    toast.error("Clipboard is unavailable. Copy the address bar URL instead.");
  }
}

function exportReportJson(response: VerificationResponse) {
  try {
    const blob = new Blob([JSON.stringify(response, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = jsonReportFilename(response);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    toast.success("Report exported as JSON.");
  } catch {
    toast.error("Export failed. Please try again.");
  }
}

function exportReportPdf(response: VerificationResponse) {
  try {
    const filename = downloadVerificationPdf(response);
    toast.success(`Downloaded ${filename}`);
  } catch {
    toast.error("PDF export failed. Please try again.");
  }
}

function EmptyReport({ reason }: { reason: string }) {
  const [, navigate] = useLocation();
  return <div className="app-shell report-shell"><ReportHeader isSample={false} reportReady={false} /><main className="report-main"><div className="container report-container"><div className="report-breadcrumb"><span>Verification report</span><span>/</span><span>Unavailable</span></div><section className="report-intro"><div><span className="eyebrow">Nothing to show here</span><h1>Start a verification to see a report.</h1><div className="claim-meta"><span><Info size={14} /> {reason}</span></div></div><button className="button button-primary hide-mobile" onClick={() => navigate("/")}><ArrowLeft size={15} /> Back to verification</button></section></div></main><footer className="site-footer"><div className="container footer-inner"><BrandMark /><span>Evidence before certainty.</span></div></footer></div>;
}

export default function Analyze() {
  const params = useParams<{ id?: string }>();
  const id = params.id ?? "";
  const isSampleRoute = id === SAMPLE_REQUEST_ID;
  const stored = useMemo(() => (isSampleRoute ? null : readVerificationResponse(id)), [id, isSampleRoute]);
  const response: VerificationResponse | null = isSampleRoute ? SAMPLE_RESPONSE : stored;
  const [activeTab, setActiveTab] = useState<"supporting" | "contradicting" | "context">("supporting");
  const [claimsCollapsed, setClaimsCollapsed] = useState(false);

  if (!response) {
    return <EmptyReport reason="Reports live in this browser tab until you start a new verification. Refreshing in a new tab clears them." />;
  }

  const insufficient = isInsufficientScore(response.overall_score) || isInsufficientClassification(response.overall_classification);
  const headline = reportHeadline(response);
  const counts = evidenceCounts(response);
  const gapCount = verificationGapCount(response);
  const gaps = allVerificationGaps(response);
  const reportId = isSampleRoute ? "VF-DEMO" : shortReportId(response.request_id);
  const generatedAt = response.report?.generated_at ?? response.processed_at;
  const firstClaim: ClaimResult | undefined = response.claims[0];
  const evidence = firstClaim ? groupClaimEvidence(firstClaim) : { supporting: [], contradicting: [], neutral: [] };
  const factChecks = response.claims.flatMap((claim) => claim.fact_checks ?? []);
  const sourceCards = response.claims.flatMap((claim) => claim.source_analysis ?? []);
  const uniqueSources = sourceCards.filter((item, index, list) => list.findIndex((other) => (other.domain || other.publisher) === (item.domain || item.publisher)) === index);
  const verdictTone = verdictVisualTone(response.overall_classification);
  const toneFor = (classification: string) => classificationTone(classification);
  const shownEvidence = activeTab === "supporting" ? evidence.supporting : activeTab === "contradicting" ? evidence.contradicting : evidence.neutral;
  const shownViews = shownEvidence.map((item, index) => toEvidenceView(item, activeTab === "contradicting" ? "orange" : activeTab === "context" ? "green" : index === 1 ? "green" : "blue"));
  const totalDuplicates = response.claims.reduce((sum, claim) => sum + (claim.duplicate_clusters?.length ?? 0), 0);
  const aiReasoning = firstClaim?.evidence_reasoning ?? null;
  const inputKind = response.input_type === "url" ? "Article URL" : response.report && response.report.claims.length > 1 ? "Article text" : "Direct claim";

  return <div className="app-shell report-shell"><ReportHeader isSample={isSampleRoute} reportReady={true} /><main className="report-main"><div className="container report-container"><div className="report-breadcrumb"><span>Verification report</span><span>/</span><span>{reportId}</span>{isSampleRoute && <span className="sample-chip">Sample report</span>}<span className="report-date">{formatReportDate(generatedAt)}</span></div><section className="report-intro"><div><span className="eyebrow">Claim under investigation</span><h1>“{headline}”</h1><div className="claim-meta"><span><Link2 size={14} /> {inputKind}</span><span><Globe2 size={14} /> Evidence window: 30 days</span></div></div><button className="button button-outline" onClick={shareReport} aria-label="Copy this page URL. Reports are not stored as a permanent public link."><ArrowUpRight size={15} /> Share report</button></section><section className="verdict-grid"><div className="score-panel"><div className="panel-label"><span className="eyebrow">Credibility score</span>{insufficient ? <span className="verified-chip insufficient-chip"><Info size={13} /> Needs evidence</span> : <span className="verified-chip"><FileCheck2 size={13} /> Verified</span>}</div>{insufficient ? <div className="score-layout"><div className="score-copy"><span className="verdict-label tone-insufficient">Insufficient evidence</span><h2>Not enough evidence<br />for a conclusion.</h2><p>There is not enough independent evidence to establish a strong conclusion. This is not a judgment that the claim is false.</p></div></div> : <div className="score-layout">{typeof response.overall_score === "number" && <ScoreRing score={response.overall_score} />}<div className="score-copy"><span className={`verdict-label tone-${verdictTone}`}>{response.overall_classification}</span><h2>{response.overall_classification === "Mostly Supported" ? <>Evidence leans<br />in one direction.</> : <>{response.overall_classification}</>}</h2><p>{response.overall_summary}</p></div></div>}</div><div className="verdict-panel"><span className="eyebrow">Verdict</span><div className={`verdict-big tone-${verdictTone}`}><span className={`verdict-dot tone-${verdictTone}`} />{response.overall_classification}</div><p>{response.overall_summary}</p><div className="verdict-bottom"><span><Fingerprint size={14} /> {counts.independent} independent source{counts.independent === 1 ? "" : "s"}</span><span><Sparkles size={14} /> {gapCount} context gap{gapCount === 1 ? "" : "s"}</span></div></div></section>{firstClaim && !isInsufficientScore(firstClaim.score) && <ScoreBreakdown claim={firstClaim} />}{firstClaim && isInsufficientScore(firstClaim.score) && <div className="breakdown-card"><div className="card-heading"><div><span className="eyebrow">The signal behind the score</span><h2>Why no score?</h2></div></div><p className="method-note"><ShieldCheck size={14} /> Fewer than two independent sources were found, so no credibility score was calculated. This is not a probability of truth.</p></div>}<section className="report-section"><div className="section-title-row"><div><span className="eyebrow">Deconstructed</span><h2>Claims analyzed <span>{String(response.claims.length).padStart(2, "0")}</span></h2></div><button className="collapse-button" onClick={() => setClaimsCollapsed((collapsed) => !collapsed)} aria-expanded={!claimsCollapsed}>{claimsCollapsed ? "Expand" : "Collapse"} <ChevronDown size={15} /></button></div>{!claimsCollapsed && response.claims.map((claim, index) => { const tone = toneFor(claim.classification); const groups = groupClaimEvidence(claim); return <div className="claim-row" key={claim.claim_id}><div className="claim-index">{String(index + 1).padStart(2, "0")}</div><div className="claim-content"><div className="claim-row-top"><h3>{claim.claim_text}</h3><span className={`status-badge tone-${verdictVisualTone(claim.classification)} ${tone === "supported" ? "supported" : tone === "contested" ? "contested" : "insufficient"}`}>{tone === "insufficient" ? <Info size={13} /> : <Check size={13} />} {claim.classification}</span></div><p>{claim.summary}</p><div className="claim-tags"><span>{claim.score === null || claim.score === undefined ? "Score: not available" : `Score: ${claim.score} / 100`}</span><span>{groups.supporting.length} supporting · {groups.contradicting.length} contradicting · {groups.neutral.length} context</span><span>{claim.independent_source_count} independent source{claim.independent_source_count === 1 ? "" : "s"}</span></div></div></div>; })}</section><section className="report-section evidence-section"><div className="section-title-row"><div><span className="eyebrow">Source trail</span><h2>Evidence <span>{String(counts.retrieved).padStart(2, "0")}</span></h2></div><div className="evidence-tabs" role="group" aria-label="Evidence stance filter"><button className={activeTab === "supporting" ? "active" : ""} aria-pressed={activeTab === "supporting"} onClick={() => setActiveTab("supporting")}>Supporting <b>{String(evidence.supporting.length).padStart(2, "0")}</b></button><button className={activeTab === "contradicting" ? "active orange" : ""} aria-pressed={activeTab === "contradicting"} onClick={() => setActiveTab("contradicting")}>Contradicting <b>{String(evidence.contradicting.length).padStart(2, "0")}</b></button>{evidence.neutral.length > 0 && <button className={activeTab === "context" ? "active" : ""} aria-pressed={activeTab === "context"} onClick={() => setActiveTab("context")}>Context <b>{String(evidence.neutral.length).padStart(2, "0")}</b></button>}</div></div>{shownViews.length > 0 ? <div className="evidence-grid">{shownViews.map((item) => <EvidenceCard key={item.key} item={item} />)}</div> : <div className="claim-row"><div className="claim-index">–</div><div className="claim-content"><div className="claim-row-top"><h3>No {activeTab} evidence retrieved</h3></div><p>Nothing in this category was returned for the first claim. Other categories above may still hold relevant material.</p></div></div>}</section>{factChecks.length > 0 && <section className="report-section evidence-section"><div className="section-title-row"><div><span className="eyebrow">Independent reviews</span><h2>Fact-checks <span>{String(factChecks.length).padStart(2, "0")}</span></h2></div></div><div className="evidence-grid">{factChecks.map((item) => <FactCheckCard key={item.fact_check_id} item={item} />)}</div></section>}{uniqueSources.length > 0 && <section className="report-section evidence-section"><div className="section-title-row"><div><span className="eyebrow">Provenance</span><h2>Source analysis <span>{String(uniqueSources.length).padStart(2, "0")}</span></h2></div></div><div className="source-grid">{uniqueSources.map((item) => <SourceCard key={`${item.domain}-${item.publisher}-${item.evidence_id ?? ""}`} item={item} />)}</div></section>}{aiReasoning && <section className="report-section"><div className="section-title-row"><div><span className="eyebrow">Grounded synthesis</span><h2>Evidence reasoning</h2></div></div><div className="claim-row"><div className="claim-index"><Sparkles size={15} /></div><div className="claim-content"><div className="claim-row-top"><h3>What the retrieved evidence shows</h3></div><p>{aiReasoning.summary}</p><div className="claim-tags"><span>Uncertainty: {aiReasoning.uncertainty}</span><span>{aiReasoning.fallback_used ? "Deterministic reasoning (AI unavailable)" : aiReasoning.ai_used ? `AI-assisted${aiReasoning.provider ? ` · ${aiReasoning.provider}` : ""}${aiReasoning.model ? ` · ${aiReasoning.model}` : ""}` : "Evidence-based synthesis"}</span></div></div></div></section>}<section className="gap-callout"><div className="gap-icon"><Info size={21} /></div><div><span className="eyebrow">Verification gap{gaps.length === 1 ? "" : "s"}</span><h2>{gaps.length > 0 ? `${gaps.length} open question${gaps.length === 1 ? "" : "s"} remain${gaps.length === 1 ? "s" : ""}.` : "No open gaps reported."}</h2>{gaps.length > 0 ? gaps.map((gap) => <p key={gap}>{gap}</p>) : <p>Every aspect of the analyzed claims was addressed by the retrieved evidence.</p>}</div><button className="icon-button" aria-label="Gap details" onClick={() => toast.info(totalDuplicates > 0 ? `${totalDuplicates} duplicate or syndication cluster${totalDuplicates === 1 ? "" : "s"} grouped — repetition was not counted as corroboration.` : "No duplicate or syndication clusters were reported.")}><ArrowUpRight size={18} /></button></section><section className="sources-footer"><div><span className="eyebrow">Audit trail</span><h2>Everything in one place.</h2></div><div className="source-count"><strong>{String(counts.retrieved).padStart(2, "0")}</strong><span>sources reviewed<br />{counts.independent} independent · {totalDuplicates} grouped duplicate{totalDuplicates === 1 ? "" : "s"}</span></div><div className="export-actions"><button className="button button-dark" onClick={() => exportReportPdf(response)}>Export PDF <ArrowUpRight size={15} /></button><button className="button button-outline" onClick={() => exportReportJson(response)}>Export JSON</button></div></section></div></main><footer className="site-footer"><div className="container footer-inner"><BrandMark /><span>Evidence before certainty.</span><span>Report {reportId}</span></div></footer></div>;
}
