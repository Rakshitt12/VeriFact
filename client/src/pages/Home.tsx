import { useEffect, useState } from "react";
import { Link, useLocation } from "wouter";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
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
import { TiltCard } from "@/components/motion/TiltCard";
import {
  buttonMotion,
  cardRevealVariants,
  chipMotion,
  EASE_OUT,
  heroCardVariants,
  heroContainerVariants,
  heroFootnoteVariants,
  heroHeadingVariants,
  heroKickerVariants,
  sectionRevealVariants,
  SPRING,
  staggerContainerVariants,
} from "@/lib/motion";

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
          <motion.button
            whileHover={buttonMotion.whileHover}
            whileTap={buttonMotion.whileTap}
            transition={buttonMotion.transition}
            className="button button-dark button-small"
            onClick={onStart}
          >
            Start verification <ArrowUpRight size={15} />
          </motion.button>
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
    <TiltCard
      variants={heroCardVariants}
      maxTilt={2.5}
      className="verify-card"
      id="verify"
    >
      <div className="verify-card-topline">
        <span className="eyebrow">Start an investigation</span>
        <span className="secure-pill"><ShieldCheck size={13} /> Evidence-first</span>
      </div>
      <div className="input-tabs" role="tablist" aria-label="Verification input type">
        {([
          ["claim", "Claim", <TextCursorInput size={16} key="claim-icon" />],
          ["url", "Article URL", <Link2 size={16} key="url-icon" />],
          ["text", "Article text", <BookOpen size={16} key="text-icon" />],
        ] as const).map(([tab, label, icon]) => {
          const isActive = mode === tab;
          return (
            <button
              key={tab}
              role="tab"
              aria-selected={isActive}
              className={`input-tab ${isActive ? "active" : ""}`}
              onClick={() => setMode(tab)}
            >
              {icon}
              <span>{label}</span>
              {isActive && (
                <motion.span
                  layoutId="activeTabUnderline"
                  className="input-tab-indicator"
                  transition={SPRING.tabIndicator}
                />
              )}
            </button>
          );
        })}
      </div>
      <div className={`input-wrap ${mode === "text" ? "textarea-wrap" : ""}`}>
        {mode === "url" ? <Globe2 size={19} /> : mode === "text" ? <BookOpen size={19} /> : <Search size={19} />}
        {mode === "text" ? (
          <textarea
            id="verification-input"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={placeholder}
            rows={4}
          />
        ) : (
          <input
            id="verification-input"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && submit()}
            placeholder={placeholder}
          />
        )}
        {value && (
          <button className="clear-input" onClick={() => setValue("")} aria-label="Clear input">
            <X size={16} />
          </button>
        )}
      </div>
      <div className="verify-actions">
        <div className="input-note-wrap">
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.p
                key="loading-note"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2, ease: EASE_OUT }}
                className="input-note"
                role="status"
                aria-live="polite"
              >
                <Search size={14} className="spinning-icon" /> {stage}… <span>stage {stageIndex + 1} of {stageCount}</span>
              </motion.p>
            ) : (
              <motion.p
                key="idle-note"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2, ease: EASE_OUT }}
                className="input-note"
              >
                <CircleHelp size={14} /> We compare retrieved evidence — not just model memory.
              </motion.p>
            )}
          </AnimatePresence>
        </div>
        <motion.button
          whileHover={loading ? {} : buttonMotion.whileHover}
          whileTap={loading ? {} : buttonMotion.whileTap}
          transition={buttonMotion.transition}
          className="button button-primary"
          onClick={submit}
          disabled={loading}
          aria-busy={loading}
        >
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.span
                key="verifying-text"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15, ease: EASE_OUT }}
                className="btn-content-wrap"
              >
                Verifying…
              </motion.span>
            ) : (
              <motion.span
                key="idle-text"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15, ease: EASE_OUT }}
                className="btn-content-wrap"
              >
                Verify {mode === "claim" ? "claim" : "source"}
                <ChevronRight size={16} className="btn-arrow" />
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
      </div>
      <div className="examples-row">
        <span>Try an example</span>
        {examples.map((example, index) => (
          <motion.button
            key={example}
            whileHover={chipMotion.whileHover}
            whileTap={chipMotion.whileTap}
            transition={chipMotion.transition}
            onClick={() => useExample(example)}
            className="example-chip"
          >
            {index + 1}. “{example.slice(0, 37)}…”
          </motion.button>
        ))}
      </div>
    </TiltCard>
  );
}

