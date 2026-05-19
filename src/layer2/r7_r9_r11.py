"""
src/layer2/r7_r9_r11.py
─────────────────────────
Layer 2 — Structured Data checks.

v2.0 changes:
  R9 — check_r9() now receives semantic_data["price"] from SemanticExtractor.
       Extended to 4 currency format patterns (was 1 symbol-only pattern).
       Contradiction detection now works for USD/GBP/EUR code formats.

v1 behaviour retained:
  R7 — schema.org field completeness (unchanged)
  R11 — JSON-LD validity (unchanged)
"""

import json
import logging

import extruct
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Schema.org field weights ───────────────────────────────────────────────────

_REQUIRED_PRODUCT_FIELDS = [
    ("name",              3),
    ("offers.price",      3),
    ("offers.availability", 2),
    ("brand",             2),
]

_RECOMMENDED_FIELDS = [
    ("description",       1),
    ("image",             1),
    ("sku",               1),
    ("aggregateRating",   2),
]

_SCHEMA_PASS_THRESHOLD = 7   # >= 7 points = PASS
_SCHEMA_WARN_THRESHOLD = 4   # >= 4 points = WARN


def _get_nested(d: dict, key: str):
    """Access nested dict key using dot notation e.g. 'offers.price'."""
    parts = key.split(".")
    val   = d
    for p in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
    return val


def _extract_schema_items(html: str) -> list:
    """
    Extract all JSON-LD items from HTML using extruct.
    Returns list of dicts (one per @type block).
    """
    if not html:
        return []
    try:
        data = extruct.extract(html, syntaxes=["json-ld"], uniform=True)
        return data.get("json-ld", [])
    except Exception as e:
        logger.warning(f"extruct extraction failed: {e}")
        return []


# ── R7 — Schema.org Presence and Completeness ─────────────────────────────────
# Unchanged from v1.

def check_r7(homepage_html: str, product_pages_html=None) -> dict:
    if not isinstance(product_pages_html, list):
        product_pages_html = [product_pages_html] if product_pages_html else []
    """
    R7 — Schema.org structured data presence and completeness.

    Scored check (0-10). Extracts all JSON-LD from homepage + product pages.
    Returns schema_data for reuse by SemanticExtractor and R9.

    Args:
        homepage_html:      Raw homepage HTML
        product_pages_html: List of raw product page HTML strings (up to 3)

    Returns:
        Check result dict with schema_data field for downstream use.
    """
    result = {
        "check":       "R7",
        "status":      "FAIL",
        "score":       0,
        "detail":      "",
        "evidence":    "",
        "schema_data": [],   # exposed for SemanticExtractor and R9
    }

    all_html = [homepage_html] + product_pages_html
    all_schema_items = []

    for html in all_html:
        if html:
            items = _extract_schema_items(html)
            all_schema_items.extend(items)

    if not all_schema_items:
        result.update({
            "detail": "No schema.org JSON-LD found on any page. "
                       "AI cannot extract structured product facts.",
        })
        return result

    result["schema_data"] = all_schema_items

    # Score by field completeness
    types_found = [item.get("@type", "") for item in all_schema_items]
    score       = 0
    found_fields = []
    missing_fields = []

    # Check required fields on Product schemas
    product_items = [i for i in all_schema_items if "Product" in str(i.get("@type", ""))]
    if product_items:
        item = product_items[0]
        for field, weight in _REQUIRED_PRODUCT_FIELDS:
            val = _get_nested(item, field)
            if val:
                score += weight
                found_fields.append(field)
            else:
                missing_fields.append(f"{field} (required, -{weight}pts)")

        for field, weight in _RECOMMENDED_FIELDS:
            val = _get_nested(item, field)
            if val:
                score += weight
                found_fields.append(field)
    else:
        # No Product schema — partial points for Organization/WebSite
        if any("Organization" in str(t) for t in types_found):
            score += 3
            found_fields.append("Organization")
        if any("WebSite" in str(t) for t in types_found):
            score += 1
            found_fields.append("WebSite")

    result["evidence"] = (
        f"Types found: {', '.join(set(str(t) for t in types_found))}. "
        f"Fields: {', '.join(found_fields) or 'none'}."
    )

    if score >= _SCHEMA_PASS_THRESHOLD:
        result.update({
            "status": "PASS",
            "score":  min(score, 10),
            "detail": f"Schema.org well-configured (score {score}/10). "
                       f"Found: {', '.join(found_fields)}.",
        })
    elif score >= _SCHEMA_WARN_THRESHOLD:
        result.update({
            "status": "WARN",
            "score":  score,
            "detail": f"Schema.org partial (score {score}/10). "
                       f"Missing: {', '.join(missing_fields)}.",
        })
    else:
        result.update({
            "status": "FAIL",
            "score":  score,
            "detail": f"Schema.org incomplete (score {score}/10). "
                       f"Missing critical fields: {', '.join(missing_fields)}.",
        })

    return result


