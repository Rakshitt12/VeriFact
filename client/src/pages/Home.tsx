import { useEffect, useState } from "react";
import { Link, useLocation } from "wouter";
import { toast } from "sonner";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  FileSearch,
  Fingerprint,
  Globe2,
  Link2,
  Menu,
  Search,
  ShieldCheck,
  Sparkles,
  TextCursorInput,
  X,
} from "lucide-react";
import { useVerification } from "@/hooks/useVerification";

const examples = [
  "Scientists discovered a new planet that could support life.",
  "The government announced a new policy this week.",
  "A major company reported record profits this quarter.",
];

type InputMode = "url" | "text" | "claim";

function BrandMark() {
  return (
    <Link href="/" className="brand-mark" aria-label="VeriFact home">
      <span className="brand-glyph"><span /></span>
      <span>verifact</span>
    </Link>
  );
}

function Header({ onStart }: { onStart: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [location] = useLocation();
  const scrollTo = (id: string) => {
    setMenuOpen(false);
    if (location !== "/") window.location.href = `/#${id}`;
    else document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <header className="site-header">
      <div className="container nav-inner">
        <BrandMark />
        <nav className={`main-nav ${menuOpen ? "is-open" : ""}`} aria-label="Primary navigation">
          <button onClick={() => scrollTo("verify")} className="nav-link nav-link-active">Verify</button>
          <button onClick={() => scrollTo("process")} className="nav-link">How it works</button>
          <button onClick={() => scrollTo("principles")} className="nav-link">Our principles</button>
        </nav>
        <div className="nav-actions">
          <button className="text-button hide-mobile" onClick={() => toast.info("Your verification history will appear here once you run a check.")}>History</button>
          <button className="button button-dark button-small" onClick={onStart}>Start verification <ArrowUpRight size={15} /></button>
          <button className="menu-toggle" onClick={() => setMenuOpen((open) => !open)} aria-label="Toggle navigation">
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  );
}

function VerificationInput({ onVerify, loading, stage, stageIndex, stageCount }: {
  onVerify: (value: string, mode: InputMode) => void;
  loading: boolean;
  stage: string;
  stageIndex: number;
  stageCount: number;
}) {
  const [mode, setMode] = useState<InputMode>("claim");
  const [value, setValue] = useState("");
  const placeholder = mode === "url"
    ? "https://example.com/article-to-check"
    : mode === "text"
      ? "Paste the article or news text here..."
      : "What claim do you want to verify?";

  const submit = () => {
    if (loading) return;
    if (!value.trim()) {
      toast.error("Add a claim, article URL, or article text first.");
      return;
    }
    onVerify(value, mode);
  };

  const useExample = (example: string) => {
    setMode("claim");
    setValue(example);
    document.getElementById("verification-input")?.focus();
  };

  return (
    <div className="verify-card" id="verify">
      <div className="verify-card-topline"><span className="eyebrow">Start an investigation</span><span className="secure-pill"><ShieldCheck size={13} /> Evidence-first</span></div>
      <div className="input-tabs" role="tablist" aria-label="Verification input type">
        {([
          ["claim", "Claim", <TextCursorInput size={16} />],
          ["url", "Article URL", <Link2 size={16} />],
          ["text", "Article text", <BookOpen size={16} />],
        ] as const).map(([tab, label, icon]) => (
          <button key={tab} role="tab" aria-selected={mode === tab} className={`input-tab ${mode === tab ? "active" : ""}`} onClick={() => setMode(tab)}>
            {icon}{label}
          </button>
        ))}
      </div>
      <div className={`input-wrap ${mode === "text" ? "textarea-wrap" : ""}`}>
        {mode === "url" ? <Globe2 size={19} /> : mode === "text" ? <BookOpen size={19} /> : <Search size={19} />}
        {mode === "text" ? (
          <textarea id="verification-input" value={value} onChange={(event) => setValue(event.target.value)} placeholder={placeholder} rows={4} />
        ) : (
          <input id="verification-input" value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => event.key === "Enter" && submit()} placeholder={placeholder} />
        )}
        {value && <button className="clear-input" onClick={() => setValue("")} aria-label="Clear input"><X size={16} /></button>}
      </div>
      <div className="verify-actions">
        {loading ? (
          <p className="input-note" role="status" aria-live="polite"><Search size={14} /> {stage}… <span>stage {stageIndex + 1} of {stageCount}</span></p>
        ) : (
          <p className="input-note"><CircleHelp size={14} /> We compare retrieved evidence — not just model memory.</p>
        )}
        <button className="button button-primary" onClick={submit} disabled={loading} aria-busy={loading}>{loading ? "Verifying…" : <>Verify {mode === "claim" ? "claim" : "source"}<ChevronRight size={16} /></>}</button>
      </div>
      <div className="examples-row">
        <span>Try an example</span>
        {examples.map((example, index) => <button key={example} onClick={() => useExample(example)} className="example-chip">{index + 1}. “{example.slice(0, 37)}…”</button>)}
      </div>
    </div>
  );
}

