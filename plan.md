# Plan: Cynbit adaptation — "agency" profile for the AI Risk Optimizer

> **Update:** the A1–A4 hypothesis checks (services enumerated, case studies, pricing, testimonials) described below were **discarded** after implementation, together with their extractors, templates and the validation script. `A5` became `R32` (llms.txt, informational). Sections 1–5 are kept as the original plan; see `session.md` for what actually exists.


**Goal:** audit whether AI assistants can find and recommend an IT-services agency
(Cynbit, Jaipur) for queries like "web development agency in Jaipur", using the same
rigor as the Shopify v2.0 engine: deterministic checks, VERIFIED/CORRELATED honesty,
one LLM call (conclusion) plus a scope-locked fix chatbot.

Branch: start from `final_version`, work on `feature/agency-profile`.

---

## 0. Decisions made (change any of these before Phase 1)

The three open questions in the brief are unanswered, so this plan assumes:

| # | Question | Assumed default | Why |
|---|---|---|---|
| 1 | New project vs extend | **Extend this repo with a `profile` parameter** (`shopify` \| `agency`) | About 85% of the code is domain-neutral (fetcher, embedder, L6 math, aggregator, db, logger). A fork would diverge. `validate.py` / `ai-visibility-analyzer` are not in this repo, so I can't plan around them. |
| 2 | Validate new checks first? | **Ship them, but unscored in the headline** (`tier: "HYPOTHESIS"`), shown as a separate "provisional" sub-score. A validation script is Phase 6; flip `scored=True` per check once it passes. | Matches the repo's own rule: README says every shipped check is VERIFIED or CORRELATED, and v0's mistake was mixing speculation into the score. |
| 3 | MCQ dimensions | 4 B2B dimensions: `service`, `client`, `differentiator`, `engagement` | Keeps the 4-key shape that `semantic_gap.py` and the 4×5 matrix expect. |

**Correction to the brief:** the list has 15 rows, not 14. That's 10 carried-over checks,
4 new agency checks, and 1 unscored llms.txt row. Dropping 3 and adding 3 would leave 16.
This plan uses **14 counted checks + 1 informational**.

---

## 1. Target checkpoint set

Existing codes are kept where the logic carries over. New checks get an `A` prefix so
old audit logs and `audits.db` rows (R9/R16/R17 mean price/refund/shipping) are never
reinterpreted.

| Code | Checkpoint | Layer | Tier | Kind | Max |
|---|---|---|---|---|---|
| R1 | robots.txt — AI crawler access | L1 | VERIFIED | checklist | 1 |
| R3 | sitemap — exists + service/portfolio URLs | L1 | VERIFIED | checklist | 1 |
| R5 | Bot protection blocking AI agents | L1 | CORRELATED | checklist | 1 |
| R6 | SSL valid | L1 | VERIFIED | checklist | 1 |
| R7 | schema.org Organization / ProfessionalService / LocalBusiness / Service | L2 | CORRELATED | scored | 10 |
| R11 | JSON-LD valid | L2 | CORRELATED | checklist | 1 |
| A1 | Services clearly enumerated (no "and more") | L2 | HYPOTHESIS | provisional | 10 |
| R13 | Service descriptions specific, not vague | L3 | CORRELATED | scored | 10 |
| R15 | FAQ exists + covers buyer topics | L3 | CORRELATED | checklist | 1 |
| A2 | Case studies — named client + measurable outcome ★ | L3 | HYPOTHESIS | provisional | 10 |
| A3 | Pricing / engagement model stated | L3 | HYPOTHESIS | provisional | 10 |
| R23 | Contact — branded email, phone, address | L4 | CORRELATED | checklist | 1 |
| R25 | Brand name consistent on-site | L4 | CORRELATED | checklist | 1 |
| A4 | Testimonials / third-party review presence | L4 | HYPOTHESIS | provisional | 1 |
| A5 | `/llms.txt` present | L5 | FORWARD-LOOKING | informational | 0 |

Headline score = validated checks only: R7, R13 (20 pts) + 8 checklist (R1, R3, R5, R6,
R11, R15, R23, R25) = **28**. Provisional score = A1–A4 = **31**. Both are shown.
Max values come from the profile, never hardcoded (see §2.4).

Dropped for agency: R9 price signal, R16 refund, R17 shipping, R28 UCP, R30 ACP, R31 GMC.

Out of scope: R25's real-world problem (directory listings disagreeing, "Cybit" vs
"Cynbit") is off-site. The engine only crawls the target domain, so it can't detect
that. R25 stays on-site and the report notes this.

---

