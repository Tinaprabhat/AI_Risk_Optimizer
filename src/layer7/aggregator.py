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

import json
import logging
import re

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


def compute_score(all_checks: dict, profile=None) -> dict:
    """
    Compute scores from all check results.

    Profile-driven: per-check max/kind come from the profile (default: shopify,
    which reproduces the v2 numbers exactly: 60 scored + 9 checklist = 69).

    Kinds:
      scored        → headline score, 0–10
      checklist     → headline score, binary
      provisional   → unvalidated HYPOTHESIS checks, reported separately
      informational → never scored (e.g. R30, llms.txt)

    UNKNOWN / ERROR / FORWARD-LOOKING / NOT-APPLICABLE → 0.
    """
    if profile is None:
        from src.profiles import get_profile
        profile = get_profile("shopify")

    scored_total      = 0.0
    checklist_total   = 0.0
    provisional_total = 0.0
    breakdown         = {}

    for code, res in all_checks.items():
        spec = profile.spec(code)
        if spec is None:
            continue   # e.g. "layer6"

        status    = res.get("status", "UNKNOWN")
        raw_score = res.get("score", 0)

        if spec.kind == "informational":
            breakdown[code] = {
                "score": 0, "max": 0, "status": status,
                "detail": res.get("detail", ""),
                "is_scored": False, "informational": True, "kind": spec.kind,
            }
            continue

        if status in ("UNKNOWN", "ERROR", "FORWARD-LOOKING", "NOT-APPLICABLE", "INFORMATIONAL"):
            raw_score = 0

        breakdown[code] = {
            "score":     raw_score,
            "max":       spec.max_score,
            "status":    status,
            "detail":    res.get("detail", ""),
            "is_scored": spec.kind in ("scored", "checklist"),
            "kind":      spec.kind,
        }

        if spec.kind == "scored":
            scored_total += raw_score
        elif spec.kind == "checklist":
            checklist_total += raw_score
        elif spec.kind == "provisional":
            provisional_total += raw_score

    max_scored    = profile.max_of("scored")
    max_checklist = profile.max_of("checklist")
    max_total     = max_scored + max_checklist
    max_prov      = profile.max_of("provisional")

    grand_total = scored_total + checklist_total
    pct         = round((grand_total / max_total) * 100, 1) if max_total else 0.0
    prov_pct    = round((provisional_total / max_prov) * 100, 1) if max_prov else 0.0

    return {
        "profile":           profile.name,
        "scored_total":      round(scored_total, 1),
        "checklist_total":   round(checklist_total, 1),
        "grand_total":       round(grand_total, 1),
        "max_scored":        max_scored,
        "max_checklist":     max_checklist,
        "max_total":         max_total,
        "pct":               pct,
        "provisional_total": round(provisional_total, 1),
        "max_provisional":   max_prov,
        "provisional_pct":   prov_pct,
        "breakdown":         breakdown,
    }


def get_failed_checks(all_checks: dict, profile=None) -> list:
    failed = []
    for code, res in all_checks.items():
        spec = profile.spec(code) if profile is not None else None
        if code == "R30" or (spec is not None and spec.kind == "informational"):
            continue   # informational checks are never shown as failures
        if res.get("status") in ("FAIL", "WARN"):
            failed.append({
                "code":   code,
                "status": res["status"],
                "detail": res.get("detail", ""),
                "fix":    res.get("fix", ""),
                "tier":   res.get("tier", ""),
                "kind":   spec.kind if spec is not None else "",
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
    profile=None,
) -> tuple:
    """
    Generate conclusion paragraph + observability block.

    Returns:
        (conclusion_text, source, observability_block)
    """
    if profile is None:
        from src.profiles import get_profile
        profile = get_profile("shopify")

    failed     = get_failed_checks(all_checks, profile)
    top_issues = [
        f"{f['code']}{' (provisional)' if f.get('kind') == 'provisional' else ''}: {f['detail']}"
        for f in failed[:5]
    ]

    system_prompt = profile.conclusion_system_prompt

    user_prompt = (
        f"The {profile.entity_noun} owner described it as: {merchant_intent}\n\n"
        f"Score: {score_info['grand_total']:g} out of {score_info['max_total']:g} points "
        f"({score_info['pct']}%). The unit is points, not checks.\n\n"
        f"Top issues:\n" + "\n".join(f"- {i}" for i in top_issues) + "\n\n"
        f"Semantic gap:\n{gap_summary[:500]}\n\n"
        "Write the conclusion paragraph now."
    )

    fallback = _rule_based_conclusion(score_info, failed, profile.entity_noun)
    conclusion, source = call_llm(user_prompt, system=system_prompt, fallback_text=fallback)
    conclusion = _normalize_noun(conclusion, profile.entity_noun)
    conclusion = _ensure_actionable(conclusion, failed)

    obs_block = _build_observability_summary(all_checks, gap_result or {})

    return conclusion, source, obs_block


def _ensure_actionable(text: str, failed: list) -> str:
    """
    Small local models sometimes write a vague paragraph. If failures exist but the
    text names none of the top ones, append a deterministic pointer to the top fix.
    """
    if not failed or not text:
        return text
    top = failed[:3]
    if any(f["code"] in text for f in top):
        return text
    first = top[0]
    fix = (first.get("fix") or "").strip().split("\n")[0][:160]
    return (text.rstrip() + f" Top fix: {first['code']} \u2014 {first['detail'][:140]}"
            + (f" ({fix})" if fix else ""))


def _normalize_noun(text: str, noun: str) -> str:
    """Small local models drift to commerce wording; force the profile's noun."""
    if noun == "store" or not text:
        return text
    text = re.sub(r"\b[Ss]tore('s)?\b", lambda m: noun + (m.group(1) or ""), text)
    text = re.sub(r"\b[Mm]erchants?\b", "owner", text)
    return text


def _rule_based_conclusion(score_info: dict, failed: list, noun: str = "store") -> str:
    pct   = score_info["pct"]
    total = score_info["grand_total"]
    max_t = score_info["max_total"]
    n     = len(failed)

    if n == 0:
        return (
            f"Your {noun} scored {total}/{max_t} ({pct}%) on AI readiness checks. "
            "No critical issues found. Focus on deepening specificity and "
            "building schema-exposed proof (reviews, case studies) over time."
        )
    top = failed[0]
    return (
        f"Your {noun} scored {total}/{max_t} ({pct}%) on AI readiness checks. "
        f"{n} issue(s) are reducing your AI visibility. "
        f"Most critical: {top['code']} — {top['detail']}. "
        f"Start here: {top['fix'][:150] if top['fix'] else 'See fix details below.'}"
    )