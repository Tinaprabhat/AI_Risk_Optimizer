import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAudit } from "../context/AuditContext";

const GAP_COLOR = {
  ALIGNED:    { color: "#22c55e", bg: "rgba(34,197,94,0.08)",    border: "rgba(34,197,94,0.2)"    },
  DRIFT:      { color: "#eab308", bg: "rgba(234,179,8,0.08)",    border: "rgba(234,179,8,0.2)"    },
  MISALIGNED: { color: "#ef4444", bg: "rgba(239,68,68,0.08)",    border: "rgba(239,68,68,0.2)"    },
  UNKNOWN:    { color: "#64748b", bg: "rgba(100,116,139,0.08)",  border: "rgba(100,116,139,0.2)"  },
};

const GAP_ICON = {
  ALIGNED:    "✓",
  DRIFT:      "⚠",
  MISALIGNED: "✗",
  UNKNOWN:    "?",
};

const GAP_DESC = {
  ALIGNED:    "Well aligned — AI understands your store correctly",
  DRIFT:      "Minor drift — small differences in how AI reads your store",
  MISALIGNED: "Misaligned — AI sees your store differently than you intend",
  UNKNOWN:    "Could not compute",
};

function GapBadge({ label }) {
  const c = GAP_COLOR[label] || GAP_COLOR.UNKNOWN;
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 5,
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: 999,
      padding: "3px 10px",
      fontSize: 11,
      fontWeight: 700,
      color: c.color,
      letterSpacing: "0.04em",
    }}>
      {GAP_ICON[label]} {label}
    </span>
  );
}

function GapBar({ value, label }) {
  if (value === null || value === undefined) return null;
  const c      = GAP_COLOR[label] || GAP_COLOR.UNKNOWN;
  const pct    = Math.min(value * 200, 100); // 0.5 gap = 100% bar
  return (
    <div style={bar.wrap}>
      <div style={bar.track}>
        <div style={{
          ...bar.fill,
          width: `${pct}%`,
          background: c.color,
        }} />
      </div>
      <span style={{ ...bar.val, color: c.color }}>{value}</span>
    </div>
  );
}

const bar = {
  wrap:  { display: "flex", alignItems: "center", gap: 10 },
  track: { flex: 1, height: 5, background: "#1c1c28", borderRadius: 999, overflow: "hidden" },
  fill:  { height: "100%", borderRadius: 999, transition: "width 0.6s ease" },
  val:   { fontSize: 12, fontWeight: 700, flexShrink: 0, minWidth: 36 },
};

function PerceptionCard({ icon, title, subtitle, text, source }) {
  const isFallback = source === "CRAWLED_FALLBACK";
  return (
    <div style={card.wrap}>
      <div style={card.header}>
        <span style={card.icon}>{icon}</span>
        <div style={card.headerText}>
          <span style={card.title}>{title}</span>
          <span style={card.subtitle}>{subtitle}</span>
        </div>
        {isFallback && (
          <span style={card.fallbackBadge}>No JSON-LD — crawled text used</span>
        )}
      </div>
      <div style={card.body}>
        {text
          ? <p style={card.text}>{text}</p>
          : <p style={card.empty}>Could not extract text for this perception.</p>
        }
      </div>
    </div>
  );
}

const card = {
  wrap: {
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 14,
    overflow: "hidden",
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    gap: 12,
    padding: "16px 20px",
    borderBottom: "1px solid #1c1c28",
    background: "#0f0f16",
  },
  icon: { fontSize: 22, flexShrink: 0, marginTop: 2 },
  headerText: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    gap: 3,
  },
  title: { fontSize: 15, fontWeight: 700, color: "#e2e8f0" },
  subtitle: { fontSize: 12, color: "#64748b" },
  fallbackBadge: {
    fontSize: 10,
    color: "#eab308",
    background: "rgba(234,179,8,0.08)",
    border: "1px solid rgba(234,179,8,0.2)",
    borderRadius: 6,
    padding: "3px 8px",
    flexShrink: 0,
    alignSelf: "center",
  },
  body: { padding: "16px 20px" },
  text: {
    fontSize: 13,
    color: "#94a3b8",
    lineHeight: 1.75,
    margin: 0,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  empty: { fontSize: 13, color: "#64748b", fontStyle: "italic", margin: 0 },
};

