"""
layer7/aggregator.py
─────────────────────
Layer 7 — Aggregation & Output Engine

Takes all L1–L6 outputs. Produces:
  1. Semantic gap display (from L6 — no LLM)
  2. Scored checklist (all 16 checks — deterministic)
  3. Total score X/79
  4. Conclusion paragraph (1 Gemini call, Ollama fallback, then rule-based)
"""

import json
import logging
from typing import Optional

from src.utils.llm import call_llm

logger = logging.getLogger(__name__)

# ── SCORING CONSTANTS ─────────────────────────────────────────────────────────

# Max score per check
SCORE_MAX = {
    # Scored checks (0–10)
    "R7":  10, "R9":  10, "R13": 10,
    "R16": 10, "R17": 10, "R30": 10, "R31": 10,
    # Binary checks (0/1)
    "R1": 1, "R3": 1, "R5": 1, "R6": 1,
    "R11": 1, "R15": 1, "R23": 1, "R25": 1, "R28": 1,
}

MAX_SCORED    = 70   # sum of 7 scored checks × 10
MAX_CHECKLIST = 9    # sum of 9 binary checks × 1
MAX_TOTAL     = 79


def compute_score(all_checks: dict) -> dict:
    """
    Compute scores from all 16 check results.

    UNKNOWN / ERROR → 0 (conservative)
    FORWARD-LOOKING / NOT-APPLICABLE → 0 (don't penalise for things outside control,
                                          but keep denominator at 79)

    Args:
        all_checks: dict mapping check_code → result dict

    Returns:
        dict with scored_total, checklist_total, grand_total, max_*, pct, breakdown
    """
    scored_total    = 0
    checklist_total = 0
    breakdown       = {}

    SCORED_CHECKS    = {"R7", "R9", "R13", "R16", "R17", "R30", "R31"}
    CHECKLIST_CHECKS = {"R1", "R3", "R5", "R6", "R11", "R15", "R23", "R25", "R28"}

    for code, res in all_checks.items():
        raw_score = res.get("score", 0)
        status    = res.get("status", "UNKNOWN")

        # WARN on scored check → keep partial score
        # UNKNOWN/ERROR/FORWARD-LOOKING → 0
        if status in ("UNKNOWN", "ERROR", "FORWARD-LOOKING", "NOT-APPLICABLE"):
            raw_score = 0

        breakdown[code] = {
            "score":   raw_score,
            "max":     SCORE_MAX.get(code, 0),
            "status":  status,
            "detail":  res.get("detail", ""),
            "is_scored": code in SCORED_CHECKS,
        }

        if code in SCORED_CHECKS:
            scored_total    += raw_score
        elif code in CHECKLIST_CHECKS:
            checklist_total += raw_score

    grand_total = scored_total + checklist_total
    pct         = round((grand_total / MAX_TOTAL) * 100, 1)

    return {
        "scored_total":    scored_total,
        "checklist_total": checklist_total,
        "grand_total":     grand_total,
        "max_scored":      MAX_SCORED,
        "max_checklist":   MAX_CHECKLIST,
        "max_total":       MAX_TOTAL,
        "pct":             pct,
        "breakdown":       breakdown,
    }


def get_failed_checks(all_checks: dict) -> list[dict]:
    """
    Return list of failed/warn checks sorted by severity.
    Used to build the fix list in Part 2.
    """
    failed = []
    for code, res in all_checks.items():
        if res.get("status") in ("FAIL", "WARN"):
            failed.append({
                "code":   code,
                "status": res["status"],
                "detail": res.get("detail", ""),
                "fix":    res.get("fix", ""),
                "tier":   res.get("tier", ""),
            })
    # Sort: FAIL before WARN, then by check code
    failed.sort(key=lambda x: (0 if x["status"] == "FAIL" else 1, x["code"]))
    return failed


def build_conclusion(
    all_checks: dict,
    score_info: dict,
    gap_summary: str,
    merchant_intent: str,
    gap_result: dict = None,
) -> tuple[str, str]:
    """
    Generate the conclusion paragraph via LLM (Gemini → Ollama → fallback).

    Returns:
        (conclusion_text, source) where source is 'gemini'|'ollama_mistral'|'fallback'
    """
    failed = get_failed_checks(all_checks)
    top_issues = [f"{f['code']}: {f['detail']}" for f in failed[:5]]

    system_prompt = (
        "You are an expert AI commerce auditor. "
        "Write a 3–4 sentence conclusion paragraph for a merchant about their store's AI visibility. "
        "Be specific, honest, and plain English. No jargon. No generic advice. "
        "Name the exact checks that failed. Tell them the impact. "
        "End with the single most important fix."
    )

    user_prompt = (
        f"Merchant described their store as: {merchant_intent}\n\n"
        f"Score: {score_info['grand_total']}/{score_info['max_total']} ({score_info['pct']}%)\n\n"
        f"Top issues:\n" + "\n".join(f"- {i}" for i in top_issues) + "\n\n"
        f"Semantic gap:\n{gap_summary[:500]}\n\n"
        "Write the conclusion paragraph now."
    )

    # Hardcoded fallback if both LLMs fail
    fallback = _rule_based_conclusion(score_info, failed, gap_result)

    return call_llm(user_prompt, system=system_prompt, fallback_text=fallback)


def _rule_based_conclusion(score_info: dict, failed: list, gap_result: dict = None) -> str:
    """
    Deterministic fallback conclusion when both Gemini and Ollama are unavailable.
    Built from structured layer data — no hallucination possible.
    """
    pct    = score_info["pct"]
    total  = score_info["grand_total"]
    max_t  = score_info["max_total"]
    n_fail = len(failed)

    parts = [f"Your store scored {total}/{max_t} ({pct}%) on AI readiness checks."]

    # Semantic gap insight (only present when gap_result is passed in)
    if gap_result:
        iw_label = gap_result.get("IW_label", "")
        is_label = gap_result.get("IS_label", "")
        iw_gap   = gap_result.get("gap_IW")
        if iw_label == "MISALIGNED":
            parts.append(
                f"AI reads your website very differently from how you describe your store "
                f"(semantic gap: {iw_gap}) — your brand positioning is not coming through in your page content."
            )
        elif iw_label == "DRIFT":
            parts.append(
                f"There is a noticeable gap between how you describe your store and what AI reads from your website "
                f"(gap: {iw_gap}) — some of your positioning is unclear to AI shopping agents."
            )
        if is_label == "NO-SCHEMA-TEXT":
            parts.append(
                "No schema markup descriptions were found — AI agents have no structured data "
                "to identify your brand or product category."
            )
        elif is_label in ("DRIFT", "MISALIGNED"):
            parts.append("Your schema markup does not accurately reflect your brand intent.")

    if n_fail == 0:
        parts.append(
            "No critical technical issues were found. "
            "AI crawlers can reach, read, and understand your store. "
            "Focus on deepening product specificity and building schema-exposed reviews over time."
        )
    else:
        top = failed[0]
        parts.append(
            f"{n_fail} issue(s) are reducing your AI visibility. "
            f"Most critical: {top['code']} — {top['detail']} "
            f"Start here: {top['fix'][:150] if top['fix'] else 'See fix details below.'}"
        )

    return " ".join(parts)
