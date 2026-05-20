# Validation Branch

> **Branch: `validation`**  
> Empirical validation study run before any production code was written.

---

## Why Validation

The core hypothesis of this tool — that specific, measurable store signals correlate with AI recommendation behaviour — needed evidence before it could justify an audit product.

AI shopping agent recommendation logic is not publicly documented. No API, no ranking weights, no disclosed criteria. Building a 35-checkpoint audit tool on untested assumptions would produce a product that misleads merchants into fixing things that do not actually affect their AI visibility.

This branch exists to answer one question before building anything: **which checkpoints actually predict AI recommendation behaviour, and which do not?**

---

## What Was Validated

**Study design:**
- Queried 3 AI shopping agents (Gemini, Perplexity, ChatGPT) × 3 times each across 5 product categories
- Identified most-recommended stores per category
- Ran 14 candidate checkpoints against each winner
- Measured pass rate correlation
- Cross-validated against **24 live DTC Shopify stores** across 9 scored checkpoints

**Checkpoints tested:**

| Code | Checkpoint | Evidence Tier |
|---|---|---|
| R1 | AI crawler access (robots.txt) | VERIFIED |
| R3 | Sitemap accessible + product URLs | VERIFIED |
| R7 | Commerce schema.org types present | CORRELATED |
| R9 | Price signal visible in crawled HTML | CORRELATED |
| R16 | Refund policy — concrete timeframe extractable | CORRELATED ★ |
| R17 | Shipping policy — concrete timeframe extractable | CORRELATED ★ |
| R25 | Brand name consistent across pages | CORRELATED |
| R30 | Product schema on homepage (Shopify ACP) | VERIFIED |
| R31 | GMC readiness signals | CORRELATED |
| R28 | UCP profile present | FORWARD-LOOKING (unscored) |

★ Strongest validated predictors.

---

## Results

**24 stores validated. Average pass rate: ~49%.**

| Verdict | Threshold | Count |
|---|---|---|
| VALIDATED | ≥ 67% | 4 stores (17%) |
| PARTIAL | 50–66% | 7 stores (29%) |
| RETHINK | < 50% | 13 stores (54%) |

**Failure rates by checkpoint:**

| Check | Failure Rate | Implication |
|---|---|---|
| R25 — Brand consistency | 91.7% | Near-universal. Highest impact fix. |
| R16 — Refund timeframe | 87.5% | AI cannot cite a window it cannot find. |
| R9 — Homepage price | 66.7% | Most prices rendered client-side — invisible to crawlers. |
| R17 — Shipping timeframe | 66.7% | Policy language is AI-hostile (vague, hedged). |
| R31 — GMC signals | 45.8% | Missing og:type, verification tags, price formatting. |
| R7 — Commerce schema | 20.8% | 5 stores had zero schema.org markup at all. |
| R3 — Sitemap | 4.2% | Shopify auto-generates — broadly fine. |
| R1 — AI crawler access | 0.0% | 100% pass. Not a real-world blocker. |

Top performers (huel.com 78%, fentybeauty.com 72%, rarebeauty.com 72%, deathwishcoffee.com 72%) share the same Shopify infrastructure as failing stores. The gap is not technical — it is editorial: visible prices, explicit policy language, consistent brand identity.

---

## Conclusions & Actions Taken

**What the study confirmed:**

- R16 and R17 are the strongest predictors — marked ★ and given highest priority weighting in the scoring engine
- R1 (AI crawler access) has 100% pass rate across real stores — deprioritised in scoring, retained as a binary check
- R25 (brand consistency) fails universally but requires semantic extraction, not simple string matching — drove the 3-tier extractor design
- Regex-only extraction produced ~18% false negatives on valid stores using natural language dates and phrasing — confirmed need for embedding-based Tier 2 extraction

**What was cut:**

- 35 initial candidate checkpoints reduced to 16
- All speculative checks with no observed signal correlation removed
- R2 (llms.txt) and R28 (UCP) moved to FORWARD-LOOKING — present but unscored
- Gemini roleplay simulation (v0 Layer 6) dropped entirely — output was not grounded in any model's actual weights or retrieval logic

**What changed in the product as a result:**

| Finding | Product Decision |
|---|---|
| ~18% false negatives from regex | 3-tier semantic extractor (spaCy → MiniLM → Gemini) |
| R16/R17 strongest predictors | Highest impact weight in scoring; ranked first in Fix Engine |
| R1 100% pass rate | Binary check retained but lowest scoring weight |
| R25 needs semantic comparison | `all-MiniLM-L6-v2` cosine similarity, not string match |
| Roleplay simulation unreliable | Replaced with 3-way embedding gap (L6 Semantic Mirror) |

Full validation report: `validation_report_2026-05-14.txt`

---

*AI Representation Optimizer · Validation Branch · 24 stores · 9 checkpoints · 2026*