function ProcessSection() {
  const steps = [
    ["01", "Input", "Submit an article, a URL, or one specific claim.", <TextCursorInput key="step-1" />],
    ["02", "Search", "Find relevant reporting, fact-checks, and primary sources.", <Search key="step-2" />],
    ["03", "Compare", "Separate independent evidence from syndicated repetition.", <Fingerprint key="step-3" />],
    ["04", "Verify", "Get an explainable report with a deterministic score.", <ShieldCheck key="step-4" />],
  ];
  return (
    <motion.section
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-60px" }}
      variants={staggerContainerVariants}
      className="process-section"
      id="process"
    >
      <div className="ambient-glow-wrap" aria-hidden="true">
        <span className="ambient-orb ambient-orb-1" />
        <span className="ambient-orb ambient-orb-2" />
      </div>
      <div className="bg-oversized-text" aria-hidden="true">EVIDENCE</div>
      <div className="container">
        <motion.div variants={sectionRevealVariants} className="section-heading split-heading">
          <div>
            <span className="eyebrow">The investigation loop</span>
            <h2>From headline<br /><em>to evidence.</em></h2>
          </div>
          <p>VeriFact turns a fast-moving story into a structured trail of evidence you can inspect, challenge, and share.</p>
        </motion.div>
        <div className="process-grid">
          {steps.map(([number, title, description, icon], index) => (
            <TiltCard
              key={`process-step-${index}`}
              variants={cardRevealVariants}
              maxTilt={3.0}
              className="process-step"
            >
              <div className="process-step-top">
                <span className="step-number">{number}</span>
                <span className="step-icon">{icon}</span>
              </div>
              <h3>{title}</h3>
              <p>{description}</p>
            </TiltCard>
          ))}
        </div>
      </div>
    </motion.section>
  );
}

function PrinciplesSection() {
  return (
    <motion.section
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-60px" }}
      variants={staggerContainerVariants}
      className="principles-section"
      id="principles"
    >
      <div className="bg-oversized-text" aria-hidden="true">PRINCIPLES</div>
      <div className="container principles-inner">
        <motion.div variants={sectionRevealVariants} className="principles-copy">
          <span className="eyebrow eyebrow-light">What we believe</span>
          <h2>Good verification<br />shows its work.</h2>
          <p>There is no single “truth detector.” There is only a clear account of what was checked, which sources agree, what conflicts, and what is still unknown.</p>
          <motion.button
            whileHover={buttonMotion.whileHover}
            whileTap={buttonMotion.whileTap}
            transition={buttonMotion.transition}
            className="button button-ghost-light"
            onClick={() => toast.info("Methodology details are coming soon.")}
          >
            Read our methodology <ArrowUpRight size={15} />
          </motion.button>
        </motion.div>
        <div className="principles-list">
          {[
            { num: "01", title: "Independent sources", text: "Syndicated copies are clustered so repetition does not masquerade as corroboration." },
            { num: "02", title: "Primary evidence", text: "Official documents and direct records are weighted when they are available." },
            { num: "03", title: "Visible uncertainty", text: "Mixed, contradicted, and insufficient evidence remain distinct outcomes." },
          ].map((item, i) => (
            <motion.div variants={cardRevealVariants} className="principle-item" key={`principle-${i}`}>
              <span>{item.num}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.section>
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
        <motion.section
          variants={heroContainerVariants}
          initial="hidden"
          animate="visible"
          className="hero-section"
        >
          <div className="ambient-glow-wrap" aria-hidden="true">
            <span className="ambient-orb ambient-orb-1" />
            <span className="ambient-orb ambient-orb-2" />
          </div>
          <div className="bg-oversized-text" aria-hidden="true">VERIFACT</div>
          <div className="hero-grid" aria-hidden="true">
            <span /><span /><span /><span /><span /><span />
          </div>
          <div className="container hero-inner">
            <motion.div variants={heroKickerVariants} className="hero-kicker">
              <span className="live-dot" /> Independent evidence, clearly explained
            </motion.div>
            <motion.div variants={heroHeadingVariants} className="hero-copy">
              <h1>Know what <em>the evidence says.</em></h1>
              <p>Verify news claims using independent sources, fact-checks, and primary evidence — not just AI predictions.</p>
            </motion.div>
            <VerificationInput
              onVerify={verify}
              loading={verification.loading}
              stage={verification.stage}
              stageIndex={verification.stageIndex}
              stageCount={verification.stageCount}
            />
            <motion.div variants={heroFootnoteVariants} className="hero-footnote">
              <span><Check size={14} /> Designed for careful readers</span>
              <span><Check size={14} /> No black-box verdicts</span>
              <span><Check size={14} /> Sources you can open</span>
            </motion.div>
          </div>
        </motion.section>
        <motion.section
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-40px" }}
          variants={sectionRevealVariants}
          className="signal-section"
        >
          <div className="container signal-inner">
            <div className="signal-label"><Sparkles size={16} /> A better signal</div>
            <p>“Credibility” is not a feeling. It is a score built from source quality, evidence agreement, independent reporting, and transparent gaps.</p>
            <Link href="/analyze/demo" className="inline-link">
              See a sample report <ArrowUpRight size={15} />
            </Link>
          </div>
        </motion.section>
        <ProcessSection />
        <PrinciplesSection />
      </main>
      <footer className="site-footer">
        <div className="container footer-inner">
          <BrandMark />
          <span>Evidence before certainty.</span>
          <span>© 2026 VeriFact</span>
        </div>
      </footer>
    </div>
  );
}