## 2. Code changes

### 2.1 New: `src/profiles/` (the core change)

One config object per domain, so no `if domain == ...` is scattered through the layers.

```
src/profiles/__init__.py   Profile, CheckSpec, get_profile(name)
src/profiles/shopify.py    current behaviour, extracted verbatim (regression guard)
src/profiles/agency.py     Cynbit config
```

```python
# src/profiles/__init__.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class CheckSpec:
    code: str
    label: str
    layer: str                 # "L1".."L5"
    tier: str                  # VERIFIED | CORRELATED | HYPOTHESIS | FORWARD-LOOKING
    kind: str                  # scored | checklist | provisional | informational
    max_score: float

@dataclass(frozen=True)
class Profile:
    name: str
    checks: tuple[CheckSpec, ...]
    mcq_options: dict          # UI choices
    mcq_templates: dict        # L6 sentence templates
    l6_page_keys: tuple[str, ...]         # replaces ("homepage","about","product","faq","policies")
    page_paths: dict           # {"about": [...], "contact": [...], "services": [...], ...}
    faq_topics: tuple[str, ...]
    conclusion_system_prompt: str
    fix_persona: str           # replaces "helpful Shopify store advisor"
    templates: dict = field(default_factory=dict)   # fix templates

def get_profile(name: str) -> Profile: ...
```

`agency.py` values:

```python
mcq_options = {
  "service":        ["Web development","App development","AI / ML","SEO / marketing","UI/UX design","Cloud / DevOps","Other"],
  "client":         ["Startups","SMEs","Enterprise","E-commerce brands","Agencies (white-label)"],
  "differentiator": ["Price","Speed of delivery","Technical depth","Domain expertise","Post-launch support"],
  "engagement":     ["Fixed price","Time & materials","Monthly retainer","Dedicated team"],
}
mcq_templates = {
  "service":        "We are an IT services agency specialising in {value}.",
  "client":         "Our primary clients are {value}.",
  "differentiator": "Our main differentiator is {value}.",
  "engagement":     "We typically work on a {value} basis.",
}
l6_page_keys = ("homepage","about","services","portfolio","faq")
page_paths = {
  "about":     ["/about","/about-us","/company","/who-we-are"],
  "contact":   ["/contact","/contact-us","/get-in-touch"],
  "services":  ["/services","/our-services","/what-we-do","/solutions"],
  "portfolio": ["/portfolio","/case-studies","/work","/our-work","/projects"],
  "pricing":   ["/pricing","/packages","/plans","/engagement-models"],
  "testimonials": ["/testimonials","/clients","/reviews"],
}
faq_topics = ("pricing","timeline","process","support","technology","contract")
```

### 2.2 `src/auditor.py` — profile-aware orchestration

- Signature: `run_audit(store_url, free_text, mcq, use_cache=True, progress_cb=None, profile="shopify")`.
  The default keeps every existing caller and test working.
- Replace the hardcoded Shopify paths with profile lookups:
  - `["/pages/about", "/pages/about-us"]` → `profile.page_paths["about"]`
  - `["/policies/refund-policy", "/policies/shipping-policy"]` → agency: services, portfolio and pricing pages go into `page_texts["services"]`, `["portfolio"]`
  - `["/pages/contact", ...]` → `profile.page_paths["contact"]`
- Branch the check block on `profile.name`: the shopify branch is today's code unchanged; the agency branch calls the new checks (§2.5). Both build the same `checks` dict, so L6, L7, logging and the DB need no changes.
- Fix a pre-existing smell while here: `product_urls` from R3 feeds R13. For agency, R3 should return `service_urls` and R13 should sample one service page.
- Cache and DB key: use `profile` in the key (§2.6).

### 2.3 `src/layer1/r3_r5_r6.py` — R3

`check_r3(base_url, profile_name="shopify")`: the counters use `re.findall(r"/products?/", …)`.
For agency, count `/services?/`, `/portfolio/`, `/case-stud(y|ies)/`, `/work/`, `/blog/` and
return `service_urls` plus `portfolio_urls`. The shopify branch is untouched. The sitemap-index
child-following logic is domain-neutral; reuse it.

### 2.4 `src/layer7/aggregator.py` — profile-driven scoring

Today `SCORE_MAX`, `SCORED_CHECKS`, `CHECKLIST_CHECKS`, `MAX_*` are module constants and R30
is special-cased by name. Replace them with values derived from the profile.

