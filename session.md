# Session log — AI Risk Optimizer → agency profile

Format: **what existed** (before this session) → **what was made** (during it).
Branch worked on: `feature/agency-profile` (cut from `final_version`). Nothing is committed.

---

## 1. Starting point (what existed)

A Shopify-only audit product, "AI Representation Optimizer":

| Area | What existed |
|---|---|
| UI | `app.py` — Streamlit form (URL, description, 4 commerce MCQs), score card, semantic-gap panel, checklist, observability panel, per-issue fix chatbot. Docstring said "X/79"; metric labels said "0–70" (real max is 69). |
| Orchestrator | `src/auditor.py` — `run_audit()`, hardcoded Shopify paths (`/pages/about`, `/policies/refund-policy`, …). |
| Checks | 16 checkpoints R1…R31 in `src/layer1…layer5` (L1 crawlability, L2 structured data, L3 semantic content, L4 trust, L5 AI-era protocols). |
| Semantic layer | `src/utils/semantic_extractor.py` — refund, shipping, brand, FAQ (commerce topics), price extraction. |
| L6 | `src/layer6/semantic_gap.py` — intent vs website vs schema cosine gaps, thresholds 0.15 / 0.30. |
| L7 | `src/layer7/aggregator.py` — module-level constants `SCORE_MAX`, `MAX_TOTAL = 69`; commerce conclusion prompt. |
| Fix engine | `src/part2/fix_engine.py` — Shopify fix templates and a Shopify-advisor chatbot prompt. |
| Utilities | fetcher, SQLite db (`db/audits.db`), MiniLM embedder, LLM wrapper (`llm.py`), observability logger, text cleaner. |
| Tests | `tests/test_suite.py` (+ `test_encoding.py`): 42 offline tests passed, **5 R25 tests already failed** (stale `check_r25` signature). |
| Data | 11 stored audit logs in `logs/`. |
| Known latent problems | R25 WARN scored 0 (docs say 0.5); L6 labelled nearly every site MISALIGNED; `llm.py` imported `google.generativeai` (not installed here, so Gemini silently fell back); `python-dotenv` missing from `requirements.txt`; `ollama_available()` broke on newer ollama responses; `check_r3` never returned `product_urls`. |

---

## 2. What was made

### 2.1 Planning
- **`plan.md`** — adaptation plan for an IT-services agency (Cynbit, Jaipur): domain-profile design, checkpoint set, code-change list, phases, tests, risks. Includes an execution-status section.

### 2.2 Domain-profile system (new)
- **`src/profiles/__init__.py`** — `CheckSpec`, `Profile`, `get_profile()`; derived helpers (`check_order`, `labels`, `layers`, `max_of(kind)`).
- **`src/profiles/shopify.py`** — the original v2.0 configuration extracted verbatim (same 16 checks, 60 + 9 = 69 points).
- **`src/profiles/agency.py`** — agency configuration: 10 carried-over checks + R32; B2B MCQs (`service`, `client`, `differentiator`, `engagement`); agency FAQ topics; agency conclusion prompt and fix persona.
- **`src/profiles/agency_templates.py`** — fix templates for every agency check (ProfessionalService JSON-LD block, FAQ, contact, llms.txt, …).

