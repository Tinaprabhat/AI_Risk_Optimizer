"""
layer4/r23_r25.py
──────────────────
R23 — Contact page exists + branded email:  CORRELATED  0/1 binary
R25 — Brand name consistent across sources: CORRELATED  0/1 binary
"""

import re
import logging

import extruct
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from src.utils.fetcher import safe_get, jitter_sleep

logger = logging.getLogger(__name__)

# ── R23 — CONTACT PAGE ────────────────────────────────────────────────────────

_CONTACT_PATHS = ["/pages/contact", "/pages/contact-us", "/contact", "/contact-us"]
_FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "rediffmail.com"}

def check_r23(base_url: str) -> dict:
    """
    R23 — Does a contact page exist with a branded (non-free) email address?

    PASS: Contact page exists + branded email (e.g. support@yourbrand.com)
    WARN: Contact page exists + free email (gmail/yahoo) — low trust signal
    FAIL: No contact page found
    """
    result = {
        "check": "R23", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    contact_text = None
    for path in _CONTACT_PATHS:
        jitter_sleep(0.4, 0.3)
        fetch = safe_get(base_url.rstrip("/") + path)
        if fetch.ok:
            soup = BeautifulSoup(fetch.text, "html.parser")
            contact_text = soup.get_text(separator=" ", strip=True)
            result["evidence"] = f"Found at {path}"
            break

    if not contact_text:
        result.update(
            status="FAIL", score=0,
            detail="No contact page found at standard paths",
            fix=(
                "Create a contact page at /pages/contact including:\n"
                "  • Branded email address (support@yourdomain.com)\n"
                "  • Response time commitment ('We reply within 24 hours')\n"
                "  • Optional: phone number, business address\n\n"
                "AI agents use contact pages to verify store accountability."
            ),
        )
        return result

    # Extract email addresses from page
    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', contact_text)

    if not emails:
        result.update(
            status="WARN", score=0,
            detail="Contact page exists but no email address found",
            fix=(
                "Add your email address to the contact page.\n"
                "Preferred: support@yourdomain.com\n"
                "Avoid: Gmail or Yahoo addresses — AI treats these as low trust signals."
            ),
        )
        return result

    # Check if any email is branded
    branded = [e for e in emails if e.split("@")[-1].lower() not in _FREE_EMAIL_DOMAINS]
    free    = [e for e in emails if e.split("@")[-1].lower() in _FREE_EMAIL_DOMAINS]

    if branded:
        result.update(
            status="PASS", score=1,
            detail=f"Contact page with branded email: {branded[0]}",
        )
    else:
        result.update(
            status="WARN", score=0,
            detail=f"Contact page has only free email: {free[0]} — low trust signal for AI",
            fix=(
                f"Replace {free[0]} with a branded email address.\n"
                f"Create support@yourdomain.com using Google Workspace, Zoho Mail (free), "
                f"or your hosting provider's email."
            ),
        )
    return result


# ── R25 — BRAND CONSISTENCY ───────────────────────────────────────────────────

_NOISE_WORDS = re.compile(
    r'\b(pvt|ltd|llc|inc|co|store|shop|official|india|online|the|and|of|by)\b',
    flags=re.IGNORECASE
)

def _normalize_brand(name: str) -> str:
    """Lowercase, strip legal suffixes and common noise words."""
    name = _NOISE_WORDS.sub("", name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name


def check_r25(base_url: str, html: str) -> dict:
    """
    R25 — Is the brand name consistent across all sources?

    Sources checked (in priority order):
      1. og:site_name meta tag  — most reliable
      2. schema.org Organization/Store name
      (Footer is excluded — regex too unreliable, see bug log)

    PASS: Both sources agree (fuzzy similarity ≥ 80%)
    WARN: Minor variation (60–79%)
    FAIL: Different names (< 60%)
    UNKNOWN: Only 1 source found — cannot compare
    """
    result = {
        "check": "R25", "tier": "CORRELATED",
        "status": "UNKNOWN", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    soup = BeautifulSoup(html, "html.parser")
    sources = {}

    # 1. og:site_name — most reliable source
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content", "").strip():
        sources["og_site_name"] = og["content"].strip()

    # 2. schema.org Organization/Store/WebSite name
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        for item in data.get("json-ld", []):
            t = item.get("@type", "")
            if t in ("Organization", "Store", "LocalBusiness", "WebSite"):
                name = item.get("name", "").strip()
                if name and len(name) > 1:
                    sources["schema_org"] = name
                    break
    except Exception as e:
        logger.debug(f"extruct error in R25: {e}")

    result["evidence"] = str(sources)

    if len(sources) < 2:
        result.update(
            status="UNKNOWN",
            detail=f"Only {len(sources)} brand source(s) found — cannot compare: {sources}",
            fix="Add og:site_name meta tag and schema.org Organization markup to your homepage.",
        )
        return result

    # Compare the two sources
    vals = list(sources.values())
    norm = [_normalize_brand(v) for v in vals]
    similarity = fuzz.ratio(norm[0], norm[1])

    if similarity >= 80:
        result.update(
            status="PASS", score=1,
            detail=f"Brand name consistent ({similarity}% match): {vals}",
        )
    elif similarity >= 60:
        result.update(
            status="WARN", score=0,
            detail=f"Minor brand variation ({similarity}% match): {vals}",
            fix=(
                f"Standardise your brand name across all sources.\n"
                f"Found: {vals}\n"
                f"Pick one canonical name and use it everywhere: og:site_name, schema.org, page title."
            ),
        )
    else:
        result.update(
            status="FAIL", score=0,
            detail=f"Inconsistent brand names ({similarity}% match): {vals}",
            fix=(
                f"AI sees your store as multiple different entities.\n"
                f"Found different names: {vals}\n"
                f"Fix: Use one consistent brand name in:\n"
                f"  1. og:site_name meta tag\n"
                f"  2. schema.org Organization name field\n"
                f"  3. Page title tags"
            ),
        )
    return result
