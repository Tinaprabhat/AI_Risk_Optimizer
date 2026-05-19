import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAudit } from "../context/AuditContext";
import { getAuditStatus } from "../api/client";

const LAYER_STEPS = [
  { key: "Layer 1", label: "Crawlability",        desc: "Checking robots.txt, sitemap, SSL, bot protection",          icon: "🤖" },
  { key: "Layer 2", label: "Structured Data",     desc: "Scanning schema.org, JSON-LD, price signals",               icon: "📋" },
  { key: "Layer 3", label: "Semantic Content",    desc: "Analysing descriptions, FAQ, refund & shipping policies",    icon: "💬" },
  { key: "Layer 4", label: "Trust Signals",       desc: "Verifying contact page, brand consistency",                 icon: "🛡" },
  { key: "Layer 5", label: "AI-Era Protocols",    desc: "Checking UCP, ACP feed, GMC signals",                       icon: "⚡" },
  { key: "Layer 6", label: "Semantic Gap",        desc: "Computing AI mirror — 3 perception vectors",                icon: "🪞" },
  { key: "Layer 7", label: "Scoring & Conclusion",desc: "Aggregating results, generating AI conclusion",             icon: "🧠" },
];

export default function Scanning() {
  const { jobId, progress, setProgress, setAuditResult, storeUrl } = useAudit();
  const navigate  = useNavigate();
  const pollRef   = useRef(null);
  const startTime = useRef(null);
  const [isCached, setIsCached] = useState(false);

  useEffect(() => {
    if (!jobId) {
      navigate("/");
      return;
    }

    startTime.current = Date.now();

    const poll = async () => {
      try {
        const res  = await getAuditStatus(jobId);
        const data = res.data;

        if (data.status === "running") {
            setProgress(data.progress || "Running audit...");
            pollRef.current = setTimeout(poll, 2000);
        } else if (data.status === "done") {
        const elapsed = (Date.now() - startTime.current) / 1000;
        if (elapsed < 4) setIsCached(true);
          setProgress("Audit complete!");
          setAuditResult(data.result);
          setTimeout(() => navigate("/results"), 800);
        } else if (data.status === "error") {
          setProgress(`Error: ${data.error}`);
        }
      } catch {
        setProgress("Connection error — retrying...");
        pollRef.current = setTimeout(poll, 3000);
      }
    };

    poll();

    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [jobId]);

  const activeLayer = LAYER_STEPS.findIndex((s) =>
    progress.toLowerCase().includes(s.label.toLowerCase()) ||
    progress.toLowerCase().includes(s.key.toLowerCase())
  );

  const isDone  = progress.toLowerCase().includes("complete");
  const isError = progress.toLowerCase().includes("error");

  return (
    <div style={styles.page}>
      <div style={styles.grid} />
      <div style={{ ...styles.orb, ...styles.orb1 }} />
      <div style={{ ...styles.orb, ...styles.orb2 }} />

      <div style={styles.container}>
        {/* Store URL badge */}
        <div style={styles.urlBadge}>
          <span style={styles.urlDot} />
          {storeUrl}
        </div>

        {/* Pulse animation */}
        <div style={styles.pulseWrap}>
          <div style={styles.pulseRing3} />
          <div style={styles.pulseRing2} />
          <div style={styles.pulseRing1} />
          <div style={styles.pulseCore}>
            {isDone ? "✓" : isError ? "✗" : "⚡"}
          </div>
        </div>

        {/* Title */}
        <h2 style={styles.h2}>
          {isDone ? "Audit Complete" : isError ? "Audit Failed" : "Scanning your store..."}
        </h2>

        {/* Live progress */}
        <div style={styles.progressBox}>
          <div style={styles.progressDot} />
          <span style={styles.progressText}>{progress || "Starting..."}</span>
        </div>

        {/* Layer steps */}
        <div style={styles.layers}>
          {LAYER_STEPS.map((step, i) => {
            const done   = isDone || i < activeLayer;
            const active = i === activeLayer && !isDone;
            return (
              <div
                key={step.key}
                style={{
                  ...styles.layerRow,
                  ...(active ? styles.layerActive : {}),
                  ...(done   ? styles.layerDone   : {}),
                }}
              >
                <div style={{
                  ...styles.layerIcon,
                  ...(active ? styles.layerIconActive : {}),
                  ...(done   ? styles.layerIconDone   : {}),
                }}>
                  {done ? "✓" : step.icon}
                </div>
                <div style={styles.layerText}>
                  <span style={styles.layerLabel}>{step.key} — {step.label}</span>
                  {active && <span style={styles.layerDesc}>{step.desc}</span>}
                </div>
                {active && (
                  <div style={styles.spinner}>
                    <div style={styles.spinnerInner} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Cache notice */}
        {isCached && (
          <div style={styles.cacheNotice}>
            ⚡ Retrieved from cache — instant result
          </div>
        )}

        <p style={styles.hint}>
          Fresh audits take 30–60 seconds. Same URL loads instantly from cache.
        </p>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { transform: scale(1);    opacity: 0.6; }
          50%       { transform: scale(1.15); opacity: 0.2; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes blink {
          0%, 100% { opacity: 1;   }
          50%       { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}

const PURPLE = "#7c6af7";

const styles = {
  page: {
    minHeight: "100vh",
    background: "#0a0a0f",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    overflow: "hidden",
    padding: "40px 20px",
  },
  grid: {
    position: "absolute",
    inset: 0,
    backgroundImage:
      "linear-gradient(rgba(124,106,247,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(124,106,247,0.04) 1px, transparent 1px)",
    backgroundSize: "40px 40px",
    pointerEvents: "none",
  },
  orb: {
    position: "absolute",
    borderRadius: "50%",
    filter: "blur(90px)",
    pointerEvents: "none",
  },
  orb1: {
    width: 400, height: 400,
    background: "rgba(124,106,247,0.13)",
    top: -120, right: -100,
  },
  orb2: {
    width: 300, height: 300,
    background: "rgba(167,139,250,0.08)",
    bottom: -80, left: -80,
  },
  container: {
    position: "relative",
    zIndex: 1,
    maxWidth: 560,
    width: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 24,
    textAlign: "center",
  },
  urlBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    background: "rgba(124,106,247,0.1)",
    border: "1px solid rgba(124,106,247,0.2)",
    borderRadius: 999,
    padding: "5px 16px",
    fontSize: 12,
    color: "#a78bfa",
    maxWidth: "100%",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  urlDot: {
    width: 6, height: 6,
    borderRadius: "50%",
    background: PURPLE,
    flexShrink: 0,
    boxShadow: `0 0 6px ${PURPLE}`,
    animation: "blink 1.5s ease-in-out infinite",
  },
  pulseWrap: {
    position: "relative",
    width: 120, height: 120,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "8px 0",
  },
  pulseRing3: {
    position: "absolute",
    width: 120, height: 120,
    borderRadius: "50%",
    background: "rgba(124,106,247,0.06)",
    animation: "pulse 2.4s ease-in-out infinite",
    animationDelay: "0.4s",
  },
  pulseRing2: {
    position: "absolute",
    width: 90, height: 90,
    borderRadius: "50%",
    background: "rgba(124,106,247,0.1)",
    animation: "pulse 2.4s ease-in-out infinite",
    animationDelay: "0.2s",
  },
  pulseRing1: {
    position: "absolute",
    width: 65, height: 65,
    borderRadius: "50%",
    background: "rgba(124,106,247,0.18)",
    animation: "pulse 2.4s ease-in-out infinite",
  },
  pulseCore: {
    position: "relative",
    width: 44, height: 44,
    borderRadius: "50%",
    background: `linear-gradient(135deg, ${PURPLE}, #6d5de6)`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 20,
    boxShadow: `0 0 20px rgba(124,106,247,0.5)`,
    zIndex: 1,
  },
  h2: {
    fontSize: 28,
    fontWeight: 800,
    color: "#e2e8f0",
    letterSpacing: "-0.02em",
  },
  progressBox: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 10,
    padding: "10px 18px",
    width: "100%",
  },
  progressDot: {
    width: 8, height: 8,
    borderRadius: "50%",
    background: PURPLE,
    flexShrink: 0,
    animation: "blink 1.2s ease-in-out infinite",
  },
  progressText: {
    fontSize: 13,
    color: "#94a3b8",
    textAlign: "left",
  },
  layers: {
    width: "100%",
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  layerRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    background: "#13131a",
    border: "1px solid #1c1c28",
    borderRadius: 10,
    padding: "10px 14px",
    transition: "all 0.3s",
    opacity: 0.45,
  },
  layerActive: {
    opacity: 1,
    border: `1px solid rgba(124,106,247,0.4)`,
    background: "rgba(124,106,247,0.06)",
  },
  layerDone: {
    opacity: 0.75,
    border: "1px solid rgba(34,197,94,0.2)",
  },
  layerIcon: {
    width: 32, height: 32,
    borderRadius: 8,
    background: "#1c1c28",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 15,
    flexShrink: 0,
  },
  layerIconActive: { background: "rgba(124,106,247,0.2)" },
  layerIconDone:   { background: "rgba(34,197,94,0.15)", color: "#22c55e" },
  layerText: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    gap: 2,
    textAlign: "left",
  },
  layerLabel: { fontSize: 13, fontWeight: 600, color: "#e2e8f0" },
  layerDesc:  { fontSize: 11, color: "#64748b" },
  spinner:      { width: 18, height: 18, flexShrink: 0 },
  spinnerInner: {
    width: 18, height: 18,
    borderRadius: "50%",
    border: `2px solid rgba(124,106,247,0.2)`,
    borderTop: `2px solid ${PURPLE}`,
    animation: "spin 0.8s linear infinite",
  },
  cacheNotice: {
    background: "rgba(34,197,94,0.08)",
    border: "1px solid rgba(34,197,94,0.2)",
    borderRadius: 8,
    padding: "8px 16px",
    fontSize: 13,
    color: "#22c55e",
  },
  hint: {
    fontSize: 12,
    color: "#64748b",
    lineHeight: 1.6,
    maxWidth: 400,
  },
};