"""
AI Representation Optimizer — Validation Script v2.1
=====================================================
Usage:
  python validate.py --store-url https://example.com
  python validate.py --store-url https://example.com --label "yoga mats"
  python validate.py --store-url https://example.com --out ./results

Outputs (saved in same directory as script, or --out):
  validation_results_<domain>_<timestamp>.json
  validation_report_<domain>_<timestamp>.txt

Active checks (10):
  R1  robots.txt AI crawler access      [VERIFIED]
  R3  sitemap.xml existence             [VERIFIED]
  R7  schema.org types on homepage      [CORRELATED]
  R9  homepage price signal             [CORRELATED]
  R16 concrete refund window            [CORRELATED]
  R17 concrete shipping timeframe       [CORRELATED]
  R25 brand name consistency            [CORRELATED]
  R28 UCP profile                       [FORWARD-LOOKING - not scored]
  R30 ACP feed quality (Shopify only)   [VERIFIED]
  R31 GMC homepage signals              [CORRELATED]

Removed (universally failed, non-predictive):
  R4  R10  R21  R22
"""

import argparse
import json
import re
import time
import random
import os
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import extruct
from rapidfuzz import fuzz

# ── CONSTANTS ─────────────────────────────────────────────────────────────────

SCRIPT_VERSION = "v2.1"

AI_CRAWLERS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "Claude-SearchBot", "anthropic-ai",
    "Google-Extended", "Gemini-Deep-Research",
    "PerplexityBot", "Perplexity-User",
    "Meta-ExternalAgent", "CCBot", "Applebot-Extended",
]

GTIN_FIELDS = ["gtin", "gtin8", "gtin12", "gtin13", "gtin14", "mpn", "sku"]

SHIPPING_PATTERNS = [
    r"\b(\d+)\s*[-to]+\s*(\d+)\s*(business\s+)?days?\b",
    r"\bships?\s+(?:in|within)\s+(\d+[-\d]*)\s*(business\s+)?days?\b",
    r"\bdelivery\s+(?:in|within)\s+(\d+[-]\d+)\s*(business\s+)?days?\b",
    r"\b(next\s+day|same\s+day|overnight|express)\s+(?:shipping|delivery)\b",
    r"\bdelivered\s+(?:in|within)\s+(\d+[-]\d+)\s*(business\s+)?days?\b",
]

RETURN_PATTERNS = [
    r"\b(\d+)\s*[-]?\s*day\s+(?:return|refund|exchange|money.back)\b",
    r"\breturn(?:s)?\s+(?:within|up\s+to|accepted\s+within)\s+(\d+)\s+days?\b",
    r"\b(\d+)\s+days?\s+(?:return|refund|money.back|easy\s+return)\b",
    r"\bfree\s+returns?\s+(?:within\s+)?(\d+)\s+days?\b",
    r"\b(30|60|90|14|15|45|7)\s*[-]?\s*day\s+(?:return|refund|money.back|exchange)\b",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ACTIVE_CHECKS = ["R1", "R3", "R7", "R9", "R16", "R17", "R25", "R28", "R30", "R31"]
SCORED_CHECKS = ["R1", "R3", "R7", "R9", "R16", "R17", "R25", "R30", "R31"]

REMOVED_CHECKS = {
    "R4":  "Removed — plain-requests JS check measured script limitations, not real AI crawler behavior.",
    "R10": "Removed — 11/11 stores failed yet were AI-recommended. Not a recommendation blocker.",
    "R21": "Removed — duplicate of R10.",
    "R22": "Removed — same root cause as R10.",
}

STATUS_ICONS = {
    "PASS": "✅", "FAIL": "❌", "WARN": "⚠️",
    "UNKNOWN": "❓", "FORWARD-LOOKING": "🔮", "ERROR": "💥",
}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def safe_get(url, timeout=12):
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.4, 0.9) * (attempt + 1))
            r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            return r
        except Exception:
            if attempt == 2:
                return None
    return None


# ── CHECKPOINTS ───────────────────────────────────────────────────────────────

