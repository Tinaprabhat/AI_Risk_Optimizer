"""
utils/obs_logger.py  — NEW in v2
──────────────────────────────────────────────────────────────────────────────
Observability logger. After every audit, writes a structured JSON log to disk.

Spec (Section 3.1):
  For every check we record:
    - What happened    : raw HTTP response, exact file content fetched
    - Why it happened  : exact directive/line that caused the outcome
    - What AI concluded: impact statement from AI crawler perspective
    - Reproducibility  : same fetch, same result, logged with timestamp
    - Causality trace  : "GPTBot blocked BECAUSE line 4 says Disallow: /"

Log structure:
  logs/
    audit_<domain>_<timestamp>.json   ← one file per audit

Log file contains:
  {
    "meta": { store_url, timestamp, score, verdict },
    "checks": {
      "R1": {
        "check_id":     "R1",
        "tier":         "VERIFIED",
        "status":       "FAIL",
        "score":        0,
        "raw_evidence": "exact fetched content",
        "what_we_did":  "human-readable trace",
        "what_AI_sees": "impact from AI crawler POV",
        "causality":    "GPTBot BLOCKED BECAUSE ...",
        "severity":     "CRITICAL",
        "fix":          "exact actionable instruction",
        "timestamp":    "2026-05-15T14:32:11Z"
      },
      ...
    },
    "gap": { gap_IW, gap_IS, gap_WS, labels, observability per gap },
    "conclusion": "...",
    "raw_page_texts": { homepage, about, policies } (first 500 chars each)
  }
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def _domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    # Sanitize for filename
    return re.sub(r"[^\w\-.]", "_", domain)


def _build_causality(check_code: str, obs: dict) -> str:
    """
    Build a causality sentence from observability data.
    Example: "GPTBot BLOCKED BECAUSE robots.txt line 4 says Disallow: /"
    """
    status = obs.get("status", "UNKNOWN")
    what   = obs.get("what_we_did", "")
    ai     = obs.get("what_AI_sees", "")

    if status == "PASS":
        return f"{check_code} PASSED — {ai}"
    elif status == "FAIL":
        return f"{check_code} FAILED — {ai} | How: {what}"
    elif status == "WARN":
        return f"{check_code} WARNING — {ai}"
    else:
        return f"{check_code} {status} — {ai or what}"


def write_audit_log(
    store_url:    str,
    all_checks:   dict,
    score_info:   dict,
    gap_result:   dict,
    conclusion:   str,
    page_texts:   dict = None,
    merchant_intent: str = "",
    mcq:          dict = None,
) -> str:
    """
    Write a full observability log for one audit to disk.

    Returns:
        Path to the written log file.
    """
    _ensure_log_dir()

    ts      = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    domain  = _domain(store_url)
    fname   = f"audit_{domain}_{ts}.json"
    fpath   = os.path.join(LOG_DIR, fname)

    # Build per-check log entries
    check_logs = {}
    for code, res in all_checks.items():
        obs = res.get("observability", {})
        check_logs[code] = {
            "check_id":     code,
            "tier":         res.get("tier", ""),
            "status":       res.get("status", "UNKNOWN"),
            "score":        res.get("score", 0),
            "detail":       res.get("detail", ""),
            # Core observability fields from spec
            "raw_evidence": obs.get("raw_evidence", res.get("evidence", "(not recorded)")),
            "what_we_did":  obs.get("what_we_did",  "(not recorded)"),
            "what_AI_sees": obs.get("what_AI_sees", "(not recorded)"),
            "causality":    _build_causality(code, obs),
            "severity":     obs.get("severity", "INFO"),
            "fix":          res.get("fix", ""),
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        }

    # Build gap log
    gap_log = {}
    if gap_result:
        gap_obs = gap_result.get("observability", {})
        gap_log = {
            "gap_IW":       gap_result.get("gap_IW"),
            "gap_IS":       gap_result.get("gap_IS"),
            "gap_WS":       gap_result.get("gap_WS"),
            "IW_label":     gap_result.get("IW_label"),
            "IS_label":     gap_result.get("IS_label"),
            "WS_label":     gap_result.get("WS_label"),
            "schema_source": gap_result.get("schema_source", ""),
            "intent_text":  gap_result.get("intent_text", "")[:500],
            "website_text": gap_result.get("website_text", "")[:500],
            "schema_text":  gap_result.get("schema_text", "")[:500],
            "per_gap_traces": {
                gap_name: {
                    "gap":         g.get("gap"),
                    "label":       g.get("label"),
                    "question":    g.get("question"),
                    "source_A":    g.get("source_A"),
                    "source_B":    g.get("source_B"),
                    "preview_A":   g.get("preview_A", "")[:300],
                    "preview_B":   g.get("preview_B", "")[:300],
                    "interpretation": g.get("interpretation"),
                }
                for gap_name, g in gap_obs.items()
            },
        }

    # Truncate page texts for log (first 500 chars only)
    page_log = {}
    if page_texts:
        for k, v in page_texts.items():
            page_log[k] = v[:500] if v else ""

    log_data = {
        "meta": {
            "store_url":       store_url,
            "domain":          domain,
            "audit_timestamp": ts,
            "merchant_intent": merchant_intent,
            "mcq":             mcq or {},
            "score":           score_info,
        },
        "checks":         check_logs,
        "gap":            gap_log,
        "conclusion":     conclusion,
        "raw_page_texts": page_log,
    }

    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Observability log written: {fpath}")
    except Exception as e:
        logger.error(f"Failed to write observability log: {e}")
        return ""

    return fpath