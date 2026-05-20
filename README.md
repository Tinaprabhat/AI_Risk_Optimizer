# AI Representation Optimizer

> **A diagnostic platform that audits Shopify stores through the lens of an AI shopping agent — and tells merchants exactly how to fix what's blocking them.**

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Validated](https://img.shields.io/badge/Validated-20%2B%20Shopify%20Stores-purple)]()
[![Cost](https://img.shields.io/badge/Prototype%20Cost-$0-brightgreen)]()

---

## The Problem

AI shopping agents — ChatGPT, Gemini, Perplexity — now decide which stores appear in recommendations and which don't. That decision is not made on product quality. It is made on **data quality**.

When a consumer asks *"recommend the best yoga mat under ₹2,000"*, an AI agent silently scans structured data, content clarity, trust signals, and crawl access. If any layer is incomplete, contradictory, or missing — the agent moves on.

**The merchant never knows why. There is no rejection notice. No error. No visibility.**

This tool makes the invisible visible — and tells the merchant exactly how to fix it.

---

## Key Features

- **16 evidence-backed checkpoints** across 7 layers — 4 Verified (mechanistic causal links), 12 Correlated. Zero speculative.
- **X / 69 transparent score** — partial-credit scoring with full evidence traces per checkpoint
- **3-Way Semantic Gap (AI Mirror)** — cosine similarity between merchant intent, website content, and schema data. No existing tool computes this.
- **Ranked Fix Engine** — per-blocker guided fix with hardcoded templates + Gemini conversational layer
- **Full fallback chain** — Gemini 2.5 Flash → Ollama (local Mistral) → hardcoded templates. Audit completes with zero internet if needed.
- **$0 at prototype scale** — CPU-only, no GPU, no paid API required to run. Runs on a laptop.
- **Validated on 20+ live Shopify stores** across 5 product categories before a single line of production code was written.
- **Ready to deploy** — FastAPI backend, PostgreSQL database, Docker + Render/Railway config included.

---

## Validated, Not Assumed

Before building, we ran an empirical validation study:

1. Queried Gemini, Perplexity, and ChatGPT × 3 times each across 5 product categories
2. Identified top-recommended stores per category
3. Ran 14 checkpoints on each winner and measured pass rate
4. Cross-validated against 20+ live Shopify stores — compared tool findings against what AI agents actually reported when queried directly

**Results:** Pass rate ≥ 10/14 across 4/5 categories. R16 (refund window) and R17 (shipping timeframe) emerged as the strongest predictors. False negative rate dropped from ~18% (regex-only) to ~5–8% after the 3-tier semantic extractor. 35 initial hypotheses reduced to 16 final checkpoints — all VERIFIED or CORRELATED.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  Landing → Onboarding (4 MCQs) → Audit Progress → Results      │
│  AI Mirror → Fix Engine → Fix Progress Tracker                  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────────────────┐
│                     BACKEND (FastAPI)                           │
│  POST /api/audit   GET /api/audit/{id}   POST /api/fix/chat    │
│  GET  /api/mirror/{id}                   GET  /health           │
└──────┬──────────────────────────────────────────┬──────────────┘
       │                                          │
┌──────▼──────────────────────┐    ┌─────────────▼──────────────┐
│      AUDIT ENGINE           │    │       DATABASE              │
│                             │    │   PostgreSQL (prod)         │
│  SEMANTIC EXTRACTOR         │    │   SQLite (dev)              │
│  ├─ Tier 1: spaCy + regex   │    │                             │
│  └─ Tier 2: MiniLM embed.   │    │   Tables:                   │
│                             │    │   - audits                  │
│  L1  Crawlability           │    │   - audit_results           │
│  L2  Structured Data        │    │   - fix_sessions            │
│  L3  Semantic Content       │    │   - chat_history            │
│  L4  Trust Signals          │    │   - semantic_gap_matrix     │
│  L5  AI-Era Protocols       │    └────────────────────────────┘
│  L6  Semantic Gap Engine    │
│  L7  Aggregation & Output   │    ┌────────────────────────────┐
│                             │    │       LLM LAYER            │
│  PART 2: FIX ENGINE         │    │                            │
│  ├─ Ranked blocker list     │    │  Primary:                  │
│  ├─ Fix templates           │    │  Gemini 2.5 Flash          │
│  └─ Chatbot session         │    │                            │
└─────────────────────────────┘    │  Fallback 1:               │
                                   │  Ollama (Mistral, local)   │
                                   │                            │
                                   │  Fallback 2:               │
                                   │  Hardcoded templates       │
                                   │  (zero hallucination)      │
                                   └────────────────────────────┘
```

### AI vs Deterministic Boundary

| Component | Type | LLM | Cost |
|---|---|---|---|
| L1–L5: 16 checkpoints | Deterministic | None | $0 |
| L6: Semantic Gap (embeddings) | Deterministic | None | $0 |
| Semantic Extractor Tier 1 | Deterministic | spaCy (local) | $0 |
| Semantic Extractor Tier 2 | Deterministic | MiniLM (local, CPU) | $0 |
| L7: Conclusion paragraph | LLM | Gemini → Ollama → Template | ~$0.017/audit |
| Part 2: Fix Chatbot | LLM | Gemini → Ollama → Template | ~$0.05/session |

Every Gemini call has a rule-based fallback. The audit completes and produces a valid score with no internet connection.

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or SQLite for local dev — no setup needed)
- Ollama (optional, for offline LLM fallback)

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/ai-rep-optimizer.git
cd ai-rep-optimizer
```

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Frontend

```bash
cd frontend
npm install
```

### 4. Environment variables

Create `backend/.env`:

```env
GEMINI_API_KEY=your_key_here

# Production
DATABASE_URL=postgresql://user:password@localhost:5432/ai_rep_optimizer

# Local dev (SQLite — no setup needed)
# DATABASE_URL=sqlite:///./audit_cache.db

# Ollama fallback (optional)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral

ENVIRONMENT=development
AUDIT_CACHE_TTL_HOURS=24
```

> If `GEMINI_API_KEY` is absent or rate-limited, the system falls through to Ollama, then to hardcoded templates automatically.

### 5. Database

```bash
# PostgreSQL
psql -U postgres -c "CREATE DATABASE ai_rep_optimizer;"
cd backend && alembic upgrade head

# SQLite (dev) — no command needed, auto-created on first run
```

### 6. Run

```bash
# Terminal 1 — Backend
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev

# App:      http://localhost:5173
# API docs: http://localhost:8000/docs
```

---

## Repository Structure

```
ai-rep-optimizer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   ├── __init__.py
│   │   └── main.py
│   │
│   ├── logs/
│   │
│   ├── src/
│   │   ├── layer1/   # Crawlability
│   │   ├── layer2/   # Structured Data
│   │   ├── layer3/   # Semantic Content
│   │   ├── layer4/   # Trust Signals
│   │   ├── layer5/   # AI Protocols
│   │   ├── layer6/   # Semantic Gap
│   │   ├── layer7/   # Aggregation
│   │   ├── part2/
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── auditor.py
│   │       └── text_cleaner.py
│   │
│   ├── tests/
│   │   ├── test_backend.py
│   │   ├── test_db.py
│   │   ├── test_encoding.py
│   │   ├── test_endpoints.py
│   │   ├── test_full_architecture.py
│   │   └── test_suite.py
│   │
│   ├── .gitignore
│   ├── README.md
│   ├── conftest.py
│   ├── pytest.ini
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   │   ├── favicon.svg
│   │   └── icons.svg
│   │
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js
│   │   │
│   │   ├── assets/
│   │   │   ├── hero.png
│   │   │   ├── react.svg
│   │   │   └── vite.svg
│   │   │
│   │   ├── context/
│   │   │   └── AuditContext.jsx
│   │   │
│   │   ├── screens/
│   │   │   ├── AiMirror.jsx
│   │   │   ├── FixNow.jsx
│   │   │   ├── Landing.jsx
│   │   │   ├── McqForm.jsx
│   │   │   ├── Results.jsx
│   │   │   └── Scanning.jsx
│   │   │
│   │   ├── styles/
│   │   │   └── index.css
│   │   │
│   │   ├── App.jsx
│   │   └── main.jsx
│   │
│   ├── README.md
│   ├── eslint.config.js
│   ├── index.html
│   ├── package-lock.json
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

### Branch Structure

| Branch | Owner | Purpose |
|---|---|---|
| `validation_results` | Empirical validation study — 20+ store checkpoint analysis, false-negative measurement, checkpoint reduction from 35 → 16 |
| `AI_logic` | AI logic — semantic extractor (Tier 1+2), L6 embedding pipeline, L7 aggregation, Streamlit prototype |
| `frontend_backend` |  Full-stack foundation — FastAPI backend, PostgreSQL schema, frontend scaffold (older version) |
| `final_version` | Production merge — updated frontend, integrated AI logic, fixed inconsistencies, deployment config |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/audit` | Start a new audit — returns job_id immediately |
| `GET` | `/api/audit/status/{job_id}` | Poll for audit progress and result |
| `DELETE` | `/api/audit/cache` | Clear cached result for a store URL |
| `POST` | `/api/chat/start` | Start a fix conversation for a failed check |
| `POST` | `/api/chat/reply` | Send a message and get advisor reply |
| `GET` | `/api/chat/history` | Load full conversation history for a check |
| `GET` | `/api/fix/template/{check_code}` | Get hardcoded fix template and steps |
| `GET` | `/api/health` | Health check |

Full interactive docs: `http://localhost:8000/docs` (Swagger UI auto-generated by FastAPI)

---

## Live Demo & Documentation
| Resource | Link |
|---|---|
| Demo Video Walkthrough | [Google Drive](https://drive.google.com/file/d/1vxx2FL6pjFGCZOJxW_MQV-6OkNWx0yKo/view?usp=drive_link) |
| Product Document | [Google Drive](https://drive.google.com/file/d/1hIM0Sx8hBT7EkJ1GAiXSTlndZ2o1dH7b/view?usp=sharing) |
| Technical Document | [Google Drive](https://drive.google.com/file/d/1bz5X4DvPJNF8RADxSr6oLIAFAqZhB17X/view?usp=sharing) |
| Product Walkthrough Document | [Google Drive](https://drive.google.com/file/d/1COzKWvczI0HeaLrrZ21h6K6X_mpF4IML/view?usp=sharing) |
| Team Contribution Document | [Google Drive](https://drive.google.com/file/d/140Gy6ST_8-5j8URBhhRPgFjWuoEBObtl/view?usp=sharing) |
| Decision Log | [`DECISIONS.md`](DECISIONS.md) |

## Cost Model

| Stage | Infrastructure | Capacity | Monthly Cost |
|---|---|---|---|
| Prototype | Laptop · SQLite · Free Gemini | ~250 audits/day | **$0** |
| Beta | VPS · PostgreSQL · cached | ~200 unique/day | **~$5** |
| SaaS scale | Cloud · PostgreSQL | Unlimited | **~$17/day @ 1K audits** |

- `$0.017` per audit (L7 only — all other layers are free)
- `$0.05` per fix chatbot session
- `~$0.50` per DAU per month at scale

---

## Known Limitations

- **Non-English stores** — spaCy `en_core_web_sm` is English-only. R16/R17 may return UNKNOWN on non-English policy pages.
- **JS-rendered storefronts** — Pure client-side rendered stores without a Storefront API token are partially audited via static Shopify endpoints only.
- **Tier 3 extractor** — Gemini-based extraction for edge-case policy language (~5% of stores) is designed and documented but scoped to v3. Tier 1 + Tier 2 cover 92%+ of cases.
- **Causal claims** — 8 of 16 checks have verified mechanistic links. The remaining 8 are empirically correlated. All findings are labelled with their evidence tier. We do not claim definitive causal links to any specific LLM's internal ranking logic.
- **Business day handling** — "5 business days" and "5 days" score identically. Disambiguation is a v3 improvement.

---

## Future Work

- **Tier 3 Semantic Extractor** — Gemini-based extraction for non-standard policy language, legal phrasing, and jurisdiction-specific text. Reduces false negatives from ~8% to near-zero.
- **Multi-language support** — Replace spaCy `en_core_web_sm` with multilingual NER model. Unlocks non-English Shopify markets.
- **llms.txt support** — As the llms.txt standard matures and citation correlation evidence grows, add R2 as a scored checkpoint.
- **UCP deep audit** — Once UCP is broadly accessible, expand R28 from binary to full profile quality scoring.
- **Category-specific query banks** — Expand the buyer query banks in L6 from 5 categories to 20+, improving semantic gap precision for niche verticals.
- **Re-audit tracking** — Allow merchants to re-run audits after fixes and track score improvement over time.
- **Shopify app distribution** — Package as a native Shopify app for in-admin access without URL input.
- **Business day disambiguation** — Differentiate "5 business days" vs "5 calendar days" in R16/R17 scoring.

---

## Contribution

**Team submission — Kasparro Agentic Commerce Hackathon 2026**

| Contributor | Role | Responsibility |
|---|---|---|
| Tina Prabhat | AI / Product | Validation study, checkpoint design, semantic extractor (Tier 1+2), L6 embedding pipeline, L7 aggregation|
| Saptarshi Giri | Full-Stack | UI-UX, Product Design, FastAPI backend, PostgreSQL schema, React frontend, deployment config |



---

## License

MIT License — see [LICENSE](LICENSE)

---

*AI Representation Optimizer · v2.0 · 2026 · Built for Kasparro Track 5*