def check_r1_robots(base_url):
    """R1 — robots.txt: are AI crawlers allowed? [VERIFIED]"""
    result = {"check": "R1", "tier": "VERIFIED",
              "status": "FAIL", "detail": "", "evidence": ""}
    resp = safe_get(base_url.rstrip("/") + "/robots.txt")
    if not resp or resp.status_code == 404:
        result.update(status="PASS", detail="robots.txt absent — allow all (per spec)")
        return result
    if resp.status_code != 200:
        result.update(status="UNKNOWN", detail=f"HTTP {resp.status_code}")
        return result
    content = resp.text
    result["evidence"] = content[:600]
    blocked = []
    current_agents = []
    for line in content.split("\n"):
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            current_agents = [line.split(":", 1)[1].strip()]
        elif line.lower().startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path in ["/", "/*"]:
                for agent in current_agents:
                    for ai in AI_CRAWLERS:
                        if ai.lower() in agent.lower() or agent == "*":
                            blocked.append(agent)
    if blocked:
        result.update(status="FAIL",
                      detail=f"AI crawlers blocked: {', '.join(set(blocked))}")
    else:
        result.update(status="PASS", detail="No AI crawlers blocked")
    return result


def check_r3_sitemap(base_url):
    """R3 — sitemap.xml: exists and parseable? [VERIFIED]"""
    result = {"check": "R3", "tier": "VERIFIED",
              "status": "FAIL", "detail": "", "evidence": ""}
    resp = safe_get(base_url.rstrip("/") + "/sitemap.xml")
    if not resp or resp.status_code != 200:
        result["detail"] = f"sitemap.xml not found ({resp.status_code if resp else 'timeout'})"
        return result
    content = resp.text[:8000]
    result["evidence"] = content[:400]
    if "<loc>" not in content and "<url>" not in content and "<sitemap>" not in content:
        result.update(status="WARN", detail="sitemap.xml found but appears malformed")
        return result
    url_count   = content.count("<loc>")
    products    = len(re.findall(r'/product', content, re.I))
    collections = len(re.findall(r'/collection', content, re.I))
    result.update(
        status="PASS",
        detail=f"{url_count} URLs | products: {products} | collections: {collections}"
    )
    return result


def check_r7_schema(base_url, html_cache):
    """R7 — schema.org commerce types on homepage [CORRELATED]"""
    result = {"check": "R7", "tier": "CORRELATED",
              "status": "FAIL", "detail": "", "evidence": ""}
    html = html_cache.get("homepage", "")
    if not html:
        result.update(status="UNKNOWN", detail="Homepage HTML unavailable")
        return result
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld", "microdata"])
        types_found = []
        for item in data.get("json-ld", []):
            t = item.get("@type", "")
            types_found.extend(t if isinstance(t, list) else [t])
        for item in data.get("microdata", []):
            types_found.append(item.get("type", "").split("/")[-1])
        types_found = [t for t in types_found if t]
        result["evidence"] = f"Types: {types_found}"
        commerce = ["Product", "Organization", "Store", "LocalBusiness",
                    "FAQPage", "AggregateRating", "WebSite"]
        found = [t for t in types_found if t in commerce]
        if any(t in found for t in ["Organization", "Store", "LocalBusiness"]):
            result.update(status="PASS", detail=f"Commerce schema: {found}")
        elif found:
            result.update(status="WARN", detail=f"Minimal schema: {found}")
        elif types_found:
            result.update(status="WARN",
                          detail=f"Schema present, no commerce types: {types_found}")
        else:
            result.update(status="FAIL", detail="No schema.org markup found")
    except Exception as e:
        result.update(status="UNKNOWN", detail=f"extruct error: {e}")
    return result


def check_r9_homepage_price_signal(base_url, html_cache):
    """R9 — homepage price signal [CORRELATED]"""
    result = {"check": "R9", "tier": "CORRELATED",
              "status": "FAIL", "detail": "", "evidence": "",
              "note": "Reframed for homepage: any crawler-visible price signal"}
    html = html_cache.get("homepage", "")
    if not html:
        result.update(status="UNKNOWN", detail="Homepage HTML unavailable")
        return result
    # 1. JSON-LD price
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        for item in data.get("json-ld", []):
            offers = item.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price") or item.get("price")
            if price:
                result.update(status="PASS",
                              detail=f"Price in JSON-LD: {price}",
                              evidence=f"schema price: {price}")
                return result
    except Exception:
        pass
    # 2. og/meta price tag
    soup = BeautifulSoup(html, "html.parser")
    for prop in ["product:price:amount", "og:price:amount"]:
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            result.update(status="PASS",
                          detail=f"Price in meta ({prop}): {meta['content']}",
                          evidence=f"meta: {meta['content']}")
            return result
    # 3. Currency-prefixed price in HTML
    hits = re.findall(
        r'(?:Rs\.?\s*|INR\s*|[₹$£€])\s*[\d,]+(?:\.\d{1,2})?',
        html[:60000]
    )
    if hits:
        result.update(status="PASS",
                      detail=f"Currency prices in HTML ({len(hits)}): {hits[:3]}",
                      evidence=str(hits[:5]))
        return result
    result.update(status="FAIL", detail="No price signal found on homepage")
    return result


