"""
layer5/r28_r30_r31.py
──────────────────────
R28 — UCP profile:       CORRELATED  0/1 binary  (Shopify=scored, non-Shopify=0)
R30 — ACP feed quality:  VERIFIED    0–10 scored  (Shopify only)
R31 — GMC signals:       CORRELATED  0–10 scored
"""

import re
import logging

import extruct
from bs4 import BeautifulSoup

from src.utils.fetcher import safe_get, jitter_sleep

logger = logging.getLogger(__name__)


def _is_shopify(html: str) -> bool:
    """Detect if the store runs on Shopify."""
    return "cdn.shopify.com" in html or "myshopify.com" in html


# ── R28 — UCP PROFILE ─────────────────────────────────────────────────────────

def check_r28(base_url: str, html: str) -> dict:
    """
    R28 — Does the store have a UCP (Universal Checkout Protocol) profile?

    Non-Shopify: score=0, status=FORWARD-LOOKING (not a current requirement)
    Shopify:     checked and scored — UCP is live for Shopify stores in 2026
    """
    result = {
        "check": "R28", "tier": "CORRELATED",
        "status": "UNKNOWN", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    shopify = _is_shopify(html)

    if not shopify:
        result.update(
            status="FORWARD-LOOKING",
            score=0,
            detail="Non-Shopify store — UCP not yet broadly available outside Shopify",
            fix="Monitor https://ucp.shopping for when UCP becomes available for your platform.",
        )
        return result

    # Shopify store — fetch UCP endpoint
    ucp_url = base_url.rstrip("/") + "/.well-known/ucp"
    jitter_sleep(0.4, 0.3)
    fetch = safe_get(ucp_url)

    if fetch.timed_out or fetch.blocked or not fetch.ok:
        result.update(
            status="FAIL",
            score=0,
            detail=f"UCP profile not found (Shopify store — should be auto-enabled)",
            fix=(
                "Enable UCP in your Shopify admin:\n"
                "Settings → Apps and sales channels → Enable AI shopping agents\n"
                "Once enabled, UCP profile auto-generates at /.well-known/ucp"
            ),
        )
        return result

    try:
        import json
        data     = json.loads(fetch.text)
        services = list(data.get("ucp", {}).get("services", {}).keys())
        result.update(
            status="PASS",
            score=1,
            detail=f"UCP profile found. Services: {services or 'declared'}",
            evidence=fetch.text[:400],
        )
    except Exception:
        result.update(
            status="WARN",
            score=0,
            detail="UCP endpoint exists but returned invalid JSON",
            fix="Contact Shopify support — your UCP profile may be corrupted.",
        )

    return result


# ── R30 — ACP FEED QUALITY ───────────────────────────────────────────────────

_GTIN_FIELDS = ["gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn", "sku"]

def check_r30(base_url: str, html: str) -> dict:
    """
    R30 — ACP feed quality for Shopify stores.

    Non-Shopify: score=0, status=NOT-APPLICABLE
    Shopify on homepage: checks product schema sub-fields
      Each of 4 sub-fields worth 2.5 points = max 10

    Sub-fields checked:
      • Descriptive title (≥3 words)
      • GTIN/MPN/SKU present
      • Price in schema
      • Availability declared
    """
    result = {
        "check": "R30", "tier": "VERIFIED",
        "status": "UNKNOWN", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    if not _is_shopify(html):
        result.update(
            status="NOT-APPLICABLE",
            score=0,
            detail="ACP auto-enrollment is Shopify-specific — not applicable here",
        )
        return result

    # Shopify confirmed — extract Product schema
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        products = [i for i in data.get("json-ld", []) if i.get("@type") == "Product"]
    except Exception as e:
        result.update(status="UNKNOWN", detail=f"extruct error: {e}")
        return result

    if not products:
        # Shopify homepage rarely has Product schema — this is expected
        result.update(
            status="WARN",
            score=5,   # partial credit — Shopify store is enrolled even without homepage schema
            detail="Shopify confirmed (auto-enrolled in ACP). No Product schema on homepage (normal). Re-run on a /products/ URL for full evaluation.",
            evidence="Shopify=True, homepage_product_schema=False",
            fix="No action needed for ACP enrollment. Product pages have schema by default in Shopify.",
        )
        return result

    # Evaluate product schema quality
    issues = []
    passes = []
    points = 0.0

    for item in products[:3]:  # evaluate up to 3 products
        offers = item.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        # Descriptive title
        title = item.get("name", "")
        if title and len(title.split()) >= 3:
            passes.append("descriptive title")
            points += 2.5
        else:
            issues.append("title too short or missing")

        # GTIN/identifier
        if any(item.get(f) for f in _GTIN_FIELDS):
            passes.append("GTIN/MPN")
            points += 2.5
        else:
            issues.append("no GTIN/MPN/SKU")

        # Price
        if offers.get("price"):
            passes.append("price in schema")
            points += 2.5
        else:
            issues.append("price missing from schema")

        # Availability
        if offers.get("availability"):
            passes.append("availability declared")
            points += 2.5
        else:
            issues.append("availability not declared")

        break  # evaluate only first product for scoring

    score = min(round(points), 10)
    result["evidence"] = f"passes={passes} issues={issues}"

    if score >= 8:
        result.update(status="PASS", score=score, detail=f"ACP feed quality good: {passes}")
    elif score >= 5:
        result.update(
            status="WARN", score=score,
            detail=f"ACP feed partial ({score}/10) — issues: {issues}",
            fix=f"Fix ACP feed issues:\n" + "\n".join(f"• {i}" for i in issues),
        )
    else:
        result.update(
            status="FAIL", score=score,
            detail=f"ACP feed quality low ({score}/10) — issues: {issues}",
            fix=(
                "Improve your Shopify product data for ACP feed quality:\n" +
                "\n".join(f"• {i}" for i in issues) +
                "\n\nIn Shopify: Products → Edit each product → Fill in all fields including barcode (GTIN)."
            ),
        )
    return result


# ── R31 — GMC SIGNALS ────────────────────────────────────────────────────────

def check_r31(base_url: str, html: str) -> dict:
    """
    R31 — Google Merchant Center readiness signals on homepage.

    4 signals × 2.5 points = max 10:
      • Google site verification meta tag
      • og:type = product
      • Currency pricing visible in HTML
      • Organization/WebSite schema present
    """
    result = {
        "check": "R31", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    soup    = BeautifulSoup(html, "html.parser")
    signals = []
    missing = []
    points  = 0.0

    # 1. Google site verification
    gsite = (
        soup.find("meta", attrs={"name": "google-site-verification"}) or
        soup.find("meta", attrs={"name": "google_site_verification"})
    )
    if gsite and gsite.get("content"):
        signals.append("google-site-verification")
        points += 2.5
    else:
        missing.append("google-site-verification meta tag")

    # 2. og:type = product
    og_type = soup.find("meta", property="og:type")
    if og_type and "product" in og_type.get("content", "").lower():
        signals.append("og:type=product")
        points += 2.5
    else:
        missing.append("og:type=product")

    # 3. Currency pricing visible
    price_hits = re.findall(
        r'(?:Rs\.?\s*|INR\s*|[₹$£€¥])\s*[\d,]+(?:\.\d{1,2})?',
        html[:60000]
    )
    if price_hits:
        signals.append(f"prices visible ({len(price_hits)})")
        points += 2.5
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
            signals.append("Organization/WebSite schema")
            points += 2.5
        else:
            missing.append("no Organization/WebSite schema")
    except Exception:
        missing.append("schema parse error")

    score = min(round(points), 10)
    result["evidence"] = f"signals={signals} | missing={missing}"

    if score >= 8:
        result.update(
            status="PASS", score=score,
            detail=f"Strong GMC signals ({len(signals)}/4): {signals}",
        )
    elif score >= 5:
        result.update(
            status="WARN", score=score,
            detail=f"Partial GMC signals ({len(signals)}/4) — missing: {missing}",
            fix=f"Add missing GMC signals:\n" + "\n".join(f"• {m}" for m in missing),
        )
    else:
        result.update(
            status="FAIL", score=score,
            detail=f"Weak GMC signals ({len(signals)}/4) — missing: {missing}",
            fix=(
                "Improve GMC readiness:\n" +
                "\n".join(f"• {m}" for m in missing) +
                "\n\nVerify store with Google Search Console to get site-verification tag.\n"
                "Add Organization schema (see R7 fix for template)."
            ),
        )
    return result
