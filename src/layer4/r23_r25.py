"""
layer4/r23_r25.py  — v2
──────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1:
  R25 — Added <title> tag as 3rd brand source (fallback)
       — Tightened normalization: strip punctuation + legal suffixes
       — WARN now scores 0.5 (partial credit) instead of 0
       — Observability trace added to every result
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import re
import logging

import extruct
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from src.utils.fetcher import safe_get, jitter_sleep
from src.utils.text_cleaner import extract_clean_text

logger = logging.getLogger(__name__)


# ── OBSERVABILITY HELPER ──────────────────────────────────────────────────────

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


# ── R23 — CONTACT PAGE ────────────────────────────────────────────────────────

_CONTACT_PATHS     = ["/pages/contact", "/pages/contact-us", "/contact", "/contact-us"]
_FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "rediffmail.com"}


_CONTACT_RE = re.compile(r"\b(contact|get[-_]?in[-_]?touch|support|reach[-_]?us)\b", re.I)


def check_r23(base_url: str, homepage_html: str = "") -> dict:
    result = {
        "check": "R23", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "", "observability": {},
    }

    contact_text = None
    found_path   = None

    # 1. Standard paths
    for path in _CONTACT_PATHS:
        jitter_sleep(0.4, 0.3)
        fetch = safe_get(base_url.rstrip("/") + path)
        if fetch.ok:
            contact_text = extract_clean_text(fetch.text)
            found_path   = path
            result["evidence"] = f"Found at {path}"
            break

    # 2. Nav/footer discovery fallback
    if not contact_text and homepage_html:
        from urllib.parse import urljoin
        soup_home = BeautifulSoup(homepage_html, "html.parser")
        for tag in soup_home.select("nav a, footer a, header a"):
            href = tag.get("href", "")
            text = tag.get_text(strip=True)
            if _CONTACT_RE.search(href) or _CONTACT_RE.search(text):
                full = urljoin(base_url, href)
                if full.startswith("http") and full != base_url:
                    jitter_sleep(0.4, 0.3)
                    fetch = safe_get(full)
                    if fetch.ok:
                        contact_text = extract_clean_text(fetch.text)
                        found_path   = full
                        result["evidence"] = f"Found via nav: {full}"
                        break

    if not contact_text:
        fix = (
            "Create a contact page at /pages/contact with:\n"
            "  • Branded email (support@yourdomain.com)\n"
            "  • Response time commitment\n"
            "AI agents use contact pages to verify store accountability."
        )
        result.update(
            status="FAIL", score=0,
            detail="No contact page found at standard paths",
            fix=fix,
            observability=_obs(
                "R23",
                raw_evidence=f"Tried: {_CONTACT_PATHS} — all 404/blocked",
                what_we_did="Sequential GET on standard contact URL paths.",
                what_AI_sees="AI cannot verify merchant accountability — no contact page.",
                status="FAIL", severity="MODERATE", fix=fix,
            ),
        )
        return result

    emails  = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', contact_text)
    branded = [e for e in emails if e.split("@")[-1].lower() not in _FREE_EMAIL_DOMAINS]
    free    = [e for e in emails if e.split("@")[-1].lower() in _FREE_EMAIL_DOMAINS]

    if not emails:
        fix = "Add branded email (support@yourdomain.com) to the contact page."
        result.update(
            status="WARN", score=0,
            detail="Contact page exists but no email found",
            fix=fix,
            observability=_obs(
                "R23",
                raw_evidence=f"Fetched {found_path} — no email pattern matched.",
                what_we_did="Regex for email addresses on contact page text.",
                what_AI_sees="AI sees a contact page but cannot extract accountability email.",
                status="WARN", severity="MODERATE", fix=fix,
            ),
        )
    elif branded:
        result.update(
            status="PASS", score=1,
            detail=f"Contact page with branded email: {branded[0]}",
            observability=_obs(
                "R23",
                raw_evidence=f"Fetched {found_path} — emails: {emails}",
                what_we_did="Classified email domain against free-provider blocklist.",
                what_AI_sees=f"AI sees branded email {branded[0]} — strong accountability signal.",
                status="PASS", severity="INFO", fix="",
            ),
        )
    else:
        fix = (
            f"Replace {free[0]} with a branded email.\n"
            f"Use Google Workspace or Zoho Mail (free) to get support@yourdomain.com."
        )
        result.update(
            status="WARN", score=0,
            detail=f"Contact page has free email only: {free[0]}",
            fix=fix,
            observability=_obs(
                "R23",
                raw_evidence=f"Fetched {found_path} — free emails: {free}",
                what_we_did="All emails matched free-provider blocklist.",
                what_AI_sees=f"AI sees {free[0]} — free email is low trust for a business.",
                status="WARN", severity="MODERATE", fix=fix,
            ),
        )
    return result


# ── R25 — BRAND CONSISTENCY ───────────────────────────────────────────────────

_NOISE = re.compile(
    r'\b(pvt|ltd|llc|inc|co|store|shop|official|india|online|the|and|of|by|us|uk)\b',
    flags=re.IGNORECASE,
)


def _normalize_brand(name: str) -> str:
    name = re.sub(r"[^\w\s]", "", name)   # strip punctuation first
    name = _NOISE.sub("", name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def _title_brand(soup: BeautifulSoup) -> str:
    """Extract brand from <title> — take first segment before separator."""
    tag = soup.find("title")
    if not tag or not tag.string:
        return ""
    raw   = tag.string.strip()
    parts = re.split(r"[–—|·\-]", raw)
    return parts[0].strip() if parts else ""


def check_r25(base_url: str, html: str) -> dict:
    """
    R25 — Brand name consistent across sources.

    Sources (priority):
      1. og:site_name
      2. schema.org Organization/Store/WebSite name
      3. <title> first segment  ← NEW in v2 (fallback)

    Scoring:
      PASS  = score 1   (similarity >= 80%)
      WARN  = score 0.5 (similarity 60–79%)  ← NEW in v2
      FAIL  = score 0   (similarity < 60%)
      UNKNOWN = score 0  (< 2 sources)
    """
    result = {
        "check": "R25", "tier": "CORRELATED",
        "status": "UNKNOWN", "score": 0,
        "detail": "", "evidence": "", "fix": "", "observability": {},
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    soup    = BeautifulSoup(html, "html.parser")
    sources = {}

    # 1. og:site_name
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content", "").strip():
        sources["og_site_name"] = og["content"].strip()

    # 2. schema.org name
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        for item in data.get("json-ld", []):
            if item.get("@type") in ("Organization", "Store", "LocalBusiness", "WebSite"):
                name = item.get("name", "").strip()
                if name and len(name) > 1:
                    sources["schema_org"] = name
                    break
    except Exception as e:
        logger.debug(f"extruct error R25: {e}")

    # 3. <title> fallback — only if still < 2 sources
    if len(sources) < 2:
        tb = _title_brand(soup)
        if tb and len(tb) > 1:
            sources["title_tag"] = tb

    raw_evidence = f"Brand sources found: {sources}"
    result["evidence"] = raw_evidence

    if len(sources) < 2:
        fix = "Add og:site_name meta tag and schema.org Organization markup to homepage."
        result.update(
            status="UNKNOWN",
            detail=f"Only {len(sources)} source(s) — cannot compare: {sources}",
            fix=fix,
            observability=_obs(
                "R25", raw_evidence=raw_evidence,
                what_we_did="Checked og:site_name, schema.org name, title tag. Found < 2.",
                what_AI_sees="AI cannot verify brand consistency — insufficient markup.",
                status="UNKNOWN", severity="MODERATE", fix=fix,
            ),
        )
        return result

    keys  = list(sources.keys())
    a, b  = sources[keys[0]], sources[keys[1]]
    na, nb = _normalize_brand(a), _normalize_brand(b)
    sim   = fuzz.ratio(na, nb)

    logic = (
        f"Compared '{keys[0]}'='{a}' (norm: '{na}') "
        f"vs '{keys[1]}'='{b}' (norm: '{nb}'). Fuzzy ratio={sim}%"
    )

    if sim >= 80:
        result.update(
            status="PASS", score=1,
            detail=f"Brand consistent ({sim}%): {list(sources.values())}",
            observability=_obs(
                "R25", raw_evidence=raw_evidence, what_we_did=logic,
                what_AI_sees=f"AI sees consistent brand '{a}' across sources.",
                status="PASS", severity="INFO", fix="",
            ),
        )
    elif sim >= 60:
        fix = (
            f"Minor brand variation detected.\n"
            f"Sources: {list(sources.values())}\n"
            f"Pick one canonical name and apply to og:site_name, schema.org, and title."
        )
        result.update(
            status="WARN", score=0.5,
            detail=f"Minor brand variation ({sim}%): {list(sources.values())}",
            fix=fix,
            observability=_obs(
                "R25", raw_evidence=raw_evidence, what_we_did=logic,
                what_AI_sees=f"AI may treat '{a}' and '{b}' as slightly different entities.",
                status="WARN", severity="MODERATE", fix=fix,
            ),
        )
    else:
        fix = (
            f"AI sees your store as multiple entities.\n"
            f"Found: {list(sources.values())}\n"
            f"Use one consistent name in: og:site_name, schema.org Organization, title tag."
        )
        result.update(
            status="FAIL", score=0,
            detail=f"Inconsistent brand names ({sim}%): {list(sources.values())}",
            fix=fix,
            observability=_obs(
                "R25", raw_evidence=raw_evidence, what_we_did=logic,
                what_AI_sees=f"AI cannot attribute products to a single brand — '{a}' vs '{b}'.",
                status="FAIL", severity="HIGH", fix=fix,
            ),
        )
    return result