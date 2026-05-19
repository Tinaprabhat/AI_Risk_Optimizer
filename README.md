#  AI Risk Optimizer

> **Find out exactly why AI shopping agents aren't recommending your Shopify store — and fix it.**

AI Risk Optimizer is a full-stack audit platform that runs a Shopify store URL through 7 layers of AI-readiness checks, computes semantic alignment gaps between how a merchant perceives their store vs how AI actually reads it, and provides a step-by-step guided fix engine powered by an LLM chatbot.

---

## 📌 Table of Contents

- [The Problem](#-the-problem)
- [The Idea](#-the-idea)
- [Live Demo Flow](#-live-demo-flow)
- [Architecture](#-architecture)
- [The 7 Layers](#-the-7-layers)
- [AI Mirror](#-ai-mirror)
- [Scoring System](#-scoring-system)
- [Fix Engine](#-fix-engine)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Environment Variables](#-environment-variables)
- [Running the App](#-running-the-app)
- [API Endpoints](#-api-endpoints)
- [Caching](#-caching)
- [LLM Fallback Chain](#-llm-fallback-chain)
- [Observability](#-observability)
- [Known Limitations](#-known-limitations)

---

## 🧩 The Problem

AI shopping agents like ChatGPT, Gemini, Perplexity, and Claude are increasingly being used by consumers to discover and buy products. These agents crawl stores, read structured data, and make recommendations — but most Shopify merchants have no visibility into why their store is or isn't being recommended.

Common reasons AI ignores a store:

- `robots.txt` blocks AI crawlers like `GPTBot` or `ClaudeBot`
- No `schema.org` structured data — AI cannot extract product facts
- Vague product descriptions — AI cannot differentiate the store from competitors
- No FAQ page — AI answers "I don't know" to buyer questions
- Missing refund/shipping timeframes — AI cannot answer policy questions
- No UCP profile — AI commerce agents cannot transact on behalf of buyers
- Brand name inconsistency — AI treats the store as multiple different entities

---

## 💡 The Idea

The core insight is that there are **three different versions** of every store:

1. **What the merchant thinks their store says** — their own description and intent
2. **What AI reads from the website HTML** — crawled page text
3. **What AI reads from structured data** — JSON-LD schema

When these three are **aligned**, AI recommends the store confidently.
When they **drift or misalign**, AI gets confused, gives incomplete answers, or skips the store entirely.

AI Rep Optimizer measures all three, computes the gaps between them, scores the store across 15 checks, and provides actionable fixes with a guided LLM chatbot.

---

## 🎬 Live Demo Flow

```
Screen 1 — Landing
  Enter your Shopify store URL

Screen 2 — MCQ Form
  4 multiple-choice questions about your store:
    • Category (Fashion, Beauty, Electronics, etc.)
    • Primary customer (Young adults, Parents, etc.)
    • Differentiator (Affordable, Premium, Fast delivery, etc.)
    • Brand tone (Playful, Minimal, Luxury, etc.)
  + Free text description of your store

Screen 3 — Scanning
  Live progress animation while backend runs all 7 layers
  Shows which layer is currently running
  Detects cache hit (same URL = instant result)

Screen 4 — Results
  Overall AI readiness score (X/69)
  Layer-by-layer breakdown (L1–L5)
  Each rule is clickable — shows evidence, what AI sees, fix instructions
  AI-generated conclusion paragraph (via Gemini or Ollama)
  Two buttons: AI Mirror and Fix Now

Screen 5 — AI Mirror
  3 perception cards side by side:
    🧑‍💼 Your Perception — what you described
    🌐 HTML Perception — what AI reads from your website
    🤖 AI Perception   — what AI reads from your schema/structured data
  Gap scores with ALIGNED / DRIFT / MISALIGNED labels
  Dimension matrix — how each MCQ dimension aligns per page

Screen 6 — Fix Now
  Left panel: all failed/warn checks with checkboxes
  Right panel: LLM chatbot that fixes one issue at a time
    • Gives one step at a time (not the whole answer at once)
    • Remembers conversation history (resumable after browser close)
    • User manually ticks checkbox when a fix is applied
    • Moving to next check loads a fresh conversation
```

---

## 🏗 Architecture

```
MERCHANT INPUT
  Store URL + Free text description + 4 MCQ answers
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                  │
│                                                         │
│  POST /api/audit/start  →  returns job_id immediately   │
│  GET  /api/audit/status/{job_id}  →  poll every 2s      │
│                                                         │
│  Background thread runs:                                │
│                                                         │
│  Layer 1  Crawlability      R1 R3 R5 R6    binary       │
│  Layer 2  Structured Data   R7 R9 R11      scored       │
│  Layer 3  Semantic Content  R13 R15 R16 R17 scored      │
│  Layer 4  Trust Signals     R23 R25        binary       │
│  Layer 5  AI-Era Protocols  R28 R30 R31    scored       │
│      │                                                  │
│      ▼                                                  │
│  Layer 6  Semantic Gap      gap_IW gap_IS gap_WS        │
│      │    (embeddings via all-MiniLM-L6-v2)             │
│      ▼                                                  │
│  Layer 7  Aggregator        Score + LLM Conclusion      │
│                             (Gemini → Ollama → fallback)│
│                                                         │
│  Result saved to PostgreSQL (cache)                     │
│  Observability log written to logs/                     │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite)              │
│                                                         │
│  6 screens navigated via React Router                   │
│  Global state via React Context                         │
│  All API calls via axios through api/client.js          │
└─────────────────────────────────────────────────────────┘
```

---

## 🔬 The 7 Layers

### Layer 1 — Crawlability
Checks if AI crawlers can physically access the store.

| Rule | What it checks | Type |
|------|----------------|------|
| R1 | `robots.txt` — are AI agents (GPTBot, ClaudeBot, Google-Extended etc.) blocked? | Binary |
| R3 | `sitemap.xml` — does it exist and contain product URLs? | Binary |
| R5 | Bot protection — is Cloudflare or similar blocking AI crawlers? | Binary |
| R6 | SSL certificate — is HTTPS valid and not expired? | Binary |

### Layer 2 — Structured Data
Checks the quality of machine-readable data on the store.

| Rule | What it checks | Type |
|------|----------------|------|
| R7 | `schema.org` commerce types (Product, Organization, FAQPage etc.) | Scored 0–10 |
| R9 | Price signal — is price visible in JSON-LD, meta tags, or HTML? | Scored 0–10 |
| R11 | JSON-LD validity — are all JSON-LD blocks parseable? | Binary |

### Layer 3 — Semantic Content
Checks the quality and specificity of human-readable content.

| Rule | What it checks | Type |
|------|----------------|------|
| R13 | Product description vagueness — specific facts vs vague adjectives | Scored 0–10 |
| R15 | FAQ page — exists and covers 6 core buyer topics | Binary |
| R16 | Refund policy — states a concrete return window (exact days) | Scored 0–10 |
| R17 | Shipping policy — states a concrete delivery timeframe | Scored 0–10 |

### Layer 4 — Trust Signals
Checks signals that help AI verify store accountability.

| Rule | What it checks | Type |
|------|----------------|------|
| R23 | Contact page with branded email (not Gmail/Yahoo) | Binary |
| R25 | Brand name consistency across og:site_name, schema.org, title tag | Binary |

### Layer 5 — AI-Era Protocols
Checks next-generation AI commerce protocols.

| Rule | What it checks | Type |
|------|----------------|------|
| R28 | UCP profile at `/.well-known/ucp` — enables AI commerce agents | Binary |
| R30 | ACP feed quality — Shopify auto-enrollment status (informational only) | Info |
| R31 | Google Merchant Center signals — 4 key signals for Gemini surfacing | Scored 0–10 |

### Layer 6 — Semantic Gap (AI Mirror)
Uses sentence embeddings (`all-MiniLM-L6-v2`) to compute cosine distance between:

- **V1** — Merchant intent vector (free text + MCQ answers)
- **V2** — Website content vector (crawled page text)
- **V3** — Schema vector (JSON-LD or crawled fallback)

Three gap scores:
- `gap_IW` — Intent vs Website (does your site say what you think?)
- `gap_IS` — Intent vs Schema (does your schema match your intent?)
- `gap_WS` — Website vs Schema (are your content and schema consistent?)

Labels: `ALIGNED` (< 0.15) | `DRIFT` (0.15–0.30) | `MISALIGNED` (> 0.30)

### Layer 7 — Aggregator
- Computes final score from all checks
- Calls Gemini 2.5 Flash (→ Ollama Mistral → rule-based fallback) to generate a 3–4 sentence conclusion
- Returns full result dict including observability block

---

## 🪞 AI Mirror

The AI Mirror is the most unique feature of the platform. It shows three simultaneous "views" of the same store:

```
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   🧑‍💼 YOUR PERCEPTION  │  │  🌐 HTML PERCEPTION   │  │  🤖 AI PERCEPTION    │
│                      │  │                      │  │                      │
│ What you described   │  │ What AI reads from   │  │ What AI reads from   │
│ in the MCQ form      │  │ your website's HTML  │  │ your JSON-LD schema  │
│ and free text        │  │ when it crawls       │  │ or crawled fallback  │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
         │                          │                          │
         └──────────── gap_IW ──────┘                          │
         │                                                     │
         └──────────────────────── gap_IS ─────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │         gap_WS                │
                    └───────────────────────────────┘
```

Also includes a **Dimension Matrix** — how each of the 4 MCQ dimensions (category, customer, differentiator, tone) aligns across each crawled page (homepage, about, policies).

---

## 📊 Scoring System

```
Scored checks (quality 0–10 each):
  R7   Schema.org commerce types
  R9   Price signal strength
  R13  Product description specificity
  R16  Refund policy concreteness
  R17  Shipping policy concreteness
  R31  Google Merchant Center signals
  ─────────────────────────────────
  Max: 60 points

Checklist checks (binary 0/1 each):
  R1   robots.txt allows AI crawlers
  R3   sitemap.xml present
  R5   No bot protection blocking
  R6   SSL valid
  R11  JSON-LD valid syntax
  R15  FAQ page covers key topics
  R23  Contact page + branded email
  R25  Brand name consistent
  R28  UCP profile exists
  ─────────────────────────────────
  Max: 9 points

R30: Informational only — not scored

TOTAL MAXIMUM: 69 points
```

Score interpretation:
- **≥ 80%** — Excellent — well optimised for AI discovery
- **60–79%** — Good — a few gaps to fix
- **40–59%** — Average — significant issues reducing visibility
- **< 40%** — Poor — major issues blocking AI recommendations

---

## 🔧 Fix Engine

The Fix Engine (Part 2) provides guided remediation for every failed check.

**How it works:**
1. Merchant selects a failed check from the left panel
2. Bot sends an opening message explaining the issue and asking if they're ready
3. Merchant replies — bot gives **one step at a time** (not the whole fix at once)
4. Conversation history is saved in PostgreSQL — resumable after browser close
5. When merchant applies a fix, they manually tick the checkbox
6. They move to the next check and a fresh conversation starts

**Template coverage:** All 15 checks have hardcoded fix templates with exact steps and copy-paste code snippets. LLM only handles follow-up questions and step explanations.

**LLM scope rule:** The system prompt restricts the LLM to only answer questions about the current check. Off-topic questions are redirected back to the fix.

---

## 🛠 Tech Stack

### Backend
| Component | Technology |
|-----------|------------|
| API framework | FastAPI + Uvicorn |
| Database | PostgreSQL (via psycopg2-binary) |
| Embeddings | `all-MiniLM-L6-v2` via sentence-transformers |
| Primary LLM | Gemini 2.5 Flash (google-generativeai) |
| Fallback LLM | Ollama Mistral (local) |
| HTML parsing | BeautifulSoup4 + extruct |
| HTTP client | requests (with retry + timeout logic) |
| Schema parsing | rapidfuzz (brand fuzzy matching) |
| Logging | Python logging + structured JSON logs |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | React 18 + Vite |
| Routing | React Router v6 |
| State management | React Context API |
| HTTP client | axios |
| Styling | Inline styles with CSS variables |

---

## 📁 Project Structure

```
kasparro/
├── backend/
│   ├── main.py                         # FastAPI entry point
│   ├── requirements.txt
│   ├── .env                            # Environment variables
│   ├── db/
│   │   └── audits.db                   # (if SQLite fallback used)
│   ├── logs/                           # Observability JSON logs (one per audit)
│   └── app/
│       ├── api/
│       │   └── routes.py               # All API endpoints
│       ├── services/
│       │   ├── auditor.py              # Main audit orchestrator
│       │   └── fix_engine.py           # Fix templates + chatbot
│       ├── layers/
│       │   ├── layer1/
│       │   │   ├── r1_robots.py        # robots.txt check
│       │   │   └── r3_r5_r6.py        # sitemap, bot protection, SSL
│       │   ├── layer2/
│       │   │   └── r7_r9_r11.py       # schema.org, price, JSON-LD
│       │   ├── layer3/
│       │   │   └── r13_r15_r16_r17.py # descriptions, FAQ, policies
│       │   ├── layer4/
│       │   │   └── r23_r25.py         # contact, brand consistency
│       │   ├── layer5/
│       │   │   └── r28_r30_r31.py     # UCP, ACP, GMC signals
│       │   ├── layer6/
│       │   │   └── semantic_gap.py    # AI mirror embeddings
│       │   └── layer7/
│       │       └── aggregator.py      # scoring + LLM conclusion
│       └── utils/
│           ├── db.py                  # PostgreSQL — cache + chat history
│           ├── embedder.py            # all-MiniLM-L6-v2 singleton
│           ├── fetcher.py             # HTTP client (retry, timeout, garbage detection)
│           ├── llm.py                 # Gemini → Ollama → fallback chain
│           ├── obs_logger.py          # Structured observability logging
│           └── text_cleaner.py        # Strip JS/JSON blobs from HTML
│
└── frontend/
    ├── .env                           # VITE_API_BASE_URL
    ├── package.json
    └── src/
        ├── main.jsx
        ├── App.jsx                    # React Router — all 6 screens
        ├── api/
        │   └── client.js              # All backend calls in one place
        ├── context/
        │   └── AuditContext.jsx       # Global state across all screens
        ├── screens/
        │   ├── Landing.jsx            # Screen 1 — URL input
        │   ├── McqForm.jsx            # Screen 2 — store description
        │   ├── Scanning.jsx           # Screen 3 — live progress
        │   ├── Results.jsx            # Screen 4 — scores + layer breakdown
        │   ├── AiMirror.jsx           # Screen 5 — 3 perception cards
        │   └── FixNow.jsx             # Screen 6 — chatbot fix engine
        └── styles/
            └── index.css
```

---

## ✅ Prerequisites

### Backend
- Python 3.11+
- PostgreSQL 14+ (installed and running)
- Ollama (optional — fallback LLM)

### Frontend
- Node.js 18+
- npm 9+

### API Keys
- Gemini API key from [Google AI Studio](https://aistudio.google.com) (free tier: 20 req/day)

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/kasparro.git
cd kasparro
```

### 2. Set up PostgreSQL

```bash
psql -U postgres
CREATE DATABASE ai_rep_optimizer;
\q
```

### 3. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
```

### 5. Set up Ollama (optional — fallback LLM)

```bash
# Install from https://ollama.com
ollama pull mistral
ollama serve
```

---

## 🔑 Environment Variables

### `backend/.env`

```env
# LLM
GEMINI_API_KEY=your_gemini_api_key_here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral

# PostgreSQL
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/ai_rep_optimizer
```

### `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

---

## ▶️ Running the App

Open two terminals:

**Terminal 1 — Backend**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

Backend API docs available at **http://localhost:8000/docs**

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/audit/start` | Start a new audit — returns `job_id` immediately |
| `GET` | `/api/audit/status/{job_id}` | Poll for audit progress and result |
| `DELETE` | `/api/audit/cache` | Clear cached result for a URL |
| `POST` | `/api/chat/start` | Start a fix conversation for a check |
| `POST` | `/api/chat/reply` | Send a message and get advisor reply |
| `GET` | `/api/chat/history` | Load full conversation history |
| `GET` | `/api/fix/template/{check_code}` | Get hardcoded fix template |
| `GET` | `/api/health` | Health check |

### Example: Start an audit

```bash
curl -X POST http://localhost:8000/api/audit/start \
  -H "Content-Type: application/json" \
  -d '{
    "store_url": "https://yourstore.myshopify.com",
    "free_text": "We sell sustainable shoes made from natural materials",
    "mcq": {
      "category": "footwear",
      "customer": "eco-conscious adults",
      "differentiator": "sustainable natural materials",
      "tone": "friendly and eco-focused"
    },
    "use_cache": true
  }'
```

Response:
```json
{ "job_id": "abc123", "status": "running" }
```

---

## 💾 Caching

Audit results are cached in PostgreSQL for **24 hours**.

- Same URL submitted on the same day → instant result from cache (< 1s)
- Same URL on a different day → full re-audit runs (30–60s)
- `use_cache: false` in the request → always forces a fresh audit

**Why 24-hour cache?** Store data changes daily — robots.txt, policies, prices, and schema can all update. A day-old audit is considered stale.

Cache hit is visible in the scanning screen as "⚡ Retrieved from cache — instant result" and in the backend terminal as:
```
💾 CACHE HIT — https://yourstore.com/
```

---

## 🤖 LLM Fallback Chain

```
1. Gemini 2.5 Flash (cloud)
   ↓ fails if: API key invalid, quota exceeded (20/day free tier), network error
2. Ollama Mistral (local)
   ↓ fails if: Ollama not running, mistral not pulled
3. Rule-based fallback (hardcoded)
   Always works — generates a deterministic conclusion from score and failed checks
```

The LLM is only used for:
- Generating the 3–4 sentence audit conclusion (Layer 7)
- Responding to fix chatbot messages (Fix Engine)

All 15 check rules, scoring, and fix templates are deterministic — no LLM required.

---

## 🔍 Observability

Every audit writes a structured JSON log to `backend/logs/`:

```
logs/
└── audit_yourstore.com_20260519T031313Z.json
```

Each log contains:
- Full per-check trace (what was fetched, what was found, why it passed/failed)
- Raw evidence for each check
- What AI sees from each check
- Causality trace ("R1 PASSED — No AI crawlers blocked")
- All 3 AI Mirror perception texts
- Gap scores with labels
- Full LLM conclusion
- First 500 chars of each crawled page

This is for **debugging and transparency** — the app functions entirely from PostgreSQL, logs are for developer inspection.

---

## ⚠️ Known Limitations

| Limitation | Detail |
|------------|--------|
| Gemini free tier | 20 requests/day. Upgrade to paid or use Ollama for heavy testing |
| Shopify-specific | Some checks (R28 UCP, R30 ACP) are Shopify-only. Non-Shopify stores get FORWARD-LOOKING status |
| Brotli encoding | Some stores serve Brotli-compressed HTML. The fetcher strips `br` from Accept-Encoding to avoid this |
| R13 on homepage | Product description vagueness is checked on homepage text only, not product pages |
| Embedding model | `all-MiniLM-L6-v2` has a 256-token context limit. Long texts are chunked before embedding |
| Single user | In-memory job store (`_jobs` dict in routes.py) is lost on server restart. Use Redis for production multi-user deployment |
| No auth | No user authentication — suitable for internal/demo use. Add JWT or session auth for production |

---

## 🗺 Future-Roadmap

- [ ] Redis job queue for production multi-user support
- [ ] Product page audit (not just homepage)
- [ ] Competitor comparison — audit two stores side by side
- [ ] Weekly automated re-audit with email diff report
- [ ] Chrome extension — audit any store while browsing
- [ ] Export audit report as PDF

---


<p align="center">
  Built to make every Shopify store AI-visible.<br/>
  <strong>If AI can't read your store, AI can't recommend your store.</strong>
</p>
