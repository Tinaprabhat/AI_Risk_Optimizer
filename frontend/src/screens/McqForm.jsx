import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAudit } from "../context/AuditContext";
import { startAudit } from "../api/client";

const MCQ_FIELDS = [
  {
    key: "category",
    label: "Store Category",
    description: "What type of products do you sell?",
    options: [
      "Fashion & Apparel",
      "Beauty & Cosmetics",
      "Electronics & Gadgets",
      "Home & Living",
      "Food & Beverages",
      "Health & Wellness",
      "Sports & Fitness",
      "Jewellery & Accessories",
      "Books & Stationery",
      "Other",
    ],
  },
  {
    key: "customer",
    label: "Primary Customer",
    description: "Who is your main target audience?",
    options: [
      "Young adults (18–25)",
      "Millennials (25–40)",
      "Parents & families",
      "Professionals",
      "Students",
      "Senior shoppers (50+)",
      "Makeup & beauty enthusiasts",
      "Fitness & health conscious",
      "Tech-savvy shoppers",
      "Budget-conscious buyers",
    ],
  },
  {
    key: "differentiator",
    label: "Main Differentiator",
    description: "What makes your store stand out from competitors?",
    options: [
      "Affordable pricing",
      "Premium / luxury quality",
      "Unique / handmade products",
      "Fast delivery",
      "Wide product range",
      "Sustainable & eco-friendly",
      "Exclusive designs",
      "Expert customer support",
      "Local / Indian brand",
      "Celebrity or influencer backed",
    ],
  },
  {
    key: "tone",
    label: "Brand Tone",
    description: "How would you describe your brand's personality?",
    options: [
      "Playful & vibrant",
      "Minimal & clean",
      "Luxury & refined",
      "Bold & edgy",
      "Friendly & warm",
      "Professional & trustworthy",
      "Youthful & trendy",
      "Earthy & natural",
      "Quirky & fun",
      "Serious & informative",
    ],
  },
];

