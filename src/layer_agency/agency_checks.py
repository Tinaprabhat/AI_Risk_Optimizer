"""
src/layer_agency/agency_checks.py
──────────────────────────────────
Agency-profile checks that do not exist in the Shopify profile.

Currently one: R32 — llms.txt presence (FORWARD-LOOKING, never scored).
(The earlier A1–A4 hypothesis checks were discarded.)
"""

import logging

from src.utils.fetcher import safe_get

logger = logging.getLogger(__name__)


def check_r32(base_url: str) -> dict:
    """R32 — /llms.txt present? Informational only: no proven effect on recommendations."""
    r = {"check": "R32", "tier": "FORWARD-LOOKING", "status": "FORWARD-LOOKING", "score": 0,
         "detail": "", "evidence": "", "fix": ""}
    fetch = safe_get(base_url.rstrip("/") + "/llms.txt")
    present = bool(fetch.ok and len(fetch.text.strip()) > 20 and "<html" not in fetch.text[:300].lower())
    if present:
        r["detail"] = "llms.txt found. No proven effect on recommendations yet — informational only."
        r["evidence"] = fetch.text[:200]
    else:
        r["detail"] = "No llms.txt found. Optional and unproven; not scored."
        r["evidence"] = f"GET /llms.txt → {getattr(fetch, 'status_code', '?')}"
        r["fix"] = "Optionally add /llms.txt summarising your services and key pages."
    r["observability"] = {
        "check_id": "R32", "raw_evidence": r["evidence"],
        "what_we_did": "Fetched /llms.txt and checked for non-HTML text content.",
        "what_AI_sees": r["detail"], "status": "FORWARD-LOOKING", "severity": "INFO", "fix": r["fix"],
    }
    return r