```python
def compute_score(all_checks: dict, profile) -> dict:
    spec = {c.code: c for c in profile.checks}
    scored = checklist = provisional = 0.0
    breakdown = {}
    for code, res in all_checks.items():
        s = spec.get(code)
        if s is None:            # e.g. "layer6"
            continue
        status = res.get("status", "UNKNOWN")
        raw = 0 if status in ("UNKNOWN","ERROR","FORWARD-LOOKING","NOT-APPLICABLE","INFORMATIONAL") \
                else res.get("score", 0)
        breakdown[code] = {"score": raw, "max": s.max_score, "status": status,
                           "detail": res.get("detail",""), "kind": s.kind, "tier": s.tier}
        if   s.kind == "scored":      scored      += raw
        elif s.kind == "checklist":   checklist   += raw
        elif s.kind == "provisional": provisional += raw
    max_headline = sum(c.max_score for c in profile.checks if c.kind in ("scored","checklist"))
    max_prov     = sum(c.max_score for c in profile.checks if c.kind == "provisional")
    ...
    return {..., "grand_total": scored+checklist, "max_total": max_headline,
            "provisional_total": provisional, "max_provisional": max_prov, ...}
```

- `get_failed_checks`: replace `if code == "R30": continue` with "skip `informational` kind".
- `build_conclusion`: take the system prompt from `profile.conclusion_system_prompt`
  (agency: "expert AI-visibility auditor… for an IT services agency… name the failed checks…").
  Keep the Gemini → Ollama → rule-based fallback.
- Keep `R25 WARN = 0.5` as is.
- Keep the shopify numbers identical (69 max) so the Shopify profile regresses to nothing.

### 2.5 New agency checks

**Extractor** (`src/utils/semantic_extractor.py`): add methods beside `extract_refund` /
`extract_shipping`, same return shape (`found`, `confidence`, `raw`, plus counts). Same
Tier 1 (regex/spaCy) → Tier 2 (MiniLM) pattern. Tier 3 stays unimplemented.

| Method | Tier 1 (deterministic) | Tier 2 |
|---|---|---|
| `extract_services` | Headings/nav on homepage + services page; schema `Service` / `OfferCatalog` names; vague-phrase regex (`and more`, `etc\.`, `all kinds of`, `end-to-end solutions`) | Reuse R13's vague/specific exemplars against service blurbs |
| `extract_case_studies` | Discover via `portfolio` paths, sitemap keyword regex, nav scan; per entry: NER `ORG` for client, outcome regex (`\d+\s?%`, `\d+x`, `reduced.*by`, `increase`, `revenue`, `traffic`), tech-stack tokens | Entry-vs-"case study" exemplar similarity when the page has no headings |
| `extract_pricing` | Currency regexes (reuse `_PRICE_*`), `starting (at|from)`, `₹`, engagement words (`fixed price`, `retainer`, `hourly`, `per month`), "get a quote" detector | — |
| `extract_testimonials` | Schema `Review` / `AggregateRating`; blockquote + attribution pattern (`— Name, Title, Company`); links to clutch.co, goodfirms.co, google reviews, trustpilot | — |

`extract_brand` already accepts `Organization`, `Store`, `LocalBusiness`; add
`ProfessionalService`.

`SemanticExtractor.extract(...)` gains `profile` and populates the matching keys
(`services`, `case_studies`, `pricing`, `testimonials`). The Shopify keys are only
populated for the shopify profile, so agency audits skip the refund/shipping crawls.

**Checks** — new file `src/layer_agency/agency_checks.py` (a separate module keeps the
Shopify layers frozen). Each returns the existing dict contract: `check`, `tier`, `status`,
`score`, `detail`, `evidence`, `fix`, and an `observability` dict for the log.

| Check | Scoring table (deterministic) |
|---|---|
| `check_a1(semantic_data)` | ≥4 named services with a description → 10 · 2–3 → 6 · 1 → 3 · 0 → 0. Vague phrase found → cap at 6 and add WARN. |
| `check_a2(semantic_data)` ★ | ≥3 case studies, ≥1 with a numeric outcome → 10 · named, no outcomes → 6 · gallery only → 3 · none → 0 |
| `check_a3(semantic_data)` | Currency range + model → 10 · model stated, no number → 6 · "get a quote" only → 3 · nothing → 0 |
| `check_a4(semantic_data)` | ≥2 attributed testimonials **or** a third-party review profile linked → PASS 1 · exactly 1 → WARN 0.5 · none → FAIL 0 |
| `check_a5(base_url)` | `GET /llms.txt` → status always `FORWARD-LOOKING`, `detail` says present/absent. Never scored. |

Adapt the existing agency-relevant checks via the profile, not by editing their logic:

- `check_r7`: `_REQUIRED_PRODUCT_FIELDS` / `_RECOMMENDED_FIELDS` become profile-supplied.
  Agency required: `@type` ∈ {Organization, ProfessionalService, LocalBusiness},
  `name`, `url`, `description`, `address` or `areaServed`; recommended: `sameAs`,
  `hasOfferCatalog`, `contactPoint`, `logo`.
- `check_r13`: the logic is unchanged, but pass `service_text` instead of `product_text`.
  Verify the exemplar sets ("316L surgical steel…") still discriminate for services. Likely
  add `_SPECIFIC_EXEMPLARS_AGENCY` ("React 18 + Node.js REST API, delivered in 8 weeks…").
- `check_r15`: `_FAQ_TOPICS` / `_MIN_TOPICS_PASS` from `profile.faq_topics` (4/6 stays).
- `check_r23`, `check_r25`: unchanged.

### 2.6 `src/utils/db.py`

`url_hash(url)` → `url_hash(url, profile="shopify")`. Hash `f"{profile}:{url}"` only when
the profile is not `shopify`, so existing `audits.db` rows and chat history stay
reachable. `save_audit` / `load_audit` / chat functions gain a `profile` argument defaulting to
`"shopify"`. No schema migration is needed.

### 2.7 `src/layer6/semantic_gap.py`

The math is domain-neutral. Only the config is hardcoded:

- `_MCQ_TEMPLATES` → `profile.mcq_templates` (pass `profile` into `compute_gap`).
- `_build_v2`'s key tuple `("homepage","about","product","faq","policies")` → `profile.l6_page_keys`.
- `_build_v3_from_schema` / `_build_v3_fallback`: **not read yet.** Confirm that they
  handle `Organization` / `Service` types and not only `Product`. Adjust if needed.
- `_build_summary` wording: check for commerce phrasing.

### 2.8 `src/part2/fix_engine.py`

- `TEMPLATES` becomes `profile.templates`. Keep the Shopify dict in `profiles/shopify.py`.
  Existing R1/R5/R6/R11/R25 templates are mostly platform-neutral. Re-word R3
  (it says "In Shopify: Online Store → Preferences…") for agency.
- Add agency templates, each with `title`, `summary`, `steps` and a copy-paste `template`:
  - **R7:** a ready-to-paste `ProfessionalService` JSON-LD block (name, url, address, areaServed "Jaipur", sameAs, hasOfferCatalog).
  - **A1:** services page structure plus a `Service` JSON-LD snippet.
  - **A2:** a case-study copy template (Client → Problem → Approach → Stack → Measured outcome → Quote) and `CreativeWork` markup.
  - **A3:** pricing-page copy with example ranges and engagement models.
  - **A4:** testimonial block with attribution, plus `Review` markup.
  - **A5:** a starter `llms.txt`.
- `chatbot_reply`: the system prompt "helpful Shopify store advisor" → `profile.fix_persona`; "merchant" → "client"; keep the scope lock and the 150-word cap.

### 2.9 `app.py` (Streamlit)

- Docstring and `st.caption` say Shopify; the score metrics label "(0–70)" and the docstring "X/79" are already stale (real max is 69). Drive all of these from `score["max_*"]`.
- Add a profile selector (or an env/secret default of `agency` for the Cynbit deployment).
- `MCQ_OPTIONS`, `CHECK_LABELS`, `CHECK_ORDER`, `LAYER_LABELS` become views of `profile.checks`.
- Line ~166: `max_val = 1 if code in {...} else 10` → `spec.max_score`.
- Render provisional checks in their own section ("Provisional — not yet validated") with the headline and provisional scores side by side.
- Export: add Markdown report download (assemble from `result`; PDF only if a dependency is already acceptable).

### 2.10 `src/utils/obs_logger.py`

Add `profile` to the log JSON. `_build_causality(code, obs)` maps check codes to text.
**Not read.** Add causality strings for A1–A5, or it'll fall through to a default.

### 2.11 `requirements.txt`

No new dependencies. `python-dotenv` is imported by `app.py` but missing from
`requirements.txt`; add it (unrelated bug, one line).

---

## 3. Phases

1. **Refactor, no behaviour change.** Add `profiles/`, move the Shopify constants into
   `profiles/shopify.py`, thread `profile` through `auditor`, `aggregator`, `db`, `gap`,
   `fix_engine`, `app`. **Gate:** existing `tests/` pass and a Shopify audit of a logged
   store gives the same 69-point breakdown as its file in `logs/`.
2. **Agency extraction.** `extract_services/case_studies/pricing/testimonials`, with unit
   tests on saved HTML fixtures. Fixtures are required because Cynbit's live site may
   change.
