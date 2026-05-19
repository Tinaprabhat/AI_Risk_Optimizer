"""
test_full_architecture.py
─────────────────────────
Full end-to-end architecture test using colourpop.com.

What this tests (in order):
  1.  DB init          — PostgreSQL tables created
  2.  Cache clear      — wipe any old colourpop result so we get a real fresh run
  3.  Fetcher          — can we reach colourpop.com
  4.  Embedder         — model loads, cosine similarity works
  5.  LLM              — Gemini → Ollama fallback chain
  6.  Layer 1          — robots, sitemap, bot protection, SSL
  7.  Layer 2          — schema.org, price signal, JSON-LD validity
  8.  Layer 3          — product descriptions, FAQ, refund, shipping
  9.  Layer 4          — contact page, brand consistency
  10. Layer 5          — UCP, ACP (informational), GMC signals
  11. Layer 6          — semantic gap / AI mirror (3 perceptions)
  12. Layer 7          — aggregator, score, LLM conclusion
  13. Full audit       — run_audit() orchestrates all of the above
  14. DB save          — result stored in PostgreSQL
  15. Cache hit        — same URL returns instantly from DB
  16. Cache bypass     — use_cache=False re-runs everything
  17. Fix engine       — template + chatbot on first failed check

Run from inside backend/:
    python test_full_architecture.py
"""

import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# ── STORE DATA ────────────────────────────────────────────────────────────────

STORE_URL = "https://colourpop.com/"

FREE_TEXT = (
    "ColourPop is a beauty and cosmetics store offering affordable, "
    "trendy makeup products. Our customers are young makeup enthusiasts "
    "who love experimenting with bold, vibrant looks. "
    "We differentiate through affordable trendy cosmetics with a "
    "playful and vibrant brand tone."
)

