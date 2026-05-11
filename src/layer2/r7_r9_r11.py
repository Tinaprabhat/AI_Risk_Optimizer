"""
layer2/r7_r9_r11.py
────────────────────
R7  — schema.org commerce types:  CORRELATED  0–10 scored
R9  — price signal visible:       CORRELATED  0–10 scored
R11 — JSON-LD valid:              CORRELATED  0/1  binary

All three operate on the same homepage HTML — passed in to avoid re-fetching.
"""

import json
import re
import logging
from typing import Optional

import extruct
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── R7 — SCHEMA.ORG COMMERCE TYPES ───────────────────────────────────────────

# Type → points mapping (max 10)
_SCHEMA_POINTS = {
    "Product":          4,
    "Organization":     3,
    "Store":            3,   # alias for Organization in commerce context
    "LocalBusiness":    3,
    "FAQPage":          2,
    "BreadcrumbList":   1,
    "WebSite":          1,
}

def check_r7(base_url: str, html: str) -> dict:
    """
    R7 — What schema.org commerce types are present on the homepage?

    Scoring:
      Product=4 · Organization/Store/LocalBusiness=3 · FAQPage=2 · BreadcrumbList=1
      Max = 10 (Product + Organization + FAQPage + BreadcrumbList)
    """
    result = {
        "check": "R7", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld", "microdata"])
    except Exception as e:
        result.update(status="UNKNOWN", detail=f"extruct error: {e}")
        return result

    # Collect all @type values found
    types_found = set()
    for item in data.get("json-ld", []):
        t = item.get("@type", "")
        if isinstance(t, list):
            types_found.update(t)
        elif t:
            types_found.add(t)

    for item in data.get("microdata", []):
        t = item.get("type", "").split("/")[-1]
        if t:
            types_found.add(t)

    result["evidence"] = f"Types found: {sorted(types_found)}"

    # Score based on which commerce types are present
    # Cap at 10 — don't double-count Organization aliases
    points = 0
    found_commerce = []
    org_counted    = False

    for t in types_found:
        if t == "Product":
            points += _SCHEMA_POINTS["Product"]
            found_commerce.append(t)
        elif t in ("Organization", "Store", "LocalBusiness") and not org_counted:
            points += _SCHEMA_POINTS["Organization"]
            found_commerce.append(t)
            org_counted = True
        elif t == "FAQPage":
            points += _SCHEMA_POINTS["FAQPage"]
            found_commerce.append(t)
        elif t == "BreadcrumbList":
            points += _SCHEMA_POINTS["BreadcrumbList"]
            found_commerce.append(t)

    score = min(points, 10)

    if score >= 7:
        status = "PASS"
    elif score >= 3:
        status = "WARN"
    else:
        status = "FAIL"

    fix = ""
    if score < 10:
        fix = (
            "Add schema.org JSON-LD to your store. Priority order:\n\n"
            "1. Organization (if missing):\n"
            '   <script type="application/ld+json">\n'
            '   {"@context":"https://schema.org","@type":"Organization",\n'
            '    "name":"YOUR STORE NAME","url":"YOUR URL"}\n'
            '   </script>\n\n'
            "2. Product schema on all product pages (Shopify usually adds this automatically).\n\n"
            "3. FAQPage schema on your FAQ page."
        )

    result.update(
        status=status,
        score=score,
        detail=f"Commerce schema score: {score}/10 — types: {found_commerce or 'none'}",
        fix=fix,
    )
    return result


# ── R9 — PRICE SIGNAL ─────────────────────────────────────────────────────────

def check_r9(base_url: str, html: str) -> dict:
    """
    R9 — Is there a price signal visible to AI crawlers on the homepage?

    Scoring:
      Price in JSON-LD schema:  10
      Price in og/meta tags:     7
      Currency price in HTML:    4
      Nothing:                   0
    """
    result = {
        "check": "R9", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    # 1. JSON-LD schema price (best signal — score 10)
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        for item in data.get("json-ld", []):
            offers = item.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price") or item.get("price")
            if price:
                result.update(
                    status="PASS", score=10,
                    detail=f"Price found in JSON-LD schema: {price}",
                    evidence=f"JSON-LD price: {price}",
                )
                return result
    except Exception as e:
        logger.debug(f"extruct error in R9: {e}")

    # 2. og/meta price tags (score 7)
    soup = BeautifulSoup(html, "html.parser")
    for prop in ["product:price:amount", "og:price:amount"]:
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            result.update(
                status="PASS", score=7,
                detail=f"Price in meta tag ({prop}): {meta['content']}",
                evidence=f"meta {prop}: {meta['content']}",
            )
            return result

    # 3. Currency-prefixed price in HTML text (score 4)
    price_pattern = r'(?:Rs\.?\s*|INR\s*|[₹$£€¥])\s*[\d,]+(?:\.\d{1,2})?'
    hits = re.findall(price_pattern, html[:60000])
    if hits:
        result.update(
            status="WARN", score=4,
            detail=f"Currency prices visible in HTML ({len(hits)} found): {hits[:3]}",
            evidence=str(hits[:5]),
            fix=(
                "Prices are in HTML but not in structured schema. Add Product schema with price:\n"
                '{"@type":"Product","offers":{"@type":"Offer","price":"XX.XX","priceCurrency":"INR"}}'
            ),
        )
        return result

    # No price signal found
    result.update(
        status="FAIL", score=0,
        detail="No price signal found on homepage",
        fix=(
            "Add price data to your homepage or product pages using schema.org.\n"
            "Shopify usually adds this automatically on product pages.\n"
            "Check that your theme is not blocking schema.org output."
        ),
    )
    return result


# ── R11 — JSON-LD VALIDITY ────────────────────────────────────────────────────

def check_r11(base_url: str, html: str) -> dict:
    """
    R11 — Are all JSON-LD blocks valid, parseable JSON?

    Malformed JSON-LD is silently ignored by all crawlers — the data simply
    does not exist for AI purposes even if visually present in page source.
    """
    result = {
        "check": "R11", "tier": "CORRELATED",
        "status": "PASS", "score": 1,  # default pass unless we find errors
        "detail": "", "evidence": "", "fix": "",
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    soup = BeautifulSoup(html, "html.parser")
    ld_scripts = soup.find_all("script", type="application/ld+json")

    if not ld_scripts:
        result.update(
            status="FAIL",
            score=0,
            detail="No JSON-LD blocks found in page source",
            fix="Add schema.org JSON-LD markup to your store (see R7 fix for template).",
        )
        return result

    errors = []
    for i, script in enumerate(ld_scripts):
        raw = script.string or ""
        try:
            parsed = json.loads(raw)
            # Check for required fields
            if not parsed.get("@context"):
                errors.append(f"Block {i+1}: missing @context")
            if not parsed.get("@type"):
                errors.append(f"Block {i+1}: missing @type")
        except json.JSONDecodeError as e:
            errors.append(f"Block {i+1}: JSON parse error at position {e.pos}: {e.msg}")

    result["evidence"] = f"{len(ld_scripts)} JSON-LD block(s) found"

    if errors:
        result.update(
            status="FAIL",
            score=0,
            detail=f"Malformed JSON-LD found — {len(errors)} error(s): {errors[0]}",
            evidence=f"Errors: {errors}",
            fix=(
                "Fix the JSON-LD errors listed above. Common causes:\n"
                "1. Trailing commas in JSON objects\n"
                "2. Unescaped quotes inside string values\n"
                "3. Missing closing braces\n\n"
                "Validate at: https://validator.schema.org/"
            ),
        )
    else:
        result.update(
            status="PASS",
            score=1,
            detail=f"All {len(ld_scripts)} JSON-LD block(s) are valid",
        )

    return result