export default function McqForm() {
  const { storeUrl, mcq, setMcq, freeText, setFreeText, setJobId, setProgress } = useAudit();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Redirect if no URL
    useEffect(() => {
    if (!storeUrl) {
        navigate("/");
    }
    }, [storeUrl]);

  const handleMcq = (key, value) => {
    setMcq((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    setError("");

    // Validate all MCQs selected
    const missing = MCQ_FIELDS.filter((f) => !mcq[f.key]);
    if (missing.length > 0) {
      setError(`Please select an option for: ${missing.map((f) => f.label).join(", ")}`);
      return;
    }

    if (!freeText.trim()) {
      setError("Please describe your store in the text box.");
      return;
    }

    setLoading(true);
    try {
      const res = await startAudit(storeUrl, freeText, mcq, true);
      const { job_id } = res.data;
      setJobId(job_id);
      setProgress("Starting audit...");
      navigate("/scan");
    } catch (e) {
      setError("Failed to start audit. Make sure your backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const allSelected = MCQ_FIELDS.every((f) => mcq[f.key]) && freeText.trim();

  return (
    <div style={styles.page}>
      <div style={styles.grid} />
      <div style={{ ...styles.orb, ...styles.orb1 }} />
      <div style={{ ...styles.orb, ...styles.orb2 }} />

      <div style={styles.container}>
        {/* Header */}
        <div style={styles.header}>
          <button style={styles.back} onClick={() => navigate("/")}>
            ← Back
          </button>
          <div style={styles.badge}>
            <span style={styles.badgeDot} />
            {storeUrl}
          </div>
        </div>

        <h2 style={styles.h2}>Tell us about your store</h2>
        <p style={styles.sub}>
          This helps us compare what you think your store says vs what AI actually reads.
        </p>

        {/* MCQ Cards */}
        <div style={styles.cards}>
          {MCQ_FIELDS.map((field) => (
            <div key={field.key} style={styles.card}>
              <div style={styles.cardHeader}>
                <span style={styles.cardLabel}>{field.label}</span>
                <span style={styles.cardDesc}>{field.description}</span>
              </div>
              <div style={styles.options}>
                {field.options.map((opt) => {
                  const selected = mcq[field.key] === opt;
                  return (
                    <button
                      key={opt}
                      style={{
                        ...styles.optBtn,
                        ...(selected ? styles.optSelected : {}),
                      }}
                      onClick={() => handleMcq(field.key, opt)}
                    >
                      {selected && <span style={styles.check}>✓ </span>}
                      {opt}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Free text */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <span style={styles.cardLabel}>Describe your store</span>
              <span style={styles.cardDesc}>
                In your own words — what do you sell, who is it for, and what makes it special?
              </span>
            </div>
            <textarea
              style={styles.textarea}
              placeholder="e.g. We sell affordable, trendy cosmetics for young makeup enthusiasts who love bold looks. Our brand is playful and vibrant with new drops every week..."
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              rows={5}
            />
            <span style={styles.charCount}>{freeText.length} / 500 chars</span>
          </div>
        </div>

        {/* Progress indicator */}
        <div style={styles.progressRow}>
          {MCQ_FIELDS.map((f) => (
            <div
              key={f.key}
              style={{
                ...styles.progressDot,
                ...(mcq[f.key] ? styles.progressDotFilled : {}),
              }}
            />
          ))}
          <div
            style={{
              ...styles.progressDot,
              ...(freeText.trim() ? styles.progressDotFilled : {}),
            }}
          />
          <span style={styles.progressText}>
            {MCQ_FIELDS.filter((f) => mcq[f.key]).length + (freeText.trim() ? 1 : 0)} / 5 completed
          </span>
        </div>

        {error && <p style={styles.error}>{error}</p>}

        {/* Submit */}
        <button
          style={{
            ...styles.btn,
            ...(!allSelected || loading ? styles.btnDisabled : {}),
          }}
          onClick={handleSubmit}
          disabled={!allSelected || loading}
        >
          {loading ? "Starting audit..." : "Analyze Store →"}
        </button>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#0a0a0f",
    display: "flex",
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
    width: 350,
    height: 350,
    background: "rgba(124,106,247,0.1)",
    top: -80,
    right: -80,
  },
  orb2: {
    width: 250,
    height: 250,
    background: "rgba(167,139,250,0.07)",
    bottom: 0,
    left: -60,
  },
  container: {
    position: "relative",
    zIndex: 1,
    maxWidth: 720,
    width: "100%",
    display: "flex",
    flexDirection: "column",
    gap: 24,
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    flexWrap: "wrap",
  },
  back: {
    background: "transparent",
    border: "1px solid #2a2a3d",
    borderRadius: 8,
    color: "#64748b",
    padding: "8px 14px",
    fontSize: 13,
    cursor: "pointer",
  },
  badge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    background: "rgba(124,106,247,0.1)",
    border: "1px solid rgba(124,106,247,0.2)",
    borderRadius: 999,
    padding: "5px 14px",
    fontSize: 12,
    color: "#a78bfa",
    maxWidth: 400,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  badgeDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#7c6af7",
    flexShrink: 0,
    boxShadow: "0 0 6px #7c6af7",
  },
  h2: {
    fontSize: 32,
    fontWeight: 800,
    color: "#e2e8f0",
    letterSpacing: "-0.02em",
  },
  sub: {
    fontSize: 15,
    color: "#64748b",
    lineHeight: 1.6,
    marginTop: -12,
  },
  cards: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  card: {
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 14,
    padding: 20,
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  cardHeader: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  cardLabel: {
    fontSize: 15,
    fontWeight: 600,
    color: "#e2e8f0",
  },
  cardDesc: {
    fontSize: 13,
    color: "#64748b",
  },
  options: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
  },
  optBtn: {
    background: "#1c1c28",
    border: "1px solid #2a2a3d",
    borderRadius: 8,
    color: "#94a3b8",
    padding: "7px 14px",
    fontSize: 13,
    cursor: "pointer",
    transition: "all 0.15s",
  },
  optSelected: {
    background: "rgba(124,106,247,0.15)",
    border: "1px solid #7c6af7",
    color: "#a78bfa",
    fontWeight: 600,
  },
  check: {
    color: "#7c6af7",
  },
  textarea: {
    background: "#1c1c28",
    border: "1px solid #2a2a3d",
    borderRadius: 10,
    color: "#e2e8f0",
    padding: "12px 14px",
    fontSize: 14,
    resize: "vertical",
    lineHeight: 1.6,
    width: "100%",
  },
  charCount: {
    fontSize: 12,
    color: "#64748b",
    textAlign: "right",
    marginTop: -8,
  },
  progressRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  progressDot: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: "#2a2a3d",
    transition: "background 0.2s",
  },
  progressDotFilled: {
    background: "#7c6af7",
    boxShadow: "0 0 6px #7c6af7",
  },
  progressText: {
    fontSize: 12,
    color: "#64748b",
    marginLeft: 4,
  },
  error: {
    color: "#ef4444",
    fontSize: 13,
    background: "rgba(239,68,68,0.08)",
    border: "1px solid rgba(239,68,68,0.2)",
    borderRadius: 8,
    padding: "10px 14px",
  },
  btn: {
    background: "linear-gradient(135deg, #7c6af7, #6d5de6)",
    color: "#fff",
    border: "none",
    borderRadius: 12,
    padding: "16px 32px",
    fontSize: 16,
    fontWeight: 700,
    width: "100%",
    transition: "opacity 0.2s",
    marginBottom: 40,
  },
  btnDisabled: {
    opacity: 0.4,
    cursor: "not-allowed",
  },
};