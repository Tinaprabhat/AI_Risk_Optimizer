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

from src.utils.fetcher      import safe_get, jitter_sleep, is_garbage
from src.utils.obs_logger   import write_audit_log
from src.utils.db           import save_audit, load_audit
from src.utils.text_cleaner import extract_clean_text
from src.layer3.r13_r15_r16_r17 import _extract_policy_body as _extract_body

from src.layer1.r1_robots        import check as check_r1
from src.layer1.r3_r5_r6         import check_r3, check_r5, check_r6
from src.layer2.r7_r9_r11        import check_r7, check_r9, check_r11
from src.layer3.r13_r15_r16_r17  import check_r13, check_r15, check_r16, check_r17
from src.layer4.r23_r25          import check_r23, check_r25
from src.layer5.r28_r30_r31      import check_r28, check_r30, check_r31
from src.layer6.semantic_gap     import compute_gap
from src.layer7.aggregator       import compute_score, get_failed_checks, build_conclusion

logger = logging.getLogger(__name__)

# ── PAGE URL DISCOVERY ────────────────────────────────────────────────────────

# ── KEYWORD REGEXES — expanded to cover real store URL patterns ──────────────

_ABOUT_KEYWORDS = re.compile(
    r'(about|our.?story|who.?we.?are|brand|mission|founders?|team|company)',
    re.I,
)
_CONTACT_KEYWORDS = re.compile(
    r'(contact|get.?in.?touch|reach.?us|support|help|customer.?service|talk.?to.?us)',
    re.I,
)
_POLICY_KEYWORDS = re.compile(
    r'(refund|return|shipping|delivery|exchange|cancellation)',
    re.I,
)
_FAQ_KEYWORDS = re.compile(
    r'(faq|faqs|help|questions?|support|help.?centre|help.?center|common.?questions?)',
    re.I,
)


def _discover_url_from_nav(base_url: str, homepage_html: str, keyword_re) -> str | None:
    """
    Scan homepage nav/footer/header links for URL matching keyword_re.
    Checks both href and link text.
    """
    if not homepage_html:
        return None
    soup = BeautifulSoup(homepage_html, "html.parser")
    candidates = soup.select("nav a, footer a, header a")
    if not candidates:
        candidates = soup.find_all("a", href=True)
    for tag in candidates:
        href = tag.get("href", "")
        text = tag.get_text(strip=True)
        if keyword_re.search(href) or keyword_re.search(text):
            full = urljoin(base_url, href)
            if full.startswith("http") and full.rstrip("/") != base_url.rstrip("/"):
                return full
    return None


def _discover_url_from_sitemap(base_url: str, sitemap_html: str, keyword_re) -> str | None:
    """
    Scan pages sitemap for URL matching keyword_re.
    Uses the already-fetched sitemap_pages content.
    """
    if not sitemap_html:
        return None
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap_html, re.I)
    for loc in locs:
        if keyword_re.search(loc):
            return loc.strip()
    return None


def _fetch_page(
    base_url: str,
    standard_paths: list,
    homepage_html: str,
    keyword_re,
    max_chars: int,
    sitemap_pages: str = "",
) -> str:
    """
    Fetch a page using 3-stage discovery:
      1. Standard hardcoded paths
      2. Nav/footer link scan
      3. Pages sitemap scan (if sitemap_pages provided)
    Returns clean text or empty string.
    """
    # Stage 1: standard paths
    for path in standard_paths:
        jitter_sleep(0.4, 0.3)
        f = safe_get(base_url.rstrip("/") + path)
        if f.ok:
            if is_garbage(f.text):
                logger.warning(f"Garbage response at {path} — skipping")
                continue
            return extract_clean_text(f.text, max_chars=max_chars)

    # Stage 2: nav/footer discovery
    discovered = _discover_url_from_nav(base_url, homepage_html, keyword_re)
    if discovered:
        jitter_sleep(0.4, 0.3)
        f = safe_get(discovered)
        if f.ok and not is_garbage(f.text):
            logger.info(f"Found via nav discovery: {discovered}")
            return extract_clean_text(f.text, max_chars=max_chars)

    # Stage 3: sitemap pages discovery
    if sitemap_pages:
        discovered = _discover_url_from_sitemap(base_url, sitemap_pages, keyword_re)
        if discovered:
            jitter_sleep(0.4, 0.3)
            f = safe_get(discovered)
            if f.ok and not is_garbage(f.text):
                logger.info(f"Found via sitemap discovery: {discovered}")
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
            logger.info(f"Cache hit for {store_url}")
            return cached

    def _progress(msg: str):
        logger.info(msg)
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

    # Fetch pages sitemap for URL discovery (used in page fetching below)
    _progress("Fetching pages sitemap for URL discovery...")
    sitemap_pages = ""
    try:
        sitemap_index_url = base_url.rstrip("/") + "/sitemap.xml"
        jitter_sleep(0.3, 0.2)
        idx = safe_get(sitemap_index_url)
        if idx.ok:
            locs = re.findall(r"<loc>(.*?)</loc>", idx.text, re.I)
            pages_sitemaps = [l for l in locs if "pages" in l.lower()]
            if pages_sitemaps:
                jitter_sleep(0.3, 0.2)
                pg = safe_get(pages_sitemaps[0])
                if pg.ok:
                    sitemap_pages = pg.text
                    logger.info(f"Pages sitemap fetched: {len(locs)} locs in index")
    except Exception as e:
        logger.debug(f"Sitemap pages fetch failed: {e}")

    # ── Layer 2 ───────────────────────────────────────────────────────────────
    _progress("Layer 2: Structured data...")
    r7  = check_r7(base_url, homepage_html)
    r9  = check_r9(base_url, homepage_html)
    r11 = check_r11(base_url, homepage_html)

    # ── Layer 3 ───────────────────────────────────────────────────────────────
    _progress("Layer 3: Semantic content...")
    r13 = check_r13(homepage_html)
    jitter_sleep()
    r15 = check_r15(base_url, homepage_html=homepage_html, sitemap_pages=sitemap_pages)
    jitter_sleep()
    r16 = check_r16(base_url)
    jitter_sleep()
    r17 = check_r17(base_url)

    # Fetch about + policy pages for semantic gap — standard paths then nav discovery
    _progress("Fetching additional pages...")
    about_text = _fetch_page(
        base_url,
        standard_paths=["/pages/about", "/pages/about-us", "/pages/our-story",
                        "/pages/about-us", "/about", "/about-us", "/our-story"],
        homepage_html=homepage_html,
        keyword_re=_ABOUT_KEYWORDS,
        max_chars=2000,
        sitemap_pages=sitemap_pages,
    )
    if about_text:
        about_body = _extract_body(about_text, max_chars=2000)
        page_texts["about"] = about_body if about_body else about_text

    policy_text = ""
    for paths, kw_re in [
        (["/policies/refund-policy", "/pages/returns", "/pages/return-policy", "/returns"], _POLICY_KEYWORDS),
        (["/policies/shipping-policy", "/pages/shipping", "/pages/shipping-policy", "/shipping"], _POLICY_KEYWORDS),
    ]:
        t = _fetch_page(base_url, paths, homepage_html, kw_re, max_chars=1000,
                        sitemap_pages=sitemap_pages)
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