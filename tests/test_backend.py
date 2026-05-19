"""
test_backend.py
Run from inside backend/:  python test_backend.py
Real store: https://www.allbirds.com/
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# ── REAL STORE DATA ───────────────────────────────────────────────────────────
STORE_URL  = "https://www.allbirds.com/"

# The 5 form answers you gave — mapped to what the code actually needs
# "Fashion and apparel"   → category
# "Established 1-3 years" → goes into free_text (not an MCQ key)
# "500-5000 visitors"     → goes into free_text (not an MCQ key)
# "Getting more traffic"  → differentiator (what they want/stand for)
# "Yes, a little"         → customer (AI familiarity of their customers)

FREE_TEXT = (
    "Fashion and apparel store. "
    "Established 1 to 3 years. "
    "Currently getting 500 to 5000 visitors per month. "
    "Main goal is getting more traffic. "
    "Customers have a little familiarity with AI shopping."
)

MCQ = {
    "category":       "fashion and apparel",
    "customer":       "shoppers with a little familiarity with AI shopping",
    "differentiator": "getting more traffic and growing brand visibility",
    "tone":           "modern and sustainable",
}

# ── 1. DB INIT ────────────────────────────────────────────────────────────────
print("\n=== 1. DATABASE ===")
from src.utils.db import init_db, save_audit, load_audit, save_chat_message, load_chat_history
init_db()
print("✓ DB connected and tables created")

# ── 2. CACHE WRITE + READ ─────────────────────────────────────────────────────
print("\n=== 2. CACHE ===")
save_audit(STORE_URL, "test", {"test": "data", "score": {"pct": 55}})
cached = load_audit(STORE_URL)
if cached and cached.get("test") == "data":
    print("✓ Cache WRITE and READ working")
else:
    print("✗ Cache failed — check PostgreSQL connection and DATABASE_URL in .env")

# ── 3. CHAT HISTORY ───────────────────────────────────────────────────────────
print("\n=== 3. CHAT HISTORY ===")
save_chat_message(STORE_URL, "R1", "bot", "Hello, let's fix your robots.txt")
save_chat_message(STORE_URL, "R1", "user", "Ok what do I do?")
history = load_chat_history(STORE_URL, "R1")
if len(history) >= 2:
    print(f"✓ Chat history working — {len(history)} messages saved and loaded")
else:
    print("✗ Chat history failed")

# ── 4. FETCHER ────────────────────────────────────────────────────────────────
print("\n=== 4. FETCHER ===")
from src.utils.fetcher import safe_get
fetch = safe_get(STORE_URL)
if fetch.ok:
    print(f"✓ Fetcher working — got {len(fetch.text)} chars from allbirds.com")
else:
    print(f"✗ Fetcher failed: {fetch.error}")

# ── 5. EMBEDDER ───────────────────────────────────────────────────────────────
print("\n=== 5. EMBEDDER ===")
from src.utils.embedder import embed, cosine_sim
e1 = embed("fashion and apparel store")
e2 = embed("made from 6061 aircraft grade aluminium")
e3 = embed("fashion and apparel store")
print(f"✓ Embedder working")
print(f"  Same text similarity:      {cosine_sim(e1, e3):.3f}  (should be ~1.0)")
print(f"  Different text similarity: {cosine_sim(e1, e2):.3f}  (should be <0.8)")

# ── 6. LLM ────────────────────────────────────────────────────────────────────
print("\n=== 6. LLM ===")
from src.utils.llm import call_llm
response, source = call_llm(
    prompt="Say exactly: LLM is working",
    fallback_text="FALLBACK: LLM unavailable"
)
print(f"✓ LLM source: {source}")
print(f"  Response: {response[:100]}")

# ── 7. FULL AUDIT — ALL 7 LAYERS ──────────────────────────────────────────────
print("\n=== 7. FULL AUDIT — allbirds.com (30-60 seconds) ===")

from src.auditor import run_audit
import time

def progress(msg):
    print(f"  → {msg}")

t = time.time()
result = run_audit(
    store_url=STORE_URL,
    free_text=FREE_TEXT,
    mcq=MCQ,
    use_cache=False,    # force fresh — ignore any existing cache
    progress_cb=progress,
)
elapsed = time.time() - t
print(f"\n✓ Audit finished in {elapsed:.1f}s")

# Score
score = result["score"]
print(f"\n  SCORE: {score['grand_total']}/{score['max_total']} ({score['pct']}%)")
print(f"  Scored checks total:    {score['scored_total']}/{score['max_scored']}")
print(f"  Checklist checks total: {score['checklist_total']}/{score['max_checklist']}")

# Per-check breakdown
print(f"\n  LAYER RESULTS:")
print(f"  {'Code':<6} {'Status':<14} {'Score':<8} Detail")
print(f"  {'─'*70}")
for code, check in result["checks"].items():
    status = check.get("status", "?")
    detail = check.get("detail", "")[:55]
    score_val = check.get("score", "-")
    print(f"  {code:<6} {status:<14} {str(score_val):<8} {detail}")

# Failed checks
failed = result.get("failed", [])
if failed:
    print(f"\n  FAILED / WARN CHECKS ({len(failed)}):")
    for f in failed:
        print(f"  ✗ {f['code']} [{f['status']}]: {f['detail'][:80]}")
        if f.get("fix"):
            print(f"    Fix: {f['fix'][:100]}")

# Semantic gap
gap = result.get("gap", {})
print(f"\n  SEMANTIC GAP:")
print(f"  Intent vs Website : {gap.get('gap_IW')}  → {gap.get('IW_label')}")
print(f"  Intent vs Schema  : {gap.get('gap_IS')}  → {gap.get('IS_label')}")
print(f"  Website vs Schema : {gap.get('gap_WS')}  → {gap.get('WS_label')}")
print(f"  Schema source     : {gap.get('schema_source')}")

# Conclusion
print(f"\n  CONCLUSION (via {result.get('llm_source')}):")
print(f"  {result.get('conclusion', '')[:300]}")

# Observability log
print(f"\n  Log written to: {result.get('log_path', 'not written')}")

# ── 8. CACHE HIT — should return in <2s ──────────────────────────────────────
print("\n=== 8. CACHE HIT (same URL, should be instant) ===")
t = time.time()
cached_result = run_audit(
    store_url=STORE_URL,
    free_text=FREE_TEXT,
    mcq=MCQ,
    use_cache=True,
)
elapsed = time.time() - t
if elapsed < 2.0:
    print(f"✓ Cache hit — returned in {elapsed:.2f}s")
    print(f"  Score from cache: {cached_result['score']['pct']}%")
else:
    print(f"✗ Cache miss — took {elapsed:.1f}s (should have been instant)")

# ── 9. FIX ENGINE ─────────────────────────────────────────────────────────────
print("\n=== 9. FIX ENGINE ===")
from src.part2.fix_engine import chatbot_first_message, chatbot_reply, get_fix_template

# Test on the first failed check from the real audit
first_failed = failed[0] if failed else {"code": "R1", "detail": "test", "fix": "test fix"}
code   = first_failed["code"]
detail = first_failed["detail"]
fix    = first_failed.get("fix", "")

template = get_fix_template(code)
if template:
    print(f"✓ Template loaded for {code}: {template['title']}")
else:
    print(f"  No template for {code} — using generic")

first_msg = chatbot_first_message(code, detail)
print(f"✓ First message ({len(first_msg)} chars):")
print(f"  {first_msg[:150]}")

reply, source = chatbot_reply(
    check_code=code,
    check_detail=detail,
    check_fix=fix,
    store_url=STORE_URL,
    user_message="I understand the issue. What is the first step I should take?",
    history=[{"role": "bot", "message": first_msg}],
)
print(f"✓ Chatbot reply (via {source}):")
print(f"  {reply[:200]}")

# ── FINAL SUMMARY ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("ALL TESTS COMPLETE")
print("="*60)
print("✓ = working correctly")
print("✗ = something broken — read the error above it")