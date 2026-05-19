import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAudit } from "../context/AuditContext";
import {
  startChat,
  sendChatReply,
  getChatHistory,
} from "../api/client";

const STATUS_COLOR = {
  FAIL:    "#ef4444",
  WARN:    "#eab308",
  PASS:    "#22c55e",
  UNKNOWN: "#64748b",
};

const STATUS_ICON = {
  FAIL:    "✗",
  WARN:    "⚠",
  PASS:    "✓",
  UNKNOWN: "?",
};

// Format bot message — handle **bold** markdown
function formatMessage(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function ChatBubble({ role, message }) {
  const isBot = role === "bot";
  return (
    <div style={{
      ...bubble.wrap,
      justifyContent: isBot ? "flex-start" : "flex-end",
    }}>
      {isBot && <div style={bubble.avatar}>🤖</div>}
      <div style={{
        ...bubble.box,
        ...(isBot ? bubble.botBox : bubble.userBox),
      }}>
        <p style={bubble.text}>{formatMessage(message)}</p>
      </div>
      {!isBot && <div style={bubble.avatar}>👤</div>}
    </div>
  );
}

const bubble = {
  wrap: {
    display: "flex",
    alignItems: "flex-end",
    gap: 8,
    marginBottom: 12,
  },
  avatar: {
    width: 28, height: 28,
    borderRadius: "50%",
    background: "#1c1c28",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 14,
    flexShrink: 0,
  },
  box: {
    maxWidth: "75%",
    borderRadius: 12,
    padding: "10px 14px",
  },
  botBox: {
    background: "#1c1c28",
    border: "1px solid #2a2a3d",
    borderBottomLeftRadius: 4,
  },
  userBox: {
    background: "rgba(124,106,247,0.15)",
    border: "1px solid rgba(124,106,247,0.3)",
    borderBottomRightRadius: 4,
  },
  text: {
    margin: 0,
    fontSize: 13,
    color: "#e2e8f0",
    lineHeight: 1.7,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
};

export default function FixNow() {
  const { auditResult, storeUrl, resolvedChecks, toggleResolved, activeChatCheck, setActiveChatCheck } = useAudit();
  const navigate  = useNavigate();
  const bottomRef = useRef(null);

  const [messages,    setMessages]    = useState([]);
  const [userInput,   setUserInput]   = useState("");
  const [sending,     setSending]     = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);

  useEffect(() => {
    if (!auditResult) navigate("/");
  }, [auditResult]);

  if (!auditResult) return null;

  const failed = auditResult.failed || [];

  // Auto-select first unresolved check on load
  useEffect(() => {
    if (!activeChatCheck && failed.length > 0) {
      const first = failed.find((f) => !resolvedChecks.includes(f.code));
      if (first) openCheck(first);
    }
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openCheck = async (checkItem) => {
    if (activeChatCheck?.code === checkItem.code) return;
    setActiveChatCheck(checkItem);
    setMessages([]);
    setLoadingChat(true);
    setUserInput("");

    try {
      // Load existing history first
      const histRes = await getChatHistory(storeUrl, checkItem.code);
      const history = histRes.data;

      if (history && history.length > 0) {
        // Resume existing conversation
        setMessages(history.map((m) => ({ role: m.role, message: m.message })));
      } else {
        // Start fresh conversation
        const res = await startChat(storeUrl, checkItem.code, checkItem.detail);
        setMessages([{ role: "bot", message: res.data.message }]);
      }
    } catch (e) {
      setMessages([{ role: "bot", message: "Sorry, I had trouble loading this fix. Please try again." }]);
    } finally {
      setLoadingChat(false);
    }
  };

  const sendMessage = async () => {
    if (!userInput.trim() || sending || !activeChatCheck) return;

    const userMsg = userInput.trim();
    setUserInput("");
    setMessages((prev) => [...prev, { role: "user", message: userMsg }]);
    setSending(true);

    try {
      const res = await sendChatReply(
        storeUrl,
        activeChatCheck.code,
        activeChatCheck.detail,
        activeChatCheck.fix || "",
        userMsg,
      );
      setMessages((prev) => [...prev, { role: "bot", message: res.data.message }]);
    } catch {
      setMessages((prev) => [...prev, {
        role: "bot",
        message: "Sorry, I couldn't get a response. Please try again.",
      }]);
    } finally {
      setSending(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleResolve = (code) => {
    toggleResolved(code);
    // If resolving current check, move to next unresolved
    if (activeChatCheck?.code === code) {
      const next = failed.find(
        (f) => f.code !== code && !resolvedChecks.includes(f.code)
      );
      if (next) openCheck(next);
    }
  };

  const resolvedCount = failed.filter((f) => resolvedChecks.includes(f.code)).length;

  return (
    <div style={styles.page}>
      <div style={styles.grid} />

      <div style={styles.layout}>

        {/* ── LEFT PANEL — check list ── */}
        <div style={styles.leftPanel}>

          {/* Header */}
          <div style={styles.leftHeader}>
            <button style={styles.backBtn} onClick={() => navigate("/results")}>
              ← Results
            </button>
            <div style={styles.leftTitle}>
              <span style={styles.wrenchIcon}>🔧</span>
              <div>
                <div style={styles.leftTitleText}>Fix Now</div>
                <div style={styles.leftSubText}>
                  {resolvedCount}/{failed.length} resolved
                </div>
              </div>
            </div>

            {/* Progress bar */}
            <div style={styles.progressTrack}>
              <div style={{
                ...styles.progressFill,
                width: `${failed.length ? (resolvedCount / failed.length) * 100 : 0}%`,
              }} />
            </div>
          </div>

          {/* Check list */}
          <div style={styles.checkList}>
            {failed.length === 0 && (
              <div style={styles.noFails}>
                🎉 No failed checks — your store is well optimised!
              </div>
            )}
            {failed.map((item) => {
              const isActive   = activeChatCheck?.code === item.code;
              const isResolved = resolvedChecks.includes(item.code);
              const color      = STATUS_COLOR[item.status] || "#64748b";

              return (
                <div
                  key={item.code}
                  style={{
                    ...styles.checkItem,
                    ...(isActive   ? styles.checkItemActive   : {}),
                    ...(isResolved ? styles.checkItemResolved : {}),
                  }}
                  onClick={() => !isResolved && openCheck(item)}
                >
                  {/* Checkbox */}
                  <div
                    style={{
                      ...styles.checkbox,
                      borderColor: isResolved ? "#22c55e" : color,
                      background:  isResolved ? "rgba(34,197,94,0.15)" : "transparent",
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleResolve(item.code);
                    }}
                    title={isResolved ? "Mark as unresolved" : "Mark as resolved"}
                  >
                    {isResolved && <span style={styles.checkmark}>✓</span>}
                  </div>

                  {/* Check info */}
                  <div style={styles.checkInfo}>
                    <div style={styles.checkTop}>
                      <span style={{
                        ...styles.checkCode,
                        color: isResolved ? "#22c55e" : color,
                      }}>
                        {STATUS_ICON[item.status]} {item.code}
                      </span>
                      <span style={{
                        ...styles.checkStatus,
                        color: isResolved ? "#22c55e" : color,
                        background: isResolved
                          ? "rgba(34,197,94,0.1)"
                          : `${color}18`,
                      }}>
                        {isResolved ? "Resolved" : item.status}
                      </span>
                    </div>
                    <p style={{
                      ...styles.checkDetail,
                      color: isResolved ? "#64748b" : "#94a3b8",
                      textDecoration: isResolved ? "line-through" : "none",
                    }}>
                      {item.detail}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Mirror button at bottom */}
          <button
            style={styles.mirrorBtn}
            onClick={() => navigate("/mirror")}
          >
            🪞 View AI Mirror
          </button>
        </div>

        {/* ── RIGHT PANEL — chatbot ── */}
        <div style={styles.rightPanel}>

          {/* Chat header */}
          {activeChatCheck ? (
            <div style={styles.chatHeader}>
              <div style={styles.chatHeaderLeft}>
                <span style={{
                  ...styles.chatCode,
                  color: STATUS_COLOR[activeChatCheck.status] || "#7c6af7",
                  background: `${STATUS_COLOR[activeChatCheck.status] || "#7c6af7"}18`,
                }}>
                  {activeChatCheck.code}
                </span>
                <div style={styles.chatHeaderText}>
                  <span style={styles.chatTitle}>Fix Assistant</span>
                  <span style={styles.chatSub}>{activeChatCheck.detail}</span>
                </div>
              </div>
              <button
                style={{
                  ...styles.resolveBtn,
                  ...(resolvedChecks.includes(activeChatCheck.code)
                    ? styles.resolveBtnDone
                    : {}),
                }}
                onClick={() => handleResolve(activeChatCheck.code)}
              >
                {resolvedChecks.includes(activeChatCheck.code)
                  ? "✓ Resolved"
                  : "Mark Resolved"}
              </button>
            </div>
          ) : (
            <div style={styles.chatHeader}>
              <span style={styles.chatTitle}>Fix Assistant</span>
            </div>
          )}

          {/* Messages area */}
          <div style={styles.messages}>
            {!activeChatCheck && (
              <div style={styles.emptyChat}>
                <span style={{ fontSize: 40 }}>🤖</span>
                <p>Select a failed check on the left to start fixing it.</p>
                <p style={{ fontSize: 12, color: "#64748b" }}>
                  The assistant will walk you through each fix one step at a time.
                </p>
              </div>
            )}

            {loadingChat && (
              <div style={styles.emptyChat}>
                <div style={styles.typingDots}>
                  <span /><span /><span />
                </div>
                <p style={{ color: "#64748b", fontSize: 13 }}>Loading conversation...</p>
              </div>
            )}

            {!loadingChat && messages.map((m, i) => (
              <ChatBubble key={i} role={m.role} message={m.message} />
            ))}

            {sending && (
              <div style={bubble.wrap}>
                <div style={bubble.avatar}>🤖</div>
                <div style={{ ...bubble.box, ...bubble.botBox }}>
                  <div style={styles.typingDots}>
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input area */}
          {activeChatCheck && !resolvedChecks.includes(activeChatCheck.code) && (
            <div style={styles.inputArea}>
              <textarea
                style={styles.textarea}
                placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={handleKey}
                rows={2}
                disabled={sending || loadingChat}
              />
              <button
                style={{
                  ...styles.sendBtn,
                  opacity: sending || !userInput.trim() ? 0.5 : 1,
                }}
                onClick={sendMessage}
                disabled={sending || !userInput.trim()}
              >
                {sending ? "..." : "Send →"}
              </button>
            </div>
          )}

          {activeChatCheck && resolvedChecks.includes(activeChatCheck.code) && (
            <div style={styles.resolvedBanner}>
              ✓ You marked this as resolved. Select another check on the left to continue.
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes blink {
          0%, 80%, 100% { opacity: 0; transform: scale(0.8); }
          40%            { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}

const styles = {
  page: {
    height: "100vh",
    background: "#0a0a0f",
    position: "relative",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
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
  layout: {
    position: "relative",
    zIndex: 1,
    display: "flex",
    height: "100vh",
    overflow: "hidden",
  },

  // ── LEFT PANEL ──
  leftPanel: {
    width: 320,
    flexShrink: 0,
    borderRight: "1px solid #2a2a3d",
    display: "flex",
    flexDirection: "column",
    background: "#0d0d13",
    overflow: "hidden",
  },
  leftHeader: {
    padding: "16px",
    borderBottom: "1px solid #2a2a3d",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  backBtn: {
    background: "transparent",
    border: "1px solid #2a2a3d",
    borderRadius: 8,
    color: "#64748b",
    padding: "6px 12px",
    fontSize: 12,
    cursor: "pointer",
    alignSelf: "flex-start",
  },
  leftTitle: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  wrenchIcon: { fontSize: 20 },
  leftTitleText: { fontSize: 15, fontWeight: 700, color: "#e2e8f0" },
  leftSubText:   { fontSize: 12, color: "#64748b" },
  progressTrack: {
    height: 4,
    background: "#1c1c28",
    borderRadius: 999,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    background: "linear-gradient(90deg, #7c6af7, #22c55e)",
    borderRadius: 999,
    transition: "width 0.4s ease",
  },
  checkList: {
    flex: 1,
    overflowY: "auto",
    padding: "8px",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  noFails: {
    padding: 20,
    fontSize: 13,
    color: "#64748b",
    textAlign: "center",
  },
  checkItem: {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
    padding: "10px 12px",
    borderRadius: 10,
    cursor: "pointer",
    border: "1px solid transparent",
    transition: "all 0.15s",
  },
  checkItemActive: {
    background: "rgba(124,106,247,0.08)",
    border: "1px solid rgba(124,106,247,0.25)",
  },
  checkItemResolved: {
    opacity: 0.5,
    cursor: "default",
  },
  checkbox: {
    width: 18, height: 18,
    borderRadius: 5,
    border: "2px solid",
    flexShrink: 0,
    marginTop: 2,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "all 0.15s",
  },
  checkmark: { fontSize: 10, color: "#22c55e", fontWeight: 800 },
  checkInfo: { flex: 1, minWidth: 0 },
  checkTop: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginBottom: 4,
  },
  checkCode: { fontSize: 12, fontWeight: 700 },
  checkStatus: {
    fontSize: 10,
    fontWeight: 600,
    borderRadius: 4,
    padding: "2px 6px",
  },
  checkDetail: {
    fontSize: 11,
    lineHeight: 1.5,
    margin: 0,
    overflow: "hidden",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
  },
  mirrorBtn: {
    margin: "8px 16px 16px",
    background: "transparent",
    border: "1px solid rgba(124,106,247,0.3)",
    borderRadius: 10,
    color: "#a78bfa",
    padding: "10px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },

  // ── RIGHT PANEL ──
  rightPanel: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    minWidth: 0,
  },
  chatHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    padding: "14px 20px",
    borderBottom: "1px solid #2a2a3d",
    background: "#0d0d13",
    flexShrink: 0,
  },
  chatHeaderLeft: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    minWidth: 0,
    flex: 1,
  },
  chatCode: {
    fontSize: 13,
    fontWeight: 700,
    borderRadius: 6,
    padding: "4px 10px",
    flexShrink: 0,
  },
  chatHeaderText: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
    minWidth: 0,
  },
  chatTitle: { fontSize: 14, fontWeight: 700, color: "#e2e8f0" },
  chatSub: {
    fontSize: 11,
    color: "#64748b",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  resolveBtn: {
    background: "transparent",
    border: "1px solid #2a2a3d",
    borderRadius: 8,
    color: "#64748b",
    padding: "7px 14px",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    flexShrink: 0,
    transition: "all 0.2s",
  },
  resolveBtnDone: {
    borderColor: "rgba(34,197,94,0.4)",
    color: "#22c55e",
    background: "rgba(34,197,94,0.08)",
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
  },
  emptyChat: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    color: "#94a3b8",
    fontSize: 14,
    textAlign: "center",
    padding: 40,
  },
  typingDots: {
    display: "flex",
    gap: 4,
    padding: "4px 2px",
    "& span": {
      width: 6, height: 6,
      borderRadius: "50%",
      background: "#64748b",
      animation: "blink 1.4s infinite",
    },
  },
  inputArea: {
    display: "flex",
    gap: 10,
    padding: "14px 20px",
    borderTop: "1px solid #2a2a3d",
    background: "#0d0d13",
    flexShrink: 0,
    alignItems: "flex-end",
  },
  textarea: {
    flex: 1,
    background: "#13131a",
    border: "1px solid #2a2a3d",
    borderRadius: 10,
    color: "#e2e8f0",
    padding: "10px 14px",
    fontSize: 13,
    resize: "none",
    lineHeight: 1.6,
    fontFamily: "inherit",
  },
  sendBtn: {
    background: "linear-gradient(135deg, #7c6af7, #6d5de6)",
    border: "none",
    borderRadius: 10,
    color: "#fff",
    padding: "10px 18px",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    flexShrink: 0,
    transition: "opacity 0.2s",
    alignSelf: "flex-end",
  },
  resolvedBanner: {
    padding: "16px 20px",
    borderTop: "1px solid rgba(34,197,94,0.2)",
    background: "rgba(34,197,94,0.06)",
    color: "#22c55e",
    fontSize: 13,
    fontWeight: 500,
    textAlign: "center",
    flexShrink: 0,
  },
};