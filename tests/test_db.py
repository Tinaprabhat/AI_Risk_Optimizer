"""
test_db.py
──────────
Verify the SQLite database layer: init, audit save/load, chat history.
Run from project root: python tests/test_db.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.utils.db import (
    init_db,
    save_audit,
    load_audit,
    save_chat_message,
    load_chat_history,
    clear_chat_history,
    _connect,
    url_hash,
)

TEST_URL  = "https://test-store.example.com/"
TEST_CODE = "R1"

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    PASS += 1
    print(f"  ✓  {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  ✗  {msg}")


# ── 1. INIT ───────────────────────────────────────────────────────────────────
print("\n=== 1. DB INIT ===")
try:
    init_db()
    ok("init_db() ran without error")
except Exception as e:
    fail(f"init_db() raised: {e}")
    sys.exit(1)

# Tables must exist
try:
    conn = _connect()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    conn.close()
    if "audits" in tables:
        ok("Table 'audits' exists")
    else:
        fail("Table 'audits' missing")
    if "chat_history" in tables:
        ok("Table 'chat_history' exists")
    else:
        fail("Table 'chat_history' missing")
except Exception as e:
    fail(f"Table check failed: {e}")


# ── 2. AUDIT SAVE / LOAD ─────────────────────────────────────────────────────
print("\n=== 2. AUDIT SAVE / LOAD ===")
payload = {"score": {"pct": 72, "grand_total": 50}, "checks": {}, "conclusion": "Test conclusion."}

try:
    save_audit(TEST_URL, "today", payload)
    ok("save_audit() completed without error")
except Exception as e:
    fail(f"save_audit() raised: {e}")

try:
    loaded = load_audit(TEST_URL)
    if loaded is None:
        fail("load_audit() returned None — row not saved")
    elif loaded.get("score", {}).get("pct") == 72:
        ok("load_audit() returned correct payload")
    else:
        fail(f"load_audit() returned unexpected data: {loaded}")
except Exception as e:
    fail(f"load_audit() raised: {e}")


# ── 3. CHAT HISTORY ───────────────────────────────────────────────────────────
print("\n=== 3. CHAT HISTORY ===")
try:
    clear_chat_history(TEST_URL, TEST_CODE)
    ok("clear_chat_history() ran without error")
except Exception as e:
    fail(f"clear_chat_history() raised: {e}")

try:
    save_chat_message(TEST_URL, TEST_CODE, "bot",  "Hello, let's fix your robots.txt")
    save_chat_message(TEST_URL, TEST_CODE, "user", "Ok, what should I do?")
    save_chat_message(TEST_URL, TEST_CODE, "bot",  "Open the file and add Disallow: /admin")
    ok("3 messages saved without error")
except Exception as e:
    fail(f"save_chat_message() raised: {e}")

try:
    history = load_chat_history(TEST_URL, TEST_CODE)
    if len(history) == 3:
        ok(f"load_chat_history() returned {len(history)} messages")
    else:
        fail(f"Expected 3 messages, got {len(history)}")
    if history[0]["role"] == "bot" and "robots" in history[0]["message"]:
        ok("Message content and order correct")
    else:
        fail(f"Unexpected first message: {history[0]}")
except Exception as e:
    fail(f"load_chat_history() raised: {e}")


# ── 4. URL HASH STABILITY ─────────────────────────────────────────────────────
print("\n=== 4. URL HASH STABILITY ===")
h1 = url_hash(TEST_URL)
h2 = url_hash(TEST_URL)
h3 = url_hash("https://different-store.com/")

if h1 == h2:
    ok(f"url_hash is deterministic: {h1[:16]}...")
else:
    fail("url_hash returns different values for same URL")

if h1 != h3:
    ok("url_hash differs for different URLs")
else:
    fail("url_hash collision between different URLs")


# ── 5. CACHE OVERWRITE ────────────────────────────────────────────────────────
print("\n=== 5. CACHE OVERWRITE ===")
updated_payload = {"score": {"pct": 88, "grand_total": 61}, "checks": {}, "conclusion": "Updated."}
try:
    save_audit(TEST_URL, "today", updated_payload)
    loaded2 = load_audit(TEST_URL)
    if loaded2 and loaded2.get("score", {}).get("pct") == 88:
        ok("Second save_audit() overwrites previous result correctly")
    else:
        fail(f"Overwrite did not work, got: {loaded2}")
except Exception as e:
    fail(f"Cache overwrite test raised: {e}")


# ── SUMMARY ───────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  Tests passed: {PASS}  |  Tests failed: {FAIL}")
if FAIL == 0:
    print("  ✓ SQLite database layer is working correctly")
else:
    print(f"  ✗ {FAIL} test(s) failed — check errors above")
print(f"{'='*50}\n")