### 2.3 Changes to existing code (all default to `shopify`, so old behaviour is preserved)
| File | Change |
|---|---|
| `src/auditor.py` | `run_audit(..., profile=)`; split into `_run_shopify` (unchanged v2.0 flow) and `_run_agency`; profile-keyed cache; passes profile to L6/L7/db/logger; returns `log_path`; fills missing observability blocks. |
| `src/layer1/r3_r5_r6.py` | `check_r3(profile_name=)` — agency branch counts service/portfolio URLs and follows up to 3 child sitemaps. |
| `src/layer2/r7_r9_r11.py` | `check_r7(profile_name=)` — agency scoring (Organization/ProfessionalService type + name, url, description, address/areaServed, contact, sameAs, offer catalog = 10 pts); `@graph` flattening. |
| `src/layer3/r13_r15_r16_r17.py` | R13 agency vague/specific exemplars; R15 `min_pass` parameter and dynamic "X/N topics". |
| `src/layer4/r23_r25.py` | R23 optional international phone regex; R25 WARN now 0.5, and a wrapper that always returns observability. |
| `src/layer6/semantic_gap.py` | Profile-driven MCQ templates, page keys, schema types (ProfessionalService, Service, OfferCatalog); **thresholds recalibrated to 0.55 / 0.75**. |
| `src/layer7/aggregator.py` | Profile-driven scoring (maxima derived from the profile instead of constants); profile conclusion prompt; noun normalisation; "name a failed check" safeguard; rule-based fallback uses the profile noun. |
| `src/part2/fix_engine.py` | Profile-aware templates and chatbot persona/wording. |
| `src/utils/db.py` | `profile` argument on all functions; hash mixes the profile in only for non-shopify (old rows stay reachable). |
| `src/utils/semantic_extractor.py` | Agency path (`_extract_agency`: brand + FAQ + services/portfolio text, no refund/shipping/price crawls); parameterised `extract_faq`; ProfessionalService brand types; en-dash title split. |
| `src/utils/llm.py` | `google-genai` SDK first, legacy SDK fallback, empty-response guard; `ollama_available()` handles object and dict listings. |
| `src/utils/obs_logger.py` | Logs the profile. |
| `app.py` | Sidebar profile selector (default `agency`, env `APP_PROFILE`); dynamic title/MCQs/labels/layers/maxima from the profile; Markdown report download; profile-scoped chat state; stale-result banner; stale "0–70"/"79" labels removed. |
| `requirements.txt` | `google-genai>=1.0` (replaces `google-generativeai`), `ollama>=0.3.3`, `python-dotenv>=1.0`. |

### 2.4 New modules
- **`src/layer_agency/agency_checks.py`** — `check_r32` (llms.txt present; FORWARD-LOOKING, never scored).
- **`src/utils/agency_extractor.py`** — discovers and fetches the services and portfolio pages (standard paths, then same-site nav links) for R13 and Layer 6.
- **`src/utils/observability.py`** — `ensure_observability()`: every check carries a "what we did / what AI sees / raw evidence" block.

### 2.5 Tests and tooling
- **`tests/test_suite.py`** — 5 stale R25 tests rewritten for the v2 signature.
- **`tests/test_agency_profile.py`** — profile maxima/parity, scoring, R7 agency variant, R32, page discovery, fix templates.
- **`tests/test_fixes.py`** — gap thresholds, observability helper, LLM helpers, FAQ regex guard, title split, conclusion normalisation/actionability.
- **`validation/calibrate_gap.py`** — reproduces the L6 threshold calibration from the logged audits.
- **Result:** 77 offline tests pass, 0 fail (integration/LLM-marked tests deselected).

### 2.6 Bugs found and fixed along the way
1. FAQ topic regexes were corrupted by an escaping mistake in an earlier patch of this session (backspace characters) — broke FAQ matching on both profiles. Fixed + regression test.
2. The agency conclusion prompt was silently not applied (a patch had not matched). Fixed.
3. The 5 pre-existing R25 test failures (stale signature) and R25 WARN scoring 0 instead of 0.5.
4. L6 thresholds that labelled every site MISALIGNED.
5. Gemini SDK mismatch; Ollama availability check.
6. A cached stale `result` leaking fix-chat state between audits.

### 2.7 Verification performed
- Scoring equals the stored result on all 11 logged Shopify audits.
- A live Shopify audit gives the same 40/69 on the old and new code.
- Live agency audit of `https://www.cynbit.in`, headless Streamlit (`AppTest`) renders for both profiles, profile switching, localhost server health.

### 2.8 Later decision — A1–A4 discarded
The four unvalidated agency checks and everything that existed only to support them were **removed**:
- Checks: A1 services enumerated, A2 case studies, A3 pricing, A4 testimonials.
- The service / case-study / pricing / testimonial extractors, the JS-rendered caveat, the fix templates for A1–A4, their tests, and `validation/validate_agency.py`.
- `A5` (llms.txt) was kept and renamed **R32**.
- The generic "provisional" score support in the aggregator/UI stays but is inactive (`max_provisional = 0`), so no provisional card is shown.
- The agency profile now has **11 checks** (10 counted = 28 points + R32 informational).
- What stays from the agency work: agency profile config, MCQs, R7/R13/R15/R3/R23 agency variants, templates for the remaining checks.

---

## 3. Open items
- Gemini is untested live (no `GEMINI_API_KEY` in this environment); only the code path and fallback are covered.
- `cynbit.in` is unconfirmed as the real Cynbit site (`cynbit.com` does not resolve).
- `plan.md` still describes A1–A4 as planned work; it carries a note that they were discarded.
- `db/audits.db` is a tracked binary that changes whenever an audit runs; restore with `git checkout db/audits.db` before committing.
