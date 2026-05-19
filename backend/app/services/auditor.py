"""
src/auditor.py  — v2
──────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1:
  - Observability block now assembled and stored in result
  - build_conclusion now receives gap_result (for obs block)
  - R30 passed through but not scored (aggregator handles)
  - Scoring denominator is now 69 (R30 removed from max)
"""

import re
import logging
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from backend.app.utils.fetcher      import safe_get, jitter_sleep, is_garbage
from backend.app.utils.obs_logger   import write_audit_log
from backend.app.utils.db           import save_audit, load_audit
from backend.app.utils.text_cleaner import extract_clean_text

from backend.app.layers.layer1.r1_robots        import check as check_r1
from backend.app.layers.layer1.r3_r5_r6         import check_r3, check_r5, check_r6
from backend.app.layers.layer2.r7_r9_r11        import check_r7, check_r9, check_r11
from backend.app.layers.layer3.r13_r15_r16_r17  import check_r13, check_r15, check_r16, check_r17
from backend.app.layers.layer4.r23_r25          import check_r23, check_r25
from backend.app.layers.layer5.r28_r30_r31      import check_r28, check_r30, check_r31
from backend.app.layers.layer6.semantic_gap     import compute_gap
from backend.app.layers.layer7.aggregator       import compute_score, get_failed_checks, build_conclusion

logger = logging.getLogger(__name__)

# ── PAGE URL DISCOVERY ────────────────────────────────────────────────────────

_ABOUT_KEYWORDS    = re.compile(r'\b(about|our[-_]?story|who[-_]?we[-_]?are|brand)\b', re.I)
_CONTACT_KEYWORDS  = re.compile(r'\b(contact|get[-_]?in[-_]?touch|reach[-_]?us|support)\b', re.I)
_POLICY_KEYWORDS   = re.compile(r'\b(refund|return|shipping|delivery)\b', re.I)


def _find_page_url(base_url: str, homepage_html: str, keyword_re) -> str | None:
    """
    Scan homepage nav/footer links for a URL matching keyword_re.
    Returns the first matching absolute URL, or None.
    Falls back to nav/footer <a> tags only — not full-page scan.
    """
    if not homepage_html:
        return None
    soup = BeautifulSoup(homepage_html, "html.parser")
    # Look in nav + footer first, then all links
    candidates = soup.select("nav a, footer a, header a") or soup.find_all("a", href=True)
    for tag in candidates:
        href = tag.get("href", "")
        text = tag.get_text(strip=True)
        if keyword_re.search(href) or keyword_re.search(text):
            full = urljoin(base_url, href)
            if full.startswith("http"):
                return full
    return None


def _fetch_page(base_url: str, standard_paths: list, homepage_html: str,
                keyword_re, max_chars: int) -> str:
    """
    Try standard paths first. If all 404, scan nav/footer links as fallback.
    Returns clean text or empty string.
    """
    for path in standard_paths:
        jitter_sleep(0.4, 0.3)
        f = safe_get(base_url.rstrip("/") + path)
        if f.ok:
            if is_garbage(f.text):
                logger.warning(f"Garbage response at {path} — skipping")
                continue
            return extract_clean_text(f.text, max_chars=max_chars)

    # Fallback: discover URL from nav/footer
    discovered = _find_page_url(base_url, homepage_html, keyword_re)
    if discovered and discovered != base_url:
        jitter_sleep(0.4, 0.3)
        f = safe_get(discovered)
        if f.ok:
            logger.info(f"Found via nav discovery: {discovered}")
            return extract_clean_text(f.text, max_chars=max_chars)
    return ""