function ProcessSection() {
  const steps = [
    ["01", "Input", "Submit an article, a URL, or one specific claim.", <TextCursorInput />],
    ["02", "Search", "Find relevant reporting, fact-checks, and primary sources.", <Search />],
    ["03", "Compare", "Separate independent evidence from syndicated repetition.", <Fingerprint />],
    ["04", "Verify", "Get an explainable report with a deterministic score.", <ShieldCheck />],
  ];
  return (
    <section className="process-section" id="process">
      <div className="container">
        <div className="section-heading split-heading"><div><span className="eyebrow">The investigation loop</span><h2>From headline<br /><em>to evidence.</em></h2></div><p>VeriFact turns a fast-moving story into a structured trail of evidence you can inspect, challenge, and share.</p></div>
        <div className="process-grid">
          {steps.map(([number, title, description, icon], index) => <div className="process-step" key={`process-step-${index}`}>
            <div className="process-step-top"><span className="step-number">{number}</span><span className="step-icon">{icon}</span></div>
            <h3>{title}</h3><p>{description}</p>{index < 3 && <span className="step-line" aria-hidden="true" />}
          </div>)}
        </div>
      </div>
    </section>
  );
}

function PrinciplesSection() {
  return (
    <section className="principles-section" id="principles">
      <div className="container principles-inner">
        <div className="principles-copy"><span className="eyebrow eyebrow-light">What we believe</span><h2>Good verification<br />shows its work.</h2><p>There is no single “truth detector.” There is only a clear account of what was checked, which sources agree, what conflicts, and what is still unknown.</p><button className="button button-ghost-light" onClick={() => toast.info("Methodology details are coming soon.")}>Read our methodology <ArrowUpRight size={15} /></button></div>
        <div className="principles-list"><div className="principle-item"><span>01</span><div><h3>Independent sources</h3><p>Syndicated copies are clustered so repetition does not masquerade as corroboration.</p></div></div><div className="principle-item"><span>02</span><div><h3>Primary evidence</h3><p>Official documents and direct records are weighted when they are available.</p></div></div><div className="principle-item"><span>03</span><div><h3>Visible uncertainty</h3><p>Mixed, contradicted, and insufficient evidence remain distinct outcomes.</p></div></div></div>
      </div>
    </section>
  );
}

export default function Home() {
  const verification = useVerification();
  const scrollToVerify = () => document.getElementById("verify")?.scrollIntoView({ behavior: "smooth", block: "center" });
  useEffect(() => {
    if (verification.error) toast.error(verification.error);
  }, [verification.error]);
  const verify = (value: string, mode: InputMode) => {
    void verification.verify(value, mode);
  };
  return (
    <div className="app-shell">
      <Header onStart={scrollToVerify} />
      <main>
        <section className="hero-section">
          <div className="hero-grid" aria-hidden="true"><span /><span /><span /><span /><span /><span /></div>
          <div className="container hero-inner">
            <div className="hero-kicker"><span className="live-dot" /> Independent evidence, clearly explained</div>
            <div className="hero-copy"><h1>Know what<br /><em>the evidence says.</em></h1><p>Verify news claims using independent sources, fact-checks, and primary evidence — not just AI predictions.</p></div>
            <VerificationInput
              onVerify={verify}
              loading={verification.loading}
              stage={verification.stage}
              stageIndex={verification.stageIndex}
              stageCount={verification.stageCount}
            />
            <div className="hero-footnote"><span><Check size={14} /> Designed for careful readers</span><span><Check size={14} /> No black-box verdicts</span><span><Check size={14} /> Sources you can open</span></div>
          </div>
        </section>
        <section className="signal-section"><div className="container signal-inner"><div className="signal-label"><Sparkles size={16} /> A better signal</div><p>“Credibility” is not a feeling. It is a score built from source quality, evidence agreement, independent reporting, and transparent gaps.</p><Link href="/analyze/demo" className="inline-link">See a sample report <ArrowUpRight size={15} /></Link></div></section>
        <ProcessSection />
        <PrinciplesSection />
      </main>
      <footer className="site-footer"><div className="container footer-inner"><BrandMark /><span>Evidence before certainty.</span><span>© 2026 VeriFact</span></div></footer>
    </div>
  );
}
