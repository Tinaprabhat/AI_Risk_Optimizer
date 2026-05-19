import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL;

const api = axios.create({
  baseURL: BASE,
  timeout: 15000,   // default — fast endpoints (status, health, templates)
});

// Higher timeout for endpoints that call the LLM (Ollama can take 30-40s)
const LLM_TIMEOUT = 60000;

// ── AUDIT ─────────────────────────────────────────────────────────

export const startAudit = (storeUrl, freeText, mcq, useCache = true) =>
  api.post("/audit/start", {
    store_url: storeUrl,
    free_text: freeText,
    mcq,
    use_cache: useCache,
  });

export const getAuditStatus = (jobId) =>
  api.get(`/audit/status/${jobId}`);

export const clearCache = (storeUrl) =>
  api.delete("/audit/cache", { params: { store_url: storeUrl } });

// ── CHAT ──────────────────────────────────────────────────────────

export const startChat = (storeUrl, checkCode, checkDetail) =>
  api.post("/chat/start", {
    store_url: storeUrl,
    check_code: checkCode,
    check_detail: checkDetail,
  }, { timeout: LLM_TIMEOUT });

export const sendChatReply = (storeUrl, checkCode, checkDetail, checkFix, userMessage) =>
  api.post("/chat/reply", {
    store_url: storeUrl,
    check_code: checkCode,
    check_detail: checkDetail,
    check_fix: checkFix,
    user_message: userMessage,
  }, { timeout: LLM_TIMEOUT });

export const getChatHistory = (storeUrl, checkCode) =>
  api.get("/chat/history", {
    params: { store_url: storeUrl, check_code: checkCode },
  });

// ── FIX TEMPLATE ──────────────────────────────────────────────────

export const getFixTemplate = (checkCode) =>
  api.get(`/fix/template/${checkCode}`);

// ── HEALTH ────────────────────────────────────────────────────────

export const healthCheck = () =>
  api.get("/health");