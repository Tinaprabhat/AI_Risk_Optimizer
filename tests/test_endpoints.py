"""
test_endpoints.py
─────────────────
Checks every API endpoint is live and returning correct responses.
Run AFTER starting uvicorn in another terminal.
"""

import time
import requests

BASE = "http://localhost:8000/api"
PASS_COUNT = 0
FAIL_COUNT = 0

def ok(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  ✓  {msg}")

def fail(msg, detail=""):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  ✗  {msg}")
    if detail:
        print(f"     {detail}")

def section(title):
    print(f"\n{'━'*55}")
    print(f"  {title}")
    print(f"{'━'*55}")

# ── 1. HEALTH ─────────────────────────────────────────────────────
section("1. GET /api/health")
try:
    r = requests.get(f"{BASE}/health", timeout=5)
    if r.status_code == 200 and r.json().get("status") == "ok":
        ok(f"Health check passed — {r.json()}")
    else:
        fail("Health returned unexpected response", str(r.json()))
except Exception as e:
    fail("Could not reach server", str(e))
    print("\n  ⚠  Is uvicorn running? Start it with:")
    print("     uvicorn main:app --reload --port 8000")
    exit(1)

# ── 2. AUDIT START ────────────────────────────────────────────────
section("2. POST /api/audit/start")
try:
    r = requests.post(f"{BASE}/audit/start", json={
        "store_url": "https://colourpop.com/",
        "free_text": "Beauty and cosmetics store",
        "mcq": {
            "category": "beauty and cosmetics",
            "customer": "young makeup enthusiasts",
            "differentiator": "affordable trendy cosmetics",
            "tone": "playful and vibrant",
        },
        "use_cache": True,
    }, timeout=10)

    if r.status_code == 200:
        data = r.json()
        job_id = data.get("job_id")
        status = data.get("status")
        if job_id and status == "running":
            ok(f"Audit started — job_id: {job_id}")
            ok(f"Status returned immediately: {status}")
        else:
            fail("Missing job_id or wrong status", str(data))
            job_id = None
    else:
        fail(f"HTTP {r.status_code}", r.text[:200])
        job_id = None
except Exception as e:
    fail("audit/start failed", str(e))
    job_id = None

# ── 3. AUDIT STATUS POLLING ───────────────────────────────────────
section("3. GET /api/audit/status/{job_id}")

if job_id:
    # Poll a few times to see it transition
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/audit/status/{job_id}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status")
                progress = data.get("progress", "")
                ok(f"Poll {attempt+1}: status={status}  progress='{progress}'")
                if status == "done":
                    score = data.get("result", {}).get("score", {})
                    ok(f"Result received — score: {score.get('grand_total')}/{score.get('max_total')} ({score.get('pct')}%)")
                    break
                elif status == "error":
                    fail(f"Audit errored: {data.get('error')}")
                    break
            else:
                fail(f"HTTP {r.status_code}", r.text[:100])
        except Exception as e:
            fail(f"Poll {attempt+1} failed", str(e))
        time.sleep(3)

    # Test invalid job_id
    r = requests.get(f"{BASE}/audit/status/invalid-job-id-xyz", timeout=5)
    if r.status_code == 404:
        ok("Invalid job_id correctly returns 404")
    else:
        fail(f"Expected 404 for invalid job_id, got {r.status_code}")
else:
    print("  Skipped — no job_id from previous step")

# ── 4. FIX TEMPLATE ───────────────────────────────────────────────
section("4. GET /api/fix/template/{check_code}")

for code in ["R1", "R7", "R16", "R31"]:
    try:
        r = requests.get(f"{BASE}/fix/template/{code}", timeout=5)
        if r.status_code == 200:
            data = r.json()
            title = data.get("title", "")
            steps = data.get("steps", [])
            ok(f"{code}: '{title}' — {len(steps)} steps")
        else:
            fail(f"{code}: HTTP {r.status_code}", r.text[:100])
    except Exception as e:
        fail(f"{code} template failed", str(e))

# Invalid code
r = requests.get(f"{BASE}/fix/template/R999", timeout=5)
if r.status_code == 404:
    ok("Invalid check_code correctly returns 404")
else:
    fail(f"Expected 404 for R999, got {r.status_code}")

# ── 5. CHAT START ─────────────────────────────────────────────────
section("5. POST /api/chat/start")
try:
    r = requests.post(f"{BASE}/chat/start", json={
        "store_url": "https://colourpop.com/",
        "check_code": "R1",
        "check_detail": "GPTBot and ClaudeBot are blocked in robots.txt",
    }, timeout=10)

    if r.status_code == 200:
        data = r.json()
        msg  = data.get("message", "")
        code = data.get("check_code", "")
        if msg and code == "R1":
            ok(f"Chat started for {code}")
            ok(f"Opening message ({len(msg)} chars): {msg[:80]}...")
        else:
            fail("Missing message or check_code in response", str(data))
    else:
        fail(f"HTTP {r.status_code}", r.text[:200])
except Exception as e:
    fail("chat/start failed", str(e))

# ── 6. CHAT REPLY ─────────────────────────────────────────────────
section("6. POST /api/chat/reply")
try:
    r = requests.post(f"{BASE}/chat/reply", json={
        "store_url": "https://colourpop.com/",
        "check_code": "R1",
        "check_detail": "GPTBot and ClaudeBot are blocked in robots.txt",
        "check_fix": "Remove Disallow rules for AI crawlers",
        "user_message": "I opened my robots.txt file. What should I look for?",
    }, timeout=15)

    if r.status_code == 200:
        data    = r.json()
        message = data.get("message", "")
        source  = data.get("source", "")
        if message:
            ok(f"Reply received via {source}")
            ok(f"Reply ({len(message)} chars): {message[:100]}...")
        else:
            fail("Empty reply message", str(data))
    else:
        fail(f"HTTP {r.status_code}", r.text[:200])
except Exception as e:
    fail("chat/reply failed", str(e))

# ── 7. CHAT HISTORY ───────────────────────────────────────────────
section("7. GET /api/chat/history")
try:
    r = requests.get(
        f"{BASE}/chat/history",
        params={"store_url": "https://colourpop.com/", "check_code": "R1"},
        timeout=5,
    )
    if r.status_code == 200:
        history = r.json()
        if isinstance(history, list) and len(history) >= 2:
            ok(f"History returned — {len(history)} messages")
            for msg in history[:3]:
                ok(f"  [{msg['role']}]: {msg['message'][:60]}...")
        else:
            fail("History empty or wrong format", str(history)[:100])
    else:
        fail(f"HTTP {r.status_code}", r.text[:100])
except Exception as e:
    fail("chat/history failed", str(e))

# ── 8. CACHE CLEAR ────────────────────────────────────────────────
section("8. DELETE /api/audit/cache")
try:
    r = requests.delete(
        f"{BASE}/audit/cache",
        params={"store_url": "https://colourpop.com/"},
        timeout=5,
    )
    if r.status_code == 200:
        data = r.json()
        ok(f"Cache cleared: {data.get('message')}")
    else:
        fail(f"HTTP {r.status_code}", r.text[:100])
except Exception as e:
    fail("cache delete failed", str(e))

# ── SUMMARY ───────────────────────────────────────────────────────
print(f"\n{'━'*55}")
print(f"  ENDPOINT TEST SUMMARY")
print(f"{'━'*55}")
print(f"  Passed : {PASS_COUNT}")
print(f"  Failed : {FAIL_COUNT}")
print()
if FAIL_COUNT == 0:
    print("  ✓ All endpoints working — backend ready for frontend")
else:
    print("  ✗ Fix the failing endpoints before starting frontend")
print(f"{'━'*55}\n")