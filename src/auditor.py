"""
src/auditor.py
───────────────
Main audit orchestrator (v2.0 + domain profiles).

run_audit(..., profile="shopify" | "agency")

  shopify (default) — unchanged v2.0 behaviour: 16 commerce checkpoints.
  agency            — IT-services profile: 10 carried-over checks + R32 (llms.txt).

Both profiles produce the same `checks` dict shape, so Layer 6 (semantic gap),
Layer 7 (aggregation), the DB, the observability log and the UI are shared.

ALL original function signatures preserved for the shopify path:
  check_r1(base_url)
  check_r3(base_url)
  check_r5(base_url, homepage_fetch=homepage_fetch)
  check_r6(base_url)
  check_r7(base_url, homepage_html)
  check_r9(base_url, homepage_html)
  check_r11(base_url, homepage_html)
  check_r13(homepage_html)
  check_r15(semantic_data)
  check_r16(semantic_data)
  check_r17(semantic_data)
  check_r23(base_url)
  check_r25(semantic_data, homepage_html)
  check_r28(base_url, homepage_html)
  check_r30(base_url, homepage_html)
  check_r31(base_url, homepage_html)
"""

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.profiles                 import get_profile
from src.utils.fetcher            import safe_get, jitter_sleep
from src.utils.db                 import save_audit, load_audit
from src.utils.text_cleaner       import extract_clean_text, is_garbage
from src.utils.semantic_extractor import SemanticExtractor
from src.utils.obs_logger         import write_audit_log
from src.utils.observability      import ensure_observability

from src.layer1.r1_robots         import check as check_r1
from src.layer1.r3_r5_r6          import check_r3, check_r5, check_r6
from src.layer2.r7_r9_r11         import check_r7, check_r9, check_r11
from src.layer3.r13_r15_r16_r17   import check_r13, check_r15, check_r16, check_r17
from src.layer4.r23_r25           import check_r23, check_r25
from src.layer5.r28_r30_r31       import check_r28, check_r30, check_r31
from src.layer_agency.agency_checks import check_r32
from src.layer6.semantic_gap      import compute_gap
from src.layer7.aggregator        import compute_score, get_failed_checks, build_conclusion

logger = logging.getLogger(__name__)

# Page-path lookups for the agency profile (about / contact pages)
_AGENCY_ABOUT_PATHS   = ["/about", "/about-us", "/company", "/who-we-are"]
_AGENCY_CONTACT_PATHS = ["/contact", "/contact-us", "/get-in-touch"]