# ── R9 — Price Contradiction ───────────────────────────────────────────────────
# v2.0: Receives semantic_data["price"] with 4-format detection.

def check_r9(homepage_html: str, product_pages_html=None, semantic_data: dict = None) -> dict:
    if not isinstance(product_pages_html, list):
        product_pages_html = [product_pages_html] if product_pages_html else []
    if semantic_data is None:
        semantic_data = {}
    """
    R9 — Price contradiction between schema.org and visible HTML.

    v2.0: Receives semantic_data["price"] from SemanticExtractor.
    SemanticExtractor detects prices in 4 formats:
      1. Symbol prefix: $99.99, £29, ₹1500
      2. Code prefix:   USD 99, GBP 29
      3. Code suffix:   99 USD, 49 EUR
      4. (Tier 2 not applicable for price — numeric extraction is reliable)

    Args:
        homepage_html:      Raw homepage HTML (still needed for fallback)
        product_pages_html: Product pages HTML (for product-level price check)
        semantic_data:      semantic_data dict from SemanticExtractor

    Returns:
        Standard check result dict (binary — contradiction = FAIL, no contradiction = PASS).
    """
    result = {
        "check":    "R9",
        "status":   "PASS",
        "score":    10,
        "detail":   "",
        "evidence": "",
    }

    price_data = semantic_data.get("price", {})

    # If semantic extractor found no price data, check if we have schema at all
    if not price_data.get("price_in_schema") and not price_data.get("price_in_html"):
        # No price in schema and no price in HTML — not a contradiction, just absence
        result.update({
            "status": "WARN",
            "score":  5,
            "detail": "No price found in schema.org or HTML. "
                       "Add offers.price to Product schema for AI price extraction.",
            "evidence": "No price signal found on homepage.",
        })
        return result

    schema_price = price_data.get("price_in_schema", "")
    html_price   = price_data.get("price_in_html", "")
    contradiction = price_data.get("contradiction", False)
    confidence   = price_data.get("confidence", 0.0)

    result["evidence"] = (
        f"Schema price: '{schema_price}'. "
        f"HTML price: '{html_price}'. "
        f"Contradiction: {contradiction}."
    )

    if contradiction:
        result.update({
            "status": "FAIL",
            "score":  0,
            "detail": f"Price contradiction detected: schema says '{schema_price}' "
                       f"but HTML shows '{html_price}'. "
                       "AI will pick the wrong value. Fix schema to match displayed price.",
        })
    elif schema_price and not html_price:
        result.update({
            "status": "WARN",
            "score":  7,
            "detail": f"Price found in schema ('{schema_price}') but not clearly visible in HTML. "
                       "Verify price displays correctly for all crawlers.",
        })
    elif html_price and not schema_price:
        result.update({
            "status": "WARN",
            "score":  5,
            "detail": f"Price visible in HTML ('{html_price}') but missing from schema.org. "
                       "AI agents read schema — add offers.price to Product schema.",
        })
    else:
        result.update({
            "status": "PASS",
            "score":  10,
            "detail": f"Price consistent: schema='{schema_price}', HTML='{html_price}'.",
        })

    return result


# ── R11 — JSON-LD Validity ────────────────────────────────────────────────────
# Unchanged from v1.

def check_r11(homepage_html: str, product_pages_html=None) -> dict:
    if not isinstance(product_pages_html, list):
        product_pages_html = [product_pages_html] if product_pages_html else []
    """
    R11 — JSON-LD blocks are valid JSON and have required @context/@type.

    Binary check: any malformed JSON-LD = FAIL.

    Args:
        homepage_html:      Raw homepage HTML
        product_pages_html: Product pages HTML

    Returns:
        Standard check result dict.
    """
    result = {
        "check":    "R11",
        "status":   "PASS",
        "score":    1,
        "detail":   "",
        "evidence": "",
    }

    all_html = [homepage_html] + product_pages_html
    errors   = []

    for html in all_html:
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", {"type": "application/ld+json"}):
            raw = tag.string or ""
            if not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
                items = parsed if isinstance(parsed, list) else [parsed]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if not item.get("@context"):
                        errors.append("Missing @context in JSON-LD block")
                    if not item.get("@type"):
                        errors.append("Missing @type in JSON-LD block")
            except json.JSONDecodeError as e:
                errors.append(f"Malformed JSON-LD: {str(e)[:80]}")

    if errors:
        result.update({
            "status": "FAIL",
            "score":  0,
            "detail": f"JSON-LD errors found: {'; '.join(errors[:3])}. "
                       "Malformed JSON-LD is silently ignored by all AI crawlers.",
            "evidence": f"{len(errors)} error(s) found.",
        })
    else:
        result.update({
            "detail":   "All JSON-LD blocks are valid.",
            "evidence": "No JSON parse errors or missing fields.",
        })

    return result