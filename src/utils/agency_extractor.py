"""
src/utils/agency_extractor.py
──────────────────────────────
Page discovery for the "agency" profile (IT-services businesses).

Fetches the services and portfolio pages once so that:
  * R13 can judge how specific the service descriptions are, and
  * Layer 6 (semantic gap) has services / portfolio text to compare against intent.

No scoring heuristics live here (the earlier service / case-study / pricing /
testimonial extractors were discarded). Deterministic, no LLM calls.
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.utils.fetcher import safe_get, jitter_sleep
from src.utils.text_cleaner import is_garbage

logger = logging.getLogger(__name__)

SERVICES_PATHS  = ["/services", "/our-services", "/what-we-do", "/solutions"]
PORTFOLIO_PATHS = ["/portfolio", "/case-studies", "/work", "/our-work", "/projects"]

_SERVICES_NAV_RE  = re.compile(r"service|solution|what[-_ ]we[-_ ]do|capabilit", re.I)
_PORTFOLIO_NAV_RE = re.compile(r"portfolio|case[-_ ]?stud|our[-_ ]work|projects?|\bwork\b", re.I)


def _visible_text(html: str, limit: int = 20000) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:limit]


def _discover(base_url: str, homepage_html: str, nav_re) -> Optional[str]:
    """Find a same-site page URL from nav/header/footer links."""
    if not homepage_html:
        return None
    soup = BeautifulSoup(homepage_html, "html.parser")
    site = urlparse(base_url).netloc.replace("www.", "")
    for tag in soup.select("nav a, header a, footer a") or soup.find_all("a", href=True):
        href = tag.get("href", "") or ""
        text = tag.get_text(strip=True)
        if href.startswith(("#", "mailto:", "tel:")):
            continue
        path = urlparse(href).path
        if path in ("", "/"):
            continue
        if nav_re.search(path) or (len(text) < 30 and nav_re.search(text)):
            full = urljoin(base_url, href)
            if full.startswith("http") and urlparse(full).netloc.replace("www.", "") == site:
                return full
    return None


def fetch_first(base_url: str, paths: list, homepage_html: str, nav_re) -> tuple:
    """Return (url, html) for the first working standard path, else a nav-discovered page, else ("", "")."""
    for path in paths:
        jitter_sleep(0.3, 0.2)
        url = base_url.rstrip("/") + path
        r = safe_get(url)
        if r.ok and not is_garbage(r.text) and len(r.text) > 300:
            return url, r.text
    url = _discover(base_url, homepage_html, nav_re)
    if url:
        jitter_sleep(0.3, 0.2)
        r = safe_get(url)
        if r.ok and not is_garbage(r.text) and len(r.text) > 300:
            return url, r.text
    return "", ""


def extract_agency(base_url: str, homepage_html: str) -> dict:
    """Fetch the services and portfolio pages; return their URLs and cleaned text."""
    s_url, s_html = fetch_first(base_url, SERVICES_PATHS, homepage_html, _SERVICES_NAV_RE)
    p_url, p_html = fetch_first(base_url, PORTFOLIO_PATHS, homepage_html, _PORTFOLIO_NAV_RE)
    return {
        "pages": {"services": s_url, "portfolio": p_url},
        "page_texts": {
            "services":  _visible_text(s_html, 3000) if s_html else "",
            "portfolio": _visible_text(p_html, 3000) if p_html else "",
        },
    }