def run_audit(
    store_url:   str,
    free_text:   str,
    mcq:         dict,
    use_cache:   bool = True,
    progress_cb=None,
) -> dict:
    """
    Run full audit. Returns result dict with checks, scores, gaps,
    conclusion, and observability block.
    """
    if not store_url.startswith("http"):
        store_url = "https://" + store_url
    parsed   = urlparse(store_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if use_cache:
        cached = load_audit(store_url)
        if cached:
            logger.info(f"CACHE HIT — returning cached result for {store_url}")
            return cached

    def _progress(msg: str):
        logger.info(msg)
        print(f"  ⚡ {msg}", flush=True)
        if progress_cb:
            progress_cb(msg)

    # ── Fetch homepage once ───────────────────────────────────────────────────
    _progress("Fetching homepage...")
    homepage_fetch = safe_get(base_url)
    homepage_html  = homepage_fetch.text if homepage_fetch.ok else ""

    # Garbage detection — if homepage is Brotli/compressed bytes decoded wrong, abort early
    if homepage_html and is_garbage(homepage_html):
        logger.error(f"GARBAGE DETECTED in homepage HTML for {base_url}. "
                     "Response is likely Brotli-compressed. Check fetcher Accept-Encoding.")
        homepage_html = ""  # treat as empty — prevents garbage from polluting embeddings

    page_texts = {"homepage": ""}
    if homepage_html:
        page_texts["homepage"] = extract_clean_text(homepage_html, max_chars=3000)

    # ── Layer 1 ───────────────────────────────────────────────────────────────
    _progress("Layer 1: Crawlability...")
    jitter_sleep()
    r1 = check_r1(base_url)
    jitter_sleep()
    r3 = check_r3(base_url)
    r5 = check_r5(base_url, homepage_fetch=homepage_fetch)
    r6 = check_r6(base_url)

    # ── Layer 2 ───────────────────────────────────────────────────────────────
    _progress("Layer 2: Structured data...")
    r7  = check_r7(base_url, homepage_html)
    r9  = check_r9(base_url, homepage_html)
    r11 = check_r11(base_url, homepage_html)

    # ── Layer 3 ───────────────────────────────────────────────────────────────
    _progress("Layer 3: Semantic content...")
    r13 = check_r13(homepage_html)
    jitter_sleep()
    r15 = check_r15(base_url)
    jitter_sleep()
    r16 = check_r16(base_url)
    jitter_sleep()
    r17 = check_r17(base_url)

    # Fetch about + policy pages for semantic gap — standard paths then nav discovery
    _progress("Fetching additional pages...")
    about_text = _fetch_page(
        base_url,
        standard_paths=["/pages/about", "/pages/about-us", "/about", "/about-us"],
        homepage_html=homepage_html,
        keyword_re=_ABOUT_KEYWORDS,
        max_chars=2000,
    )
    if about_text:
        page_texts["about"] = about_text

    policy_text = ""
    for paths, kw_re in [
        (["/policies/refund-policy", "/pages/returns", "/returns"], _POLICY_KEYWORDS),
        (["/policies/shipping-policy", "/pages/shipping", "/shipping"], _POLICY_KEYWORDS),
    ]:
        t = _fetch_page(base_url, paths, homepage_html, kw_re, max_chars=1000)
        if t:
            policy_text += t + " "
    if policy_text:
        page_texts["policies"] = policy_text

    # ── Layer 4 ───────────────────────────────────────────────────────────────
    _progress("Layer 4: Trust signals...")
    jitter_sleep()
    r23 = check_r23(base_url, homepage_html)
    r25 = check_r25(base_url, homepage_html)

    # ── Layer 5 ───────────────────────────────────────────────────────────────
    _progress("Layer 5: AI-era protocols...")
    jitter_sleep()
    r28 = check_r28(base_url, homepage_html)
    r30 = check_r30(base_url, homepage_html)   # informational only
    r31 = check_r31(base_url, homepage_html)

    # ── Layer 6 ───────────────────────────────────────────────────────────────
    _progress("Layer 6: Semantic gap analysis...")
    gap_result = compute_gap(
        free_text=free_text,
        mcq=mcq,
        page_texts=page_texts,
        homepage_html=homepage_html,
        base_url=base_url,
    )

    # ── Layer 7 ───────────────────────────────────────────────────────────────
    _progress("Layer 7: Scoring and conclusion...")
    all_checks = {
        "R1": r1,  "R3": r3,  "R5": r5,  "R6": r6,
        "R7": r7,  "R9": r9,  "R11": r11,
        "R13": r13, "R15": r15, "R16": r16, "R17": r17,
        "R23": r23, "R25": r25,
        "R28": r28, "R30": r30, "R31": r31,
    }

    score_info = compute_score(all_checks)
    failed     = get_failed_checks(all_checks)

    conclusion, llm_source, obs_block = build_conclusion(
        all_checks=all_checks,
        score_info=score_info,
        gap_summary=gap_result.get("summary", ""),
        merchant_intent=free_text,
        gap_result=gap_result,
    )

    result = {
        "store_url":      store_url,
        "base_url":       base_url,
        "free_text":      free_text,
        "mcq":            mcq,
        "checks":         all_checks,
        "gap":            gap_result,
        "score":          score_info,
        "failed":         failed,
        "conclusion":     conclusion,
        "llm_source":     llm_source,
        "observability":  obs_block,    # NEW: full observability block
    }

    # Write observability log to disk (logs/ directory)
    log_path = write_audit_log(
        store_url=store_url,
        all_checks=all_checks,
        score_info=score_info,
        gap_result=gap_result,
        conclusion=conclusion,
        page_texts=page_texts,
        merchant_intent=free_text,
        mcq=mcq,
    )
    result["log_path"] = log_path

    save_audit(store_url, free_text[:50], result)
    _progress("Audit complete.")
    return result