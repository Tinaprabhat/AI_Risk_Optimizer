import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAudit } from "../context/AuditContext";

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

const LAYER_OF = {
  R1: "Crawlability", R3: "Crawlability", R5: "Crawlability", R6: "Crawlability",
  R7: "Structured Data", R9: "Structured Data", R11: "Structured Data",
  R13: "Semantic Content", R15: "Semantic Content", R16: "Semantic Content", R17: "Semantic Content",
  R23: "Trust Signals", R25: "Trust Signals",
  R28: "AI-Era Protocols", R30: "AI-Era Protocols", R31: "AI-Era Protocols",
};

// Priority order — higher index = higher priority when failed
const PRIORITY = [
  "R1","R5","R6","R3","R11","R6",
  "R7","R9","R13","R16","R17",
  "R15","R23","R25","R28","R31",
];

function ScoreGauge({ pct }) {
  const color = pct >= 70 ? "#22c55e" : pct >= 45 ? "#eab308" : "#ef4444";
  const label = pct >= 70 ? "Good" : pct >= 45 ? "Average" : "Poor";
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (pct / 100) * circumference;
  return (
    <div style={gauge.wrap}>
      <svg width="140" height="140" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="70" cy="70" r="54" fill="none" stroke="#1c1c28" strokeWidth="10" />
        <circle cx="70" cy="70" r="54" fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
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
  wrap: { position: "relative", width: 140, height: 140, flexShrink: 0 },
  center: { position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2 },
  pct: { fontSize: 28, fontWeight: 800, lineHeight: 1 },
  label: { fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" },
};

// ── PRIORITY BANNER CARD ─────────────────────────────────────────────────────
function PriorityCard({ code, check, maxScore, rank }) {
  const [open, setOpen] = useState(false);
  const status = check.status;
  const color  = STATUS_COLOR[status];
  const bg     = STATUS_BG[status];

  const rankColors = ["#ef4444", "#f97316", "#eab308"];
  const rankLabels = ["#1 Priority", "#2 Priority", "#3 Priority"];

  return (
    <div style={{
      ...priority.card,
      borderColor: rankColors[rank],
      background: `${rankColors[rank]}08`,
    }}>
      {/* Rank badge */}
      <div style={{ ...priority.rankBadge, background: rankColors[rank] }}>
        {rankLabels[rank]}
      </div>

      {/* Header */}
      <div style={priority.header}>
        <div style={{ ...priority.codeBadge, background: bg, color }}>
          {STATUS_ICON[status]} {code}
        </div>
        <div style={priority.meta}>
          <span style={priority.layer}>{LAYER_OF[code]}</span>
          <span style={priority.detail}>{check.detail}</span>
        </div>
        <div style={priority.scoreWrap}>
          <div style={priority.scoreBar}>
            <div style={{
              ...priority.scoreBarFill,
              width: `${maxScore ? (check.score / maxScore) * 100 : 0}%`,
              background: color,
            }} />
          </div>
          <span style={{ ...priority.scorePill, color, background: bg }}>
            {maxScore === 1
              ? status === "PASS" ? "Passed" : status === "WARN" ? "Warning" : "Failed"
              : `Score: ${check.score}/${maxScore}`}
          </span>
        </div>
      </div>

      {/* Fix preview — always visible for top 3 */}
      {check.fix && (
        <div style={priority.fixPreview}>
          <span style={priority.fixLabel}>⚡ Quick Fix</span>
          <p style={priority.fixText}>{check.fix.split("\n")[0]}</p>
        </div>
      )}

      {/* Expandable evidence */}
      <button style={priority.expandBtn} onClick={() => setOpen(p => !p)}>
        {open ? "▲ Hide details" : "▼ Show evidence & full fix"}
      </button>

      {open && (
        <div style={priority.expandBody}>
          {check.raw_evidence && check.raw_evidence !== "(not recorded)" && (
            <div style={priority.section}>
              <span style={priority.sectionLabel}>Evidence</span>
              <pre style={priority.pre}>{check.raw_evidence}</pre>
            </div>
          )}
          {check.what_AI_sees && check.what_AI_sees !== "(not recorded)" && (
            <div style={priority.section}>
              <span style={priority.sectionLabel}>What AI sees</span>
              <p style={priority.text}>{check.what_AI_sees}</p>
            </div>
          )}
          {check.fix && (
            <div style={{ ...priority.section, ...priority.fixSection }}>
              <span style={priority.sectionLabel}>Full Fix</span>
              <pre style={priority.fixPre}>{check.fix}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const priority = {
  card: {
    border: "2px solid",
    borderRadius: 14,
    overflow: "hidden",
    position: "relative",
    paddingTop: 8,
  },
  rankBadge: {
    position: "absolute",
    top: 0, left: 0,
    fontSize: 10,
    fontWeight: 800,
    color: "#fff",
    padding: "3px 12px",
    borderBottomRightRadius: 8,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  },
  header: {
    display: "flex",
    alignItems: "flex-start",
    gap: 12,
    padding: "24px 16px 12px",
    flexWrap: "wrap",
  },
  codeBadge: {
    display: "flex", alignItems: "center", gap: 5,
    borderRadius: 6, padding: "5px 12px",
    fontSize: 13, fontWeight: 700, flexShrink: 0,
  },
  meta: { flex: 1, display: "flex", flexDirection: "column", gap: 4, minWidth: 0 },
  layer: { fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 },
  detail: { fontSize: 13, color: "#e2e8f0", lineHeight: 1.5 },
  scoreWrap: { display: "flex", alignItems: "center", gap: 8, flexShrink: 0 },
  scoreBar: { width: 60, height: 4, background: "#2a2a3d", borderRadius: 999, overflow: "hidden" },
  scoreBarFill: { height: "100%", borderRadius: 999, transition: "width 0.5s ease" },
  scorePill: { fontSize: 11, fontWeight: 700, borderRadius: 999, padding: "2px 8px" },
  fixPreview: {
    margin: "0 16px 12px",
    background: "rgba(124,106,247,0.06)",
    border: "1px solid rgba(124,106,247,0.15)",
    borderRadius: 8, padding: "10px 14px",
  },
  fixLabel: { fontSize: 11, fontWeight: 700, color: "#7c6af7", display: "block", marginBottom: 4 },
  fixText: { fontSize: 12, color: "#a78bfa", margin: 0, lineHeight: 1.6 },
  expandBtn: {
    width: "100%", background: "transparent",
    border: "none", borderTop: "1px solid #1c1c28",
    color: "#64748b", fontSize: 12, padding: "10px 16px",
    cursor: "pointer", textAlign: "left",
  },
  expandBody: { padding: "12px 16px 16px", display: "flex", flexDirection: "column", gap: 12 },
  section: { display: "flex", flexDirection: "column", gap: 6 },
  fixSection: {
    background: "rgba(124,106,247,0.04)",
    border: "1px solid rgba(124,106,247,0.15)",
    borderRadius: 8, padding: 12,
  },
  sectionLabel: { fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em" },
  pre: { fontSize: 12, color: "#94a3b8", background: "#0a0a0f", borderRadius: 6, padding: "8px 12px", overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, lineHeight: 1.6 },
  fixPre: { fontSize: 12, color: "#a78bfa", background: "transparent", padding: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, lineHeight: 1.7 },
  text: { fontSize: 13, color: "#94a3b8", lineHeight: 1.6, margin: 0 },
};

// ── BULLET RULE ROW ──────────────────────────────────────────────────────────
function BulletRule({ code, check, maxScore }) {
  const [open, setOpen] = useState(false);
  const status = check.status;
  const color  = STATUS_COLOR[status];
  const bg     = STATUS_BG[status];

  return (
    <div style={{
      ...bullet.row,
      borderColor: open ? color : "#2a2a3d",
      background: open ? bg : "#13131a",
    }}>
      <div style={bullet.header} onClick={() => setOpen(p => !p)}>
        <div style={{ ...bullet.badge, background: bg, color }}>
          {STATUS_ICON[status]} {code}
        </div>
        <span style={bullet.layer}>{LAYER_OF[code]}</span>
        <span style={bullet.detail}>{check.detail}</span>
        <div style={bullet.scoreWrap}>
          <div style={bullet.scoreBar}>
            <div style={{
              ...bullet.scoreBarFill,
              width: `${maxScore ? (check.score / maxScore) * 100 : 0}%`,
              background: color,
            }} />
          </div>
          <span style={{ ...bullet.scorePill, color, background: bg }}>
            {maxScore === 1
              ? status === "PASS" ? "Passed" : status === "WARN" ? "Warning" : "Failed"
              : `Score: ${check.score}/${maxScore}`}
          </span>
        </div>
        <span style={{ color, fontSize: 10 }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={bullet.body}>
          {check.raw_evidence && check.raw_evidence !== "(not recorded)" && (
            <div style={bullet.section}>
              <span style={bullet.sectionLabel}>Evidence</span>
              <pre style={bullet.pre}>{check.raw_evidence}</pre>
            </div>
          )}
          {check.what_AI_sees && check.what_AI_sees !== "(not recorded)" && (
            <div style={bullet.section}>
              <span style={bullet.sectionLabel}>What AI sees</span>
              <p style={bullet.text}>{check.what_AI_sees}</p>
            </div>
          )}
          {check.fix && (
            <div style={{ ...bullet.section, ...bullet.fixSection }}>
              <span style={bullet.sectionLabel}>Fix</span>
              <pre style={bullet.fixPre}>{check.fix}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const bullet = {
  row: { border: "1px solid", borderRadius: 10, overflow: "hidden", transition: "all 0.2s" },
  header: {
    display: "flex", alignItems: "center", gap: 10,
    padding: "10px 14px", cursor: "pointer", flexWrap: "wrap",
  },
  badge: { display: "flex", alignItems: "center", gap: 4, borderRadius: 6, padding: "3px 10px", fontSize: 12, fontWeight: 700, flexShrink: 0 },
  layer: { fontSize: 11, color: "#64748b", flexShrink: 0, textTransform: "uppercase", letterSpacing: "0.04em" },
  detail: { fontSize: 12, color: "#94a3b8", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  scoreWrap: { display: "flex", alignItems: "center", gap: 6, flexShrink: 0 },
  scoreBar: { width: 50, height: 3, background: "#2a2a3d", borderRadius: 999, overflow: "hidden" },
  scoreBarFill: { height: "100%", borderRadius: 999, transition: "width 0.5s ease" },
  scorePill: { fontSize: 10, fontWeight: 700, borderRadius: 999, padding: "2px 7px" },
  body: { padding: "0 14px 14px", display: "flex", flexDirection: "column", gap: 10, borderTop: "1px solid #1c1c28", paddingTop: 12 },
  section: { display: "flex", flexDirection: "column", gap: 5 },
  fixSection: { background: "rgba(124,106,247,0.04)", border: "1px solid rgba(124,106,247,0.15)", borderRadius: 8, padding: 10 },
  sectionLabel: { fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em" },
  pre: { fontSize: 11, color: "#94a3b8", background: "#0a0a0f", borderRadius: 6, padding: "6px 10px", overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, lineHeight: 1.6 },
  fixPre: { fontSize: 11, color: "#a78bfa", background: "transparent", padding: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, lineHeight: 1.7 },
  text: { fontSize: 12, color: "#94a3b8", lineHeight: 1.6, margin: 0 },
};

// ── PASSED RULE ROW ──────────────────────────────────────────────────────────
function PassedRule({ code, check, maxScore }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      ...passed.row,
      background: open ? "rgba(34,197,94,0.04)" : "#13131a",
      borderColor: open ? "rgba(34,197,94,0.25)" : "#2a2a3d",
    }}>
      <div style={passed.header} onClick={() => setOpen(p => !p)}>
        <div style={passed.badge}>✓ {code}</div>
        <span style={passed.layer}>{LAYER_OF[code]}</span>
        <span style={passed.detail}>{check.detail}</span>
        <span style={passed.pill}>
          {maxScore === 1 ? "Passed" : `Score: ${check.score}/${maxScore}`}
        </span>
        <span style={{ color: "#22c55e", fontSize: 10 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={passed.body}>
          {check.raw_evidence && check.raw_evidence !== "(not recorded)" && (
            <div style={passed.section}>
              <span style={passed.sectionLabel}>Evidence</span>
              <pre style={passed.pre}>{check.raw_evidence}</pre>
            </div>
          )}
          {check.what_AI_sees && check.what_AI_sees !== "(not recorded)" && (
            <div style={passed.section}>
              <span style={passed.sectionLabel}>What AI sees</span>
              <p style={passed.text}>{check.what_AI_sees}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const passed = {
  row: { border: "1px solid", borderRadius: 10, overflow: "hidden", transition: "all 0.2s" },
  header: { display: "flex", alignItems: "center", gap: 10, padding: "9px 14px", cursor: "pointer", flexWrap: "wrap" },
  badge: { fontSize: 11, fontWeight: 700, color: "#22c55e", background: "rgba(34,197,94,0.08)", borderRadius: 6, padding: "3px 10px", flexShrink: 0 },
  layer: { fontSize: 11, color: "#64748b", flexShrink: 0, textTransform: "uppercase", letterSpacing: "0.04em" },
  detail: { fontSize: 12, color: "#64748b", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  pill: { fontSize: 10, fontWeight: 700, color: "#22c55e", background: "rgba(34,197,94,0.08)", borderRadius: 999, padding: "2px 8px", flexShrink: 0 },
  body: { padding: "0 14px 12px", display: "flex", flexDirection: "column", gap: 8, borderTop: "1px solid #1c1c28", paddingTop: 10 },
  section: { display: "flex", flexDirection: "column", gap: 4 },
  sectionLabel: { fontSize: 10, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em" },
  pre: { fontSize: 11, color: "#94a3b8", background: "#0a0a0f", borderRadius: 6, padding: "6px 10px", overflowX: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, lineHeight: 1.5 },
  text: { fontSize: 12, color: "#64748b", lineHeight: 1.6, margin: 0 },
};

// ── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function Results() {
  const { auditResult, storeUrl } = useAudit();
  const navigate = useNavigate();
  const [passedOpen, setPassedOpen] = useState(false);

  useEffect(() => {
    if (!auditResult) navigate("/");
  }, [auditResult]);

  if (!auditResult) return null;

  const { score, checks, conclusion, llm_source } = auditResult;

  // Separate failed/warn from passed, skip INFORMATIONAL
  const failedCodes = Object.keys(checks).filter(
    (c) => ["FAIL", "WARN"].includes(checks[c].status)
  );
  const passedCodes = Object.keys(checks).filter(
    (c) => checks[c].status === "PASS"
  );

  // Sort failed by priority
  const sortedFailed = [...failedCodes].sort((a, b) => {
    const pa = PRIORITY.indexOf(a);
    const pb = PRIORITY.indexOf(b);
    // Also sort FAIL before WARN
    const sa = checks[a].status === "FAIL" ? 0 : 1;
    const sb = checks[b].status === "FAIL" ? 0 : 1;
    if (sa !== sb) return sa - sb;
    return (pa === -1 ? 99 : pa) > (pb === -1 ? 99 : pb) ? -1 : 1;
  });

  const top3    = sortedFailed.slice(0, 3);
  const restFailed = sortedFailed.slice(3);

  return (
    <div style={styles.page}>
      <div style={styles.grid} />

      <div style={styles.container}>

        {/* Top bar */}
        <div style={styles.topBar}>
          <button style={styles.backBtn} onClick={() => navigate("/")}>← New Audit</button>
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
              {[
                { val: score.scored_total,    max: score.max_scored,    label: "Scored checks" },
                { val: score.checklist_total, max: score.max_checklist, label: "Checklist" },
                { val: score.grand_total,     max: score.max_total,     label: "Total" },
              ].map((s, i) => (
                <>
                  {i > 0 && <div key={`d${i}`} style={styles.scoreDivider} />}
                  <div key={s.label} style={styles.scorePart}>
                    <span style={styles.scoreVal}>{s.val}</span>
                    <span style={styles.scoreMax}>/ {s.max}</span>
                    <span style={styles.scoreDesc}>{s.label}</span>
                  </div>
                </>
              ))}
            </div>
          </div>
        </div>

        {/* AI Conclusion */}
        <div style={styles.conclusionBox}>
          <div style={styles.conclusionHeader}>
            <span>🧠</span>
            <span style={styles.conclusionTitle}>AI Conclusion</span>
            <span style={styles.conclusionSource}>via {llm_source}</span>
          </div>
          <p style={styles.conclusionText}>{conclusion}</p>
        </div>

        {/* ── ISSUES SECTION ── */}
        {sortedFailed.length === 0 ? (
          <div style={styles.noIssues}>
            🎉 No failed checks — your store is well optimised for AI discovery!
          </div>
        ) : (
          <>
            <div style={styles.sectionHeader}>
              <span style={styles.sectionTitle}>
                ⚠ Issues Found
              </span>
              <span style={styles.sectionCount}>
                {sortedFailed.length} issue{sortedFailed.length !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Top 3 priority banners */}
            <div style={styles.priorityGrid}>
              {top3.map((code, i) => (
                <PriorityCard
                  key={code}
                  code={code}
                  check={checks[code]}
                  maxScore={score.breakdown?.[code]?.max}
                  rank={i}
                />
              ))}
            </div>

            {/* Remaining failed — bullet list */}
            {restFailed.length > 0 && (
              <div style={styles.bulletSection}>
                <div style={styles.bulletHeader}>
                  Other issues ({restFailed.length})
                </div>
                <div style={styles.bulletList}>
                  {restFailed.map((code) => (
                    <BulletRule
                      key={code}
                      code={code}
                      check={checks[code]}
                      maxScore={score.breakdown?.[code]?.max}
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* ── PASSED SECTION — collapsible ── */}
        {passedCodes.length > 0 && (
          <div style={styles.passedBox}>
            <button
              style={styles.passedToggle}
              onClick={() => setPassedOpen(p => !p)}
            >
              <span style={styles.passedToggleLeft}>
                <span style={styles.passedIcon}>✓</span>
                <span style={styles.passedTitle}>
                  {passedCodes.length} check{passedCodes.length !== 1 ? "s" : ""} passed
                </span>
              </span>
              <span style={styles.passedChevron}>
                {passedOpen ? "▲ Hide" : "▼ Show all passed checks"}
              </span>
            </button>

            {passedOpen && (
              <div style={styles.passedList}>
                {passedCodes.map((code) => (
                  <PassedRule
                    key={code}
                    code={code}
                    check={checks[code]}
                    maxScore={score.breakdown?.[code]?.max}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Bottom actions */}
        <div style={styles.actions}>
          <button style={styles.mirrorBtn} onClick={() => navigate("/mirror")}>
            🪞 AI Mirror
          </button>
          <button style={styles.fixBtn} onClick={() => navigate("/fix")}>
            🔧 Fix Now
          </button>
        </div>

      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#0a0a0f", position: "relative", padding: "32px 20px 80px" },
  grid: {
    position: "fixed", inset: 0,
    backgroundImage: "linear-gradient(rgba(124,106,247,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(124,106,247,0.03) 1px, transparent 1px)",
    backgroundSize: "40px 40px", pointerEvents: "none", zIndex: 0,
  },
  container: { position: "relative", zIndex: 1, maxWidth: 800, margin: "0 auto", display: "flex", flexDirection: "column", gap: 24 },
  topBar: { display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" },
  backBtn: { background: "transparent", border: "1px solid #2a2a3d", borderRadius: 8, color: "#64748b", padding: "8px 14px", fontSize: 13, cursor: "pointer" },
  urlBadge: { display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(124,106,247,0.08)", border: "1px solid rgba(124,106,247,0.18)", borderRadius: 999, padding: "5px 14px", fontSize: 12, color: "#a78bfa", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 400 },
  urlDot: { width: 6, height: 6, borderRadius: "50%", background: "#7c6af7", flexShrink: 0, boxShadow: "0 0 6px #7c6af7" },
  hero: { display: "flex", alignItems: "center", gap: 28, background: "#13131a", border: "1px solid #2a2a3d", borderRadius: 16, padding: "28px 32px", flexWrap: "wrap" },
  heroText: { flex: 1, display: "flex", flexDirection: "column", gap: 16, minWidth: 200 },
  h1: { fontSize: 22, fontWeight: 800, color: "#e2e8f0", letterSpacing: "-0.02em", margin: 0 },
  scoreBreakdown: { display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" },
  scorePart: { display: "flex", flexDirection: "column", gap: 2 },
  scoreVal: { fontSize: 26, fontWeight: 800, color: "#e2e8f0", lineHeight: 1 },
  scoreMax: { fontSize: 13, color: "#64748b", marginTop: 2 },
  scoreDesc: { fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" },
  scoreDivider: { width: 1, height: 36, background: "#2a2a3d" },
  conclusionBox: { background: "#13131a", border: "1px solid rgba(124,106,247,0.25)", borderRadius: 14, padding: "20px 24px", display: "flex", flexDirection: "column", gap: 12 },
  conclusionHeader: { display: "flex", alignItems: "center", gap: 10 },
  conclusionTitle: { fontSize: 14, fontWeight: 700, color: "#e2e8f0", flex: 1 },
  conclusionSource: { fontSize: 11, color: "#64748b", fontStyle: "italic" },
  conclusionText: { fontSize: 14, color: "#94a3b8", lineHeight: 1.75, margin: 0 },
  noIssues: { background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)", borderRadius: 12, padding: "20px 24px", fontSize: 14, color: "#22c55e", textAlign: "center" },
  sectionHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", paddingLeft: 4 },
  sectionTitle: { fontSize: 15, fontWeight: 700, color: "#e2e8f0" },
  sectionCount: { fontSize: 12, color: "#ef4444", background: "rgba(239,68,68,0.1)", borderRadius: 999, padding: "3px 10px", fontWeight: 600 },
  priorityGrid: { display: "flex", flexDirection: "column", gap: 14 },
  bulletSection: { display: "flex", flexDirection: "column", gap: 8 },
  bulletHeader: { fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", paddingLeft: 4 },
  bulletList: { display: "flex", flexDirection: "column", gap: 5 },
  passedBox: { background: "#0d0d13", border: "1px solid #2a2a3d", borderRadius: 14, overflow: "hidden" },
  passedToggle: { width: "100%", background: "transparent", border: "none", padding: "14px 18px", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between" },
  passedToggleLeft: { display: "flex", alignItems: "center", gap: 10 },
  passedIcon: { width: 24, height: 24, borderRadius: "50%", background: "rgba(34,197,94,0.12)", color: "#22c55e", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800 },
  passedTitle: { fontSize: 14, fontWeight: 600, color: "#22c55e" },
  passedChevron: { fontSize: 12, color: "#64748b" },
  passedList: { padding: "0 12px 12px", display: "flex", flexDirection: "column", gap: 5 },
  actions: { display: "flex", gap: 14, position: "sticky", bottom: 20, zIndex: 10 },
  mirrorBtn: { flex: 1, background: "#13131a", border: "1px solid rgba(124,106,247,0.4)", borderRadius: 12, color: "#a78bfa", padding: "16px", fontSize: 15, fontWeight: 700, cursor: "pointer" },
  fixBtn: { flex: 1, background: "linear-gradient(135deg, #7c6af7, #6d5de6)", border: "none", borderRadius: 12, color: "#fff", padding: "16px", fontSize: 15, fontWeight: 700, cursor: "pointer" },
};