3. **Agency checks.** R3/R7/R13/R15 profile hooks, then A1–A5.
4. **Scoring and L6.** Headline vs provisional score, agency MCQs, page keys.
5. **Fix engine + UI.** Agency templates, provisional section, export.
6. **Validation script** (`validation/validate_agency.py`):
   - Query Gemini, Perplexity and ChatGPT 3× each on ~5 service queries ("best web development company in Jaipur", "AI development agency India", …). Responses are collected manually or via API, so this isn't automated end to end.
   - Take the top-recommended agencies per query, then run the 14 checks on each winner and on a control set of non-recommended agencies.
   - Compare pass rates per check. Promote a check from `HYPOTHESIS` to `CORRELATED` and set `kind="scored"` only if winners clearly beat controls. Drop or re-tier any with no signal.
   - Small samples: report counts, not percentages, and say so.
7. **Cynbit run.** Audit `cynbit.com` (confirm the domain), save the log, review the output by hand for false negatives before trusting it.

---

## 4. Tests

- `tests/test_agency_profile.py` (new): per-check fixtures for pass / warn / fail on A1–A4, R7 agency schema, R15 topics. Offline only (mock `safe_get`).
- Profile parity test: `compute_score` with the shopify profile equals the old module constants (69 / 60 / 9).
- Ensure the extractor doesn't crawl refund/shipping paths under the agency profile (assert zero fetches to `/policies/*`).
- Existing `tests/test_suite.py` and `tests/test_encoding.py` must still pass untouched.

## 5. Risks and open items

- **A1–A4 are unvalidated.** They influence the provisional score only until Phase 6 says otherwise.
- **Small-sample validation.** The agency validation can't match the 24-store Shopify study. Say so in the README.
- **Heuristic fragility.** Case-study and testimonial detection on arbitrary agency sites (JS-rendered pages, carousels) will have false negatives. The existing `is_garbage` / empty-HTML handling applies; JS-only sites will score low. Surface "page appears JS-rendered" in the observability trace instead of silently failing.
- **Files I haven't read in full** (verify when implementing): `layer3` R13/R15 internals, `layer4` R23, `layer6` V3 builders, `obs_logger._build_causality`, `fix_engine` templates beyond R1–R5, `tests/`.
- **Cynbit's domain and Jaipur geography signal** (LocalBusiness `areaServed`, address) are only checked through R7/R23. A dedicated NAP-consistency check is a possible later addition.

---

## 6. Execution status (2026-11-08)

Implemented on branch `feature/agency-profile`, Phases 1–5 plus a Phase-6 script. Phase 6 has not been run, because it needs the LLM-recommended winner/control agency list.

- **Deviations from this plan:**
  - Fix templates live in `src/profiles/agency_templates.py` (agency) and stay in `fix_engine.TEMPLATES` (shopify), rather than on the profile object for both.
  - Extraction for agency pages is in `src/utils/agency_extractor.py`, called from `SemanticExtractor._extract_agency`.
  - The profile selector defaults to `agency` (override with env `APP_PROFILE=shopify`).
- **Verified:**
  - Shopify scoring matches the stored result on all 11 logged audits.
  - A live Shopify audit gives the same 40/69 on the old and new code.
  - 96 offline tests pass.
  - The 5 previously failing `TestR25BrandConsistency` tests were rewritten and pass (see below).
- **Issues fixed after the first pass:**
  - L6 thresholds recalibrated to 0.55 / 0.75 (`validation/calibrate_gap.py` reproduces the numbers).
  - The agency conclusion prompt was never being applied (a patch had silently failed); it is now used, with noun and actionability safeguards.
  - FAQ topic regexes were corrupted by an escaping mistake (backspace characters). This broke FAQ topic matching on both profiles. Fixed, with a regression test.
  - R25: WARN now scores 0.5 as documented, en-dash titles split correctly, and the 5 stale tests were rewritten for the v2 signature.
  - `llm.py` uses the `google-genai` SDK (legacy SDK as fallback) and `ollama_available()` handles the newer ollama response type.
  - Every check now carries an observability block, and non-PASS A1–A4 findings on JS-rendered homepages carry a crawl-limitation caveat.
- **Still open:**
  - `A1`–`A4` are tuned on fixtures plus one live site; run `validation/validate_agency.py` on real winner/control agencies.
  - Gemini itself is untested (no `GEMINI_API_KEY` in this environment); only the code path and the fallback are covered.
  - The cynbit.in domain is unconfirmed as the real Cynbit site.
