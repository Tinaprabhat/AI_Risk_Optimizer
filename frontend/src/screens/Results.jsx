import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAudit } from "../context/AuditContext";

const LAYER_MAP = [
  { name: "Layer 1 — Crawlability",        codes: ["R1","R3","R5","R6"],         icon: "🤖" },
  { name: "Layer 2 — Structured Data",     codes: ["R7","R9","R11"],             icon: "📋" },
  { name: "Layer 3 — Semantic Content",    codes: ["R13","R15","R16","R17"],      icon: "💬" },
  { name: "Layer 4 — Trust Signals",       codes: ["R23","R25"],                 icon: "🛡" },
  { name: "Layer 5 — AI-Era Protocols",    codes: ["R28","R30","R31"],           icon: "⚡" },
];

const STATUS_COLOR = {
  PASS:          "#22c55e",
  FAIL:          "#ef4444",
  WARN:          "#eab308",
  UNKNOWN:       "#64748b",
  INFORMATIONAL: "#7c6af7",
};

const STATUS_BG = {
  PASS:          "rgba(34,197,94,0.08)",
  FAIL:          "rgba(239,68,68,0.08)",
  WARN:          "rgba(234,179,8,0.08)",
  UNKNOWN:       "rgba(100,116,139,0.08)",
  INFORMATIONAL: "rgba(124,106,247,0.08)",
};

const STATUS_ICON = {
  PASS:          "✓",
  FAIL:          "✗",
  WARN:          "⚠",
  UNKNOWN:       "?",
  INFORMATIONAL: "ℹ",
};

function ScoreGauge({ pct }) {
  const color = pct >= 70 ? "#22c55e" : pct >= 45 ? "#eab308" : "#ef4444";
  const label = pct >= 70 ? "Good" : pct >= 45 ? "Average" : "Poor";
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div style={gauge.wrap}>
      <svg width="140" height="140" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="70" cy="70" r="54" fill="none" stroke="#1c1c28" strokeWidth="10" />
        <circle
          cx="70" cy="70" r="54"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1s ease" }}
        />
      </svg>
      <div style={gauge.center}>
        <span style={{ ...gauge.pct, color }}>{pct}%</span>
        <span style={{ ...gauge.label, color }}>{label}</span>
      </div>
    </div>
  );
}

