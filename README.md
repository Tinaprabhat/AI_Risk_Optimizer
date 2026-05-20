# AI Logic Branch

> **Branch: `AI_logic`**  
> The full AI reasoning engine behind the audit — 7 layers, 16 checkpoints,  
> 3-tier semantic extraction, the AI Mirror, and the Fix Engine.  
> Built in Python. Runs entirely on CPU. Costs $0 at prototype scale.

---

## Table of Contents

1. [What This Branch Is](#what-this-branch-is)
2. [The Journey — v0 → v1 → v2](#the-journey--v0--v1--v2)
3. [Architecture Overview](#architecture-overview)
4. [The 16 Checkpoints](#the-16-checkpoints)
5. [Layer by Layer](#layer-by-layer)
6. [Semantic Extraction Layer](#semantic-extraction-layer)
7. [The AI Mirror — L6](#the-ai-mirror--l6)
8. [Aggregation & Output — L7](#aggregation--output--l7)
9. [The Fix Engine — Part 2](#the-fix-engine--part-2)
10. [Key Design Decisions](#key-design-decisions)
11. [What We Ditched and Why](#what-we-ditched-and-why)
12. [What We Broke and Fixed](#what-we-broke-and-fixed)
13. [Known Limitations](#known-limitations)
14. [Stack](#stack)

---

## What This Branch Is

This branch contains the core AI reasoning layer of the product — everything
that happens between receiving a merchant's URL and producing a scored,
ranked, fixable audit output.

It is not a wrapper around an LLM. The vast majority of the system —
16 checkpoints, semantic extraction, embedding-based gap analysis — is
deterministic, reproducible, and runs at $0. The LLM (Gemini 2.5 Flash)
is called exactly once per audit, for the conclusion paragraph only.

The Streamlit prototype in this branch was the working proof-of-concept
before the full-stack frontend was built by the teammate. Everything you
see in the final UI started here.

---

## The Journey — v0 → v1 → v2

Understanding how the system evolved matters more than just reading what
it does now. Each version answered a problem the previous one created.

### v0 — The Hypothesis (35 Reasons)

The first question was simple: why does AI skip stores? We mapped every
plausible reason into 6 layers and arrived at 35 checkpoints.

The problem with v0: all 35 reasons were treated with equal confidence.
Verified mechanistic facts sat alongside weak speculation — with no
distinction between them. A tool that audits things that don't actually
affect AI recommendation behaviour misleads merchants instead of helping them.

We also had a Layer 6 that asked Gemini to roleplay as a ChatGPT shopping
agent — simulating what another AI would conclude about a store.

> *"Gemini has no access to ChatGPT's weights, retrieval index, ranking  
> logic, or tool-use pipeline. What it produced was creative writing  
> dressed as evaluation."*

That entire layer was scrapped.

### v1 — Validation Before Building

Before writing a single line of production code, we ran an empirical
validation study. The method:

- Query 3 AI shopping agents (Gemini, Perplexity, ChatGPT) × 3 times
  each across 5 product categories
- Identify the most-recommended stores per category
- Run 14 checkpoints on each winner and measure pass rate
- Cross-validate against 24 live Shopify stores across 9 checkpoints

**Result:** Pass rate ≥ 10/14 across 4/5 categories — directionally confirmed.
R16 (refund window) and R17 (shipping timeframe) emerged as the strongest
predictors. Checks with no signal correlation were re-tiered or dropped.

35 checkpoints → 16. Zero speculative. All either VERIFIED or CORRELATED.

Six architecture issues were also identified and resolved in v1:

| Issue | Resolution |
|---|---|
| Causal claims unverified | 35 checks tiered: VERIFIED / CORRELATED / DERIVATIVE / SPECULATIVE |
| Gemini roleplay is not simulation | Replaced with embedding-based gap analysis (honest, verifiable) |
| Semantic gap collapsed to one number | Decomposed into 4×5 dimension-page matrix |
| UCP/llms.txt severity miscalibrated | Moved to FORWARD-LOOKING tier — not scored, not a blocker |
| JS-heavy stores treated as dead ends | Sequential + jitter fetching, static Shopify endpoint fallback |
| Parallel requests trigger Cloudflare | All fetches sequential with ±500ms jitter |

### v2 — The Regex Problem

After v1 validation on real stores, a second failure mode emerged.
Stores with perfectly valid refund and shipping policies were being
flagged as FAIL — not because the data was absent, but because their
phrasing didn't match hardcoded regex.

| Checkpoint | False Negative Rate | Example Missed Phrase |
|---|---|---|
| R9 — Price signal | ~15% | 'USD 99', '99 EUR', '99 dollars' |
| R16 — Refund timeframe | ~20% | 'fortnight', '30-day guarantee', 'one month' |
| R17 — Shipping timeframe | ~20% | '1-2 weeks', 'Arrives in 5-7 days' |
| R15 — FAQ discovery | ~25% | '/customer-support', '/knowledgebase', '/help-centre' |

**Combined: ~18% of stores with correct, complete data were failing
checkpoints because they wrote naturally instead of robotically.**

The fix was architectural. v2.0 introduced a Semantic Extraction Layer
that runs once before all checkpoints, extracts structured meaning, and
feeds it downstream. Checkpoints no longer search HTML — they score
pre-extracted data.

Result: false negative rate dropped from ~18% to ~5–8%. +3 seconds to
audit time. $0 additional cost.

---

## Architecture Overview

```
MERCHANT INPUT
  URL + free text description + 4 MCQs
  │
  ├── SEMANTIC EXTRACTOR  (runs once, feeds L1–L5)
  │    Tier 1: spaCy NER + numeric regex + SPELLED_NUMBERS map
  │    Tier 2: all-MiniLM-L6-v2 embeddings vs POLICY_EXISTS_EXEMPLARS
  │    Tier 3: Gemini 2.5 Flash structured JSON  [v3 — not yet live]
  │    Output: {refund, shipping, brand, faq, price} structured dict
  │
  ├── PART 1 — AUDIT ENGINE
  │    ├── L1  Crawlability          R1 R3 R5 R6         binary 0/1
  │    ├── L2  Structured Data       R7 R9 R11           scored 0–10
  │    ├── L3  Semantic Content      R13 R15 R16 R17     scored 0–10
  │    ├── L4  Trust Signals         R23 R25             binary 0/1
  │    ├── L5  AI-Era Protocols      R28 R30 R31         scored 0–10
  │    ├── L6  Semantic Gap Engine   (pure embeddings, 0 LLM calls)
  │    │    V1 = merchant intent     (MCQ answers + free text)
  │    │    V2 = website content     (crawled + cleaned HTML)
  │    │    V3 = schema content      (JSON-LD extracted by extruct)
  │    │    gap_IW, gap_IS, gap_WS → 4×3 dimension-page matrix
  │    └── L7  Aggregation & Output  (1 Gemini call)
  │         X/79 score + ranked blockers + AI Mirror display
  │         + conclusion paragraph
  │         Fallback: Ollama → hardcoded template
  │
  └── PART 2 — FIX ENGINE
       Ranked blocker list → hardcoded fix template → Gemini chatbot
       Fallback: Ollama → template only (zero hallucination guaranteed)
```

### The AI / Deterministic Boundary

This boundary is the most important architectural decision in the system.

| Component | Type | LLM | Cost |
|---|---|---|---|
| Semantic Extractor Tier 1 | Deterministic | spaCy (local NLP) | $0 |
| Semantic Extractor Tier 2 | Deterministic | MiniLM embeddings (CPU) | $0 |
| L1–L5: 16 checkpoints | Deterministic | None | $0 |
| L6: Semantic Gap | Deterministic | MiniLM embeddings (CPU) | $0 |
| L7: Conclusion paragraph | LLM | Gemini → Ollama → Template | ~$0.017 |
| Part 2: Fix Chatbot | LLM | Gemini → Ollama → Template | ~$0.05/session |

Everything upstream of L7 is fully reproducible with no internet
connection. The same URL always produces the same checkpoint scores.
Gemini is never a hard dependency.

---

## The 16 Checkpoints

Final checkpoint set after validation. Every check is VERIFIED
(mechanistic causal link, documented source) or CORRELATED (empirically
observed across 24 stores). R16 and R17 ★ are the strongest predictors.

| Code | Checkpoint | Layer | Evidence | Type |
|---|---|---|---|---|
| **R1** | robots.txt — AI crawler access | L1 | VERIFIED | Binary |
| **R3** | sitemap.xml — exists + product URLs | L1 | VERIFIED | Binary |
| **R5** | Bot protection blocking AI agents | L1 | CORRELATED | Binary |
| **R6** | SSL certificate valid | L1 | VERIFIED | Binary |
| **R7** | schema.org commerce types present | L2 | CORRELATED | Scored |
| **R9** | Price signal visible to crawler | L2 | CORRELATED | Scored |
| **R11** | JSON-LD valid — not malformed | L2 | CORRELATED | Binary |
| **R13** | Product descriptions — specific not vague | L3 | CORRELATED | Scored |
| **R15** | FAQ — exists + covers buyer topics | L3 | CORRELATED | Binary |
| **R16 ★** | Refund window — concrete days extractable | L3 | CORRELATED | Scored |
| **R17 ★** | Shipping — concrete timeframe extractable | L3 | CORRELATED | Scored |
| **R23** | Contact page — exists + branded email | L4 | CORRELATED | Binary |
| **R25** | Brand name — consistent across pages | L4 | CORRELATED | Binary |
| **R28** | UCP profile — Shopify scored, non-Shopify 0 | L5 | CORRELATED | Binary |
| **R30** | ACP feed quality — Shopify only | L5 | VERIFIED | Scored |
| **R31** | GMC homepage signals | L5 | CORRELATED | Scored |

**Scoring system: X / 79**

| Type | Checks | Max Points |
|---|---|---|
| Scored (0–10 continuous) | R7, R9, R13, R16, R17, R30, R31 | 70 points |
| Binary (0 or 1) | R1, R3, R5, R6, R11, R15, R23, R25, R28 | 9 points |
| **Total** | **16** | **79** |

Rules: WARN → partial score (proportional, not zero). UNKNOWN → 0
(conservative). Non-Shopify R28 and R30 → 0, not excluded from denominator.

---

## Layer by Layer

### L1 — Crawlability

**Can AI physically reach the store?**

Output format: binary checklist (not score). Either GPTBot is blocked
or it isn't. A score of 70/100 would hide a hard block — the checklist
forces the actual problem to surface.

**R1 — robots.txt**  
`GET /robots.txt` → parsed with `robotparser`. Checked against 20+ AI
user-agents: GPTBot, OAI-SearchBot, ClaudeBot, Claude-SearchBot,
Google-Extended, Gemini-Deep-Research, PerplexityBot, CCBot.
404 on robots.txt = allow all (per RFC spec). 403 = BOT PROTECTION,
severity CRITICAL, no retry.

**R3 — sitemap.xml**  
`GET /sitemap.xml` → parse XML. If sitemap index found, follows child
sitemaps (`/sitemap_pages_1.xml`, etc.) to count actual product URLs.
v2.0 fix: v1 only checked the index and missed product counts behind
child sitemaps.

**R5 — Bot protection**  
Fetches with each AI user-agent. Checks for 403/429/503, Cloudflare
challenge page markers, CAPTCHA text, `cf-ray` header.
Distinguishes hard block (CRITICAL) from rate limit (WARN).

**R6 — SSL**  
`ssl.get_server_certificate()` — validates cert validity and expiry.
Expired SSL = instant disqualification from AI recommendation.

**Retry logic across all L1 checks:**
- Retry on: 429, 503, 504, ConnectionError, Timeout
- Backoff: 0s → 2s → 8s + ±500ms jitter
- No retry on: 404 (definitive missing), 403 (definitive block)

---

### L2 — Structured Data

**Can AI extract machine-readable facts?**

Uses `extruct` to pull JSON-LD, Microdata, and RDFa simultaneously.
Output: 0–10 score per check + binary flag for contradictions.

**R7 — Commerce schema types**  
`extruct.extract(html, syntaxes=["json-ld","microdata","rdfa"])`.
Checks for commerce-relevant types: Product, Organization, WebSite,
FAQPage, BreadcrumbList. Score = types found / expected types × 10.

**R9 — Price signal (v2.0 upgraded)**  
v1: regex on raw HTML for `$`/`£`/`€` symbols only.  
v2: receives `semantic_data['price']` from the extractor. Detects
4 currency formats: symbol prefix, code prefix, code suffix, text amount.
Also checks for schema price vs HTML price contradiction — mismatch
= CONTRADICTION, severity CRITICAL.

**R11 — JSON-LD validity**  
`JSON.parse()` on every `<script type="application/ld+json">` block.
Malformed JSON-LD is silently ignored by all crawlers — fixing it
is a zero-effort, high-impact repair. FAIL includes the exact line
and character position of the parse error.

---

### L3 — Semantic Content

**Can AI understand what the store means?**

The most NLP-heavy layer. All checks run without LLM calls.
`all-MiniLM-L6-v2` handles all semantic comparison.

**R13 — Vagueness detection**  
Embeds each product description sentence. Compares cosine similarity
against two pre-built exemplar sets:
- `VAGUE_EXEMPLARS`: "premium quality", "great product", "you'll love it"
- `SPECIFIC_EXEMPLARS`: "316L surgical steel, 2mm thickness, weight 85g"

`delta = sim_vague - sim_specific`. If delta > 0.20 for more than half
the sentences → VAGUE FAIL. Score proportional to delta.

This catches the core problem: AI agents cannot distinguish a store
from its competitors if descriptions contain no extractable specifics.

**R15 — FAQ coverage (v2.0 upgraded)**  
v1: checked 4 hardcoded paths (/pages/faq, /faq, /help, /pages/help).  
v2: 3-stage discovery via `semantic_data['faq']`:
1. Standard paths
2. Keyword regex on sitemap: `faq|help|qa|support|knowledgebase|help-centre`
3. Nav link scan on homepage

Once the page is found, 6 topic centroids are pre-embedded (returns,
shipping, sizing, payment, contact, warranty). Each FAQ answer is
compared against all 6. Topic score: max cosine similarity ≥ 0.45 =
covered. Output: `X/6 topics covered`.

**R16 ★ — Refund window (v2.0 upgraded)**  
v1: regex looking for `(\d+)[\s-]*(day|days)` — missed 'one month',
'fortnight', '30-day guarantee'.  
v2: receives `semantic_data['refund']`. Full scoring table:

| Extracted window | Score |
|---|---|
| ≥ 30 days (any unit) | 10/10 — PASS |
| 14–29 days | 9/10 — PASS |
| 7–13 days | 6/10 — WARN |
| < 7 days | 3/10 — WARN |
| Policy exists, no window extractable | 2/10 — FAIL |
| No policy page | 0/10 — FAIL |

**R17 ★ — Shipping timeframe (v2.0 upgraded)**  
Same upgrade pattern as R16. Receives `semantic_data['shipping']`.
Unit normalisation converts all formats to day-equivalents before
scoring, so "2 weeks" and "14 days" score identically.

---

### L4 — Trust Signals

**Will AI risk recommending the store?**

Output: binary checklist. Trust is binary from an AI perspective —
a branded contact email either exists or it doesn't.

**R23 — Contact page**  
Detects contact page via sitemap + nav link scan. Checks for:
branded email (not gmail/yahoo), phone number, physical address.
Non-branded email = WARN not FAIL (still shows accountability).

**R25 — Brand consistency (v2.0 upgraded)**  
v1: string comparison across page titles.  
v2: receives `semantic_data['brand']`. Multi-source extraction with
priority ranking:
- `og:site_name` meta tag (confidence 0.95)
- `schema.org Organization.name` (confidence 0.90)
- HTML title first segment (confidence 0.75)

NER sanity filter rejects strings with punctuation prefix, `&`
characters, >40 chars, or >5 words. Consistency score = cosine
similarity across all source names after normalisation.

Why this matters: 91.7% of stores in the validation study failed R25.
Inconsistent brand name presentation ("Morphe US" vs "Morphe" vs
footer plain text) causes AI to treat them as separate entities,
weakening attribution and recommendation confidence.

---

### L5 — AI-Era Protocols

**Is the store opted into emerging AI commerce standards?**

**R28 — UCP profile**  
`GET /.well-known/ucp` → parse JSON response. Shopify stores get this
automatically — scored if valid, 0 if non-Shopify (not excluded from
denominator). One store in validation (madeincookware.com) had a UCP
endpoint returning invalid JSON — flagged FAIL.

**R30 — ACP feed quality**  
Shopify-only check. Validates Agentic Commerce Protocol feed: checks
for marketing language in titles, price consistency, GTIN presence.
Non-Shopify stores score 0 (expected behaviour, documented).

**R31 — GMC readiness signals**  
Checks 4 Google Merchant Center signals on homepage:
`google-site-verification` meta tag, `og:type=product`, currency-formatted
price in HTML, `Organization` schema type.
Score = signals found / 4 × 10. Validation found 5/24 stores (21%)
passed this — lowest pass rate after R25 and R16.

---

## Semantic Extraction Layer

This is the most significant architectural addition in v2.0.

### The Problem It Solves

The v1 pipeline was:
```
HTML page → regex match → PASS / FAIL
```

This worked for exact known phrasings and failed for everything else.
~18% false negative rate on stores with valid, complete data.

The v2 pipeline is:
```
HTML page → Semantic Extractor → structured meaning → checkpoint scores
```

Checkpoints receive pre-extracted structured data. They no longer
search HTML at all.

### Three-Tier Extraction Strategy

The extractor tries three approaches in sequence, escalating only
when the previous tier is uncertain:

**Tier 1 — spaCy NER + numeric regex + SPELLED_NUMBERS map**  
Always runs first. Handles ~85–90% of stores.

```python
SPELLED_NUMBERS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'fourteen': 14, 'thirty': 30, 'sixty': 60, 'fortnight': 14,
    ...
}

TEMPORAL_MAPPINGS = {
    'day': 1, 'days': 1,
    'week': 7, 'weeks': 7,
    'fortnight': 14,
    'month': 30, 'months': 30,
}
```

If Tier 1 confidence ≥ 0.85 → extraction complete. Otherwise → Tier 2.

**Tier 2 — all-MiniLM-L6-v2 embedding similarity**  
Handles additional ~7–10% of stores. Compares text against
`POLICY_EXISTS_EXEMPLARS` pre-built sentence sets. Distinguishes:
- "Policy exists but timeframe unclear" → WARN (not false FAIL)
- "No policy at all" → FAIL

Critically: Tier 2 changes FAIL to WARN only. It never changes
FAIL to PASS without a concrete extracted value. This prevents
false positives.

**Tier 3 — Gemini 2.5 Flash structured JSON extraction**  
Designed and documented. Not implemented in v2.0.  
Expected to handle remaining ~3–5% (legal language, jurisdiction-based
policies). Scoped to v3 — at prototype scale with English Shopify
stores, Tier 1 + Tier 2 cover 92%+ of cases.

### What the Extractor Returns

```python
{
  'refund':   {value_min, value_max, unit, raw, found, confidence},
  'shipping': {value_min, value_max, unit, raw, found, confidence},
  'brand':    {brand_name, source, confidence, alternatives, consistency_score},
  'faq':      {page_found, page_url, topics_covered, completeness},
  'price':    {price_in_schema, price_in_html, contradiction, confidence},
  'pages_crawled': 7,
  'crawl_time_s':  12.4,
  'extraction_confidence': 0.87
}
```

This dict is passed to every checkpoint that needs it.
The extractor runs once — not once per checkpoint.

### Observability on Every Extraction

Every extraction is fully logged. Merchants see exactly what
was extracted and at what confidence:

```
check_id:         R16
extraction_tier:  Tier 1 (numeric regex)
raw_match:        'return your purchase within 28 days for a refund'
extracted_value:  {value_min: 28, value_max: 28, unit: 'days'}
confidence:       0.95
normalised_days:  28
score:            9 / 10
status:           PASS
what_AI_sees:     Merchant offers 28-day return window. AI can extract and cite this.
```

Compare to v1, which only showed: `status: PASS, detail: 'within 28 days found'`

---

## The AI Mirror — L6

**What does AI actually perceive about this store?**

L6 is the most technically novel component. It measures the semantic
gap between three sources of store identity:

- **V1 — Merchant intent**: embedded from MCQ answers + free text
- **V2 — Website content**: embedded from crawled + cleaned HTML
- **V3 — Schema content**: embedded from JSON-LD extracted by `extruct`

### The Three Gap Scores

```python
gap_IW = 1 - cosine_sim(V1, V2)
# "Does your website say what you think it says?"

gap_IS = 1 - cosine_sim(V1, V3)
# "Does your schema match your intent?"

gap_WS = 1 - cosine_sim(V2, V3)
# "Are your website and schema consistent with each other?"
```

Thresholds:
- gap < 0.15 → ALIGNED (synonym-level variation, not a real problem)
- gap 0.15–0.30 → DRIFT (meaningful divergence — show raw text to merchant)
- gap > 0.30 → MISALIGNED (genuinely different meaning)

### The 4×3 Dimension-Page Matrix

A single gap score is not enough. It collapses WHERE the gap is.

Merchant intent is decomposed into 4 dimensions from the MCQ answers:
Tone, Category, Customer, Differentiator.

Website content is split into 3 page types:
About, Homepage, Policies.

Each of the 4 intent dimensions is compared against each of the
3 page vectors — producing 12 independent gap scores.

```
              About    Homepage   Policies
Tone          0.798    0.662      0.832
Category      0.745    0.737      0.748
Customer      0.868    0.834      0.855
Differentiator 0.784   0.633      0.820
```

This tells the merchant exactly which aspect of their brand is
misrepresented on which page — not just "you have a gap somewhere."

### Why All Embeddings, No LLM

The choice to use embedding similarity instead of asking Gemini to
evaluate the gap was deliberate. Cosine similarity is:
- Deterministic — same inputs always produce the same scores
- Auditable — the exact vectors and distances can be shown to the merchant
- $0 — the MiniLM model runs on CPU

An LLM evaluating the gap would produce probabilistic, non-reproducible
assessments that vary run to run. That is not acceptable for a diagnostic tool.

### The 256-Token Limit Fix

`all-MiniLM-L6-v2` has a 256-token context window. In v1, large pages
were silently truncated — the embedding represented only the first ~200
words of each page.

v2 fix: content is chunked into page-type slices before embedding.
Each chunk is explicitly capped at 256 tokens. Truncation is logged,
not silent. The merchant can see which pages were truncated.

---

## Aggregation & Output — L7

**One Gemini call. Everything else is deterministic.**

L7 receives the full JSON output from all layers and does two things:

1. Computes the weighted X/79 score with ranked blockers
2. Calls Gemini once for the conclusion paragraph

### Score Computation (deterministic)

```python
def compute_score(layer_results: dict) -> AuditScore:
    scored_checks = [R7, R9, R13, R16, R17, R30, R31]
    binary_checks = [R1, R3, R5, R6, R11, R15, R23, R25, R28]

    scored_total = sum(check.score for check in scored_checks)   # max 70
    binary_total = sum(check.score for check in binary_checks)   # max 9
    total = scored_total + binary_total                           # max 79

    # Blocker ranking: by impact weight, not by layer order
    blockers = sorted(failures, key=lambda c: IMPACT_WEIGHTS[c.code], reverse=True)
    return AuditScore(total=total, max=79, blockers_ranked=blockers)
```

R16 and R17 carry the highest impact weights — confirmed by the
validation study as the strongest predictors.

### Conclusion Paragraph (Gemini → Ollama → Template)

```python
prompt = f"""
You are an AI readiness advisor. Based on this audit data:
{json.dumps(layer_results)}

Write one paragraph for a non-technical Shopify merchant explaining:
- Their current AI visibility score ({score}/79)
- The 2-3 most critical issues blocking AI recommendation
- One sentence of encouragement about what they're doing right

Tone: direct, plain English, no jargon. Max 120 words.
"""
result = await llm.generate(prompt)
# llm.generate() tries Gemini → Ollama → hardcoded template
```

The `source` field on the result (`gemini_flash`, `ollama_mistral`,
or `template`) is returned to the frontend and shown to the merchant.
Transparency about which system generated the conclusion.

---

## The Fix Engine — Part 2

**Hardcoded templates first. LLM second. Always.**

The fix engine activates after the audit. For every failing or warning
checkpoint, the merchant gets two things:

### 1. Hardcoded Fix Template (instant, zero LLM, zero hallucination)

Every checkpoint has a pre-written fix template. These are not
generated — they are written once and stored in `fix_engine.py`.

Example for R13:

```python
TEMPLATES = {
    "R13": {
        "title": "Product descriptions — replace vague with specific",
        "problem": "AI cannot distinguish your products from competitors "
                   "without factual, measurable descriptions.",
        "example_before": "premium quality materials",
        "example_after": "made from 316L surgical stainless steel, "
                         "2mm thickness, weight 85g",
        "fix_steps": [
            "Identify your 5 best-selling products",
            "For each: add material, dimensions, weight, compatibility",
            "Remove adjectives that have no factual basis (premium, luxury, best)",
            "Test: can an AI answer 'what is this made of?' from your description?"
        ],
        "why": "AI agents build product representations from factual attributes. "
               "Vague descriptions produce weak representations — "
               "the store becomes interchangeable with hundreds of others.",
        "time_to_fix": "2–4 hours",
        "impact": "HIGH"
    },
    "R15": { ... },
    "R16": { ... },
    # All 16 checkpoints covered
}
```

The template renders immediately — no API call, no wait, no
possibility of hallucination. A merchant at 3am with no Gemini
access gets the same fix guidance as one with full connectivity.

### 2. Gemini Chatbot Layer (conversational adaptation)

The hardcoded template covers the general case. The chatbot handles
the merchant's specific situation.

```python
async def build_fix_prompt(template, audit_context, history, message):
    return f"""
You are a Shopify AI readiness consultant.

The merchant's store: {audit_context['url']}
Category: {audit_context['category']}
The issue: {template['problem']}
Standard fix: {template['fix_steps']}

Conversation so far:
{format_history(history)}

Merchant says: {message}

Help them apply the fix to their specific store.
Be concrete. If they sell {audit_context['category']}, give examples
from that category. Do not repeat the template — build on it.
"""
```

Fallback chain: Gemini → Ollama → `"Guided fix temporarily unavailable.
Use the template above — it contains everything you need."`

Chat history is persisted in PostgreSQL per session. A merchant
can close and resume. The LLM receives the full history on each turn.

---

## Key Design Decisions

| Decision | What was considered | What was chosen | Why |
|---|---|---|---|
| No LLM in L1–L6 | Gemini call for every layer | Zero LLM in L1–L6 | Deterministic, auditable, $0, no rate-limit exposure |
| Hardcoded templates first | Fully LLM-generated fixes | Hardcoded + LLM for dialogue only | Hardcoded = zero hallucination, instant response, works offline |
| Sequential fetching | Parallel HTTP requests | Sequential + ±500ms jitter | Parallel triggers Cloudflare after 3–5 hits on same domain |
| Embedding model | GPT-4 embeddings, Ollama local | all-MiniLM-L6-v2 (CPU, 80MB) | Deterministic, zero cost, already in stack for L3 |
| 4×3 gap matrix | Single cosine similarity score | 4 dimensions × 3 page types | One number hides WHERE the gap is — matrix makes it actionable |
| Raw score /79 | Percentage /100 | Raw number only | /100 invites comparison to SEO tools that give everything 85+ |
| WARN ≠ FAIL | Binary pass/fail | Partial credit on scored checks | A store with a 14-day refund window is meaningfully better than one with none |
| Tier 2 → WARN not PASS | Embeddings confirm policy exists | WARN only without a number | Without an extractable value, we cannot confirm the timeframe is sufficient |

---

## What We Ditched and Why

**Gemini roleplay simulation (v0 Layer 6)**  
Asked Gemini to pretend to be a ChatGPT shopping agent and predict
recommendation behaviour. The output looked plausible and was useless.
Gemini has no access to ChatGPT's weights, retrieval index, or
ranking logic. It produced creative writing. Replaced entirely with
embedding-based gap analysis — verifiable, deterministic, honest.

**35 original checkpoints → 16**  
The 19 dropped checks fell into two categories:
- Speculative (weak or wrong causal logic) — e.g., R14 keyword stuffing
  detection required assumptions about how LLMs weight repetition
- Derivative (reasonable inference, no evidence) — e.g., R22 review
  count thresholds had no correlation in the validation study

All 19 were either relabelled FORWARD-LOOKING (UCP, llms.txt) or
dropped entirely.

**UCP and llms.txt as scored checkpoints**  
v0 flagged missing UCP as CRITICAL. A study of 300,000 domains found
no correlation between llms.txt and AI citations. UCP is gated for
most small merchants — flagging it as critical for something they
cannot fix destroys trust in the tool. Both moved to FORWARD-LOOKING.

**Ollama as primary LLM**  
v0 used Ollama running locally. Switched to Gemini 2.5 Flash: 2–4s
vs 15–25s response time, free tier, better conversational follow-up,
and no local model dependency for production. Ollama remains as fallback.

**Single blended score for all layers**  
A 70/100 overall score would hide a CRITICAL failure in L1 (GPTBot
blocked). Mixed model: binary checklist for existence checks, 0–10
for continuous quality measurements.

---

## What We Broke and Fixed

**The Brotli encoding crash**  
v1 `fetcher.py` included `Accept-Encoding: br` in request headers.
Some Shopify CDN edges returned Brotli-compressed responses. Python
`requests` does not decompress Brotli by default — the raw compressed
bytes were fed to BeautifulSoup, which extracted garbage text.
Fix: removed `br` from `Accept-Encoding`. Simple one-line fix that
took an embarrassingly long time to diagnose.

**The child sitemap miss**  
v1 R3 checked `/sitemap.xml` and counted product URLs in the top-level
file. Most Shopify stores use sitemap indexes — the top-level file
contains only pointers to child sitemaps like `/sitemap_products_1.xml`.
v1 was reporting 0 product URLs for stores with 500+ products because
it wasn't following the index. Fix: added child sitemap discovery
in the semantic extractor Phase 1.

**The 256-token silent truncation**  
v1 L6 embedded entire pages as single vectors. `all-MiniLM-L6-v2`
has a 256-token window — anything beyond that was silently truncated.
For a homepage with 2,000 tokens, only the first ~200 words were
embedded. The semantic gap scores for content-heavy pages were
computed on headers and hero text only.
Fix: content chunked by page type, each chunk explicitly capped at
256 tokens. Truncation logged and surfaced in observability output.

**The Cloudflare parallelism problem**  
v0 and v1 ran some layer checks in parallel for speed. After 3–5
rapid requests to the same domain, Cloudflare would return 403
challenge pages to all subsequent requests — the entire audit failing
mid-run. Fix: all requests to the same domain are sequential with
±500ms jitter. Slower, but reliable.

**The confidence threshold for Tier 2**  
First version of Tier 2 used a cosine similarity threshold of 0.50.
This produced false WARNs on stores whose policy pages contained a lot
of legal boilerplate (jurisdiction language, limitation of liability).
The exemplars were too similar to formal legal text. Threshold adjusted
to 0.65, and exemplar sets were rewritten to be more specifically
about timeframes, not just policy existence.

---

## Known Limitations

- **Non-English stores** — spaCy `en_core_web_sm` is English-only.
  R16 and R17 may return UNKNOWN on non-English policy text.

- **JS-rendered storefronts** — Pure CSR stores without a Storefront
  API token are partially audited via static Shopify endpoints only.
  Covers ~16 of 16 checks via static paths; product descriptions may
  be unavailable.

- **Tier 3 not live** — ~5–8% of hard cases (legal language,
  jurisdiction-based policies) remain as potential false negatives
  until v3 implementation.

- **Business day handling** — "5 business days" and "5 days" score
  identically. Not yet disambiguated.

- **Causal claims** — 8 of 16 checks have verified mechanistic links.
  The remaining 8 are empirically correlated. All findings are labelled
  with their evidence tier. We do not claim definitive causal links to
  any specific LLM's recommendation logic.

- **Non-determinism in conclusion** — The L7 conclusion paragraph
  varies between runs (LLM output). All checkpoint scores above it are
  fully deterministic and reproducible.

---

## Stack

| Component | Version | Role | Cost |
|---|---|---|---|
| Python | 3.11 | Primary language | $0 |
| spaCy `en_core_web_sm` | 3.x | NER — DATE, TIME, ORG entities (Tier 1) | $0 |
| sentence-transformers | 2.x | `all-MiniLM-L6-v2` — all embeddings (80MB, CPU) | $0 |
| extruct | latest | JSON-LD, Microdata, RDFa extraction | $0 |
| BeautifulSoup4 | 4.x | HTML parsing, text extraction | $0 |
| textstat | latest | Readability scores (Flesch, FK grade) | $0 |
| requests | 2.x | HTTP fetches — retry, jitter, user-agent rotation | $0 |
| Gemini 2.5 Flash | API | L7 conclusion + Part 2 chatbot (primary LLM) | ~$0.017/audit |
| Ollama + Mistral | local | LLM fallback if Gemini unavailable | $0 |
| SQLite | built-in | Audit cache + chat history (dev) | $0 |
| PostgreSQL | 15 | Audit cache + chat history (prod) | ~$5/mo VPS |
| Streamlit | 1.x | Prototype UI (this branch) | $0 |

**Total cost at prototype scale: $0**  
All embedding operations, all 16 checkpoint evaluations, and the
semantic extraction layer are fully local. Gemini is called exactly
once per full audit run.

---

*AI Representation Optimizer · AI Logic Branch · v2.0 · 2026 · Kasparro Track 5*  
*Built by Tina Prabhat*
