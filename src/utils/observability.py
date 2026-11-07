"""
src/utils/observability.py
───────────────────────────
Guarantee every check result carries an `observability` block, so the UI's
"How we validated each check" panel and the audit log have no blind spots.
Checks that build their own richer block are left untouched.
"""

_SEVERITY = {"FAIL": "HIGH", "WARN": "MEDIUM", "ERROR": "HIGH", "UNKNOWN": "MEDIUM"}


def ensure_observability(code: str, result: dict, what_we_did: str = "") -> dict:
    if not isinstance(result, dict) or result.get("observability"):
        return result
    status = result.get("status", "UNKNOWN")
    result["observability"] = {
        "check_id":     code,
        "raw_evidence": result.get("evidence") or result.get("detail", "") or "(none)",
        "what_we_did":  what_we_did or f"Ran automated check {code} ({result.get('tier', 'untiered')}).",
        "what_AI_sees": result.get("detail", ""),
        "status":       status,
        "severity":     _SEVERITY.get(status, "INFO"),
        "fix":          result.get("fix", ""),
    }
    return result