const gauge = {
  wrap: {
    position: "relative",
    width: 140,
    height: 140,
    flexShrink: 0,
  },
  center: {
    position: "absolute",
    inset: 0,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
  },
  pct: {
    fontSize: 28,
    fontWeight: 800,
    lineHeight: 1,
  },
  label: {
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
};

function RuleCard({ code, check, maxScore}) {
  const [open, setOpen] = useState(false);
  const status  = check.status || "UNKNOWN";
  const color   = STATUS_COLOR[status] || "#64748b";
  const bg      = STATUS_BG[status]    || "rgba(100,116,139,0.08)";
  const icon    = STATUS_ICON[status]  || "?";
  const isInfo  = status === "INFORMATIONAL";

  return (
    <div
      style={{
        ...rule.card,
        borderColor: open ? color : "#2a2a3d",
        background:  open ? bg    : "#13131a",
      }}
    >
      {/* Header row — always visible */}
      <div style={rule.header} onClick={() => setOpen((p) => !p)}>
        <div style={{ ...rule.badge, background: bg, color }}>
          <span>{icon}</span>
          <span>{code}</span>
        </div>
        <div style={rule.meta}>
          <span style={rule.detail}>{check.detail || "No detail"}</span>
          {!isInfo && (
            <div style={rule.scoreWrap} title={maxScore === 10 ? "AI readiness score for this check" : ""}>
                <div style={rule.scoreBar}>
                <div style={{
                    ...rule.scoreBarFill,
                    width: `${maxScore ? (check.score / maxScore) * 100 : 0}%`,
                    background: color,
                }} />
                </div>
                <span style={{ ...rule.scorePill, color, background: bg }}>
                {maxScore === 1
                    ? check.status === "PASS"
                        ? "Passed"
                        : check.status === "WARN"
                        ? "Warning"
                        : "Failed"
                    : `${check.score}/${maxScore}`}
                </span>
            </div>
            )}
          {isInfo && (
            <span style={{ ...rule.scorePill, color: "#7c6af7", background: "rgba(124,106,247,0.1)" }}>
              INFO
            </span>
          )}
        </div>
        <span style={{ ...rule.chevron, color }}>
          {open ? "▲" : "▼"}
        </span>
      </div>

      {/* Expanded evidence + fix */}
      {open && (
        <div style={rule.body}>
          {check.raw_evidence && check.raw_evidence !== "(not recorded)" && (
            <div style={rule.section}>
              <span style={rule.sectionLabel}>Evidence</span>
              <pre style={rule.pre}>{check.raw_evidence}</pre>
            </div>
          )}
          {check.what_AI_sees && check.what_AI_sees !== "(not recorded)" && (
            <div style={rule.section}>
              <span style={rule.sectionLabel}>What AI sees</span>
              <p style={rule.text}>{check.what_AI_sees}</p>
            </div>
          )}
          {check.fix && (
            <div style={{ ...rule.section, ...rule.fixSection }}>
              <span style={rule.sectionLabel}>Fix</span>
              <pre style={rule.fixPre}>{check.fix}</pre>
            </div>
          )}
          {check.tier && (
            <span style={rule.tier}>Tier: {check.tier}</span>
          )}
        </div>
      )}
    </div>
  );
}

const rule = {

  scoreWrap: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexShrink: 0,
    },
    scoreBar: {
    width: 60,
    height: 4,
    background: "#2a2a3d",
    borderRadius: 999,
    overflow: "hidden",
    },
    scoreBarFill: {
    height: "100%",
    borderRadius: 999,
    transition: "width 0.5s ease",
    },
  card: {
    border: "1px solid #2a2a3d",
    borderRadius: 12,
    overflow: "hidden",
    transition: "border-color 0.2s, background 0.2s",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 16px",
    cursor: "pointer",
    userSelect: "none",
  },
  badge: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    borderRadius: 6,
    padding: "4px 10px",
    fontSize: 12,
    fontWeight: 700,
    flexShrink: 0,
  },
  meta: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    minWidth: 0,
  },
  detail: {
    fontSize: 13,
    color: "#94a3b8",
    flex: 1,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  scorePill: {
    fontSize: 11,
    fontWeight: 700,
    borderRadius: 999,
    padding: "2px 8px",
    flexShrink: 0,
  },
  chevron: {
    fontSize: 10,
    flexShrink: 0,
  },
  body: {
    padding: "0 16px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 12,
    borderTop: "1px solid #1c1c28",
    paddingTop: 12,
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  fixSection: {
    background: "rgba(124,106,247,0.04)",
    border: "1px solid rgba(124,106,247,0.15)",
    borderRadius: 8,
    padding: 12,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  pre: {
    fontSize: 12,
    color: "#94a3b8",
    background: "#0a0a0f",
    borderRadius: 6,
    padding: "8px 12px",
    overflowX: "auto",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    margin: 0,
    lineHeight: 1.6,
  },
  fixPre: {
    fontSize: 12,
    color: "#a78bfa",
    background: "transparent",
    borderRadius: 6,
    padding: 0,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    margin: 0,
    lineHeight: 1.7,
  },
  text: {
    fontSize: 13,
    color: "#94a3b8",
    lineHeight: 1.6,
    margin: 0,
  },
  tier: {
    fontSize: 11,
    color: "#64748b",
    fontStyle: "italic",
  },
};

export default function Results() {
  const { auditResult, storeUrl } = useAudit();
  const navigate = useNavigate();

  useEffect(() => {
    if (!auditResult) navigate("/");
}, [auditResult]);

if (!auditResult) return null;

  const { score, checks, conclusion, llm_source, gap } = auditResult;
  const isFromCache = auditResult.from_cache || false;

  return (
    <div style={styles.page}>
      <div style={styles.grid} />

      <div style={styles.container}>
        {/* Top bar */}
        <div style={styles.topBar}>
          <button style={styles.backBtn} onClick={() => navigate("/")}>
            ← New Audit
          </button>
          <div style={styles.urlBadge}>
            <span style={styles.urlDot} />
            {storeUrl}
          </div>
        </div>

        {/* Score hero */}
        <div style={styles.hero}>
          <ScoreGauge pct={score.pct} />
          <div style={styles.heroText}>
            <h1 style={styles.h1}>AI Readiness Score</h1>
            <div style={styles.scoreBreakdown}>
              <div style={styles.scorePart}>
                <span style={styles.scoreVal}>{score.scored_total}</span>
                <span style={styles.scoreMax}>/ {score.max_scored}</span>
                <span style={styles.scoreDesc}>Scored checks</span>
              </div>
              <div style={styles.scoreDivider} />
              <div style={styles.scorePart}>
                <span style={styles.scoreVal}>{score.checklist_total}</span>
                <span style={styles.scoreMax}>/ {score.max_checklist}</span>
                <span style={styles.scoreDesc}>Checklist</span>
              </div>
              <div style={styles.scoreDivider} />
              <div style={styles.scorePart}>
                <span style={styles.scoreVal}>{score.grand_total}</span>
                <span style={styles.scoreMax}>/ {score.max_total}</span>
                <span style={styles.scoreDesc}>Total</span>
              </div>
            </div>
          </div>
        </div>

        {/* AI Conclusion */}
        <div style={styles.conclusionBox}>
          <div style={styles.conclusionHeader}>
            <span style={styles.conclusionIcon}>🧠</span>
            <span style={styles.conclusionTitle}>AI Conclusion</span>
            <span style={styles.conclusionSource}>via {llm_source}</span>
          </div>
          <p style={styles.conclusionText}>{conclusion}</p>
        </div>

        {/* Layer-by-layer checks */}
        <div style={styles.layers}>
          {LAYER_MAP.map((layer) => {
            const layerChecks = layer.codes.filter((c) => checks[c]);
            const nonInfo = layerChecks.filter((c) => checks[c].status !== "INFORMATIONAL");
            const passed  = nonInfo.filter((c) => checks[c].status === "PASS").length;
            const total   = nonInfo.length;

            return (
              <div key={layer.name} style={styles.layerBlock}>
                <div style={styles.layerHeader}>
                  <span style={styles.layerIcon}>{layer.icon}</span>
                  <span style={styles.layerName}>{layer.name}</span>
                  <span style={{
                    ...styles.layerScore,
                    color: passed === total ? "#22c55e" : passed === 0 ? "#ef4444" : "#eab308",
                  }}>
                    {passed}/{total} passed
                  </span>
                </div>
                <div style={styles.ruleList}>
                  {layer.codes.map((code) =>
                    checks[code] ? (
                        <RuleCard
                        key={code}
                        code={code}
                        check={checks[code]}
                        maxScore={score.breakdown?.[code]?.max}
                        />
                    ) : null
                    )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom action buttons */}
        <div style={styles.actions}>
          <button
            style={styles.mirrorBtn}
            onClick={() => navigate("/mirror")}
          >
            🪞 AI Mirror
          </button>
          <button
            style={styles.fixBtn}
            onClick={() => navigate("/fix")}
          >
            🔧 Fix Now
          </button>
        </div>
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
    gap: 28,
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
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#7c6af7",
    flexShrink: 0,
    boxShadow: "0 0 6px #7c6af7",
  },
  hero: {
    display: "flex",
    alignItems: "center",
    gap: 28,
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 16,
    padding: "28px 32px",
    flexWrap: "wrap",
  },
  heroText: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    gap: 16,
    minWidth: 200,
  },
  h1: {
    fontSize: 22,
    fontWeight: 800,
    color: "#e2e8f0",
    letterSpacing: "-0.02em",
    margin: 0,
  },
  scoreBreakdown: {
    display: "flex",
    alignItems: "center",
    gap: 20,
    flexWrap: "wrap",
  },
  scorePart: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  scoreVal: {
    fontSize: 26,
    fontWeight: 800,
    color: "#e2e8f0",
    lineHeight: 1,
  },
  scoreMax: {
    fontSize: 13,
    color: "#64748b",
    marginTop: 2,
  },
  scoreDesc: {
    fontSize: 11,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  scoreDivider: {
    width: 1,
    height: 36,
    background: "#2a2a3d",
  },
  conclusionBox: {
    background: "#13131a",
    border: "1px solid rgba(124,106,247,0.25)",
    borderRadius: 14,
    padding: "20px 24px",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  conclusionHeader: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  conclusionIcon: { fontSize: 18 },
  conclusionTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: "#e2e8f0",
    flex: 1,
  },
  conclusionSource: {
    fontSize: 11,
    color: "#64748b",
    fontStyle: "italic",
  },
  conclusionText: {
    fontSize: 14,
    color: "#94a3b8",
    lineHeight: 1.75,
    margin: 0,
  },
  layers: {
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  layerBlock: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  layerHeader: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "0 4px",
  },
  layerIcon: { fontSize: 16 },
  layerName: {
    fontSize: 14,
    fontWeight: 700,
    color: "#e2e8f0",
    flex: 1,
  },
  layerScore: {
    fontSize: 12,
    fontWeight: 600,
  },
  ruleList: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  actions: {
    display: "flex",
    gap: 14,
    position: "sticky",
    bottom: 20,
    zIndex: 10,
  },
  mirrorBtn: {
    flex: 1,
    background: "#13131a",
    border: "1px solid rgba(124,106,247,0.4)",
    borderRadius: 12,
    color: "#a78bfa",
    padding: "16px",
    fontSize: 15,
    fontWeight: 700,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  fixBtn: {
    flex: 1,
    background: "linear-gradient(135deg, #7c6af7, #6d5de6)",
    border: "none",
    borderRadius: 12,
    color: "#fff",
    padding: "16px",
    fontSize: 15,
    fontWeight: 700,
    cursor: "pointer",
    transition: "opacity 0.2s",
  },
};