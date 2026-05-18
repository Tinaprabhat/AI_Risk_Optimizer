"""
layer3/r13_r15_r16_r17.py
──────────────────────────
R13 — Product description vagueness:  CORRELATED  0–10 scored
R15 — FAQ page coverage:              CORRELATED  0/1  binary
R16 — Refund window concrete:         CORRELATED  0–10 scored
R17 — Shipping timeframe concrete:    CORRELATED  0–10 scored
"""

import re
import logging
from typing import Optional

from bs4 import BeautifulSoup
try:
    from ..utils.text_cleaner import extract_clean_text, soup_to_clean_text
    from ..utils.fetcher import safe_get, jitter_sleep
    from ..utils.embedder import embed, cosine_sim, chunk_text, embed_batch
except ImportError:
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from src.utils.text_cleaner import extract_clean_text, soup_to_clean_text
    from src.utils.fetcher import safe_get, jitter_sleep
    from src.utils.embedder import embed, cosine_sim, chunk_text, embed_batch

logger = logging.getLogger(__name__)

# ── R13 — PRODUCT DESCRIPTION VAGUENESS ──────────────────────────────────────

# Exemplars for semantic comparison via embeddings
_VAGUE_EXEMPLARS = [
    "premium quality product",
    "best in class materials",
    "high quality craftsmanship",
    "superior performance",
    "excellent value for money",
]

_SPECIFIC_EXEMPLARS = [
    "made from 6061 aircraft-grade aluminium alloy, weighing 450g",
    "100% organic cotton, GOTS certified, 200 thread count",
    "compatible with iOS 14 and above, Bluetooth 5.0, 30-hour battery life",
    "hand-stitched full-grain vegetable-tanned leather, 2mm thickness",
    "dimensions 30cm × 20cm × 5cm, weight 1.2kg, waterproof IPX4",
]

# Pre-computed exemplar embeddings (computed on first call)
_vague_embeds   = None
_specific_embeds = None

def _get_exemplar_embeds():
    global _vague_embeds, _specific_embeds
    if _vague_embeds is None:
        _vague_embeds    = embed_batch(_VAGUE_EXEMPLARS)
        _specific_embeds = embed_batch(_SPECIFIC_EXEMPLARS)
    return _vague_embeds, _specific_embeds


def _vagueness_score(text: str) -> float:
    """
    Returns vagueness delta:
      positive = more vague than specific
      negative = more specific than vague
    Range roughly -1 to 1.
    """
    vague_e, specific_e = _get_exemplar_embeds()
    text_e = embed(chunk_text(text, max_sentences=5))

    sim_vague    = float(max(cosine_sim(text_e, v) for v in vague_e))
    sim_specific = float(max(cosine_sim(text_e, s) for s in specific_e))

    return sim_vague - sim_specific  # positive = vague