export default function AiMirror() {
  const { auditResult, storeUrl } = useAudit();
  const navigate = useNavigate();

  useEffect(() => {
    if (!auditResult) navigate("/");
  }, [auditResult]);

  if (!auditResult) return null;

  const gap = auditResult.gap || {};

  const {
    intent_text, website_text, schema_text,
    gap_IW, gap_IS, gap_WS,
    IW_label, IS_label, WS_label,
    schema_source, matrix,
  } = gap;

  const overallLabel = (() => {
    const labels = [IW_label, IS_label, WS_label].filter(Boolean);
    if (labels.includes("MISALIGNED")) return "MISALIGNED";
    if (labels.includes("DRIFT"))      return "DRIFT";
    if (labels.includes("ALIGNED"))    return "ALIGNED";
    return "UNKNOWN";
  })();

  const overall = GAP_COLOR[overallLabel] || GAP_COLOR.UNKNOWN;

  return (
    <div style={styles.page}>
      <div style={styles.grid} />

      <div style={styles.container}>

        {/* Top bar */}
        <div style={styles.topBar}>
          <button style={styles.backBtn} onClick={() => navigate("/results")}>
            ← Back to Results
          </button>
          <div style={styles.urlBadge}>
            <span style={styles.urlDot} />
            {storeUrl}
          </div>
        </div>

        {/* Hero */}
        <div style={{ ...styles.hero, borderColor: overall.border, background: overall.bg }}>
          <div style={styles.heroLeft}>
            <span style={styles.mirrorEmoji}>🪞</span>
            <div>
              <h1 style={styles.h1}>AI Mirror</h1>
              <p style={styles.heroSub}>
                3 different "views" of your store — yours, your website's, and what AI reads.
                Gaps between them mean AI misunderstands your store.
              </p>
            </div>
          </div>
          <div style={{ ...styles.overallBadge, background: overall.bg, borderColor: overall.border }}>
            <span style={{ fontSize: 22 }}>{GAP_ICON[overallLabel]}</span>
            <span style={{ color: overall.color, fontWeight: 800, fontSize: 16 }}>{overallLabel}</span>
            <span style={{ color: "#64748b", fontSize: 12 }}>{GAP_DESC[overallLabel]}</span>
          </div>
        </div>

        {/* Gap scores */}
        <div style={styles.gapGrid}>
          {[
            {
              name: "Your Intent vs Website",
              question: "Does your website say what you think it says?",
              gap: gap_IW,
              label: IW_label,
            },
            {
              name: "Your Intent vs AI Data",
              question: "Does your structured data match your intent?",
              gap: gap_IS,
              label: IS_label,
            },
            {
              name: "Website vs AI Data",
              question: "Are your website and structured data consistent?",
              gap: gap_WS,
              label: WS_label,
            },
          ].map((g) => {
            const c = GAP_COLOR[g.label] || GAP_COLOR.UNKNOWN;
            return (
              <div key={g.name} style={{ ...styles.gapCard, borderColor: c.border }}>
                <span style={styles.gapName}>{g.name}</span>
                <span style={styles.gapQ}>{g.question}</span>
                <GapBar value={g.gap} label={g.label} />
                <GapBadge label={g.label} />
              </div>
            );
          })}
        </div>

        {/* 3 Perception cards */}
        <div style={styles.sectionLabel}>The 3 Perceptions</div>

        <PerceptionCard
          icon="🧑‍💼"
          title="Your Perception"
          subtitle="What YOU think your store says — based on your description and answers"
          text={intent_text}
          source={null}
        />

        <PerceptionCard
          icon="🌐"
          title="HTML Perception"
          subtitle="What AI reads from your actual website text when it crawls your pages"
          text={website_text}
          source={null}
        />

        <PerceptionCard
          icon="🤖"
          title="AI Perception"
          subtitle={
            schema_source === "CRAWLED_FALLBACK"
              ? "Built from crawled content — no JSON-LD schema found on your store"
              : "What AI reads from your structured data (JSON-LD schema)"
          }
          text={schema_text}
          source={schema_source}
        />

        {/* Dimension matrix */}
        {matrix && Object.keys(matrix).length > 0 && (
          <>
            <div style={styles.sectionLabel}>Dimension Gap Matrix</div>
            <div style={styles.matrixWrap}>
              <p style={styles.matrixDesc}>
                How well each aspect of your brand description aligns across your pages.
                Lower gap = better alignment.
              </p>
              <div style={styles.matrixTable}>
                {Object.entries(matrix).map(([dim, pages]) => (
                  <div key={dim} style={styles.matrixRow}>
                    <span style={styles.matrixDim}>{dim}</span>
                    <div style={styles.matrixCells}>
                      {Object.entries(pages).map(([page, entry]) => {
                        const c = GAP_COLOR[entry.label] || GAP_COLOR.UNKNOWN;
                        return (
                          <div
                            key={page}
                            style={{
                              ...styles.matrixCell,
                              background: c.bg,
                              borderColor: c.border,
                            }}
                            title={`${dim} on ${page}: gap=${entry.gap} (${entry.label})`}
                          >
                            <span style={{ color: c.color, fontSize: 11, fontWeight: 700 }}>
                              {entry.label?.slice(0, 3)}
                            </span>
                            <span style={{ color: c.color, fontSize: 10 }}>{entry.gap}</span>
                            <span style={{ color: "#64748b", fontSize: 10 }}>{page}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Bottom button */}
        <button
          style={styles.fixBtn}
          onClick={() => navigate("/fix")}
        >
          🔧 Fix Now — resolve these gaps
        </button>

      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#0a0a0f",
    position: "relative",
    padding: "32px 20px 60px",
  },
  grid: {
    position: "fixed",
    inset: 0,
    backgroundImage:
      "linear-gradient(rgba(124,106,247,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(124,106,247,0.03) 1px, transparent 1px)",
    backgroundSize: "40px 40px",
    pointerEvents: "none",
    zIndex: 0,
  },
  container: {
    position: "relative",
    zIndex: 1,
    maxWidth: 800,
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    flexWrap: "wrap",
  },
  backBtn: {
    background: "transparent",
    border: "1px solid #2a2a3d",
    borderRadius: 8,
    color: "#64748b",
    padding: "8px 14px",
    fontSize: 13,
    cursor: "pointer",
    flexShrink: 0,
  },
  urlBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    background: "rgba(124,106,247,0.08)",
    border: "1px solid rgba(124,106,247,0.18)",
    borderRadius: 999,
    padding: "5px 14px",
    fontSize: 12,
    color: "#a78bfa",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    maxWidth: 400,
  },
  urlDot: {
    width: 6, height: 6,
    borderRadius: "50%",
    background: "#7c6af7",
    flexShrink: 0,
    boxShadow: "0 0 6px #7c6af7",
  },
  hero: {
    display: "flex",
    alignItems: "flex-start",
    gap: 20,
    border: "1px solid",
    borderRadius: 16,
    padding: "24px 28px",
    flexWrap: "wrap",
  },
  heroLeft: {
    display: "flex",
    alignItems: "flex-start",
    gap: 16,
    flex: 1,
    minWidth: 200,
  },
  mirrorEmoji: { fontSize: 32, flexShrink: 0 },
  h1: {
    fontSize: 22,
    fontWeight: 800,
    color: "#e2e8f0",
    margin: "0 0 6px",
    letterSpacing: "-0.02em",
  },
  heroSub: {
    fontSize: 13,
    color: "#64748b",
    lineHeight: 1.65,
    margin: 0,
  },
  overallBadge: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 4,
    border: "1px solid",
    borderRadius: 12,
    padding: "16px 24px",
    flexShrink: 0,
    textAlign: "center",
  },
  gapGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: 12,
  },
  gapCard: {
    background: "#13131a",
    border: "1px solid",
    borderRadius: 12,
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  gapName: { fontSize: 13, fontWeight: 700, color: "#e2e8f0" },
  gapQ:    { fontSize: 12, color: "#64748b", lineHeight: 1.5 },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    paddingLeft: 4,
    marginTop: 8,
  },
  matrixWrap: {
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 14,
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  matrixDesc: {
    fontSize: 13,
    color: "#64748b",
    margin: 0,
    lineHeight: 1.6,
  },
  matrixTable: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  matrixRow: {
    display: "flex",
    alignItems: "center",
    gap: 14,
    flexWrap: "wrap",
  },
  matrixDim: {
    fontSize: 12,
    fontWeight: 600,
    color: "#94a3b8",
    width: 120,
    flexShrink: 0,
    textTransform: "capitalize",
  },
  matrixCells: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  matrixCell: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
    border: "1px solid",
    borderRadius: 8,
    padding: "8px 12px",
    minWidth: 70,
  },
  fixBtn: {
    background: "linear-gradient(135deg, #7c6af7, #6d5de6)",
    border: "none",
    borderRadius: 12,
    color: "#fff",
    padding: "18px",
    fontSize: 15,
    fontWeight: 700,
    cursor: "pointer",
    width: "100%",
    marginTop: 8,
  },
};