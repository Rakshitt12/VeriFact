import { useState } from "react";
import { Link, useLocation } from "wouter";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CloudLightning,
  ExternalLink,
  FlaskConical,
  Menu,
  Swords,
  User,
  X,
} from "lucide-react";
import { fakeNewsItems, type FakeNewsItem } from "@/data/fakeNews";
import { cardRevealVariants, sectionRevealVariants, staggerContainerVariants, EASE_OUT } from "@/lib/motion";

/* ─────────────────────── types ──────────────────────────────── */

type Category = FakeNewsItem["category"] | "all";

/* ─────────────────────── category config ───────────────────── */

const CATEGORIES: { value: Category; label: string; icon: React.ReactNode }[] = [
  { value: "all", label: "All", icon: <AlertTriangle size={14} /> },
  { value: "conflict-misinformation", label: "Conflict", icon: <Swords size={14} /> },
  { value: "disaster-misinformation", label: "Disaster", icon: <CloudLightning size={14} /> },
  { value: "celebrity-hoax", label: "Celebrity", icon: <User size={14} /> },
  { value: "scam-deepfake", label: "Deepfake", icon: <Bot size={14} /> },
  { value: "science-myth", label: "Science", icon: <FlaskConical size={14} /> },
];

const CATEGORY_LABELS: Record<FakeNewsItem["category"], string> = {
  "conflict-misinformation": "Conflict",
  "disaster-misinformation": "Disaster",
  "celebrity-hoax": "Celebrity Hoax",
  "scam-deepfake": "Deepfake Scam",
  "science-myth": "Science Myth",
};

function getCategoryIcon(category: FakeNewsItem["category"]) {
  switch (category) {
    case "conflict-misinformation": return <Swords size={13} />;
    case "disaster-misinformation": return <CloudLightning size={13} />;
    case "celebrity-hoax": return <User size={13} />;
    case "scam-deepfake": return <Bot size={13} />;
    case "science-myth": return <FlaskConical size={13} />;
  }
}

function formatDate(raw: string) {
  if (raw === "evergreen") return "Evergreen";
  const d = new Date(raw);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/* ─────────────────────── shared brand + header ─────────────── */

function BrandMark() {
  return (
    <Link href="/" className="brand-mark" aria-label="VeriFact home">
      <span className="brand-glyph"><span /></span>
      <span>verifact</span>
    </Link>
  );
}

function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [location] = useLocation();

  return (
    <header className="site-header">
      <div className="container nav-inner">
        <BrandMark />
        <nav className={`main-nav ${menuOpen ? "is-open" : ""}`} aria-label="Primary navigation">
          <Link
            href="/"
            className={`nav-link ${location === "/" ? "nav-link-active" : ""}`}
          >
            Verify
          </Link>
          <Link
            href="/fake-news"
            className={`nav-link ${location === "/fake-news" ? "nav-link-active" : ""}`}
          >
            Top Fake News
          </Link>
        </nav>
        <div className="nav-actions">
          <button
            className="menu-toggle"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Toggle navigation"
          >
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  );
}

/* ─────────────────────── card ───────────────────────────────── */

