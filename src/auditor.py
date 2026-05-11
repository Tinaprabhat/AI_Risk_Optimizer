"""
src/auditor.py
───────────────
Main audit orchestrator.

Runs all layers in sequence. Fetches homepage once and passes HTML to
all checks that need it — avoids redundant requests.

Sequential request pattern:
  - All requests to same domain are sequential + jittered (±0.5s)
  - No parallel requests to same domain (triggers Cloudflare bot protection)
  - Homepage fetched ONCE and reused across layers
"""

import logging
from typing import Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from src.utils.fetcher import safe_get, jitter_sleep
from src.utils.db import save_audit, load_audit

# Layer imports
from src.layer1.r1_robots      import check as check_r1
from src.layer1.r3_r5_r6       import check_r3, check_r5, check_r6
from src.layer2.r7_r9_r11      import check_r7, check_r9, check_r11
from src.layer3.r13_r15_r16_r17 import check_r13, check_r15, check_r16, check_r17
from src.layer4.r23_r25        import check_r23, check_r25
from src.layer5.r28_r30_r31    import check_r28, check_r30, check_r31
from src.layer6.semantic_gap   import compute_gap
from src.layer7.aggregator     import compute_score, get_failed_checks, build_conclusion

logger = logging.getLogger(__name__)


def run_audit(
    store_url:      str,
    free_text:      str,
    mcq:            dict,
    use_cache:      bool = True,
    progress_cb=None,   # optional callback(step: str) for Streamlit progress updates
) -> dict:
    """
    Run the full audit for a store URL.

    Args:
        store_url:   Full store URL e.g. https://wiselife.in
        free_text:   Merchant description of their store
        mcq:         Dict: {category, customer, differentiator, tone}
        use_cache:   Return cached result if audited today
        progress_cb: Optional callback(step_name) called before each layer

    Returns:
        Full audit result dict (also saved to SQLite)
    """
    # ── Normalise URL ─────────────────────────────────────────────────────────
    if not store_url.startswith("http"):
        store_url = "https://" + store_url
    parsed   = urlparse(store_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # ── Cache check ───────────────────────────────────────────────────────────
    if use_cache:
        cached = load_audit(store_url)
        if cached:
            logger.info(f"Returning cached audit for {store_url}")
            return cached

    def _progress(msg: str):
        logger.info(msg)
        if progress_cb:
            progress_cb(msg)

    # ── Fetch homepage once ───────────────────────────────────────────────────
    _progress("Fetching homepage...")
    homepage_fetch = safe_get(base_url)
    homepage_html  = homepage_fetch.text if homepage_fetch.ok else ""

    # Build plain text from homepage HTML for semantic gap
    page_texts = {"homepage": ""}
    if homepage_html:
        soup = BeautifulSoup(homepage_html, "html.parser")
        page_texts["homepage"] = soup.get_text(separator=" ", strip=True)[:3000]

    # ── Layer 1 — Crawlability ────────────────────────────────────────────────
    _progress("Layer 1: Crawlability...")

    jitter_sleep()
    r1  = check_r1(base_url)
    jitter_sleep()
    r3  = check_r3(base_url)
    r5  = check_r5(base_url, homepage_fetch=homepage_fetch)  # reuse homepage
    r6  = check_r6(base_url)

    # ── Layer 2 — Structured Data ─────────────────────────────────────────────
    _progress("Layer 2: Structured data...")

    r7  = check_r7(base_url, homepage_html)
    r9  = check_r9(base_url, homepage_html)
    r11 = check_r11(base_url, homepage_html)

    # ── Layer 3 — Semantic Content ────────────────────────────────────────────
    _progress("Layer 3: Semantic content...")

    r13 = check_r13(homepage_html)

    jitter_sleep()
    r15 = check_r15(base_url)

    jitter_sleep()
    r16 = check_r16(base_url)

    jitter_sleep()
    r17 = check_r17(base_url)

    # Try to fetch about + policy pages for semantic gap V2
    _progress("Fetching additional pages for semantic analysis...")
    for path, key in [("/pages/about", "about"), ("/pages/about-us", "about")]:
        if "about" not in page_texts or not page_texts.get("about"):
            jitter_sleep(0.4, 0.3)
            f = safe_get(base_url.rstrip("/") + path)
            if f.ok:
                s = BeautifulSoup(f.text, "html.parser")
                page_texts["about"] = s.get_text(separator=" ", strip=True)[:2000]

    # Policies text for semantic gap
    policy_pages = {
        "/policies/refund-policy": "policies",
        "/policies/shipping-policy": "policies",
    }
    combined_policy = ""
    for path in policy_pages:
        jitter_sleep(0.3, 0.2)
        f = safe_get(base_url.rstrip("/") + path)
        if f.ok:
            s = BeautifulSoup(f.text, "html.parser")
            combined_policy += s.get_text(separator=" ", strip=True)[:1000] + " "
    if combined_policy:
        page_texts["policies"] = combined_policy

    # ── Layer 4 — Trust Signals ───────────────────────────────────────────────
    _progress("Layer 4: Trust signals...")

    jitter_sleep()
    r23 = check_r23(base_url)
    r25 = check_r25(base_url, homepage_html)

    # ── Layer 5 — AI-Era Protocols ────────────────────────────────────────────
    _progress("Layer 5: AI-era protocols...")

    jitter_sleep()
    r28 = check_r28(base_url, homepage_html)
    r30 = check_r30(base_url, homepage_html)
    r31 = check_r31(base_url, homepage_html)

    # ── Layer 6 — Semantic Gap ────────────────────────────────────────────────
    _progress("Layer 6: Semantic gap analysis...")

    gap_result = compute_gap(
        free_text=free_text,
        mcq=mcq,
        page_texts=page_texts,
        homepage_html=homepage_html,
        base_url=base_url,
    )

    # ── Layer 7 — Aggregation ─────────────────────────────────────────────────
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

    conclusion, llm_source = build_conclusion(
        all_checks=all_checks,
        score_info=score_info,
        gap_summary=gap_result.get("summary", ""),
        merchant_intent=free_text,
        gap_result=gap_result,
    )

    # ── Assemble final result ─────────────────────────────────────────────────
    result = {
        "store_url":    store_url,
        "base_url":     base_url,
        "free_text":    free_text,
        "mcq":          mcq,
        "checks":       all_checks,
        "gap":          gap_result,
        "score":        score_info,
        "failed":       failed,
        "conclusion":   conclusion,
        "llm_source":   llm_source,
    }

    # Save to SQLite
    save_audit(store_url, free_text[:50], result)

    _progress("Audit complete.")
    return result