def check_r16_refund_window(base_url):
    """R16 — concrete refund window in policy [CORRELATED - strongest signal]"""
    result = {"check": "R16", "tier": "CORRELATED",
              "status": "FAIL", "detail": "", "evidence": ""}
    paths = ["/policies/refund-policy", "/pages/returns",
             "/pages/refund-policy", "/pages/return-policy",
             "/refund-policy", "/returns"]
    resp = None
    for path in paths:
        r = safe_get(base_url.rstrip("/") + path)
        if r and r.status_code == 200:
            resp = r
            break
    if not resp:
        result["detail"] = "Refund policy page not found"
        return result
    text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ")
    result["evidence"] = text[:400]
    for pattern in RETURN_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result.update(status="PASS",
                          detail=f"Return window: '{m.group(0).strip()}'")
            return result
    result["detail"] = "Policy exists but no concrete timeframe extractable"
    return result


def check_r17_shipping_timeframe(base_url):
    """R17 — concrete shipping timeframe in policy [CORRELATED]"""
    result = {"check": "R17", "tier": "CORRELATED",
              "status": "FAIL", "detail": "", "evidence": ""}
    paths = ["/policies/shipping-policy", "/pages/shipping",
             "/pages/shipping-policy", "/pages/delivery",
             "/shipping", "/shipping-policy"]
    resp = None
    for path in paths:
        r = safe_get(base_url.rstrip("/") + path)
        if r and r.status_code == 200:
            resp = r
            break
    if not resp:
        result["detail"] = "Shipping policy page not found"
        return result
    text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ")
    result["evidence"] = text[:400]
    for pattern in SHIPPING_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result.update(status="PASS",
                          detail=f"Shipping timeframe: '{m.group(0).strip()}'")
            return result
    result["detail"] = "Policy exists but no concrete timeframe extractable"
    return result