def check_r13(html: str) -> dict:
    """
    R13 — Are product descriptions specific or vague?

    Scoring (0–10):
      embedding similarity delta < -0.10  →  Specific (10)
      -0.10 to 0.05                       →  Mixed    (6)
      0.05 to 0.15                        →  Vague    (3)
      > 0.15                              →  Very vague (0)
    """
    result = {
        "check": "R13", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    if not html:
        result.update(status="UNKNOWN", detail="No HTML available")
        return result

    soup = BeautifulSoup(html, "html.parser")
    # Try to get product description text from common containers
    desc_candidates = (
        soup.find_all(class_=re.compile(r'product.desc|description|product-detail', re.I))
        or soup.find_all("p")
    )

    # Build a mini-soup from candidates and extract clean text (strips inline JSON/scripts)
    mini_soup = BeautifulSoup(
        "".join(
            str(el) for el in desc_candidates[:10]
            if len(el.get_text(strip=True)) > 20
        ),
        "html.parser",
    )
    desc_text = soup_to_clean_text(mini_soup, max_chars=1000)

    if len(desc_text.split()) < 10:
        result.update(
            status="UNKNOWN",
            detail="Could not extract product description text from homepage",
        )
        return result

    delta = _vagueness_score(desc_text)
    result["evidence"] = f"Vagueness delta: {delta:.3f} | Sample: {desc_text[:200]}"

    if delta < -0.10:
        score, status = 10, "PASS"
        detail = f"Descriptions are specific (delta={delta:.2f})"
        fix = ""
    elif delta < 0.05:
        score, status = 6, "WARN"
        detail = f"Descriptions are mixed — some specifics present (delta={delta:.2f})"
        fix = "Add concrete details: materials, dimensions, weight, compatibility, certifications."
    elif delta < 0.15:
        score, status = 3, "FAIL"
        detail = f"Descriptions are mostly vague (delta={delta:.2f})"
        fix = (
            "Replace vague adjectives with measurable facts.\n"
            "Instead of: 'premium quality materials'\n"
            "Write: 'made from 316L surgical stainless steel, 2mm thickness, weight 85g'\n\n"
            "AI cannot distinguish you from competitors without specific, factual descriptions."
        )
    else:
        score, status = 0, "FAIL"
        detail = f"Descriptions are very vague (delta={delta:.2f}) — AI cannot extract meaningful product facts"
        fix = (
            "Your descriptions contain almost no extractable facts.\n"
            "For each product, include at minimum:\n"
            "  • Material composition\n"
            "  • Dimensions or weight\n"
            "  • Key feature with a number (e.g. '500ml capacity', '30-day battery')\n"
            "  • Who it is for / use case"
        )

    result.update(status=status, score=score, detail=detail, fix=fix)
    return result


# ── R15 — FAQ COVERAGE ────────────────────────────────────────────────────────

_FAQ_TOPIC_CENTROIDS = [
    "returns and refunds policy",
    "shipping delivery time",
    "sizing guide fit",
    "payment methods accepted",
    "contact customer support",
    "warranty guarantee",
]

_FAQ_PATHS = [
    "/pages/faq", "/pages/faqs", "/pages/help", "/pages/help-centre",
    "/pages/help-center", "/pages/common-questions", "/pages/support",
    "/faq", "/faqs", "/help",
]

_FAQ_KW_RE = re.compile(
    r"\b(faq|faqs|help|questions?|support|help.?centre|help.?center|common.?questions?)\b",
    re.I,
)

def check_r15(base_url: str, homepage_html: str = "", sitemap_pages: str = "") -> dict:
    """
    R15 — Does an FAQ page exist and cover the main buyer topics?
    Binary: 1 if FAQ found with ≥3 topics covered, 0 otherwise.
    """
    result = {
        "check": "R15", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    # Try to find FAQ page — 3-stage discovery
    faq_text = None

    # Stage 1: standard paths
    for path in _FAQ_PATHS:
        jitter_sleep(0.4, 0.3)
        fetch = safe_get(base_url.rstrip("/") + path)
        if fetch.ok:
            faq_text = extract_clean_text(fetch.text, max_chars=3000)
            result["evidence"] = f"Found FAQ at {path}"
            break

    # Stage 2: nav/footer discovery
    if not faq_text and homepage_html:
        from urllib.parse import urljoin
        from bs4 import BeautifulSoup as _BS
        soup_h = _BS(homepage_html, "html.parser")
        for tag in soup_h.select("nav a, footer a, header a"):
            href = tag.get("href", "")
            txt  = tag.get_text(strip=True)
            if _FAQ_KW_RE.search(href) or _FAQ_KW_RE.search(txt):
                full = urljoin(base_url, href)
                if full.startswith("http") and full.rstrip("/") != base_url.rstrip("/"):
                    jitter_sleep(0.4, 0.3)
                    fetch = safe_get(full)
                    if fetch.ok:
                        faq_text = extract_clean_text(fetch.text, max_chars=3000)
                        result["evidence"] = f"Found FAQ via nav: {full}"
                        break

    # Stage 3: sitemap pages discovery
    if not faq_text and sitemap_pages:
        import re as _re
        locs = _re.findall(r"<loc>(.*?)</loc>", sitemap_pages, _re.I)
        for loc in locs:
            if _FAQ_KW_RE.search(loc):
                jitter_sleep(0.4, 0.3)
                fetch = safe_get(loc.strip())
                if fetch.ok:
                    faq_text = extract_clean_text(fetch.text, max_chars=3000)
                    result["evidence"] = f"Found FAQ via sitemap: {loc.strip()}"
                    break

    if not faq_text:
        result.update(
            status="FAIL",
            detail="No FAQ page found at standard paths, nav links, or sitemap",
            fix=(
                "Create a FAQ page at /pages/faq covering:\n"
                "1. Returns & refunds (include exact days)\n"
                "2. Shipping times by region\n"
                "3. Sizing / compatibility guide\n"
                "4. Payment methods\n"
                "5. How to contact support\n"
                "6. Warranty / guarantee terms\n\n"
                "AI agents use FAQ content to answer buyer questions directly.\n"
                "Missing FAQ = AI answers 'I don't know' when asked about your store policies."
            ),
        )
        return result

    # Check topic coverage via embedding similarity
    faq_embed    = embed(chunk_text(faq_text, 20))
    topic_embeds = embed_batch(_FAQ_TOPIC_CENTROIDS)

    covered   = []
    uncovered = []
    for topic, t_embed in zip(_FAQ_TOPIC_CENTROIDS, topic_embeds):
        sim = cosine_sim(faq_embed, t_embed)
        if sim >= 0.35:
            covered.append(topic)
        else:
            uncovered.append(topic)

    if len(covered) >= 4:
        result.update(
            status="PASS", score=1,
            detail=f"FAQ found, {len(covered)}/6 topics covered: {covered}",
        )
    elif len(covered) >= 2:
        result.update(
            status="WARN", score=0,
            detail=f"FAQ found but only {len(covered)}/6 topics covered",
            fix=f"Add content about: {uncovered}",
        )
    else:
        result.update(
            status="FAIL", score=0,
            detail=f"FAQ page thin — only {len(covered)}/6 topics covered",
            fix=f"Expand your FAQ to cover: {uncovered}",
        )

    return result


# ── SHARED PATTERN BANKS ──────────────────────────────────────────────────────

_RETURN_PATTERNS_EXACT = [
    # Days patterns
    r'\b(\d+)\s*[-–]?\s*day\s+(?:return|refund|exchange|money.?back)\b',
    r'\breturn(?:s)?\s+within\s+(\d+)\s+days?\b',
    r'\b(\d+)\s+days?\s+(?:return|refund|money.?back)\b',
    r'\bfree\s+returns?\s+(?:within\s+)?(\d+)\s+days?\b',
    r'\bwithin\s+(\d+)\s+days?\s+of\s+(?:purchase|delivery|order|receipt)\b',
    # Months patterns — e.g. "within 6 months", "eligible within 6 months"
    r'\b(?:eligible\s+)?within\s+(\d+)\s+months?\b',
    r'\b(\d+)\s+months?\s+(?:return|refund|money.?back|guarantee)\b',
    r'\b(\d+)\s*[-–]?\s*month\s+(?:return|refund|guarantee|money.?back)\b',
    # Weeks
    r'\b(\d+)\s+weeks?\s+(?:return|refund|money.?back)\b',
    r'\breturn(?:s)?\s+within\s+(\d+)\s+weeks?\b',
    # Named periods — "60 day money back", "30-day guarantee"
    r'\b(\d+)[\s-]*day\s+money[\s-]*back\b',
    r'\b(\d+)[\s-]*day\s+guarantee\b',
]
_RETURN_PATTERNS_VAGUE = [
    r'\breturns?\s+accepted\b',
    r'\bmoney.?back\s+guarantee\b',
    r'\brefundable\b',
    r'\beach\s+item\s+(?:can be|is)\s+returned\b',
    r'\brefund(?:s)?\s+(?:are\s+)?(?:available|accepted|processed)\b',
]

_SHIPPING_PATTERNS_EXACT = [
    r'\b(\d+)\s*[-–]\s*(\d+)\s*(?:business\s+)?days?\b',
    r'\bships?\s+(?:in|within)\s+(\d+)\s*[-–]?\s*(\d+)?\s*(?:business\s+)?days?\b',
    r'\b(next\s+day|same\s+day|overnight)\s+(?:shipping|delivery)\b',
    r'\bdelivered?\s+in\s+(\d+)\s*[-–]\s*(\d+)\s*(?:business\s+)?days?\b',
]
_SHIPPING_PATTERNS_VAGUE = [
    r'\bfast\s+shipping\b',
    r'\bquick\s+delivery\b',
    r'\bprompt\s+dispatch\b',
    r'\bshipped\s+soon\b',
]


# Headings that mark the START of actual policy content
_POLICY_HEADING_RE = re.compile(
    r'(refund|return|shipping|delivery|exchange|cancellation|warranty)\s*(policy|information|terms|details)?',
    re.IGNORECASE,
)

# Noise patterns that indicate we're still in nav/header/promo territory
_NAV_NOISE_RE = re.compile(
    r'(free\s+bowl|subscribers|limited\s+time|back\s+in\s+stock|new\s+arrivals|shop\s+all|build\s+your\s+own)',
    re.IGNORECASE,
)


def _extract_policy_body(html: str, max_chars: int = 5000) -> str:
    """
    Extract policy body text from a policy page HTML.

    Problem: Shopify stores use sticky announcement bars / promo divs that
    repeat throughout the page DOM. They are <div> tags, not <nav>/<header>,
    so tag-name stripping doesn't remove them. find_all_next(string=True)
    after a heading picks up ALL subsequent strings including these divs.

    Fix (3-stage):
      Stage 1: Find semantic content container — <main>, <article>,
               or any div with class containing 'policy','content','rte','body'.
               Extract ONLY from that container, ignoring everything outside.

      Stage 2: Within the container, find the policy heading and extract
               from that point forward, paragraph by paragraph.
               Skip any paragraph that looks like nav/promo noise.

      Stage 3: Fallback — if no container and no heading found, split on
               double-newline, filter noise lines, return cleaned body.
    """
    from bs4 import BeautifulSoup
    import re as _re

    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Always strip these
    for tag in soup(["script", "style", "noscript", "svg", "nav", "header", "footer"]):
        tag.decompose()

    # ── Stage 1: Find content container ──────────────────────────────────────
    container = None

    # Try semantic tags first
    container = soup.find("main") or soup.find("article")

    # Try Shopify/common CMS content div class names
    if not container:
        for cls in ["policy", "rte", "page-content", "content-body",
                    "article-body", "entry-content", "page__content",
                    "shopify-policy__body"]:
            container = soup.find(attrs={"class": _re.compile(cls, _re.I)})
            if container:
                break

    # Use full soup if no container found
    if not container:
        container = soup

    # ── Stage 2: Find policy heading within container ─────────────────────────
    for heading in container.find_all(["h1", "h2", "h3"]):
        heading_text = heading.get_text(strip=True)
        if not _POLICY_HEADING_RE.search(heading_text):
            continue

        # Walk siblings of the heading — collect paragraph/text blocks only
        parts = [heading_text]
        # Use parent of heading to walk siblings
        parent = heading.parent
        found_heading = False
        for child in parent.children:
            if child == heading:
                found_heading = True
                continue
            if not found_heading:
                continue
            if hasattr(child, "get_text"):
                block = child.get_text(separator=" ", strip=True)
            else:
                block = str(child).strip()

            if not block or len(block) < 3:
                continue
            # Skip repeated promo noise blocks
            if _NAV_NOISE_RE.search(block):
                continue
            # Stop if we hit another major section heading unrelated to policy
            parts.append(block)

        body = " ".join(parts)
        if len(body) > 100:   # meaningful content found
            return body[:max_chars]

    # Stage 3: Fallback - filter noise from container text
    full_text = container.get_text(separator=" ", strip=True)
    lines = [l.strip() for l in full_text.split("  ") if l.strip()]

    filtered = []
    policy_started = False
    for line in lines:
        if _POLICY_HEADING_RE.search(line):
            policy_started = True
            filtered.append(line)
            continue
        if not policy_started:
            continue
        # Skip repeating promo noise
        if _NAV_NOISE_RE.search(line):
            continue
        if len(line) < 4:
            continue
        filtered.append(line)

    if filtered:
        return " ".join(filtered)[:max_chars]

    # Last resort: return first max_chars of container text, noise included
    return container.get_text(separator=" ", strip=True)[:max_chars]


# Patterns that indicate a login wall / access denied page — not real policy content
_ACCESS_DENIED_RE = re.compile(
    r"\b(access\s+denied|invalid\s+password|password\s+required|"
    r"enable\s+customer\s+accounts|easylockdown|locked\s+down|"
    r"login\s+required|sign\s+in\s+to\s+view|members?\s+only)\b",
    re.IGNORECASE,
)

def _is_access_denied(text: str) -> bool:
    """Return True if the fetched page is a login wall, not real content."""
    return bool(_ACCESS_DENIED_RE.search(text[:2000]))


def _fetch_policy_text(base_url: str, paths: list[str]) -> Optional[str]:
    """
    Try a list of paths and return policy body text of first successful fetch.
    Uses _extract_policy_body() to skip nav/promo header noise.
    Detects and rejects login-wall / access-denied pages.
    """
    for path in paths:
        jitter_sleep(0.4, 0.3)
        fetch = safe_get(base_url.rstrip("/") + path)
        if fetch.ok:
            # Reject login walls — EasyLockdown, password-protected pages etc.
            if _is_access_denied(fetch.text):
                logger.warning(f"Access-denied page detected at {path} — skipping")
                continue
            text = _extract_policy_body(fetch.text, max_chars=5000)
            if text:
                return text
    return None


# ── R16 — REFUND WINDOW ───────────────────────────────────────────────────────

_REFUND_PATHS = [
    "/policies/refund-policy", "/pages/returns",
    "/pages/refund-policy",    "/pages/return-policy",
    "/refund-policy",          "/returns",
]

def check_r16(base_url: str) -> dict:
    """
    R16 — Does the refund policy state a concrete return window?

    Scoring (0–10):
      Exact days stated ('30 days'):      10
      Vague window ('few weeks'):          5
      Policy exists but totally vague:     2
      No policy page found:                0
    """
    result = {
        "check": "R16", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    policy_text = _fetch_policy_text(base_url, _REFUND_PATHS)

    if not policy_text:
        result.update(
            status="FAIL", score=0,
            detail="No refund/return policy page found",
            fix=(
                "Create a refund policy at /policies/refund-policy.\n"
                "Must include: exact number of days (e.g. '30 days from delivery').\n\n"
                "Template:\n"
                "'We accept returns within 30 days of delivery. Items must be unused "
                "and in original packaging. To initiate a return, contact us at [email].'"
            ),
        )
        return result

    result["evidence"] = policy_text[:400]

    # Check for exact timeframe
    for pattern in _RETURN_PATTERNS_EXACT:
        m = re.search(pattern, policy_text, re.IGNORECASE)
        if m:
            result.update(
                status="PASS", score=10,
                detail=f"Concrete return window found: '{m.group(0).strip()}'",
            )
            return result

    # Check for vague mention
    for pattern in _RETURN_PATTERNS_VAGUE:
        m = re.search(pattern, policy_text, re.IGNORECASE)
        if m:
            result.update(
                status="WARN", score=5,
                detail=f"Policy exists but no specific timeframe — found: '{m.group(0).strip()}'",
                fix=(
                    "Your policy mentions returns but no specific number of days.\n"
                    "Add an exact timeframe: 'within 30 days of delivery'.\n"
                    "AI agents cannot extract 'how many days to return' without a number."
                ),
            )
            return result

    # Policy exists but nothing useful
    result.update(
        status="FAIL", score=2,
        detail="Refund policy page exists but no return window is extractable",
        fix=(
            "Your policy page exists but AI cannot extract a return timeframe.\n"
            "Add clearly: 'Returns accepted within [NUMBER] days of delivery.'\n"
            "Make the number explicit — not 'a few weeks' or 'reasonable time'."
        ),
    )
    return result


# ── R17 — SHIPPING TIMEFRAME ─────────────────────────────────────────────────

_SHIPPING_PATHS = [
    "/policies/shipping-policy", "/pages/shipping",
    "/pages/shipping-policy",    "/pages/delivery",
    "/shipping",                 "/shipping-policy",
]

def check_r17(base_url: str) -> dict:
    """
    R17 — Does the shipping policy state a concrete timeframe?

    Scoring (0–10):
      Exact days range ('3–5 business days'):  10
      Single day count or named service:        7
      Vague ('fast shipping', 'ships soon'):    3
      No policy page found:                     0
    """
    result = {
        "check": "R17", "tier": "CORRELATED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    policy_text = _fetch_policy_text(base_url, _SHIPPING_PATHS)

    if not policy_text:
        result.update(
            status="FAIL", score=0,
            detail="No shipping policy page found",
            fix=(
                "Create a shipping policy at /policies/shipping-policy.\n"
                "Must include: exact delivery timeframe.\n\n"
                "Template:\n"
                "'We ship within 1–2 business days. Delivery typically takes "
                "3–5 business days within India. International orders: 7–14 business days.'"
            ),
        )
        return result

    result["evidence"] = policy_text[:400]

    # Check for exact range (best)
    for pattern in _SHIPPING_PATTERNS_EXACT:
        m = re.search(pattern, policy_text, re.IGNORECASE)
        if m:
            matched = m.group(0).strip()
            # Range is better than single day
            score = 10 if re.search(r'\d+\s*[-–]\s*\d+', matched) else 7
            result.update(
                status="PASS", score=score,
                detail=f"Shipping timeframe found: '{matched}'",
            )
            return result

    # Vague mention
    for pattern in _SHIPPING_PATTERNS_VAGUE:
        m = re.search(pattern, policy_text, re.IGNORECASE)
        if m:
            result.update(
                status="WARN", score=3,
                detail=f"Shipping page exists but timeframe is vague: '{m.group(0).strip()}'",
                fix=(
                    "Replace vague shipping language with exact days.\n"
                    "Instead of 'fast shipping' write: 'Ships in 1–2 business days, "
                    "delivered in 3–5 business days across India.'"
                ),
            )
            return result

    result.update(
        status="FAIL", score=2,
        detail="Shipping policy page exists but no timeframe extractable",
        fix=(
            "Add an explicit delivery timeframe to your shipping policy.\n"
            "Example: 'Orders are processed within 24 hours and delivered within "
            "3–7 business days depending on location.'"
        ),
    )
    return result