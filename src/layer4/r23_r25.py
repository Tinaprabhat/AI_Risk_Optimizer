"""
src/layer4/r23_r25.py
──────────────────────
Layer 4 — Trust Signal checks.

v2.0 changes:
  R25 — check_r25() now receives semantic_data["brand"] from SemanticExtractor.
        No longer does its own og:site_name / schema / NER extraction.
        NER sanity filter lives in SemanticExtractor.
  R23 — unchanged (contact page detection).

v1.1 fixes retained:
  - Contact page fetches use extract_clean_text() (not raw get_text())
  - og:site_name regex fallback on raw HTML (BeautifulSoup truncation fix)
    — now handled entirely by SemanticExtractor for R25
"""

import re
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from src.utils.fetcher      import safe_get, jitter_sleep
from src.utils.text_cleaner import extract_clean_text, is_garbage

logger = logging.getLogger(__name__)

# ── R23 — Contact Page Presence ───────────────────────────────────────────────
# Unchanged from v1.

_CONTACT_PATHS = [
    "/pages/contact",
    "/contact",
    "/pages/contact-us",
    "/pages/help",
    "/help",
]

_CONTACT_NAV_RE = re.compile(
    r'\b(contact|get[-_\s]in[-_\s]touch|reach[-_\s]us|support|help)\b',
    re.IGNORECASE
)

_BRANDED_EMAIL_RE  = re.compile(r'\b[A-Za-z0-9._%+-]+@(?!gmail|yahoo|hotmail|outlook)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
_GMAIL_EMAIL_RE    = re.compile(r'\b[A-Za-z0-9._%+-]+@(?:gmail|yahoo|hotmail|outlook)\.[A-Za-z]{2,}\b')
_PHONE_RE          = re.compile(r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
_LIVE_CHAT_RE      = re.compile(r'tidio|intercom|gorgias|zendesk|crisp|tawk|livechat', re.IGNORECASE)


def check_r23(contact_text: str) -> dict:
    """
    R23 — Contact page presence and quality.

    Binary check: PASS = contact page found with at least one contact method.

    Args:
        contact_text: Cleaned text of contact page (from auditor._fetch_page).
                      Empty string if page not found.

    Returns:
        Standard check result dict (binary score 0/1).
    """
    result = {
        "check":    "R23",
        "status":   "FAIL",
        "score":    0,
        "detail":   "",
        "evidence": "",
    }

    if not contact_text or len(contact_text.strip()) < 30:
        result.update({
            "detail": "No contact page found. "
                       "AI cannot verify store accountability.",
        })
        return result

    has_branded_email = bool(_BRANDED_EMAIL_RE.search(contact_text))
    has_gmail_email   = bool(_GMAIL_EMAIL_RE.search(contact_text))
    has_phone         = bool(_PHONE_RE.search(contact_text))
    has_live_chat     = bool(_LIVE_CHAT_RE.search(contact_text))

    has_any_contact = has_branded_email or has_gmail_email or has_phone or has_live_chat

    if not has_any_contact:
        result.update({
            "status": "WARN",
            "score":  0,
            "detail": "Contact page found but no contact method detected "
                       "(no email, phone, or live chat).",
        })
        return result

    # Build detail
    signals = []
    if has_branded_email:
        signals.append("branded email")
    if has_gmail_email:
        signals.append("gmail/yahoo email (low trust signal)")
    if has_phone:
        signals.append("phone number")
    if has_live_chat:
        signals.append("live chat widget")

    warn_gmail = has_gmail_email and not has_branded_email

    result.update({
        "status":   "WARN" if warn_gmail else "PASS",
        "score":    1,
        "detail":   f"Contact page found with: {', '.join(signals)}." +
                    (" Consider adding a branded email for higher AI trust." if warn_gmail else ""),
        "evidence": f"Contact signals: {', '.join(signals)}",
    })

    return result


# ── R25 — Brand Name Consistency ──────────────────────────────────────────────
# v2.0: Receives semantic_data["brand"] — no own extraction logic.

_CONSISTENCY_PASS_THRESHOLD = 0.85   # cosine similarity between brand name sources
_MAX_VARIATIONS_PASS        = 2      # <= 2 distinct names = PASS


def check_r25(semantic_data: dict, homepage_html: str = "") -> dict:
    """
    R25 — Brand name consistency across sources.

    v2.0: Receives semantic_data["brand"] from SemanticExtractor.
    SemanticExtractor handles all og:site_name/schema/title/NER extraction
    including the BeautifulSoup truncation fix and NER sanity filter.

    Scores on:
      - consistency_score (cosine similarity between name sources)
      - number of distinct brand name variations found

    Args:
        semantic_data: Full semantic_data dict from SemanticExtractor.
        homepage_html: Raw homepage HTML (passed for logging only).

    Returns:
        Standard check result dict (binary score 0/1).
    """
    result = {
        "check":    "R25",
        "status":   "FAIL",
        "score":    0,
        "detail":   "",
        "evidence": "",
    }

    brand = semantic_data.get("brand", {})

    # No brand name found from any source
    if not brand.get("found") or not brand.get("brand_name"):
        result.update({
            "detail": "Brand name not detectable from any source "
                       "(og:site_name, schema.org, HTML title). "
                       "Add Organization schema and og:site_name meta tag.",
        })
        return result

    brand_name    = brand["brand_name"]
    source        = brand.get("source", "unknown")
    alternatives  = brand.get("alternatives", [])
    consistency   = brand.get("consistency_score", 1.0)
    confidence    = brand.get("confidence", 0.0)

    # Normalise: lowercase, strip punctuation for comparison
    def _norm(s: str) -> str:
        return re.sub(r'[^\w\s]', '', s.lower()).strip()

    all_names    = [brand_name] + alternatives
    norm_names   = [_norm(n) for n in all_names if n]
    unique_norms = list(dict.fromkeys(norm_names))  # deduplicate preserving order

    result["evidence"] = (
        f"Primary: '{brand_name}' (from {source}). "
        f"Alternatives: {alternatives or 'none'}. "
        f"Consistency score: {consistency:.2f}."
    )

    # Too many distinct variations
    if len(unique_norms) > _MAX_VARIATIONS_PASS:
        result.update({
            "status": "FAIL",
            "score":  0,
            "detail": f"Brand name appears as {len(unique_norms)} different variations: "
                       f"{', '.join(all_names[:4])}. "
                       "AI treats these as different entities. Pick one and use it everywhere.",
        })
        return result

    # Low consistency score (names are semantically different)
    if consistency < _CONSISTENCY_PASS_THRESHOLD and len(unique_norms) > 1:
        result.update({
            "status": "WARN",
            "score":  0,
            "detail": f"Brand name slightly inconsistent across sources "
                       f"(consistency={consistency:.2f}). "
                       f"Found: {', '.join(all_names[:3])}. "
                       "Ensure og:site_name, schema.org, and HTML title all use the same name.",
        })
        return result

    # PASS
    result.update({
        "status": "PASS",
        "score":  1,
        "detail": f"Brand name consistent: '{brand_name}' "
                   f"(confidence={confidence:.2f}, consistency={consistency:.2f}).",
    })

    return result