def check_r25_brand_consistency(base_url, html_cache):
    """R25 — brand name consistency [CORRELATED - parsing bug fixed]"""
    result = {"check": "R25", "tier": "CORRELATED",
              "status": "FAIL", "detail": "", "evidence": ""}
    html = html_cache.get("homepage", "")
    if not html:
        result.update(status="UNKNOWN", detail="HTML unavailable")
        return result
    soup = BeautifulSoup(html, "html.parser")
    names = {}
    # 1. og:site_name — most reliable
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content", "").strip():
        names["og_site_name"] = og["content"].strip()
    # 2. schema.org Organization name
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        for item in data.get("json-ld", []):
            if item.get("@type") in ["Organization", "Store", "LocalBusiness", "WebSite"]:
                n = item.get("name", "").strip()
                if n and len(n) > 1:
                    names["schema_org"] = n
                    break
    except Exception:
        pass
    # 3. Footer copyright
    footer = soup.find("footer")
    if footer:
        m = re.search(
            r'[c\u00a9]\s*(?:\d{4}[-]?\d{0,4})?\s*([^\n\r,|]{3,50})',
            footer.get_text(), re.IGNORECASE
        )
        if m:
            candidate = m.group(1).strip(" .")
            if not re.match(r'all\s+rights|reserved|pvt|private|ltd', candidate, re.I):
                names["footer"] = candidate
    # 4. Title tag — last resort only
    if len(names) < 2:
        title = soup.find("title")
        if title:
            parts = re.split(r'[|\-]', title.text)
            brand_part = parts[-1].strip() if len(parts) > 1 else parts[0].strip()
            if not re.match(
                r'^(buy|shop|online|india|store|official|best|top|home|get)',
                brand_part, re.I
            ):
                names["title_fallback"] = brand_part
    result["evidence"] = str(names)
    if len(names) < 2:
        result.update(status="UNKNOWN",
                      detail=f"Only 1 brand source found — cannot assess: {names}")
        return result

    def normalize(s):
        s = re.sub(r'\b(pvt|ltd|llc|inc|co|store|shop|official|india|online)\b',
                   '', s, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', s).strip().lower()

    normed = {k: normalize(v) for k, v in names.items() if v}
    vals = list(normed.values())
    sims = [fuzz.ratio(vals[i], vals[j])
            for i in range(len(vals)) for j in range(i + 1, len(vals))]
    min_sim = min(sims) if sims else 100
    if min_sim >= 80:
        result.update(status="PASS",
                      detail=f"Consistent across {len(names)} sources (min {min_sim}%) — {names}")
    elif min_sim >= 55:
        result.update(status="WARN",
                      detail=f"Minor variation (min {min_sim}%) — {names}")
    else:
        result.update(status="FAIL",
                      detail=f"Inconsistent (min {min_sim}%) — {names}")
    return result


def check_r28_ucp(base_url):
    """R28 — UCP profile [FORWARD-LOOKING - not scored]"""
    result = {"check": "R28", "tier": "FORWARD-LOOKING",
              "status": "FORWARD-LOOKING", "detail": "", "evidence": ""}
    resp = safe_get(base_url.rstrip("/") + "/.well-known/ucp")
    if not resp or resp.status_code == 404:
        result["detail"] = "UCP not found (Shopify auto-provides when store enables it)"
        return result
    if resp.status_code == 200:
        try:
            data = resp.json()
            services = list(data.get("ucp", {}).get("services", {}).keys())
            result.update(status="PASS",
                          detail=f"UCP found. Services: {services or 'declared'}",
                          evidence=json.dumps(data)[:400])
        except Exception:
            result.update(status="WARN", detail="UCP endpoint exists but invalid JSON")
    else:
        result["detail"] = f"UCP returned HTTP {resp.status_code}"
    return result


def check_r30_acp_feed(base_url, html_cache):
    """R30 — ACP feed quality, Shopify only [VERIFIED for Shopify]"""
    result = {"check": "R30", "tier": "VERIFIED",
              "status": "UNKNOWN",
              "detail": "Not a Shopify store — ACP auto-enrollment does not apply",
              "evidence": ""}
    html = html_cache.get("homepage", "")
    if not html:
        result.update(status="UNKNOWN", detail="HTML unavailable")
        return result
    is_shopify = "cdn.shopify.com" in html or "myshopify.com" in html
    if not is_shopify:
        return result
    issues = []
    passes = []
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        products = [i for i in data.get("json-ld", []) if i.get("@type") == "Product"]
        if not products:
            soup = BeautifulSoup(html, "html.parser")
            og_type = soup.find("meta", property="og:type")
            if og_type and "product" in og_type.get("content", "").lower():
                passes.append("og:type=product")
            result.update(
                status="WARN",
                detail=(
                    "Shopify confirmed. No Product schema on homepage (normal). "
                    f"Re-run on a /products/ URL for full evaluation. Signals: {passes or 'none'}"
                ),
                evidence=f"Shopify=True, product_schema=False, signals={passes}"
            )
            return result
        for item in products:
            offers = item.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if item.get("name", "") and len(item.get("name", "").split()) >= 3:
                passes.append("descriptive title")
            else:
                issues.append("title too short")
            if any(item.get(f) for f in GTIN_FIELDS):
                passes.append("GTIN/MPN")
            else:
                issues.append("no GTIN/MPN")
            if offers.get("price"):
                passes.append("price in schema")
            else:
                issues.append("price missing")
            if offers.get("availability"):
                passes.append("availability declared")
            else:
                issues.append("availability missing")
        result["evidence"] = f"passes={passes} issues={issues}"
        if not issues:
            result.update(status="PASS", detail=f"Feed quality good: {passes}")
        elif len(passes) >= len(issues):
            result.update(status="WARN", detail=f"Partial — issues: {issues}")
        else:
            result.update(status="FAIL", detail=f"Feed issues: {issues}")
    except Exception as e:
        result.update(status="UNKNOWN", detail=f"Error: {e}")
    return result


def check_r31_gmc_homepage_signals(base_url, html_cache):
    """R31 — GMC homepage signals [CORRELATED - reframed for homepage]"""
    result = {"check": "R31", "tier": "CORRELATED",
              "status": "FAIL", "detail": "", "evidence": "",
              "note": "Reframed for homepage: GMC readiness signals"}
    html = html_cache.get("homepage", "")
    if not html:
        result.update(status="UNKNOWN", detail="HTML unavailable")
        return result
    soup = BeautifulSoup(html, "html.parser")
    signals = []
    missing = []
    # 1. Google site verification
    gsite = (soup.find("meta", attrs={"name": "google-site-verification"}) or
             soup.find("meta", attrs={"name": "google_site_verification"}))
    if gsite:
        signals.append("google-site-verification")
    else:
        missing.append("no google-site-verification")
    # 2. og:type product
    og_type = soup.find("meta", property="og:type")
    if og_type and "product" in og_type.get("content", "").lower():
        signals.append("og:type=product")
    else:
        missing.append("og:type not product")
    # 3. Currency-visible pricing
    hits = re.findall(
        r'(?:Rs\.?\s*|INR\s*|[₹$£€])\s*[\d,]+(?:\.\d{1,2})?',
        html[:60000]
    )
    if hits:
        signals.append(f"prices visible ({len(hits)})")
    else:
        missing.append("no currency pricing visible")
    # 4. Organization/WebSite schema
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        has_org = any(
            i.get("@type") in ["Organization", "WebSite", "Store", "LocalBusiness"]
            for i in data.get("json-ld", [])
        )
        if has_org:
            signals.append("Organization/WebSite schema")
        else:
            missing.append("no Org/WebSite schema")
    except Exception:
        missing.append("schema parse error")
    result["evidence"] = f"signals={signals} missing={missing}"
    ratio = len(signals) / (len(signals) + len(missing)) if (signals or missing) else 0
    if ratio >= 0.75:
        result.update(status="PASS",
                      detail=f"Strong GMC signals ({len(signals)}/4): {signals}")
    elif ratio >= 0.50:
        result.update(status="WARN",
                      detail=f"Partial GMC signals ({len(signals)}/4): {signals} | missing: {missing}")
    else:
        result.update(status="FAIL",
                      detail=f"Weak GMC signals ({len(signals)}/4) — missing: {missing}")
    return result


# ── RUNNER ────────────────────────────────────────────────────────────────────

def run_checks(store_url):
    parsed   = urlparse(store_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    print(f"\n{'='*60}")
    print(f"  Store: {store_url}")
    print(f"  Base:  {base_url}")
    print(f"{'='*60}")

    # Fetch homepage once
    html_cache = {}
    print("  Fetching homepage...", end=" ", flush=True)
    resp = safe_get(base_url)
    if resp and resp.status_code == 200:
        html_cache["homepage"] = resp.text
        print(f"OK ({len(resp.text):,} chars)")
    else:
        print(f"FAILED ({resp.status_code if resp else 'timeout'})")

    fns = {
        "R1":  lambda: check_r1_robots(base_url),
        "R3":  lambda: check_r3_sitemap(base_url),
        "R7":  lambda: check_r7_schema(base_url, html_cache),
        "R9":  lambda: check_r9_homepage_price_signal(base_url, html_cache),
        "R16": lambda: check_r16_refund_window(base_url),
        "R17": lambda: check_r17_shipping_timeframe(base_url),
        "R25": lambda: check_r25_brand_consistency(base_url, html_cache),
        "R28": lambda: check_r28_ucp(base_url),
        "R30": lambda: check_r30_acp_feed(base_url, html_cache),
        "R31": lambda: check_r31_gmc_homepage_signals(base_url, html_cache),
    }

    results = {}
    print()
    for name in ACTIVE_CHECKS:
        print(f"  {name}...", end=" ", flush=True)
        try:
            r = fns[name]()
            results[name] = r
            icon = STATUS_ICONS.get(r["status"], "❓")
            print(f"{icon} {r['status']}: {r['detail'][:70]}")
        except Exception as e:
            results[name] = {"check": name, "tier": "UNKNOWN",
                             "status": "ERROR", "detail": str(e), "evidence": ""}
            print(f"💥 ERROR: {e}")
        time.sleep(random.uniform(0.3, 0.6))

    return results


# ── SCORING ───────────────────────────────────────────────────────────────────

def score(checks):
    passes   = sum(1 for r in SCORED_CHECKS if checks.get(r, {}).get("status") == "PASS")
    warns    = sum(1 for r in SCORED_CHECKS if checks.get(r, {}).get("status") == "WARN")
    fails    = sum(1 for r in SCORED_CHECKS if checks.get(r, {}).get("status") == "FAIL")
    unknowns = sum(1 for r in SCORED_CHECKS
                   if checks.get(r, {}).get("status") in ["UNKNOWN", "ERROR"])
    effective = passes + (warns * 0.5)
    scoreable = len(SCORED_CHECKS) - unknowns
    rate      = round(effective / scoreable, 2) if scoreable > 0 else 0.0
    return {
        "pass_rate":      rate,
        "passes":         passes,
        "warns":          warns,
        "fails":          fails,
        "unknowns":       unknowns,
        "total_scored":   len(SCORED_CHECKS),
        "total_scoreable": scoreable,
        "r28_status":     checks.get("R28", {}).get("status", "N/A"),
        "verdict": (
            "VALIDATED" if rate >= 0.71 else
            "PARTIAL"   if rate >= 0.50 else
            "RETHINK"
        ),
    }


# ── REPORT ────────────────────────────────────────────────────────────────────

def build_report(store_url, label, checks, sc):
    lines = []
    sep = "=" * 65
    lines += [
        sep,
        f"AI REPRESENTATION OPTIMIZER — VALIDATION ({SCRIPT_VERSION})",
        f"Store:     {store_url}",
        f"Label:     {label or '—'}",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        sep,
        "",
        "CHECKPOINT RESULTS:",
    ]
    for name in ACTIVE_CHECKS:
        r    = checks.get(name, {})
        icon = STATUS_ICONS.get(r.get("status", "?"), "❓")
        tier = r.get("tier", "")
        lines.append(f"  {icon} {name:4s} [{tier:16s}] {r.get('detail', '')[:75]}")
        if r.get("note"):
            lines.append(f"            Note: {r['note']}")
    lines += [
        "",
        f"R28 (FORWARD-LOOKING, not scored): {sc['r28_status']}",
        "",
        f"SCORE:   {sc['passes']} PASS  {sc['warns']} WARN  "
        f"{sc['fails']} FAIL  {sc['unknowns']} UNKNOWN",
        f"RATE:    {sc['pass_rate']:.0%}  ({sc['passes']} + {sc['warns']}×0.5 "
        f"out of {sc['total_scoreable']} scoreable checks)",
        f"VERDICT: {sc['verdict']}",
        "",
        "REMOVED CHECKS (not run):",
    ]
    for code, reason in REMOVED_CHECKS.items():
        lines.append(f"  {code}: {reason[:100]}")
    return "\n".join(lines)


# ── SAVE ──────────────────────────────────────────────────────────────────────

def save_results(store_url, label, checks, sc, out_dir):
    domain = urlparse(store_url).netloc.replace(".", "_").replace("-", "_")
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Aggregate file — appends all runs
    agg_path = os.path.join(out_dir, "all_validations.json")
    existing = []
    if os.path.exists(agg_path):
        try:
            with open(agg_path) as f:
                existing = json.load(f)
        except Exception:
            existing = []

    entry = {
        "store_url":      store_url,
        "label":          label or "",
        "timestamp":      datetime.now().isoformat(),
        "script_version": SCRIPT_VERSION,
        "checks":         checks,
        "score":          sc,
    }
    existing.append(entry)
    with open(agg_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    # Per-run files
    json_path = os.path.join(out_dir, f"validation_results_{domain}_{ts}.json")
    txt_path  = os.path.join(out_dir, f"validation_report_{domain}_{ts}.txt")

    with open(json_path, "w") as f:
        json.dump(entry, f, indent=2, default=str)

    report = build_report(store_url, label, checks, sc)
    with open(txt_path, "w") as f:
        f.write(report)

    return json_path, txt_path, agg_path


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=f"AI Rep Optimizer Validation {SCRIPT_VERSION}"
    )
    parser.add_argument(
        "--store-url", required=True,
        help="Full store URL, e.g. https://wiselife.in"
    )
    parser.add_argument(
        "--label", default="",
        help="Optional label for this run, e.g. 'yoga mats - recommended by ChatGPT'"
    )
    parser.add_argument(
        "--out", default=None,
        help="Output directory (default: same directory as this script)"
    )
    args = parser.parse_args()

    store_url = args.store_url.strip()
    if not store_url.startswith("http"):
        store_url = "https://" + store_url

    out_dir = args.out or os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)

    # Run checks
    checks = run_checks(store_url)
    sc     = score(checks)

    # Print score
    print(f"\n{'─'*60}")
    print(f"  {sc['passes']}✅  {sc['warns']}⚠️   {sc['fails']}❌  {sc['unknowns']}❓")
    print(f"  Pass rate: {sc['pass_rate']:.0%}  →  {sc['verdict']}")
    print(f"  R28 (not scored): {sc['r28_status']}")
    print(f"{'─'*60}")

    # Save
    json_path, txt_path, agg_path = save_results(
        store_url, args.label, checks, sc, out_dir
    )

    # Print report
    print()
    print(build_report(store_url, args.label, checks, sc))

    print(f"\nFiles saved:")
    print(f"  {json_path}")
    print(f"  {txt_path}")
    print(f"  {agg_path}  ← all runs aggregated here")


if __name__ == "__main__":
    main()