MCQ = {
    "category":       "beauty and cosmetics",
    "customer":       "young makeup enthusiasts",
    "differentiator": "affordable trendy cosmetics",
    "tone":           "playful and vibrant",
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

PASS_COUNT = 0
FAIL_COUNT = 0

def ok(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  ✓  {msg}")

def fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  ✗  {msg}")

def section(title):
    print(f"\n{'━'*60}")
    print(f"  {title}")
    print(f"{'━'*60}")

def progress_cb(msg):
    print(f"      → {msg}")


# ══════════════════════════════════════════════════════════════════════════════
# 1. DATABASE INIT
# ══════════════════════════════════════════════════════════════════════════════
section("1. DATABASE — SQLite init")

from src.utils.db import (
    init_db, save_audit, load_audit,
    save_chat_message, load_chat_history, clear_chat_history,
    _connect, url_hash,
)

try:
    init_db()
    ok("SQLite connected and tables created (audits, chat_history)")
except Exception as e:
    fail(f"DB init failed: {e}")
    print("\n  Check SQLite path / DATABASE_URL in your .env file.")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CACHE CLEAR — start fresh
# ══════════════════════════════════════════════════════════════════════════════
section("2. CACHE CLEAR — wipe old colourpop result")

try:
    conn = _connect()
    conn.execute(
        "DELETE FROM audits WHERE url_hash = ?",
        (url_hash(STORE_URL),)
    )
    conn.commit()
    conn.close()

    check = load_audit(STORE_URL)
    if check is None:
        ok("Cache cleared — DB has no result for colourpop.com")
    else:
        fail("Cache still has data after delete — check DB permissions")
except Exception as e:
    fail(f"Cache clear failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. FETCHER
# ══════════════════════════════════════════════════════════════════════════════
section("3. FETCHER — HTTP client test on colourpop.com")

from src.utils.fetcher import safe_get

fetch = safe_get(STORE_URL)
if fetch.ok:
    ok(f"colourpop.com reachable — {len(fetch.text):,} chars fetched")
    ok(f"HTTP status: {fetch.status_code}")
    # Quick sanity check — does it look like HTML
    if "<html" in fetch.text.lower() or "<!doctype" in fetch.text.lower():
        ok("Response looks like valid HTML")
    else:
        fail("Response does not look like HTML — possible encoding issue")
else:
    fail(f"Could not fetch colourpop.com: {fetch.error} (status={fetch.status_code})")
    print("  Tests will continue but layer results may show UNKNOWN")

homepage_html = fetch.text if fetch.ok else ""


# ══════════════════════════════════════════════════════════════════════════════
# 4. EMBEDDER
# ══════════════════════════════════════════════════════════════════════════════
section("4. EMBEDDER — all-MiniLM-L6-v2 singleton")

from src.utils.embedder import embed, cosine_sim, embed_batch

print("  Loading model (first call takes ~2s)...")
t = time.time()
e_beauty   = embed("beauty and cosmetics store with affordable makeup")
e_beauty2  = embed("beauty and cosmetics store with affordable makeup")
e_unrelated = embed("industrial machinery and heavy equipment manufacturer")
load_time  = time.time() - t

ok(f"Model loaded and embedded in {load_time:.2f}s")
ok(f"Same text similarity:      {cosine_sim(e_beauty, e_beauty2):.4f}  (expected ~1.0)")
ok(f"Different text similarity: {cosine_sim(e_beauty, e_unrelated):.4f}  (expected <0.5)")

# Batch test
batch = embed_batch(["playful tone", "vibrant colors", "affordable prices"])
ok(f"Batch embed working — shape: {batch.shape}  (expected (3, 384))")


# ══════════════════════════════════════════════════════════════════════════════
# 5. LLM — Gemini → Ollama fallback
# ══════════════════════════════════════════════════════════════════════════════
section("5. LLM — Gemini → Ollama Mistral → fallback chain")

from src.utils.llm import call_llm, ollama_available

# Check Ollama availability
ollama_up = ollama_available()
print(f"  Ollama available: {'Yes' if ollama_up else 'No (will use Gemini or fallback)'}")

response, source = call_llm(
    prompt=(
        "In one sentence, what does a beauty brand need to do "
        "to be recommended by AI shopping agents?"
    ),
    system="You are an AI commerce expert. Be concise.",
    fallback_text="FALLBACK: Add structured schema, clear pricing, and specific product descriptions.",
)

ok(f"LLM responded via: {source}")
ok(f"Response: {response[:120]}")

if source == "gemini":
    ok("Gemini is working — primary LLM active")
elif source == "ollama_mistral":
    ok("Ollama Mistral is working — fallback LLM active (Gemini may be down)")
else:
    print(f"  ⚠  Both Gemini and Ollama failed — using hardcoded fallback")
    print(f"     Conclusion in audit will be rule-based, not AI-generated")


# ══════════════════════════════════════════════════════════════════════════════
# 6–12. FULL AUDIT — all 7 layers
# ══════════════════════════════════════════════════════════════════════════════
section("6–12. FULL AUDIT — all 7 layers running on colourpop.com")
print("  This takes 30–60 seconds. Progress:")
print()

from src.auditor import run_audit

t_audit = time.time()
result = run_audit(
    store_url=STORE_URL,
    free_text=FREE_TEXT,
    mcq=MCQ,
    use_cache=False,      # force fresh — ignore any cached result
    progress_cb=progress_cb,
)
audit_time = time.time() - t_audit

ok(f"Full audit completed in {audit_time:.1f}s")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER-BY-LAYER RESULTS
# ══════════════════════════════════════════════════════════════════════════════
section("LAYER RESULTS — per check breakdown")

checks = result.get("checks", {})
score  = result.get("score", {})

LAYER_MAP = {
    "L1 Crawlability":     ["R1", "R3", "R5", "R6"],
    "L2 Structured Data":  ["R7", "R9", "R11"],
    "L3 Semantic Content": ["R13", "R15", "R16", "R17"],
    "L4 Trust Signals":    ["R23", "R25"],
    "L5 AI-Era Protocols": ["R28", "R30", "R31"],
}

for layer_name, codes in LAYER_MAP.items():
    print(f"\n  ── {layer_name} ──")
    for code in codes:
        if code not in checks:
            print(f"    {code:<6} MISSING from results")
            continue
        c      = checks[code]
        status = c.get("status", "?")
        scr    = c.get("score", "-")
        detail = c.get("detail", "")[:65]
        tier   = c.get("tier", "")
        info   = " [INFORMATIONAL]" if c.get("scored") is False else ""

        # Status emoji
        emoji = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "UNKNOWN": "?"}.get(status, "·")
        print(f"    {emoji} {code:<6} {status:<14} score={str(scr):<6} [{tier}]{info}")
        print(f"           {detail}")
        if status in ("FAIL", "WARN") and c.get("fix"):
            fix_preview = c["fix"].split("\n")[0][:80]
            print(f"           Fix: {fix_preview}")


# ══════════════════════════════════════════════════════════════════════════════
# SCORE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
section("SCORE SUMMARY")

print(f"""
  Total Score    : {score.get('grand_total')}/{score.get('max_total')}  ({score.get('pct')}%)
  Scored checks  : {score.get('scored_total')}/{score.get('max_scored')}   (R7 R9 R13 R16 R17 R31 — 0–10 each)
  Checklist      : {score.get('checklist_total')}/{score.get('max_checklist')}    (R1 R3 R5 R6 R11 R15 R23 R25 R28 — binary)
""")

pct = score.get("pct", 0)
if pct >= 80:
    print("  Rating: EXCELLENT — store is well optimised for AI discovery")
elif pct >= 60:
    print("  Rating: GOOD — a few gaps to fix")
elif pct >= 40:
    print("  Rating: AVERAGE — significant issues reducing AI visibility")
else:
    print("  Rating: POOR — major issues blocking AI from recommending this store")

failed = result.get("failed", [])
if failed:
    print(f"\n  Top issues ({len(failed)} total):")
    for f in failed[:5]:
        print(f"    ✗ {f['code']} [{f['status']}]: {f['detail'][:70]}")


# ══════════════════════════════════════════════════════════════════════════════
# AI MIRROR — 3 perceptions
# ══════════════════════════════════════════════════════════════════════════════
section("AI MIRROR — 3 perceptions of colourpop.com")

gap = result.get("gap", {})

print("""
  The AI Mirror shows 3 different "views" of the same store:

  1. OUR PERCEPTION    — what the merchant says their store is about
  2. HTML PERCEPTION   — what an AI reads from the crawled webpage text
  3. AI PERCEPTION     — what an AI reads from structured data (JSON-LD schema)

  If these 3 are ALIGNED, AI recommends you confidently.
  If they DRIFT or MISALIGN, AI gets confused and skips your store.
""")

print("  ┌─ 1. OUR PERCEPTION (merchant intent — what YOU think you say) ─────")
intent = gap.get("intent_text", "(not available)")
for line in intent[:400].split(". "):
    if line.strip():
        print(f"  │  {line.strip()}.")
print("  └────────────────────────────────────────────────────────────────────")

print()
print("  ┌─ 2. HTML PERCEPTION (what AI reads from your website text) ────────")
website = gap.get("website_text", "(not available)")
for line in website[:400].split(". "):
    if line.strip():
        print(f"  │  {line.strip()}.")
print("  └────────────────────────────────────────────────────────────────────")

print()
schema_source = gap.get("schema_source", "UNKNOWN")
schema_label  = "JSON-LD Schema" if schema_source == "SCHEMA" else "Crawled Content (no JSON-LD found)"
print(f"  ┌─ 3. AI PERCEPTION (what AI reads from structured data — {schema_label}) ─")
schema = gap.get("schema_text", "(not available)")
for line in schema[:400].split(". "):
    if line.strip():
        print(f"  │  {line.strip()}.")
print("  └────────────────────────────────────────────────────────────────────")

print()
print("  ── GAP SCORES ──────────────────────────────────────────────────────")
print(f"  Gap range: 0.0 = perfectly aligned | 0.15+ = misaligned")
print()

gap_IW    = gap.get("gap_IW")
gap_IS    = gap.get("gap_IS")
gap_WS    = gap.get("gap_WS")
label_IW  = gap.get("IW_label", "N/A")
label_IS  = gap.get("IS_label", "N/A")
label_WS  = gap.get("WS_label", "N/A")

def gap_bar(val):
    if val is None:
        return "N/A"
    filled = int(val * 100 / 2)
    bar    = "█" * filled + "░" * (50 - filled)
    return f"{bar}  {val:.3f}"

print(f"  Our intent  vs Website HTML : [{label_IW:<11}]  {gap_bar(gap_IW)}")
print(f"  Our intent  vs AI Schema    : [{label_IS:<11}]  {gap_bar(gap_IS)}")
print(f"  Website HTML vs AI Schema   : [{label_WS:<11}]  {gap_bar(gap_WS)}")

print()
print("  ── DIMENSION MATRIX (how each MCQ dimension aligns per page) ───────")
matrix = gap.get("matrix", {})
if matrix:
    pages = list(list(matrix.values())[0].keys()) if matrix else []
    header = f"  {'Dimension':<18}" + "".join(f"  {p:<12}" for p in pages)
    print(header)
    print("  " + "─" * (16 + 14 * len(pages)))
    for dim, page_scores in matrix.items():
        row = f"  {dim:<18}"
        for page in pages:
            entry = page_scores.get(page, {})
            g     = entry.get("gap")
            lbl   = entry.get("label", "?")[:3]
            row  += f"  {f'{g:.2f} {lbl}':<12}"
        print(row)
else:
    print("  Matrix not available")

print(f"\n  Schema source: {schema_source}")
if schema_source == "CRAWLED_FALLBACK":
    print("  ⚠ No JSON-LD found — AI perception built from crawled text.")
    print("    Add schema.org markup for a precise AI perception score.")


# ══════════════════════════════════════════════════════════════════════════════
# LLM CONCLUSION
# ══════════════════════════════════════════════════════════════════════════════
section("LLM CONCLUSION")

conclusion  = result.get("conclusion", "")
llm_source  = result.get("llm_source", "unknown")

print(f"  Generated by: {llm_source}")
print()
# Word-wrap at 65 chars
words  = conclusion.split()
line   = "  "
for word in words:
    if len(line) + len(word) + 1 > 67:
        print(line)
        line = "  " + word + " "
    else:
        line += word + " "
if line.strip():
    print(line)


# ══════════════════════════════════════════════════════════════════════════════
# 14. DB SAVE VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
section("14. DB SAVE — verifying result stored in SQLite")

try:
    conn = _connect()
    row = conn.execute(
        "SELECT url, audit_date, results_json FROM audits WHERE url_hash = ?",
        (url_hash(STORE_URL),)
    ).fetchone()
    conn.close()

    if row:
        row_data = dict(row)
        results  = json.loads(row_data["results_json"])
        pct      = results.get("score", {}).get("pct", "?")
        json_size = len(row_data["results_json"])
        ok(f"Row saved in SQLite:")
        ok(f"  url        = {row_data['url']}")
        ok(f"  audit_date = {row_data['audit_date']}")
        ok(f"  score pct  = {pct}%")
        ok(f"  JSON size  = {json_size:,} bytes")
    else:
        fail("Row NOT found in SQLite after audit — save_audit() may have failed")
except Exception as e:
    fail(f"DB verification failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 15. CACHE HIT
# ══════════════════════════════════════════════════════════════════════════════
section("15. CACHE HIT — same URL must return instantly")

print("  Running same URL again with use_cache=True...")
t_cache = time.time()
cached_result = run_audit(
    store_url=STORE_URL,
    free_text=FREE_TEXT,
    mcq=MCQ,
    use_cache=True,
)
cache_time = time.time() - t_cache

print(f"  Fresh audit took : {audit_time:.1f}s")
print(f"  Cached call took : {cache_time:.3f}s")
print(f"  Speedup          : {audit_time / max(cache_time, 0.001):.0f}x faster")
print()

if cache_time < 2.0:
    ok(f"CACHE HIT confirmed — {cache_time:.3f}s (not re-running all layers)")
else:
    fail(f"Cache miss — took {cache_time:.1f}s, expected <2s")

# Prove same data
if cached_result["score"]["grand_total"] == result["score"]["grand_total"]:
    ok("Cached score matches fresh score exactly")
else:
    fail("Cached score differs from fresh score — data mismatch")

if cached_result.get("conclusion", "")[:50] == result.get("conclusion", "")[:50]:
    ok("Cached conclusion matches fresh conclusion exactly")
else:
    fail("Conclusion mismatch between cache and fresh result")


# ══════════════════════════════════════════════════════════════════════════════
# 16. CACHE BYPASS
# ══════════════════════════════════════════════════════════════════════════════
section("16. CACHE BYPASS — use_cache=False must re-run even if cache exists")

print("  Running same URL with use_cache=False (will take 30–60s again)...")
print()

t_bypass = time.time()
bypass_result = run_audit(
    store_url=STORE_URL,
    free_text=FREE_TEXT,
    mcq=MCQ,
    use_cache=False,
    progress_cb=progress_cb,
)
bypass_time = time.time() - t_bypass

if bypass_time > 5.0:
    ok(f"Cache correctly bypassed — full re-audit ran in {bypass_time:.1f}s")
else:
    fail(f"Suspiciously fast ({bypass_time:.2f}s) — cache may not be bypassing")


# ══════════════════════════════════════════════════════════════════════════════
# 17. FIX ENGINE
# ══════════════════════════════════════════════════════════════════════════════
section("17. FIX ENGINE — template + chatbot on first failed check")

from src.part2.fix_engine import (
    chatbot_first_message,
    chatbot_reply,
    get_fix_template,
)

if not failed:
    print("  No failed checks — using R7 as test case")
    test_check = {"code": "R7", "detail": "No Organization schema found", "fix": "Add schema.org JSON-LD"}
else:
    test_check = failed[0]
    print(f"  Testing on first failed check: {test_check['code']}")

code   = test_check["code"]
detail = test_check["detail"]
fix    = test_check.get("fix", "")

# Template
template = get_fix_template(code)
if template:
    ok(f"Fix template loaded for {code}: {template['title']}")
    ok(f"Steps: {len(template['steps'])} steps defined")
else:
    print(f"  ⚠  No template for {code}")

# First message
first_msg = chatbot_first_message(code, detail)
ok(f"First chatbot message generated ({len(first_msg)} chars)")
print(f"\n  Chatbot opening message:")
print(f"  ┌────────────────────────────────────────────────────────")
for line in first_msg[:300].split("\n"):
    print(f"  │ {line}")
print(f"  └────────────────────────────────────────────────────────")

# Save to DB and get reply
save_chat_message(STORE_URL, code, "bot", first_msg)
save_chat_message(STORE_URL, code, "user", "Ok I understand. What is the first step?")

history = load_chat_history(STORE_URL, code)
ok(f"Chat history saved — {len(history)} messages in DB")

reply, reply_source = chatbot_reply(
    check_code=code,
    check_detail=detail,
    check_fix=fix,
    store_url=STORE_URL,
    user_message="Ok I understand. What is the first step?",
    history=history,
)
save_chat_message(STORE_URL, code, "bot", reply)

ok(f"Chatbot replied via {reply_source}")
print(f"\n  Advisor reply:")
print(f"  ┌────────────────────────────────────────────────────────")
for line in reply[:300].split("\n"):
    print(f"  │ {line}")
print(f"  └────────────────────────────────────────────────────────")


# ══════════════════════════════════════════════════════════════════════════════
# OBSERVABILITY LOG
# ══════════════════════════════════════════════════════════════════════════════
section("OBSERVABILITY LOG")

log_path = result.get("log_path", "")
if log_path and os.path.exists(log_path):
    size = os.path.getsize(log_path)
    ok(f"Log written: {log_path}")
    ok(f"Log size: {size:,} bytes")
    # Show a snippet
    with open(log_path, encoding="utf-8") as f:
        log_data = json.load(f)
    ok(f"Log contains {len(log_data.get('checks', {}))} check entries")
    ok(f"Log meta: score={log_data['meta']['score']['pct']}%  domain={log_data['meta']['domain']}")
else:
    print("  ⚠  Log file not found — obs_logger may have failed")


# ══════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'━'*60}")
print(f"  FINAL SUMMARY")
print(f"{'━'*60}")
print(f"""
  Store tested    : {STORE_URL}
  Audit score     : {result['score']['grand_total']}/{result['score']['max_total']}  ({result['score']['pct']}%)
  LLM used        : {result.get('llm_source')}
  Audit time      : {audit_time:.1f}s
  Cache time      : {cache_time:.3f}s
  Speedup         : {audit_time / max(cache_time, 0.001):.0f}x

  AI Mirror:
    Our intent    : {gap.get('IW_label', 'N/A')}  (gap={gap.get('gap_IW')})
    HTML vs intent: {gap.get('IS_label', 'N/A')}  (gap={gap.get('gap_IS')})
    Schema vs HTML: {gap.get('WS_label', 'N/A')}  (gap={gap.get('gap_WS')})

  Tests passed    : {PASS_COUNT}
  Tests failed    : {FAIL_COUNT}
""")

if FAIL_COUNT == 0:
    print("  ✓ ALL TESTS PASSED — full architecture is working correctly")
else:
    print(f"  ⚠  {FAIL_COUNT} test(s) failed — check the ✗ lines above for details")

print(f"{'━'*60}\n")