def run_audit(
    store_url:   str,
    free_text:   str,
    mcq:         dict,
    use_cache:   bool = True,
    progress_cb=None,
    profile:     str = "shopify",
) -> dict:
    """
    Run the full audit for a URL.

    Args:
        store_url:   Full URL e.g. "https://corridorseven.coffee"
        free_text:   Owner's free-text description
        mcq:         Dict of MCQ answers (keys defined by the profile)
        use_cache:   Return cached result if same URL+profile audited today
        progress_cb: Optional callback(step: str) for Streamlit progress bar
        profile:     "shopify" (default) or "agency"

    Returns:
        Full audit result dict.
    """
    prof = get_profile(profile)

    # Normalise URL
    if not store_url.startswith("http"):
        store_url = "https://" + store_url
    parsed   = urlparse(store_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Cache check
    if use_cache:
        cached = load_audit(store_url, prof.name)
        if cached:
            logger.info(f"Returning cached audit for {store_url} [{prof.name}]")
            return cached

    def _progress(msg: str):
        logger.info(msg)
        if progress_cb:
            progress_cb(msg)

    # ── Fetch homepage once ───────────────────────────────────────────────────
    _progress("Fetching homepage...")
    homepage_fetch = safe_get(base_url)
    homepage_html  = ""

    if homepage_fetch.ok:
        if is_garbage(homepage_fetch.text):
            logger.warning("Homepage looks Brotli-compressed or garbage — treating as empty.")
        else:
            homepage_html = homepage_fetch.text
    else:
        logger.warning(f"Homepage fetch failed: {homepage_fetch.status_code}")

    # Plain text for semantic gap
    page_texts = {"homepage": ""}
    if homepage_html:
        page_texts["homepage"] = extract_clean_text(homepage_html, max_chars=3000)

    if prof.name == "agency":
        checks, semantic_data = _run_agency(
            prof, base_url, homepage_fetch, homepage_html, page_texts, _progress)
    else:
        checks, semantic_data = _run_shopify(
            prof, base_url, homepage_fetch, homepage_html, page_texts, _progress)

    for _code, _res in checks.items():
        ensure_observability(_code, _res)

    # ── Layer 6 — Semantic Gap ────────────────────────────────────────────────
    _progress("Layer 6: Semantic gap analysis...")
    gap_result = compute_gap(
        free_text     = free_text,
        mcq           = mcq,
        page_texts    = page_texts,
        homepage_html = homepage_html,
        base_url      = base_url,
        profile       = prof,
    )
    checks["layer6"] = gap_result

    # ── Layer 7 — Aggregation ─────────────────────────────────────────────────
    _progress("Layer 7: Computing final score...")

    score         = compute_score(checks, prof)
    failed_checks = get_failed_checks(checks, prof)

    gap_summary     = gap_result.get("summary", "")
    merchant_intent = free_text + " " + " ".join(str(v) for v in mcq.values())
    conclusion_text, conclusion_source, obs_block = build_conclusion(
        checks, score, gap_summary, merchant_intent, gap_result, prof
    )

    final_result = {
        "profile":            prof.name,
        "store_url":          base_url,
        "score":              score,
        "failed_checks":      failed_checks,
        "failed":             failed_checks,
        "gap":                gap_result,
        "conclusion":         conclusion_text,
        "conclusion_source":  conclusion_source,
        "observability":      obs_block,
        "checks":             checks,
        "semantic_data":      semantic_data,
    }

    save_audit(base_url, parsed.netloc, final_result, prof.name)

    log_path = write_audit_log(
        store_url       = base_url,
        all_checks      = checks,
        score_info      = score,
        gap_result      = gap_result,
        conclusion      = conclusion_text,
        page_texts      = page_texts,
        merchant_intent = merchant_intent,
        mcq             = mcq,
        profile         = prof.name,
    )
    final_result["log_path"] = log_path

    _progress("Audit complete.")
    return final_result


# ═════════════════════════════════════════════════════════════════════════════
# SHOPIFY PROFILE — v2.0 flow, unchanged
# ═════════════════════════════════════════════════════════════════════════════

def _run_shopify(prof, base_url, homepage_fetch, homepage_html, page_texts, _progress):
    # ── Layer 1 — Crawlability ────────────────────────────────────────────────
    _progress("Layer 1: Crawlability...")
    jitter_sleep()
    r1 = check_r1(base_url)
    jitter_sleep()
    r3 = check_r3(base_url)
    r5 = check_r5(base_url, homepage_fetch=homepage_fetch)
    r6 = check_r6(base_url)

    # ── Layer 2 — Structured Data ─────────────────────────────────────────────
    _progress("Layer 2: Structured data...")
    r7  = check_r7(homepage_html)
    r11 = check_r11(homepage_html)

    # ── v2.0: Semantic Extraction ─────────────────────────────────────────────
    # Runs after Layer 2 so schema_data from r7 is available.
    _progress("Semantic extraction (v2.0)...")
    schema_org    = r7.get("schema_data", [])
    extractor     = SemanticExtractor()
    semantic_data = extractor.extract(base_url, homepage_html, schema_org)
    logger.info(
        f"Extraction done — confidence: {semantic_data['extraction_confidence']}, "
        f"pages: {semantic_data['pages_crawled']}"
    )

    # R9 runs after semantic extraction so price data is available
    r9 = check_r9(homepage_html, semantic_data=semantic_data)

    # Fetch one product page for R13 vagueness check
    product_text = ""
    product_urls = r3.get("product_urls", [])
    if product_urls:
        jitter_sleep(0.4, 0.3)
        p = safe_get(product_urls[0])
        if p.ok and not is_garbage(p.text):
            product_text = extract_clean_text(p.text, max_chars=3000)

    # ── Layer 3 — Semantic Content ────────────────────────────────────────────
    _progress("Layer 3: Semantic content...")
    r13 = check_r13(page_texts["homepage"], product_text)

    # R15/R16/R17 now receive semantic_data (v2.0)
    r15 = check_r15(semantic_data)
    r16 = check_r16(semantic_data)
    r17 = check_r17(semantic_data)

    # Fetch about + policy pages for semantic gap (same as v1)
    _progress("Fetching additional pages for semantic analysis...")
    for path in ["/pages/about", "/pages/about-us"]:
        if not page_texts.get("about"):
            jitter_sleep(0.4, 0.3)
            f = safe_get(base_url.rstrip("/") + path)
            if f.ok and not is_garbage(f.text):
                page_texts["about"] = extract_clean_text(f.text, max_chars=2000)

    combined_policy = ""
    for path in ["/policies/refund-policy", "/policies/shipping-policy"]:
        jitter_sleep(0.3, 0.2)
        f = safe_get(base_url.rstrip("/") + path)
        if f.ok and not is_garbage(f.text):
            combined_policy += extract_clean_text(f.text, max_chars=1000) + " "
    if combined_policy:
        page_texts["policies"] = combined_policy

    # ── Layer 4 — Trust Signals ───────────────────────────────────────────────
    _progress("Layer 4: Trust signals...")
    contact_text = ""
    for path in ["/pages/contact", "/contact", "/pages/contact-us"]:
        jitter_sleep(0.3, 0.2)
        f = safe_get(base_url.rstrip("/") + path)
        if f.ok and not is_garbage(f.text):
            contact_text = extract_clean_text(f.text, max_chars=2000)
            break
    r23 = check_r23(contact_text)
    r25 = check_r25(semantic_data, homepage_html)

    # ── Layer 5 — AI-Era Protocols ────────────────────────────────────────────
    _progress("Layer 5: AI-era protocols...")
    jitter_sleep()
    r28 = check_r28(base_url, homepage_html)
    r30 = check_r30(base_url, homepage_html)
    r31 = check_r31(base_url, homepage_html)

    # Uppercase keys to match the profile's check codes
    checks = {
        "R1": r1, "R3": r3, "R5": r5, "R6": r6,
        "R7": r7, "R9": r9, "R11": r11,
        "R13": r13, "R15": r15, "R16": r16, "R17": r17,
        "R23": r23, "R25": r25,
        "R28": r28, "R30": r30, "R31": r31,
    }
    return checks, semantic_data


# ═════════════════════════════════════════════════════════════════════════════
# AGENCY PROFILE — IT-services discoverability
# ═════════════════════════════════════════════════════════════════════════════

def _fetch_text(base_url: str, paths: list, max_chars: int) -> str:
    for path in paths:
        jitter_sleep(0.3, 0.2)
        f = safe_get(base_url.rstrip("/") + path)
        if f.ok and not is_garbage(f.text):
            return extract_clean_text(f.text, max_chars=max_chars)
    return ""


def _run_agency(prof, base_url, homepage_fetch, homepage_html, page_texts, _progress):
    # ── Layer 1 — Crawlability ────────────────────────────────────────────────
    _progress("Layer 1: Crawlability...")
    jitter_sleep()
    r1 = check_r1(base_url)
    jitter_sleep()
    r3 = check_r3(base_url, profile_name="agency")
    r5 = check_r5(base_url, homepage_fetch=homepage_fetch)
    r6 = check_r6(base_url)

    # ── Layer 2 — Structured Data ─────────────────────────────────────────────
    _progress("Layer 2: Structured data...")
    r7  = check_r7(homepage_html, profile_name="agency")
    r11 = check_r11(homepage_html)

    # ── Semantic extraction ─
    _progress("Semantic extraction (agency pages)...")
    schema_org    = r7.get("schema_data", [])
    extractor     = SemanticExtractor()
    semantic_data = extractor.extract(
        base_url, homepage_html, schema_org,
        profile_name="agency",
    )
    logger.info(
        f"Agency extraction done — confidence: {semantic_data['extraction_confidence']}, "
        f"pages: {semantic_data['pages_crawled']}"
    )

    agency_texts = semantic_data.get("agency_page_texts", {})
    if agency_texts.get("services"):
        page_texts["services"] = agency_texts["services"]
    if agency_texts.get("portfolio"):
        page_texts["portfolio"] = agency_texts["portfolio"]

    # ── Layer 3 — Semantic Content ────────────────────────────────────────────
    _progress("Layer 3: Semantic content...")
    r13 = check_r13(page_texts["homepage"], page_texts.get("services", ""), profile_name="agency")
    r15 = check_r15(semantic_data, min_pass=prof.faq_min_pass)

    _progress("Fetching about page for semantic analysis...")
    about = _fetch_text(base_url, _AGENCY_ABOUT_PATHS, 2000)
    if about:
        page_texts["about"] = about

    # ── Layer 4 — Trust Signals ───────────────────────────────────────────────
    _progress("Layer 4: Trust signals...")
    contact_text = _fetch_text(base_url, _AGENCY_CONTACT_PATHS, 2000)
    r23 = check_r23(contact_text, intl_phone=True)
    r25 = check_r25(semantic_data, homepage_html)

    # ── Layer 5 — Agent-readiness (forward-looking, unscored) ─────────────────
    _progress("Layer 5: Agent-readiness...")
    jitter_sleep()
    r32 = check_r32(base_url)

    checks = {
        "R1": r1, "R3": r3, "R5": r5, "R6": r6,
        "R7": r7, "R11": r11,
        "R13": r13, "R15": r15,
        "R23": r23, "R25": r25,
        "R32": r32,
    }
    return checks, semantic_data
