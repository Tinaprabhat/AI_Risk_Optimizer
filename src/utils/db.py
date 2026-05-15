"""
utils/db.py
───────────
SQLite database — WAL mode enabled for concurrent reads.

Tables:
  audits      — one row per completed audit, keyed by URL hash
  chat_history — per-check chatbot conversation history

Write strategy: single write at end of full audit — not per check.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import sqlite3
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# DB file lives in the db/ directory at repo root
_DB_PATH = Path(__file__).parent.parent.parent / "db" / "audits.db"


def _connect() -> sqlite3.Connection:
    """Open connection with WAL mode and row factory."""
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # concurrent reads without blocking
    conn.execute("PRAGMA synchronous=NORMAL") # safe + faster than FULL
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Call once at app startup."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audits (
            url_hash    TEXT PRIMARY KEY,
            url         TEXT NOT NULL,
            label       TEXT,
            audit_date  TEXT NOT NULL,
            results_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash    TEXT NOT NULL,
            check_code  TEXT NOT NULL,
            role        TEXT NOT NULL,
            message     TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chat_url_check
            ON chat_history (url_hash, check_code);
    """)
    conn.commit()
    conn.close()
    logger.info("DB initialised")


def url_hash(url: str) -> str:
    """SHA-256 hash of the URL — used as primary key."""
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]


def save_audit(url: str, label: str, results: dict) -> None:
    """Save a completed audit result. Overwrites if same URL."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO audits
               (url_hash, url, label, audit_date, results_json)
               VALUES (?, ?, ?, ?, ?)""",
            (url_hash(url), url, label, datetime.utcnow().isoformat(), json.dumps(results))
        )
        conn.commit()
        logger.info(f"Audit saved for {url}")
    except Exception as e:
        logger.error(f"Failed to save audit: {e}")
    finally:
        conn.close()


def load_audit(url: str) -> Optional[dict]:
    """
    Load cached audit for a URL.
    Returns dict if found today, None otherwise (forces re-audit).
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM audits WHERE url_hash = ?",
            (url_hash(url),)
        ).fetchone()
        if not row:
            return None
        # Only use cache if audited today
        audit_date = row["audit_date"][:10]
        today      = datetime.utcnow().date().isoformat()
        if audit_date != today:
            logger.info(f"Cache expired for {url} (audited {audit_date})")
            return None
        return json.loads(row["results_json"])
    except Exception as e:
        logger.error(f"Failed to load audit: {e}")
        return None
    finally:
        conn.close()


def save_chat_message(url: str, check_code: str, role: str, message: str) -> None:
    """Append one message to a fix chatbot conversation."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO chat_history
               (url_hash, check_code, role, message, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (url_hash(url), check_code, role, message, datetime.utcnow().isoformat())
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to save chat message: {e}")
    finally:
        conn.close()


def load_chat_history(url: str, check_code: str) -> list[dict]:
    """Load all messages for a specific check's chatbot conversation."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT role, message FROM chat_history
               WHERE url_hash = ? AND check_code = ?
               ORDER BY id ASC""",
            (url_hash(url), check_code)
        ).fetchall()
        return [{"role": r["role"], "message": r["message"]} for r in rows]
    except Exception as e:
        logger.error(f"Failed to load chat history: {e}")
        return []
    finally:
        conn.close()


def clear_chat_history(url: str, check_code: str) -> None:
    """Clear chatbot history for a specific check (allows restarting fix conversation)."""
    conn = _connect()
    try:
        conn.execute(
            "DELETE FROM chat_history WHERE url_hash = ? AND check_code = ?",
            (url_hash(url), check_code)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to clear chat history: {e}")
    finally:
        conn.close()