function FakeNewsCard({ item }: { item: FakeNewsItem }) {
  return (
    <motion.a
      variants={cardRevealVariants}
      href={item.sourceUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="fact-check-card process-step interactive-card"
      style={{ textDecoration: "none", display: "block" }}
      aria-label={`Read debunk: ${item.claim}`}
    >
      {/* category badge */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
        <span
          className="status-badge"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            background: "var(--accent)",
            color: "var(--accent-foreground)",
            borderRadius: "99px",
            padding: "5px 9px",
            fontSize: "10px",
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: ".05em",
          }}
        >
          {getCategoryIcon(item.category)}
          {CATEGORY_LABELS[item.category]}
        </span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            color: "var(--primary)",
            fontSize: "10px",
            fontWeight: 800,
            textTransform: "uppercase",
            letterSpacing: ".06em",
          }}
        >
          Debunked
        </span>
      </div>

      {/* claim */}
      <p
        className="fact-check-value"
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: "17px",
          fontWeight: 570,
          letterSpacing: "-.035em",
          lineHeight: 1.2,
          marginBottom: "10px",
          color: "var(--card-foreground)",
        }}
      >
        "{item.claim}"
      </p>

      {/* excerpt */}
      <p
        style={{
          color: "var(--muted-foreground)",
          fontSize: "13px",
          lineHeight: 1.6,
          margin: "0 0 16px",
        }}
      >
        {item.excerpt}
      </p>

      {/* footer row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid var(--border)",
          paddingTop: "12px",
          gap: "10px",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            color: "var(--muted-foreground)",
            fontSize: "11px",
            fontWeight: 700,
          }}
        >
          <ExternalLink size={12} style={{ color: "var(--accent-foreground)" }} />
          {item.sourceName}
        </span>
        <span
          style={{
            color: "var(--muted-foreground)",
            fontSize: "10px",
            letterSpacing: ".02em",
          }}
        >
          {formatDate(item.dateFlagged)}
        </span>
      </div>

      {/* hover arrow */}
      <div
        className="card-link-icon"
        style={{
          position: "absolute",
          top: "22px",
          right: "22px",
          color: "var(--muted-foreground)",
        }}
        aria-hidden="true"
      >
        <ArrowUpRight size={16} />
      </div>
    </motion.a>
  );
}

/* ─────────────────────── filter tabs ───────────────────────── */

function CategoryTabs({
  active,
  onChange,
}: {
  active: Category;
  onChange: (c: Category) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Filter by category"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "4px",
        flexWrap: "wrap",
        borderBottom: "1px solid var(--border)",
        marginBottom: "36px",
        paddingBottom: "0",
      }}
    >
      {CATEGORIES.map(({ value, label, icon }) => {
        const isActive = active === value;
        return (
          <button
            key={value}
            role="tab"
            aria-selected={isActive}
            className={`input-tab ${isActive ? "active" : ""}`}
            onClick={() => onChange(value)}
            style={{ position: "relative" }}
          >
            {icon}
            <span>{label}</span>
            {isActive && (
              <motion.span
                layoutId="fnActiveTabUnderline"
                className="input-tab-indicator"
                transition={{ type: "spring", stiffness: 380, damping: 34 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ─────────────────────── page ───────────────────────────────── */

export default function FakeNews() {
  const [activeCategory, setActiveCategory] = useState<Category>("all");

  const filtered =
    activeCategory === "all"
      ? fakeNewsItems
      : fakeNewsItems.filter((item) => item.category === activeCategory);

  return (
    <div className="app-shell">
      <Header />
      <main>
        <motion.section
          className="process-section"
          style={{ paddingTop: "72px", paddingBottom: "96px" }}
          initial="hidden"
          animate="visible"
          variants={staggerContainerVariants}
        >
          {/* ambient glows */}
          <div className="ambient-glow-wrap" aria-hidden="true">
            <span className="ambient-orb ambient-orb-1" />
            <span className="ambient-orb ambient-orb-2" />
          </div>
          <div className="bg-oversized-text" aria-hidden="true">DEBUNKED</div>

          <div className="container">
            {/* heading */}
            <motion.div variants={sectionRevealVariants} className="section-heading split-heading">
              <div>
                <span className="eyebrow">Curated misinformation feed</span>
                <h2 style={{ marginTop: "14px" }}>
                  Top <em>Fake News</em>
                </h2>
              </div>
              <p style={{ maxWidth: "340px", color: "var(--muted-foreground)", lineHeight: 1.6, fontSize: "14px", margin: 0 }}>
                Every entry is verified and linked to the original fact-check source. Click any card to read the full debunk.
              </p>
            </motion.div>

            {/* filter tabs */}
            <CategoryTabs active={activeCategory} onChange={setActiveCategory} />

            {/* grid */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeCategory}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.22, ease: EASE_OUT }}
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 340px), 1fr))",
                  gap: "20px",
                }}
              >
                {filtered.map((item) => (
                  <FakeNewsCard key={item.id} item={item} />
                ))}
              </motion.div>
            </AnimatePresence>

            {filtered.length === 0 && (
              <p style={{ color: "var(--muted-foreground)", textAlign: "center", paddingTop: "48px" }}>
                No items in this category yet.
              </p>
            )}
          </div>
        </motion.section>
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
