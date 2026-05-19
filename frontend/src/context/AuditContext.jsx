import { createContext, useContext, useState } from "react";

const AuditContext = createContext(null);

export function AuditProvider({ children }) {
  // Screen 1
  const [storeUrl, setStoreUrl] = useState("");

  // Screen 2
  const [freeText, setFreeText] = useState("");
  const [mcq, setMcq] = useState({
    category: "",
    customer: "",
    differentiator: "",
    tone: "",
  });

  // Screen 3
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState("");

  // Screen 4, 5, 6
  const [auditResult, setAuditResult] = useState(null);

  // Screen 6 — which check is open in chatbot
  const [activeChatCheck, setActiveChatCheck] = useState(null);

  // Screen 6 — checks user manually ticked as resolved
  const [resolvedChecks, setResolvedChecks] = useState([]);

  const toggleResolved = (checkCode) => {
    setResolvedChecks((prev) =>
      prev.includes(checkCode)
        ? prev.filter((c) => c !== checkCode)
        : [...prev, checkCode]
    );
  };

  const resetAudit = () => {
    setStoreUrl("");
    setFreeText("");
    setMcq({ category: "", customer: "", differentiator: "", tone: "" });
    setJobId(null);
    setProgress("");
    setAuditResult(null);
    setActiveChatCheck(null);
    setResolvedChecks([]);
  };

  return (
    <AuditContext.Provider
      value={{
        storeUrl, setStoreUrl,
        freeText, setFreeText,
        mcq, setMcq,
        jobId, setJobId,
        progress, setProgress,
        auditResult, setAuditResult,
        activeChatCheck, setActiveChatCheck,
        resolvedChecks, toggleResolved,
        resetAudit,
      }}
    >
      {children}
    </AuditContext.Provider>
  );
}

export function useAudit() {
  const ctx = useContext(AuditContext);
  if (!ctx) throw new Error("useAudit must be used inside AuditProvider");
  return ctx;
}