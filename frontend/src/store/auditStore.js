import { create } from "zustand";

const useAuditStore = create((set) => ({

  // STORE URL
  storeUrl: "",

  setStoreUrl: (url) =>
    set({
      storeUrl: url,
    }),

  // QUESTIONS
  questions: {
    category: "",
    customer: "",
    differentiator: "",
    tone: "",
  },

  setQuestions: (data) =>
    set({
      questions: data,
    }),

  // AUDIT RESULTS
  auditResult: null,

  setAuditResult: (result) =>
    set({
      auditResult: result,
    }),

  // SCAN STATUS
  scanStatus: "idle",

  setScanStatus: (status) =>
    set({
      scanStatus: status,
    }),

  // LIVE PROGRESS LOGS
  progressLogs: [],

  setProgressLogs: (logs) =>
    set({
      progressLogs: logs,
    }),

  addProgressLog: (log) =>
    set((state) => ({
      progressLogs: [
        ...state.progressLogs,
        log,
      ],
    })),

}));

export default useAuditStore;