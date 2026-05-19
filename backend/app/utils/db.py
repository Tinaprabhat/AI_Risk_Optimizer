"""
utils/db.py  — PostgreSQL version
───────────────────────────────────
Same interface as the original SQLite version.
All function signatures are identical — nothing else in the codebase changes.

Tables:
  audits       — one row per completed audit, keyed by url_hash
  chat_history — per-check chatbot conversation history

Cache logic:
  load_audit() returns a result only if audited TODAY (UTC).
  Different day = re-run the full audit.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── CONNECTION ─────────────────────────────────────────────────────────────────

_DATABASE_URL = os.getenv("DATABASE_URL", "")


def _connect() -> psycopg2.extensions.connection:
    """
    Open a new PostgreSQL connection.
    Uses DATABASE_URL from environment.
    psycopg2 uses RealDictCursor so rows behave like dicts (same as sqlite3.Row).
    """
    if not _DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL not set. Add it to your .env file.\n"
            "Example: postgresql://postgres:password@localhost:5432/ai_rep_optimizer"
        )
    conn = psycopg2.connect(_DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


# ── INIT ──────────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create tables if they don't exist.
    Called once at FastAPI startup in main.py.
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audits (
                    url_hash    TEXT PRIMARY KEY,
                    url         TEXT NOT NULL,
                    label       TEXT,
                    audit_date  TEXT NOT NULL,
                    results_json JSONB NOT NULL
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id          SERIAL PRIMARY KEY,
                    url_hash    TEXT NOT NULL,
                    check_code  TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    message     TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_url_check
                    ON chat_history (url_hash, check_code);
            """)

        conn.commit()
        logger.info("PostgreSQL DB initialised")
    except Exception as e:
        logger.error(f"init_db failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


# ── HELPERS ───────────────────────────────────────────────────────────────────

def url_hash(url: str) -> str:
    """SHA-256 hash of the URL — used as primary key. First 16 hex chars."""
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]


# ── AUDIT CACHE ───────────────────────────────────────────────────────────────

def save_audit(url: str, label: str, results: dict) -> None:
    """
    Save a completed audit result to PostgreSQL.
    Uses INSERT ... ON CONFLICT DO UPDATE (upsert) — overwrites same URL.
    results dict is stored as JSONB.
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audits (url_hash, url, label, audit_date, results_json)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (url_hash) DO UPDATE SET
                    url          = EXCLUDED.url,
                    label        = EXCLUDED.label,
                    audit_date   = EXCLUDED.audit_date,
                    results_json = EXCLUDED.results_json
                """,
                (
                    url_hash(url),
                    url,
                    label,
                    datetime.utcnow().date().isoformat(),   # "2026-05-18"
                    json.dumps(results),
                )
            )
        conn.commit()
        logger.info(f"Audit saved for {url}")
    except Exception as e:
        logger.error(f"save_audit failed: {e}")
        conn.rollback()
    finally:
        conn.close()


def load_audit(url: str) -> Optional[dict]:
    """
    Load cached audit for a URL.

    Cache rule: only returns result if audit_date == today (UTC).
    If audited yesterday or earlier → returns None → forces re-audit.

    This is intentional: store data changes daily (prices, policies, robots.txt).
    A day-old audit is stale.
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT audit_date, results_json FROM audits WHERE url_hash = %s",
                (url_hash(url),)
            )
            row = cur.fetchone()

        if not row:
            return None

        audit_date = row["audit_date"]          # stored as "2026-05-18"
        today      = datetime.utcnow().date().isoformat()

        if audit_date != today:
            logger.info(f"Cache expired for {url} (audited {audit_date}, today is {today})")
            return None

        logger.info(f"CACHE HIT — returning cached result for {url}")
        print(f"  💾 CACHE HIT — {url}", flush=True)

        # results_json comes back as dict already (psycopg2 parses JSONB automatically)
        result = row["results_json"]
        if isinstance(result, str):
            result = json.loads(result)
        return result

    except Exception as e:
        logger.error(f"load_audit failed: {e}")
        return None
    finally:
        conn.close()


# ── CHAT HISTORY ──────────────────────────────────────────────────────────────

def save_chat_message(url: str, check_code: str, role: str, message: str) -> None:
    """
    Append one message to a fix chatbot conversation.
    role is either "user" or "bot".
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_history (url_hash, check_code, role, message, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    url_hash(url),
                    check_code,
                    role,
                    message,
                    datetime.utcnow().isoformat(),
                )
            )
        conn.commit()
    except Exception as e:
        logger.error(f"save_chat_message failed: {e}")
        conn.rollback()
    finally:
        conn.close()


def load_chat_history(url: str, check_code: str) -> list[dict]:
    """
    Load all messages for a specific check's chatbot conversation.
    Returns list of {"role": "user"|"bot", "message": str} in order.
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, message
                FROM chat_history
                WHERE url_hash = %s AND check_code = %s
                ORDER BY id ASC
                """,
                (url_hash(url), check_code)
            )
            rows = cur.fetchall()
        return [{"role": r["role"], "message": r["message"]} for r in rows]
    except Exception as e:
        logger.error(f"load_chat_history failed: {e}")
        return []
    finally:
        conn.close()


def clear_chat_history(url: str, check_code: str) -> None:
    """
    Delete all chat messages for a check.
    Called when merchant starts a fresh fix conversation.
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_history WHERE url_hash = %s AND check_code = %s",
                (url_hash(url), check_code)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"clear_chat_history failed: {e}")
        conn.rollback()
    finally:
        conn.close()