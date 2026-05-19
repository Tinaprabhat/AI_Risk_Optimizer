import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAudit } from "../context/AuditContext";
import { healthCheck } from "../api/client";

export default function Landing() {
  const { storeUrl, setStoreUrl, resetAudit } = useAudit();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const validateUrl = (url) => {
    try {
      const u = new URL(url.startsWith("http") ? url : "https://" + url);
      return u.hostname.length > 2;
    } catch {
      return false;
    }
  };

  const handleAnalyze = async () => {
    setError("");
    const trimmed = storeUrl.trim();
    if (!trimmed) {
      setError("Please enter your store URL.");
      return;
    }
    if (!validateUrl(trimmed)) {
      setError("Please enter a valid URL e.g. https://yourstore.com");
      return;
    }
    // Normalize URL
    const normalized = trimmed.startsWith("http") ? trimmed : "https://" + trimmed;
    setLoading(true);
    try {
      await healthCheck();
      resetAudit();
      setStoreUrl(normalized);
      navigate("/mcq");
    } catch {
      setError("Cannot reach backend. Make sure uvicorn is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter") handleAnalyze();
  };

  return (
    <div style={styles.page}>
      {/* Background grid */}
      <div style={styles.grid} />

      {/* Floating orbs */}
      <div style={{ ...styles.orb, ...styles.orb1 }} />
      <div style={{ ...styles.orb, ...styles.orb2 }} />

      <div style={styles.container}>
        {/* Badge */}
        <div style={styles.badge}>
          <span style={styles.badgeDot} />
          AI Visibility Auditor
        </div>

        {/* Headline */}
        <h1 style={styles.h1}>
          Why isn't AI
          <br />
          <span style={styles.accent}>recommending</span>
          <br />
          your store?
        </h1>

        <p style={styles.sub}>
          Paste your Shopify URL. We run it through 7 layers of AI readiness
          checks and tell you exactly what's blocking you — with fixes.
        </p>

        {/* Input row */}
        <div style={styles.inputWrap}>
          <div style={styles.inputRow}>
            <span style={styles.inputIcon}>🔗</span>
            <input
              style={styles.input}
              type="text"
              placeholder="https://yourstore.myshopify.com"
              value={storeUrl}
              onChange={(e) => setStoreUrl(e.target.value)}
              onKeyDown={handleKey}
              autoFocus
            />
            <button
              style={{
                ...styles.btn,
                ...(loading ? styles.btnDisabled : {}),
              }}
              onClick={handleAnalyze}
              disabled={loading}
            >
              {loading ? "Checking..." : "Analyze Store →"}
            </button>
          </div>
          {error && <p style={styles.error}>{error}</p>}
        </div>

        {/* Stats row */}
        <div style={styles.stats}>
          {[
            { label: "Layers checked", value: "7" },
            { label: "Rules audited", value: "15+" },
            { label: "Max score", value: "69" },
          ].map((s) => (
            <div key={s.label} style={styles.stat}>
              <span style={styles.statVal}>{s.value}</span>
              <span style={styles.statLabel}>{s.label}</span>
            </div>
          ))}
        </div>

        {/* Layer pills */}
        <div style={styles.pills}>
          {[
            "🤖 Crawlability",
            "📋 Structured Data",
            "💬 Semantic Content",
            "🛡 Trust Signals",
            "⚡ AI Protocols",
            "🪞 AI Mirror",
            "🔧 Fix Engine",
          ].map((p) => (
            <span key={p} style={styles.pill}>
              {p}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

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
    filter: "blur(80px)",
    pointerEvents: "none",
  },
  orb1: {
    width: 400,
    height: 400,
    background: "rgba(124,106,247,0.12)",
    top: -100,
    right: -100,
  },
  orb2: {
    width: 300,
    height: 300,
    background: "rgba(167,139,250,0.08)",
    bottom: -80,
    left: -80,
  },
  container: {
    position: "relative",
    zIndex: 1,
    maxWidth: 680,
    width: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 28,
    textAlign: "center",
  },
  badge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    background: "rgba(124,106,247,0.12)",
    border: "1px solid rgba(124,106,247,0.25)",
    borderRadius: 999,
    padding: "6px 16px",
    fontSize: 13,
    color: "#a78bfa",
    fontWeight: 500,
    letterSpacing: "0.02em",
  },
  badgeDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#7c6af7",
    display: "inline-block",
    boxShadow: "0 0 6px #7c6af7",
  },
  h1: {
    fontSize: "clamp(42px, 7vw, 72px)",
    fontWeight: 800,
    lineHeight: 1.1,
    letterSpacing: "-0.03em",
    color: "#e2e8f0",
  },
  accent: {
    background: "linear-gradient(135deg, #7c6af7, #a78bfa)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  sub: {
    fontSize: 17,
    color: "#64748b",
    lineHeight: 1.7,
    maxWidth: 520,
  },
  inputWrap: {
    width: "100%",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  inputRow: {
    display: "flex",
    alignItems: "center",
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 14,
    padding: "6px 6px 6px 16px",
    gap: 10,
    transition: "border-color 0.2s",
  },
  inputIcon: {
    fontSize: 18,
    flexShrink: 0,
  },
  input: {
    flex: 1,
    background: "transparent",
    border: "none",
    color: "#e2e8f0",
    fontSize: 15,
    padding: "8px 0",
  },
  btn: {
    background: "linear-gradient(135deg, #7c6af7, #6d5de6)",
    color: "#fff",
    border: "none",
    borderRadius: 10,
    padding: "12px 22px",
    fontSize: 14,
    fontWeight: 600,
    whiteSpace: "nowrap",
    transition: "opacity 0.2s, transform 0.1s",
  },
  btnDisabled: {
    opacity: 0.5,
  },
  error: {
    color: "#ef4444",
    fontSize: 13,
    textAlign: "left",
    paddingLeft: 4,
  },
  stats: {
    display: "flex",
    gap: 40,
    justifyContent: "center",
  },
  stat: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 4,
  },
  statVal: {
    fontSize: 32,
    fontWeight: 800,
    color: "#7c6af7",
    lineHeight: 1,
  },
  statLabel: {
    fontSize: 12,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  pills: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    justifyContent: "center",
  },
  pill: {
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 999,
    padding: "6px 14px",
    fontSize: 12,
    color: "#64748b",
  },
};