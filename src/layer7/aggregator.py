"""
layer7/aggregator.py  — v2
──────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1:
  SCORING — R30 removed from scored/checklist. It is INFORMATIONAL only.
             New max: scored=60 (6 checks), checklist=9, total=69
             Validation-aligned: matches validate.py v2.1 scoring.

  R25 WARN — now scores 0.5 (partial) not 0.

  OBSERVABILITY — build_conclusion now returns full observability block
                  with per-layer trace summary alongside the conclusion text.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging

from src.utils.llm import call_llm

logger = logging.getLogger(__name__)

# ── SCORING — v2 ─────────────────────────────────────────────────────────────
# R30 removed from scoring. R25 WARN = 0.5 partial credit.

SCORE_MAX = {
    # Scored 0–10
    "R7": 10, "R9": 10, "R13": 10,
    "R16": 10, "R17": 10, "R31": 10,
    # Binary 0/1
    "R1": 1, "R3": 1, "R5": 1, "R6": 1,
    "R11": 1, "R15": 1, "R23": 1, "R25": 1, "R28": 1,
    # R30 intentionally absent — INFORMATIONAL, not scored
}

SCORED_CHECKS    = {"R7", "R9", "R13", "R16", "R17", "R31"}
CHECKLIST_CHECKS = {"R1", "R3", "R5", "R6", "R11", "R15", "R23", "R25", "R28"}

MAX_SCORED    = 60   # 6 checks × 10  (was 70 — R30 removed)
MAX_CHECKLIST = 9    # unchanged
MAX_TOTAL     = 69   # was 79


def compute_score(all_checks: dict) -> dict:
    """
    Compute scores from all check results.

    R30 is explicitly skipped (INFORMATIONAL).
    R25 WARN = 0.5 partial score.
    UNKNOWN / ERROR / FORWARD-LOOKING / NOT-APPLICABLE → 0.
    """
    scored_total    = 0.0
    checklist_total = 0.0
    breakdown       = {}

    for code, res in all_checks.items():
        if code == "R30":
            # R30 never contributes to score — log only
            breakdown[code] = {
                "score": 0, "max": 0,
                "status": res.get("status", "INFORMATIONAL"),
                "detail": res.get("detail", ""),
                "is_scored": False,
                "informational": True,
            }
            continue

        raw_score = res.get("score", 0)
        status    = res.get("status", "UNKNOWN")

        if status in ("UNKNOWN", "ERROR", "FORWARD-LOOKING", "NOT-APPLICABLE", "INFORMATIONAL"):
            raw_score = 0

        breakdown[code] = {
            "score":    raw_score,
            "max":      SCORE_MAX.get(code, 0),
            "status":   status,
            "detail":   res.get("detail", ""),
            "is_scored": code in SCORED_CHECKS,
        }

        if code in SCORED_CHECKS:
            scored_total    += raw_score
        elif code in CHECKLIST_CHECKS:
            checklist_total += raw_score

    grand_total = scored_total + checklist_total
    pct         = round((grand_total / MAX_TOTAL) * 100, 1)

    return {
        "scored_total":    round(scored_total, 1),
        "checklist_total": round(checklist_total, 1),
        "grand_total":     round(grand_total, 1),
        "max_scored":      MAX_SCORED,
        "max_checklist":   MAX_CHECKLIST,
        "max_total":       MAX_TOTAL,
        "pct":             pct,
        "breakdown":       breakdown,
    }


def get_failed_checks(all_checks: dict) -> list:
    failed = []
    for code, res in all_checks.items():
        if code == "R30":
            continue   # never show R30 as a failure
        if res.get("status") in ("FAIL", "WARN"):
            failed.append({
                "code":   code,
                "status": res["status"],
                "detail": res.get("detail", ""),
                "fix":    res.get("fix", ""),
                "tier":   res.get("tier", ""),
            })
    failed.sort(key=lambda x: (0 if x["status"] == "FAIL" else 1, x["code"]))
    return failed


def _build_observability_summary(all_checks: dict, gap_result: dict) -> dict:
    """
    Collect per-check observability traces into one structured block.
    Shown in UI as expandable 'How we checked this' section.
    """
    traces = {}
    for code, res in all_checks.items():
        obs = res.get("observability", {})
        if obs:
            traces[code] = obs

    # Layer 6 gap observability
    gap_obs = gap_result.get("observability", {}) if gap_result else {}
    if gap_obs:
        traces["L6_gaps"] = gap_obs

    return {
        "per_check_traces": traces,
        "schema_source": gap_result.get("schema_source", "") if gap_result else "",
        "gap_summary": gap_result.get("summary", "") if gap_result else "",
    }


def build_conclusion(
    all_checks:      dict,
    score_info:      dict,
    gap_summary:     str,
    merchant_intent: str,
    gap_result:      dict = None,
) -> tuple:
    """
    Generate conclusion paragraph + observability block.

    Returns:
        (conclusion_text, source, observability_block)
    """
    failed     = get_failed_checks(all_checks)
    top_issues = [f"{f['code']}: {f['detail']}" for f in failed[:5]]

    system_prompt = (
        "You are an expert AI commerce auditor. "
        "Write a 3–4 sentence conclusion paragraph for a merchant about their store's AI visibility. "
        "Be specific, honest, plain English. No jargon. No generic advice. "
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

    fallback = _rule_based_conclusion(score_info, failed)
    conclusion, source = call_llm(user_prompt, system=system_prompt, fallback_text=fallback)

    obs_block = _build_observability_summary(all_checks, gap_result or {})

    return conclusion, source, obs_block


def _rule_based_conclusion(score_info: dict, failed: list) -> str:
    pct   = score_info["pct"]
    total = score_info["grand_total"]
    max_t = score_info["max_total"]
    n     = len(failed)

    if n == 0:
        return (
            f"Your store scored {total}/{max_t} ({pct}%) on AI readiness checks. "
            "No critical issues found. Focus on deepening product specificity and "
            "building schema-exposed reviews over time."
        )
    top = failed[0]
    return (
        f"Your store scored {total}/{max_t} ({pct}%) on AI readiness checks. "
        f"{n} issue(s) are reducing your AI visibility. "
        f"Most critical: {top['code']} — {top['detail']}. "
        f"Start here: {top['fix'][:150] if top['fix'] else 'See fix details below.'}"
    )