"""
layer5/r28_r30_r31.py  — v2
──────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1:
  R30 — REMOVED from scoring. Kept as informational only.
        Reason: Shopify auto-WARN for all stores = platform noise, not merchant signal.
        Now returns status="INFORMATIONAL", score=0, not counted in total.
  R28, R31 — Observability traces added.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import re
import logging

import extruct
from bs4 import BeautifulSoup

from src.utils.fetcher import safe_get, jitter_sleep

logger = logging.getLogger(__name__)


def _is_shopify(html: str) -> bool:
    return "cdn.shopify.com" in html or "myshopify.com" in html


def _obs(check_id, raw_evidence, what_we_did, what_AI_sees, status, severity, fix):
    return {
        "check_id":     check_id,
        "raw_evidence": raw_evidence,
        "what_we_did":  what_we_did,
        "what_AI_sees": what_AI_sees,
        "status":       status,
        "severity":     severity,
        "fix":          fix,
    }


# ── R28 — UCP PROFILE ─────────────────────────────────────────────────────────

def check_r28(base_url: str, html: str) -> dict:
    result = {
        "check": "R28", "tier": "CORRELATED",
        "status": "UNKNOWN", "score": 0,
        "detail": "", "evidence": "", "fix": "", "observability": {},
    }

    shopify = _is_shopify(html)

    if not shopify:
        result.update(
            status="FORWARD-LOOKING", score=0,
            detail="Non-Shopify store — UCP not yet broadly available outside Shopify",
            fix="Monitor https://ucp.shopping for availability on your platform.",
            observability=_obs(
                "R28",
                raw_evidence="Shopify fingerprint (cdn.shopify.com) not found in HTML.",
                what_we_did="Checked for Shopify CDN fingerprint in homepage HTML.",
                what_AI_sees="Store not on Shopify — UCP not applicable yet.",
                status="FORWARD-LOOKING", severity="INFO",
                fix="Monitor https://ucp.shopping for availability on your platform.",
            ),
        )
        return result

    ucp_url = base_url.rstrip("/") + "/.well-known/ucp"
    jitter_sleep(0.4, 0.3)
    fetch   = safe_get(ucp_url)

    if fetch.timed_out or fetch.blocked or not fetch.ok:
        fix = (
            "Enable UCP in Shopify admin:\n"
            "Settings → Apps and sales channels → Enable AI shopping agents\n"
            "UCP profile auto-generates at /.well-known/ucp once enabled."
        )
        result.update(
            status="FAIL", score=0,
            detail="UCP profile not found (Shopify store — should be auto-enabled)",
            fix=fix,
            observability=_obs(
                "R28",
                raw_evidence=f"GET {ucp_url} → {getattr(fetch, 'status_code', 'no response')}",
                what_we_did="GET /.well-known/ucp with retry. Shopify store confirmed.",
                what_AI_sees="AI commerce agents cannot discover this store's capabilities.",
                status="FAIL", severity="MODERATE", fix=fix,
            ),
        )
        return result

    try:
        data     = json.loads(fetch.text)
        services = list(data.get("ucp", {}).get("services", {}).keys())
        result.update(
            status="PASS", score=1,
            detail=f"UCP profile found. Services: {services or 'declared'}",
            evidence=fetch.text[:400],
            observability=_obs(
                "R28",
                raw_evidence=fetch.text[:400],
                what_we_did=f"GET {ucp_url} → 200. Parsed JSON for services.",
                what_AI_sees=f"AI commerce agents can discover store with services: {services}.",
                status="PASS", severity="INFO", fix="",
            ),
        )
    except Exception:
        fix = "Contact Shopify support — UCP profile returned invalid JSON."
        result.update(
            status="WARN", score=0,
            detail="UCP endpoint exists but returned invalid JSON",
            fix=fix,
            observability=_obs(
                "R28",
                raw_evidence=fetch.text[:200],
                what_we_did=f"GET {ucp_url} → 200 but JSON parse failed.",
                what_AI_sees="AI agents may fail to parse UCP — store capabilities unclear.",
                status="WARN", severity="MODERATE", fix=fix,
            ),
        )
    return result


# ── R30 — ACP FEED QUALITY (INFORMATIONAL ONLY — NOT SCORED IN v2) ────────────

_GTIN_FIELDS = ["gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn", "sku"]


def check_r30(base_url: str, html: str) -> dict:
    """
    R30 — ACP feed quality.

    v2 CHANGE: R30 is now INFORMATIONAL ONLY — score=0, not counted in total.
    Reason: All Shopify stores auto-WARN (no Product schema on homepage is normal).
    This was platform noise, not a merchant-controllable signal.

    Still runs and logs findings for merchant awareness — shown in UI as info card,
    not as a failure.
    """
    result = {
        "check": "R30", "tier": "VERIFIED",
        "status": "INFORMATIONAL", "score": 0,   # score always 0 in v2
        "detail": "", "evidence": "", "fix": "", "observability": {},
        "scored": False,   # explicit flag: aggregator skips this check
    }

    if not _is_shopify(html):
        result.update(
            detail="Not a Shopify store — ACP auto-enrollment not applicable.",
            observability=_obs(
                "R30",
                raw_evidence="Shopify fingerprint not found.",
                what_we_did="Platform detection via HTML fingerprint.",
                what_AI_sees="Store not enrolled in ACP (not Shopify).",
                status="INFORMATIONAL", severity="INFO", fix="",
            ),
        )
        return result

    try:
        data     = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        products = [i for i in data.get("json-ld", []) if i.get("@type") == "Product"]
    except Exception as e:
        result.update(detail=f"extruct error: {e}")
        return result

    if not products:
        result.update(
            detail="Shopify confirmed (auto-enrolled in ACP). No Product schema on homepage — normal for Shopify. Product pages have schema by default.",
            evidence="Shopify=True, homepage_product_schema=False",
            observability=_obs(
                "R30",
                raw_evidence="Shopify CDN confirmed. extruct found 0 Product schema on homepage.",
                what_we_did="extruct JSON-LD extraction on homepage HTML.",
                what_AI_sees="Store is enrolled in ACP via Shopify. Homepage product schema absent (expected).",
                status="INFORMATIONAL", severity="INFO",
                fix="No action needed. Product pages carry schema automatically in Shopify.",
            ),
        )
        return result

    # Has product schema on homepage — evaluate quality
    issues, passes, points = [], [], 0.0
    item   = products[0]
    offers = item.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}

    title = item.get("name", "")
    if title and len(title.split()) >= 3:
        passes.append("descriptive title"); points += 2.5
    else:
        issues.append("title too short")

    if any(item.get(f) for f in _GTIN_FIELDS):
        passes.append("GTIN/MPN"); points += 2.5
    else:
        issues.append("no GTIN/MPN/SKU")

    if offers.get("price"):
        passes.append("price in schema"); points += 2.5
    else:
        issues.append("price missing from schema")

    if offers.get("availability"):
        passes.append("availability declared"); points += 2.5
    else:
        issues.append("availability not declared")

    info = f"ACP feed info ({round(points)}/10): passes={passes} | issues={issues}"
    result.update(
        detail=info,
        evidence=info,
        observability=_obs(
            "R30",
            raw_evidence=f"Product schema found on homepage. passes={passes} issues={issues}",
            what_we_did="Evaluated Product schema sub-fields: title, GTIN, price, availability.",
            what_AI_sees=f"ACP feed partial data. Issues: {issues}",
            status="INFORMATIONAL", severity="INFO",
            fix=f"Optional improvements: {', '.join(issues)}" if issues else "",
        ),
    )
    return result


# ── R31 — GMC SIGNALS ────────────────────────────────────────────────────────

def check_r31(base_url: str, html: str) -> dict:
    """
    R31 — Google Merchant Center readiness signals on homepage.
    4 signals × 2.5 points = max 10. Still scored in v2.
    """
    result = {
        "check": "R31", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "", "observability": {},
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    soup    = BeautifulSoup(html, "html.parser")
    signals, missing, points = [], [], 0.0

    # 1. Google site verification
    gsite = (
        soup.find("meta", attrs={"name": "google-site-verification"}) or
        soup.find("meta", attrs={"name": "google_site_verification"})
    )
    if gsite and gsite.get("content"):
        signals.append("google-site-verification"); points += 2.5
    else:
        missing.append("google-site-verification meta tag")

    # 2. og:type = product
    og_type = soup.find("meta", property="og:type")
    if og_type and "product" in og_type.get("content", "").lower():
        signals.append("og:type=product"); points += 2.5
    else:
        missing.append("og:type=product")

    # 3. Currency pricing visible in raw HTML
    price_hits = re.findall(
        r'(?:Rs\.?\s*|INR\s*|[₹$£€¥])\s*[\d,]+(?:\.\d{1,2})?',
        html[:60000]
    )
    if price_hits:
        signals.append(f"prices visible ({len(price_hits)})"); points += 2.5
    else:
        missing.append("no currency pricing visible in HTML")

    # 4. Organization/WebSite schema
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        has_org = any(
            i.get("@type") in ("Organization", "WebSite", "Store", "LocalBusiness")
            for i in data.get("json-ld", [])
        )
        if has_org:
            signals.append("Organization/WebSite schema"); points += 2.5
        else:
            missing.append("no Organization/WebSite schema")
    except Exception:
        missing.append("schema parse error")

    score = min(round(points), 10)
    ev    = f"signals={signals} | missing={missing}"
    result["evidence"] = ev

    fix = (
        "Improve GMC readiness:\n" +
        "\n".join(f"• {m}" for m in missing) +
        "\n\nVerify store with Google Search Console to get site-verification tag."
    ) if missing else ""

    ai_view = (
        f"AI/Gemini can surface products from this store ({len(signals)}/4 GMC signals)."
        if score >= 8
        else f"Gemini product surfacing limited — only {len(signals)}/4 GMC signals present."
    )

    obs = _obs(
        "R31", raw_evidence=ev,
        what_we_did=(
            "Checked 4 GMC signals: google-site-verification meta, og:type=product, "
            "currency price in raw HTML, Organization/WebSite schema.org."
        ),
        what_AI_sees=ai_view,
        status="PASS" if score >= 8 else ("WARN" if score >= 5 else "FAIL"),
        severity="INFO" if score >= 8 else ("MODERATE" if score >= 5 else "HIGH"),
        fix=fix,
    )
    result["observability"] = obs

    if score >= 8:
        result.update(status="PASS", score=score,
                      detail=f"Strong GMC signals ({len(signals)}/4): {signals}")
    elif score >= 5:
        result.update(status="WARN", score=score,
                      detail=f"Partial GMC signals ({len(signals)}/4) — missing: {missing}",
                      fix=fix)
    else:
        result.update(status="FAIL", score=score,
                      detail=f"Weak GMC signals ({len(signals)}/4) — missing: {missing}",
                      fix=fix)
    return result
