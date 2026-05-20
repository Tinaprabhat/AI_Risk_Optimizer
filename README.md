# AI Representation Optimizer — Full Stack Reference

> **Branch: `frontend-Backend`** — Production-ready full stack.  
> FastAPI backend · PostgreSQL · React frontend · 7-layer audit engine · Gemini → Ollama → Template fallback chain.

---

## Table of Contents

1. [Repository Structure](#repository-structure)
2. [Frontend — Screen by Screen](#frontend--screen-by-screen)
3. [Backend — Architecture & Logic](#backend--architecture--logic)
4. [Database Schema](#database-schema)
5. [Setup & Run](#setup--run)
6. [Environment Variables](#environment-variables)
7. [API Endpoints](#api-endpoints)
8. [Design Decisions](#design-decisions)

---

## Repository Structure

```
kasparro/
├── backend/
│   ├── main.py                    # FastAPI entry — mounts router, CORS, lifespan
│   ├── requirements.txt
│   ├── .env
│   ├── db/
│   │   └── audits.db              # SQLite fallback (dev only)
│   ├── logs/                      # One structured JSON log per audit (observability)
│   └── app/
│       ├── api/
│       │   └── routes.py          # All endpoints — imported and mounted in main.py
│       ├── services/
│       │   ├── auditor.py         # Orchestrates L1→L7, calls each layer, assembles result
│       │   └── fix_engine.py      # Fix templates + Gemini chatbot session manager
│       ├── layers/
│       │   ├── layer1/
│       │   │   ├── r1_robots.py
│       │   │   └── r3_r5_r6.py
│       │   ├── layer2/
│       │   │   └── r7_r9_r11.py
│       │   ├── layer3/
│       │   │   └── r13_r15_r16_r17.py
│       │   ├── layer4/
│       │   │   └── r23_r25.py
│       │   ├── layer5/
│       │   │   └── r28_r30_r31.py
│       │   ├── layer6/
│       │   │   └── semantic_gap.py
│       │   └── layer7/
│       │       └── aggregator.py
│       └── utils/
│           ├── db.py              # PostgreSQL connection + query helpers
│           ├── embedder.py        # all-MiniLM-L6-v2 singleton (loaded once)
│           ├── fetcher.py         # HTTP client — retry, jitter, timeout, garbage detection
│           ├── llm.py             # Gemini → Ollama → template fallback chain
│           ├── obs_logger.py      # Structured JSON observability logger
│           └── text_cleaner.py    # Strips JS blobs, nav chrome, cookie banners from HTML
│
└── frontend/
    ├── .env                       # VITE_API_BASE_URL
    ├── package.json
    └── src/
        ├── main.jsx
        ├── App.jsx                # React Router — all 6 screens wired here
        ├── api/
        │   └── client.js          # Single file — every backend call in one place
        ├── context/
        │   └── AuditContext.jsx   # Global audit state — shared across all screens
        ├── screens/
        │   ├── Landing.jsx        # Screen 1 — URL input
        │   ├── McqForm.jsx        # Screen 2 — MCQs + free text
        │   ├── Scanning.jsx       # Screen 3 — live audit progress
        │   ├── Results.jsx        # Screen 4 — score + layer breakdown
        │   ├── AiMirror.jsx       # Screen 5 — 3-perception comparison
        │   └── FixNow.jsx         # Screen 6 — chatbot fix engine
        └── styles/
            └── index.css
```

---

## Frontend — Screen by Screen

All screens share state through `AuditContext.jsx`. No prop drilling.  
Navigation is handled by React Router in `App.jsx`.  
Every backend call goes through `api/client.js` — nowhere else.

---

### Screen 1 — `Landing.jsx`

**What the merchant sees:**  
A single bold headline: *"Why isn't AI recommending your store?"*  
One input field for the Shopify URL. One button: *Analyze Store →*  
Three stat chips below the fold: 7 Layers Checked · 15+ Rules Audited · 69 Max Score.  
Layer tags as visual context: Crawlability · Structured Data · Semantic Content · Trust Signals · AI Protocols · AI Mirror · Fix Engine.

**UX rationale:**  
The merchant arrives with a single anxiety — "AI is ignoring me and I don't know why." The headline names that anxiety directly. No feature list, no explanation of how it works. One input, one action. Cognitive load at entry point: zero.

The stat chips and layer tags serve a secondary purpose: they signal credibility without demanding attention. A merchant who glances at "15+ Rules Audited" before clicking trusts the tool more than one who sees a blank input field.

**What happens on submit:**  
URL is validated (must be https, must resolve). Stored in `AuditContext`. Router pushes to `/mcq`.

**Code note — `Landing.jsx`:**
```jsx
const { setUrl } = useAudit();

const handleSubmit = () => {
  if (!isValidUrl(input)) { setError("Enter a valid Shopify URL"); return; }
  setUrl(input);
  navigate("/mcq");
};
```

---

### Screen 2 — `McqForm.jsx`

**What the merchant sees:**  
Four multiple-choice selectors and one free-text box:
1. **Store Category** — Fashion & Apparel / Beauty & Cosmetics / Electronics / Home & Living / Food & Beverages / Health & Wellness / Sports & Fitness / Jewellery / Books & Stationery / Other
2. **Primary Customer** — Young adults / Millennials / Parents & families / Professionals / Students / Senior shoppers / Makeup enthusiasts / Fitness conscious / Tech-savvy / Budget-conscious
3. **Main Differentiator** — Premium quality / Lowest price / Fastest delivery / Widest range / Sustainability / Handmade / Local brand / Exclusive / Custom-made
4. **Brand Tone** — Playful / Minimal / Luxury & refined / Bold / Friendly / Professional / Youthful / Earthy / Quirky / Serious
5. **Describe your store** — free text, 500 chars, placeholder example shown

Progress indicator at bottom: `4 / 5 completed` with dot stepper.  
*Analyze Store →* button activates only when all 4 MCQs are answered.

**UX rationale:**  
This screen is not a form — it is intent capture for the semantic gap engine. The merchant's answers become **Vector V1** (merchant intent) in L6. Without this, the AI Mirror has nothing to compare against.

The MCQ format over free text for the first 4 questions is deliberate. A non-technical merchant asked to "describe your brand tone in their own words" will write something that is difficult to embed consistently. Constrained options produce cleaner, more comparable embeddings. The free text field in question 5 is additive — it feeds the same vector but is not required for scoring.

The progress stepper communicates that this is a short, bounded commitment. Merchants abandon multi-page forms. A visible "4/5 completed" reduces drop-off at the last step.

**What happens on submit:**  
MCQ selections and description stored in `AuditContext`. `POST /api/audit` called with `{ url, category, customer, differentiator, tone, description }`. Router pushes to `/scanning` with the pending audit promise.

---

### Screen 3 — `Scanning.jsx`

**What the merchant sees:**  
*"Audit Complete"* heading once done.  
Seven layer cards checking off in sequence, each with a green tick as it completes:
- Layer 1 — Crawlability
- Layer 2 — Structured Data
- Layer 3 — Semantic Content
- Layer 4 — Trust Signals
- Layer 5 — AI-Era Protocols
- Layer 6 — Semantic Gap
- Layer 7 — Scoring & Conclusion

Cache indicator at bottom: `⚡ Retrieved from cache — instant result` or `Fresh audits take 30–60 seconds`.

**UX rationale:**  
The audit takes 30–60 seconds on a fresh URL. Showing a spinner for 45 seconds without context destroys trust — the merchant assumes it's broken. Showing layer progress converts wait time into understanding. By the time the audit completes, the merchant already knows what the 7 layers are. This reduces explanation burden on the Results screen.

The cache indicator is honest and functional. A merchant re-running the same URL sees an instant result and knows why. A first-time run sees a timer expectation. Both are correct.

The layer-by-layer reveal is not cosmetic. It is powered by server-sent events (SSE) from the backend — each layer emits a completion event as it finishes. The frontend listens and updates the UI in real time.

**Code note — SSE listener in `Scanning.jsx`:**
```jsx
useEffect(() => {
  const source = new EventSource(`${API_BASE}/api/audit/stream/${auditId}`);
  source.onmessage = (e) => {
    const { layer, status } = JSON.parse(e.data);
    setLayerStatus(prev => ({ ...prev, [layer]: status }));
    if (layer === "L7" && status === "complete") {
      source.close();
      navigate("/results");
    }
  };
  return () => source.close();
}, [auditId]);
```

---

### Screen 4 — `Results.jsx`

**What the merchant sees:**

**Score card (top):**  
Circular arc gauge showing percentage.  
`42% — POOR` in red / `67% — FAIR` in amber / `85% — GOOD` in green.  
Three sub-scores: `22 / 60` Scored Checks · `7 / 9` Checklist · `29 / 69` Total.

**AI Conclusion card:**  
LLM-generated paragraph (Gemini or Ollama fallback) explaining the score in plain merchant language. References specific checkpoint codes. Attributes source: `via gemini_flash` or `via ollama_mistral`.

**Issues Found — ranked priority list:**  
Each failing checkpoint shown as a numbered priority card:
- `#1 PRIORITY` — Red border. Checkpoint code + layer label + one-line finding. Quick Fix preview. `▼ Show evidence & full fix` expandable.
- `#2 PRIORITY` — Orange border.
- `#3 PRIORITY` — Yellow border.

**Passed checks — collapsible dropdown:**  
`✓ 8 checks passed` — collapsed by default. Expands to show all passing checkpoints with exact evidence:  
`✓ R1 CRAWLABILITY No AI crawlers blocked in robots.txt`  
`✓ R3 CRAWLABILITY Sitemap index (5 child sitemaps). Products: 290`  
`✓ R23 TRUST SIGNALS Contact page with branded email: hello@store.com`

Two CTAs at the bottom: `AI Mirror` (ghost button) · `Fix Now →` (primary, purple).

**UX rationale:**  
The most important UX decision on this screen: **failed checks appear naturally, passed checks are hidden in a dropdown.**

This is intentional. A merchant who sees 8 green ticks and 7 red crosses reads it as "mostly fine." A merchant who sees 7 ranked problems with fixes reads it as "here is my action plan." The framing changes behaviour. The dropdown is available for merchants who want reassurance — but it is not the default view.

Priority ranking is not alphabetical or by layer — it is by **impact weight**, computed in `layer7/aggregator.py`. R15 (FAQ coverage) ranks above R17 (shipping timeframe) because it blocks more buyer query types, not because it appears first in the checkpoint list.

The score being out of 69 (not 100) is also deliberate. A percentage score out of 100 invites comparison to SEO tools that give everything 85+. A raw score out of 69 communicates that this is a specific, bounded measurement with real meaning per point.

---

### Screen 5 — `AiMirror.jsx`

**What the merchant sees:**

**Header card:**  
`AI Mirror` with status badge: `✗ MISALIGNED` (red) or `✓ ALIGNED` (green).  
Subtitle: *"3 different views of your store — yours, your website's, and what AI reads."*

**Three perception cards side by side:**
1. **Your Perception** 🧑 — What YOU think your store says, built from MCQ answers + free text. Displayed as a natural language summary.
2. **HTML Perception** 🌐 — What AI reads from your actual website text when it crawls your pages. Extracted from crawled content.
3. **AI Perception** 🤖 — Built from structured data (JSON-LD). Badge: `No JSON-LD — crawled text used` if schema absent.

**Three gap scores:**
- `Your Intent vs Website` — cosine similarity score + `✗ MISALIGNED` / `⚠ DRIFT` / `✓ ALIGNED`
- `Your Intent vs AI Data` — same scale
- `Website vs AI Data` — same scale

**Dimension Gap Matrix (4×5 grid):**  
Rows: Tone · Category · Customer · Differentiator  
Columns: About · Homepage · Policies · Products · FAQs
Each cell shows gap score + status label (MIS / DRIFT / OK).  
Lower score = worse alignment.

`Fix Now — resolve these gaps →` CTA at bottom.

**UX rationale:**  
This screen exists because a score alone does not explain *why* the merchant's store is misunderstood. A merchant can score 42/69 and not know whether the problem is crawlability (fixable in 10 minutes) or fundamental brand-content misalignment (requires rewriting pages).

The three-perception frame solves this by making the gap visible as a comparison rather than a number. A merchant who sees their "Luxury & refined" intent sitting next to a crawled homepage that reads as a promotional coupon page understands the problem immediately — no technical explanation needed.

The dimension gap matrix is the most technically novel output in the product. It is computed in `layer6/semantic_gap.py` using `all-MiniLM-L6-v2` embeddings. The 4 merchant intent dimensions (Tone, Category, Customer, Differentiator) are each encoded separately and compared against the corresponding embeddings from 3 page types (About, Homepage, Policies). This gives 12 independent gap scores — not one blended number.

**Why this matters for AI recommendation:** An AI agent building a store representation for a query like *"luxury bedding for families"* pulls from multiple pages. If the Homepage talks about discounts and the About page talks about craftsmanship, the AI receives a contradictory signal and either averages them (weakening the luxury positioning) or deprioritises the store entirely. The matrix makes each of those contradictions individually visible.

---

### Screen 6 — `FixNow.jsx`

**What the merchant sees:**

**Progress header:**  
`Fix Now — 4/7 resolved` with a linear progress bar (green fill).

**Issue list — two states:**

*Resolved issues* (strikethrough, green tick):
```
✓ R13  Resolved
   Descriptions are mostly vague (delta=0.13)

✓ R15  Resolved
   FAQ page thin — only 1/6 topics covered
```

*Unresolved issues* (active, checkbox):
```
☐ ⚠ R5   WARN
   Possible bot challenge page detected — markers: ['captcha']

☐ ⚠ R7   WARN
   Commerce schema score: 3/10 — types: ['Organization']

☐ ⚠ R9   WARN
   Currency prices visible in HTML (9 found): ['$25', '$50.00', '$75.00']
```

**Fix panel (opens when checkbox selected):**  
Hardcoded fix template shown first:
```
FIX
Replace vague adjectives with measurable facts.
Instead of: 'premium quality materials'
Write: 'made from 316L surgical stainless steel, 2mm thickness, weight 85g'

AI cannot distinguish you from competitors without specific, factual descriptions.
```

Below the template: **Gemini chatbot** for conversational follow-up.  
`View AI Mirror` ghost button at bottom.

**UX rationale:**  
The fix engine is Part 2 of the system — it only activates after the audit. The critical design decision here is **hardcoded templates first, LLM second**.

Hardcoded templates are shown immediately for every failing checkpoint — no API call, no wait, no hallucination risk. The template for R13 (vague descriptions) always shows the same before/after example. The template for R16 (refund window) always shows the same policy rewrite format. This is deterministic and auditable.

The Gemini chatbot layer sits below the template — not instead of it. Its role is conversational adaptation: a merchant who sells handmade ceramics needs different specifics than one who sells electronics. The chatbot takes the hardcoded template as context and helps the merchant apply it to their specific store.

The progress tracker (4/7 resolved) is driven by merchant self-reporting — checking a box marks an issue as resolved. This is intentional. The tool cannot verify that a merchant has actually updated their site. But giving the merchant a visible progress indicator creates commitment and reduces abandonment. A merchant at 4/7 is more likely to finish than one with an undifferentiated list of problems.

**Fallback behaviour:** If Gemini is unavailable, the chatbot panel shows: *"Guided fix unavailable — use the template above. Gemini API is currently unreachable."* The merchant still has the complete hardcoded fix. Zero blocking.

---

## Backend — Architecture & Logic

### `main.py` — Entry Point

`main.py` does four things and nothing else:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router
from app.utils.db import init_db
from app.utils.embedder import load_embedder

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise DB tables, load embedder into memory once
    await init_db()
    load_embedder()          # all-MiniLM-L6-v2 — 80MB, CPU, loaded once
    yield
    # Shutdown: nothing to clean up

app = FastAPI(title="AI Rep Optimizer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", os.getenv("FRONTEND_URL", "")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
```

The embedder is loaded at startup and held as a module-level singleton in `embedder.py`. Loading it per-request would add 3–5 seconds per audit. Loading it once at startup costs nothing per request.

---

### `app/api/routes.py` — All Endpoints

All endpoints live here. Mounted at `/api` by `main.py`.

```python
@router.post("/audit")              # Trigger new audit
@router.get("/audit/{audit_id}")    # Retrieve cached result
@router.get("/audit/stream/{id}")   # SSE — live layer progress
@router.get("/mirror/{audit_id}")   # AI Mirror — 3-perception data
@router.post("/fix/start")          # Start fix session for a checkpoint
@router.post("/fix/chat")           # Continue chatbot conversation
@router.get("/health")              # Gemini + Ollama + DB status
```

Each endpoint does only two things: validate input and call a service. No business logic in routes.

```python
@router.post("/audit")
async def trigger_audit(payload: AuditRequest, db: AsyncSession = Depends(get_db)):
    # 1. Check cache
    cached = await get_cached_audit(db, payload.url)
    if cached:
        return cached

    # 2. Run audit (delegated entirely to auditor.py)
    result = await run_audit(payload, db)
    return result
```

---

### `app/services/auditor.py` — Audit Orchestrator

The core orchestration layer. Called by the `/audit` endpoint. Runs all 7 layers sequentially, assembles the full result, writes to PostgreSQL, emits SSE events.

```python
async def run_audit(payload: AuditRequest, db: AsyncSession) -> AuditResult:

    audit_id = str(uuid4())
    await emit_sse(audit_id, "L0", "started")

    # Semantic extractor runs once — feeds all layers
    extracted = await run_extractor(payload.url)

    # L1–L5: fully deterministic, no LLM
    l1 = await run_layer1(payload.url, extracted)
    await emit_sse(audit_id, "L1", "complete")

    l2 = await run_layer2(payload.url, extracted)
    await emit_sse(audit_id, "L2", "complete")

    l3 = await run_layer3(payload.url, extracted)
    await emit_sse(audit_id, "L3", "complete")

    l4 = await run_layer4(payload.url, extracted)
    await emit_sse(audit_id, "L4", "complete")

    l5 = await run_layer5(payload.url, extracted)
    await emit_sse(audit_id, "L5", "complete")

    # L6: embeddings — deterministic, no LLM
    l6 = await run_semantic_gap(payload, extracted)
    await emit_sse(audit_id, "L6", "complete")

    # L7: one LLM call — Gemini → Ollama → template
    l7 = await run_aggregator(l1, l2, l3, l4, l5, l6, payload)
    await emit_sse(audit_id, "L7", "complete")

    # Assemble, persist, log
    result = assemble_result(audit_id, l1, l2, l3, l4, l5, l6, l7)
    await save_audit(db, result)
    await write_obs_log(audit_id, result)

    return result
```

All fetches are sequential with per-domain jitter (±500ms). Parallel requests trigger Cloudflare bot protection after 3–5 rapid hits on the same domain.

---

### `app/services/fix_engine.py` — Fix Engine

Manages fix sessions. Two distinct components:

**Hardcoded templates** — `TEMPLATES` dict keyed by checkpoint code. No LLM. No hallucination. Returns instantly.

```python
TEMPLATES = {
    "R13": {
        "title": "Product descriptions — replace vague with specific",
        "fix": "Replace vague adjectives with measurable facts...",
        "example_before": "premium quality materials",
        "example_after": "made from 316L surgical stainless steel, 2mm thickness, weight 85g",
        "why": "AI cannot distinguish you from competitors without specific, factual descriptions."
    },
    "R15": { ... },
    "R16": { ... },
    # ... all 16 checkpoints
}
```

**Gemini chatbot layer** — wraps the template as context, adds merchant store details, runs a conversational session.

```python
async def chat(session_id: str, message: str, db: AsyncSession) -> str:
    history = await get_chat_history(db, session_id)
    session = await get_session(db, session_id)
    template = TEMPLATES[session.checkpoint]

    prompt = build_prompt(template, session.audit_context, history, message)
    response = await llm.generate(prompt)   # Gemini → Ollama → template

    await save_chat_turn(db, session_id, message, response)
    return response
```

Chat history is persisted in PostgreSQL per session. A merchant can close the browser and resume.

---

### `app/layers/` — The 16 Checkpoints

Each layer module receives the crawled/extracted data and returns a standardised result object:

```python
@dataclass
class CheckResult:
    code: str           # "R1", "R13", etc.
    status: str         # "PASS" | "FAIL" | "WARN" | "UNKNOWN"
    score: float        # 0.0–10.0 for scored checks, 0 or 1 for binary
    finding: str        # One-line human-readable finding
    evidence: dict      # Raw extracted values that produced the result
    fix_template: str   # Checkpoint code — looked up in fix_engine.TEMPLATES
```

**`layer6/semantic_gap.py`** is the most complex module. It:
1. Encodes V1 (merchant intent from MCQ answers) using `embedder.py`
2. Encodes V2 (website content from crawled HTML, cleaned by `text_cleaner.py`)
3. Encodes V3 (schema content from JSON-LD extracted by `extruct`)
4. Computes cosine distance for all three pairs
5. Breaks intent into 4 dimensions (Tone, Category, Customer, Differentiator) and computes per-dimension distances against 3 page types (About, Homepage, Policies, FAQs, Product)
6. Returns the 4×5 gap matrix + three summary gap scores

**`layer7/aggregator.py`** receives all layer results, computes the weighted X/69 score, ranks blockers by impact weight, and calls `llm.py` for the conclusion paragraph.

---

### `app/utils/` — Shared Utilities

**`fetcher.py`** — All HTTP fetching goes through here. Never call `requests` directly in a layer.

```python
async def fetch(url: str, timeout: int = 5) -> FetchResult:
    await asyncio.sleep(random.uniform(0, 0.5))   # jitter — avoids Cloudflare
    for attempt in [0, 2, 8]:
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS)
            if is_garbage(resp):          # JS-only page, challenge page
                return FetchResult(content="", garbage=True)
            return FetchResult(content=resp.text, status=resp.status_code)
        except requests.Timeout:
            await asyncio.sleep(attempt)
    return FetchResult(content="", timeout=True)
```

**`llm.py`** — The fallback chain. Every LLM call in the system goes through here.

```python
async def generate(prompt: str) -> LLMResult:
    # Try Gemini 2.5 Flash
    try:
        result = await gemini_generate(prompt)
        return LLMResult(text=result, source="gemini_flash")
    except (GeminiRateLimitError, GeminiUnavailableError):
        pass

    # Try Ollama (local Mistral)
    try:
        result = await ollama_generate(prompt)
        return LLMResult(text=result, source="ollama_mistral")
    except OllamaUnavailableError:
        pass

    # Hardcoded template fallback
    result = template_generate(prompt)
    return LLMResult(text=result, source="template")
```

The `source` field is returned to the frontend and displayed in the AI Conclusion card (`via gemini_flash` or `via ollama_mistral`). Transparency about which system generated the conclusion.

**`embedder.py`** — `all-MiniLM-L6-v2` loaded once at startup as a module-level singleton. 80MB on disk. Runs entirely on CPU. Deterministic — same input always produces same embedding.

```python
_model = None

def load_embedder():
    global _model
    _model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(texts: list[str]) -> np.ndarray:
    if _model is None:
        raise RuntimeError("Embedder not initialised — call load_embedder() at startup")
    return _model.encode(texts, normalize_embeddings=True)
```

**`obs_logger.py`** — Writes one structured JSON log per audit to `/logs/`. Each log contains: audit_id, url, all 16 checkpoint results with raw evidence, layer timings, LLM source used, total audit time. Used for debugging and post-hoc validation.

**`text_cleaner.py`** — Strips JS blobs, JSON embedded in `<script>` tags, cookie banners, navigation chrome, and inline CSS before feeding HTML to the semantic extractor. Without this, the embedder receives noise that degrades cosine similarity measurements.

---

## Database Schema

PostgreSQL (production). SQLite fallback available for local dev (same schema, managed by `db.py`).

```sql
-- Audit cache — avoids re-running expensive audits
CREATE TABLE audits (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url             TEXT NOT NULL,
    url_hash        TEXT NOT NULL UNIQUE,   -- MD5(normalised URL) for fast cache lookup
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,            -- NULL = no expiry
    score           INTEGER,
    max_score       INTEGER DEFAULT 69,
    score_pct       FLOAT,
    grade           TEXT,                   -- POOR / FAIR / GOOD / EXCELLENT
    payload         JSONB,                  -- Full AuditRequest (url + MCQ answers)
    result          JSONB,                  -- Full AuditResult (all layer outputs)
    llm_source      TEXT,                   -- gemini_flash | ollama_mistral | template
    audit_time_s    FLOAT
);

-- Per-checkpoint results (normalised from audits.result for querying)
CREATE TABLE checkpoint_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id        UUID REFERENCES audits(id) ON DELETE CASCADE,
    code            TEXT NOT NULL,          -- R1, R7, R13, etc.
    layer           INTEGER,               -- 1–7
    status          TEXT,                  -- PASS | FAIL | WARN | UNKNOWN
    score           FLOAT,
    finding         TEXT,
    evidence        JSONB
);

-- Semantic gap matrix (L6 output)
CREATE TABLE semantic_gaps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id        UUID REFERENCES audits(id) ON DELETE CASCADE,
    gap_iw          FLOAT,                 -- Intent vs Website
    gap_is          FLOAT,                 -- Intent vs Schema
    gap_ws          FLOAT,                 -- Website vs Schema
    matrix          JSONB,                 -- 4x5 dimension gap matrix
    overall_status  TEXT                   -- ALIGNED | DRIFT | MISALIGNED
);

-- Fix sessions
CREATE TABLE fix_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id        UUID REFERENCES audits(id) ON DELETE CASCADE,
    checkpoint      TEXT NOT NULL,         -- R13, R15, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    audit_context   JSONB                  -- Snapshot of relevant audit data for LLM
);

-- Chat history (per fix session)
CREATE TABLE chat_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES fix_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,         -- user | assistant
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    llm_source      TEXT                   -- which model generated this turn
);

-- Indexes
CREATE INDEX idx_audits_url_hash ON audits(url_hash);
CREATE INDEX idx_audits_created_at ON audits(created_at DESC);
CREATE INDEX idx_checkpoint_results_audit ON checkpoint_results(audit_id);
CREATE INDEX idx_chat_history_session ON chat_history(session_id, created_at);
```

**Why PostgreSQL over SQLite in production:**  
Concurrent audit requests write to the same `audits` table. SQLite's write-locking causes queuing under load. PostgreSQL handles concurrent writes cleanly. The schema is identical — `db.py` switches between them based on `DATABASE_URL` format.

---

## Setup & Run

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use SQLite for dev — auto-created, no setup)
- Ollama (optional — local LLM fallback)

---

### Backend

```bash
cd kasparro/backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# First run downloads all-MiniLM-L6-v2 (~80MB) and caches it
# No manual step needed — happens automatically on startup

# Set up environment variables (see section below)
cp .env.example .env
# Edit .env with your values

# Run database migrations (PostgreSQL)
alembic upgrade head
# For SQLite dev: skip — tables created automatically on first run

# Start the server
uvicorn main:app --reload --port 8000
```

Backend running at: `http://localhost:8000`  
Interactive API docs: `http://localhost:8000/docs`

---

### Frontend

```bash
cd kasparro/frontend

# Install dependencies
npm install

# Set environment variable
echo "VITE_API_BASE_URL=http://localhost:8000" > .env

# Start dev server
npm run dev
```

Frontend running at: `http://localhost:5173`

---

### Ollama (optional — local LLM fallback)

```bash
# Install Ollama: https://ollama.com/download
ollama pull mistral
# Runs automatically on localhost:11434
# Backend detects it via OLLAMA_HOST in .env
```

If Ollama is not running, the backend falls through to hardcoded templates. No configuration change needed.

---


## Environment Variables

### `backend/.env`

```env
# Primary LLM
GEMINI_API_KEY=your_gemini_api_key

# Database
# PostgreSQL (production)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ai_rep_optimizer
# SQLite (dev — no setup needed)
# DATABASE_URL=sqlite+aiosqlite:///./db/audits.db

# Ollama (local fallback — optional)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral

# App settings
ENVIRONMENT=development
AUDIT_CACHE_TTL_HOURS=24
REQUEST_JITTER_MS=500
LOG_LEVEL=INFO
FRONTEND_URL=http://localhost:5173
```

### `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|---|
| `POST` | `/api/audit/start` | Start a new audit — returns job_id immediately |
| `GET` | `/api/audit/status/{job_id}` | Poll for audit progress and result |
| `DELETE` | `/api/audit/cache` | Clear cached result for a store URL |
| `POST` | `/api/chat/start` | Start a fix conversation for a failed check |
| `POST` | `/api/chat/reply` | Send a message and get advisor reply |
| `GET` | `/api/chat/history` | Load full conversation history for a check |
| `GET` | `/api/fix/template/{check_code}` | Get hardcoded fix template and steps |
| `GET` | `/api/health` | Health check |

### `POST /api/audit` — request body

```json
{
  "url": "https://example.myshopify.com",
  "category": "Home & Living",
  "customer": "Parents & families",
  "differentiator": "Premium / luxury quality",
  "tone": "Luxury & refined",
  "description": "Optional free text"
}
```

### `POST /api/audit` — response

```json
{
  "audit_id": "uuid",
  "score": 29,
  "max_score": 69,
  "score_pct": 42.0,
  "grade": "POOR",
  "cached": false,
  "audit_time_s": 38.4,
  "llm_source": "gemini_flash",
  "layers": {
    "L1": { "checks": [...], "all_passed": true },
    "L2": { "checks": [...] },
    "L3": { "checks": [...] },
    "L4": { "checks": [...] },
    "L5": { "checks": [...] },
    "L6": { "gap_iw": 0.455, "gap_is": 0.398, "gap_ws": 0.159, "matrix": {...} }
  },
  "blockers_ranked": [
    { "rank": 1, "code": "R15", "layer": "L3", "status": "FAIL",
      "finding": "FAQ page thin — only 1/6 topics covered",
      "score": 0, "quick_fix": "Expand your FAQ to cover..." }
  ],
  "passed_checks": [...],
  "conclusion": "Your bedding store's AI visibility score is currently 42%..."
}
```

### `GET /health` — response

```json
{
  "status": "ok",
  "gemini": "available",
  "ollama": "available",
  "db": "connected",
  "embedder": "loaded",
  "version": "2.0"
}
```

---

## Design Decisions

| Decision | What was considered | What was chosen | Why |
|---|---|---|---|
| No LLM in L1–L6 | Gemini for every layer | Zero LLM in L1–L6 | Deterministic, auditable, $0, no rate-limit exposure |
| Hardcoded fix templates | Fully LLM-generated fixes | 90% hardcoded + LLM for dialogue only | Hardcoded = zero hallucination, instant response |
| Sequential fetching | Parallel HTTP requests | Sequential + ±500ms jitter | Parallel triggers Cloudflare after 3–5 hits |
| Embedder as singleton | Load per request | Load once at startup | 3–5s load time — unacceptable per request |
| SSE for scan progress | Polling every 2s | Server-sent events | Lower overhead, real-time layer-by-layer updates |
| Raw score /69 | Percentage /100 | Raw number only | Percentage invites false comparison to SEO tools |
| Passed checks collapsed | Show all checks | Collapsed by default | Visible passes reduce urgency — merchants don't fix things |
| PostgreSQL + SQLite | PostgreSQL only | Both — switched by DATABASE_URL | Dev needs zero setup; prod needs concurrent write safety |

---

*AI Representation Optimizer · v2.0 · Full Stack Reference · 2026 · Kasparro Track 5*
