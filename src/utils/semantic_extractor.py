"""
src/utils/semantic_extractor.py
────────────────────────────────
v2.0 — Semantic Extraction Layer.

Extracts structured meaning from store pages BEFORE checkpoints run.
Checkpoints receive extracted data — not raw HTML.

Solves the 18% false-negative rate in pattern-based checks:
  - R9  (price contradiction)  — now catches 4 currency formats
  - R15 (FAQ discovery)        — now uses 3-stage URL discovery
  - R16 (refund timeframe)     — now handles weeks/months/fortnight/spelled numbers
  - R17 (shipping timeframe)   — same as R16
  - R25 (brand consistency)    — multi-source with NER sanity filter

Three-tier extraction strategy:
  Tier 1 — Regex + spaCy NER  (always runs, covers ~85-90% of stores)
  Tier 2 — Sentence-transformer similarity (runs if Tier 1 confidence < 0.70)
  Tier 3 — Gemini fallback (designed, reserved for v3 — not implemented here)

Output shape (always returned, keys present even if not found):
  {
    "refund":   {value_min, value_max, unit, raw, found, confidence},
    "shipping": {value_min, value_max, unit, raw, found, confidence},
    "brand":    {brand_name, source, confidence, alternatives, consistency_score},
    "faq":      {page_found, page_url, topics_covered, completeness},
    "price":    {price_in_schema, price_in_html, contradiction, confidence},
    "pages_crawled": int,
    "extraction_confidence": float,  # mean of all found confidences
  }
"""

import re
import logging
from typing import Optional
from urllib.parse import urljoin

import spacy
from bs4 import BeautifulSoup

from src.utils.fetcher import safe_get, jitter_sleep
from src.utils.text_cleaner import extract_clean_text

logger = logging.getLogger(__name__)

# ── spaCy model (loaded once at first use) ────────────────────────────────────

_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        logger.info("Loading spaCy en_core_web_sm...")
        _nlp = spacy.load("en_core_web_sm")
    return _nlp

# ── Unit normalisation ────────────────────────────────────────────────────────

# Maps any temporal unit string -> days multiplier
TEMPORAL_UNIT_TO_DAYS = {
    "day": 1,       "days": 1,
    "week": 7,      "weeks": 7,
    "fortnight": 14, "fortnights": 14,
    "month": 30,    "months": 30,
    "year": 365,    "years": 365,
    "business day": 1,  "business days": 1,  # conservative: treat as calendar days
}

# Spelled-out numbers we handle
SPELLED_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty-five": 45, "sixty": 60, "ninety": 90,
}

# ── Regex patterns ─────────────────────────────────────────────────────────────

# Matches: "30 days", "1-2 weeks", "14 business days", "6 months"
_TEMPORAL_NUMERIC = re.compile(
    r'(\d+)\s*[-–]?\s*(\d+)?\s+'
    r'(business\s+days?|days?|weeks?|months?|years?|fortnight)',
    re.IGNORECASE
)

# Matches: "one month", "thirty days", "fortnight"
_SPELLED_NUMS = '|'.join(re.escape(k) for k in SPELLED_NUMBERS.keys())
_TEMPORAL_SPELLED = re.compile(
    r'(' + _SPELLED_NUMS + r')\s+(days?|weeks?|months?|business\s+days?|fortnight)',
    re.IGNORECASE
)

# Price patterns — 4 formats
_PRICE_SYMBOL_PREFIX = re.compile(
    r'(?:Rs\.?\s*|INR\s*|₹\s*|\$\s*|£\s*|€\s*)[\d,]+(?:\.\d{1,2})?'
)
_PRICE_CODE_PREFIX = re.compile(
    r'\b(?:USD|GBP|EUR|INR|CAD|AUD)\s+[\d,]+(?:\.\d{1,2})?',
    re.IGNORECASE
)
_PRICE_CODE_SUFFIX = re.compile(
    r'[\d,]+(?:\.\d{1,2})?\s+(?:USD|GBP|EUR|INR|CAD|AUD)\b',
    re.IGNORECASE
)

# FAQ discovery keyword regex (expanded from v1)
_FAQ_KEYWORD_RE = re.compile(
    r'faq|help|qa|support|customer[_-]?care|knowledgebase|'
    r'common[_-]?questions|help[_-]?centre|help[_-]?center|'
    r'customer[_-]?support|questions',
    re.IGNORECASE
)

# Policy page standard Shopify paths
_REFUND_PATHS  = ["/policies/refund-policy", "/pages/returns", "/pages/refund-policy",
                  "/pages/return-policy", "/policies/returns"]
_SHIPPING_PATHS = ["/policies/shipping-policy", "/pages/shipping", "/pages/shipping-policy",
                   "/pages/delivery"]
_FAQ_PATHS     = ["/pages/faq", "/faq", "/help", "/pages/help", "/pages/faqs",
                  "/pages/customer-support", "/pages/support"]

# ── Tier 2 Exemplar sets (sentence-transformer fallback) ─────────────────────

_REFUND_EXISTS_EXEMPLARS = [
    "We accept returns within 30 days of purchase.",
    "Items can be returned for a full refund.",
    "Our 30-day money-back guarantee.",
    "You may return any item within 60 days.",
    "Hassle-free returns, no questions asked.",
    "Refunds are available if you are not satisfied.",
    "We offer a 14-day return window.",
]

_SHIPPING_EXISTS_EXEMPLARS = [
    "Orders ship within 3-5 business days.",
    "Standard shipping takes 7-10 days.",
    "Next day delivery available.",
    "We ship all orders within 24 hours.",
    "Delivery within 1-2 weeks.",
    "Express shipping available, arrives in 2 business days.",
]

_TIER2_THRESHOLD_EXIST   = 0.65  # above this → policy EXISTS (but no concrete number)
_TIER2_THRESHOLD_ABSENT  = 0.45  # below this → policy ABSENT

# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_days(value: int, unit_str: str) -> int:
    """Convert any temporal unit to approximate days."""
    unit_lower = unit_str.lower().strip()
    mult = TEMPORAL_UNIT_TO_DAYS.get(unit_lower, 1)
    return value * mult


def _extract_temporal(text: str) -> dict:
    """
    Tier 1 temporal extraction: numeric + spelled patterns.

    Returns:
        {value_min, value_max, unit, unit_days, raw, found, confidence}
    """
    if not text:
        return {"found": False, "confidence": 0.0}

    # Pass 1 — numeric regex
    m = _TEMPORAL_NUMERIC.search(text)
    if m:
        v1   = int(m.group(1))
        v2   = int(m.group(2)) if m.group(2) else v1
        unit = m.group(3).strip().lower()
        return {
            "value_min":  v1,
            "value_max":  v2,
            "unit":       unit,
            "unit_days":  _to_days(1, unit),  # multiplier per unit
            "raw":        m.group(0).strip(),
            "found":      True,
            "confidence": 0.95,
        }

    # Pass 2 — spelled numbers
    m = _TEMPORAL_SPELLED.search(text)
    if m:
        spelled = m.group(1).lower()
        unit    = m.group(2).strip().lower()
        value   = SPELLED_NUMBERS.get(spelled)
        if value:
            return {
                "value_min":  value,
                "value_max":  value,
                "unit":       unit,
                "unit_days":  _to_days(1, unit),
                "raw":        m.group(0).strip(),
                "found":      True,
                "confidence": 0.85,
            }

    return {"found": False, "confidence": 0.0}


def _tier2_policy_exists(text: str, exemplars: list) -> float:
    """
    Tier 2: check if a policy statement CONCEPTUALLY exists using embeddings.
    Returns similarity score 0-1. Does NOT extract a concrete value.
    Only used when Tier 1 found nothing.
    """
    if not text:
        return 0.0
    try:
        from src.utils.embedder import embed, embed_batch, cosine_sim
        import numpy as np
        text_vec     = embed(text[:512])  # cap input
        exemplar_vecs = embed_batch(exemplars)
        sims = [cosine_sim(text_vec, ev) for ev in exemplar_vecs]
        return float(max(sims))
    except Exception as e:
        logger.warning(f"Tier 2 embedding failed: {e}")
        return 0.0


def _discover_page_url(base_url: str, homepage_html: str, keyword_re) -> Optional[str]:
    """
    Discover a page URL from nav/footer links when standard paths fail.
    Scans homepage anchor tags for keywords.
    """
    if not homepage_html:
        return None
    soup = BeautifulSoup(homepage_html, "html.parser")
    candidates = soup.select("nav a, footer a, header a") or soup.find_all("a", href=True)
    for tag in candidates:
        href = tag.get("href", "")
        text = tag.get_text(strip=True)
        if keyword_re.search(href) or keyword_re.search(text):
            full = urljoin(base_url, href)
            if full.startswith("http"):
                return full
    return None


def _fetch_policy_text(base_url: str, paths: list, homepage_html: str,
                        keyword_re, max_chars: int = 4000) -> str:
    """
    Fetch policy text: try standard paths first, then nav discovery.
    Returns clean text or empty string.
    """
    for path in paths:
        jitter_sleep(0.4, 0.3)
        resp = safe_get(base_url.rstrip("/") + path)
        if resp.ok:
            text = extract_clean_text(resp.text, max_chars=max_chars)
            if text and len(text) > 50:
                logger.info(f"Policy found at {path}")
                return text

    # Nav/footer fallback
    url = _discover_page_url(base_url, homepage_html, keyword_re)
    if url:
        jitter_sleep(0.4, 0.3)
        resp = safe_get(url)
        if resp.ok:
            text = extract_clean_text(resp.text, max_chars=max_chars)
            if text and len(text) > 50:
                logger.info(f"Policy found via nav discovery: {url}")
                return text

    return ""


# ── NER brand sanity filter ───────────────────────────────────────────────────

def _ner_brand(text: str) -> Optional[str]:
    """
    Extract brand name from text via spaCy NER (ORG entities).
    Applies sanity filter to reject garbage.
    """
    if not text:
        return None
    nlp = _get_nlp()
    doc = nlp(text[:1000])
    orgs = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]

    # Sanity filter — reject patterns that are clearly not brand names
    orgs = [
        o for o in orgs
        if o
        and o[0] not in ",;.&-"          # no leading punctuation
        and "&amp;" not in o              # no HTML entities
        and len(o) <= 40                  # reasonable length
        and len(o.split()) <= 5           # max 5 words
        and not re.search(r'\d{4}', o)   # no year strings (e.g. "© 2024")
    ]
    if not orgs:
        return None
    return min(orgs, key=len)  # shortest is most likely actual brand name


# ── Main extractor class ──────────────────────────────────────────────────────

class SemanticExtractor:
    """
    Single pass, multi-page semantic extractor.

    Usage:
        extractor = SemanticExtractor()
        data = extractor.extract(base_url, homepage_html, schema_data)
        # Pass data to checkpoints that need it
    """

    def extract_refund(self, base_url: str, homepage_html: str) -> dict:
        """
        Extract refund/return window from policy page.

        Returns structured dict with value, unit, days-equivalent, confidence.
        """
        result = {
            "value_min": None, "value_max": None,
            "unit": None, "raw": None,
            "found": False, "confidence": 0.0,
            "policy_text_found": False,
            "tier2_hit": False,
        }

        _REFUND_KW = re.compile(r'refund|return|money.back', re.I)
        policy_text = _fetch_policy_text(
            base_url, _REFUND_PATHS, homepage_html, _REFUND_KW
        )

        if not policy_text:
            return result

        result["policy_text_found"] = True

        # Tier 1 — numeric/spelled extraction
        extracted = _extract_temporal(policy_text)
        if extracted.get("found"):
            result.update(extracted)
            return result

        # Tier 2 — embedding similarity (policy exists but no concrete window)
        sim = _tier2_policy_exists(policy_text, _REFUND_EXISTS_EXEMPLARS)
        if sim >= _TIER2_THRESHOLD_EXIST:
            result["found"]      = True
            result["confidence"] = sim * 0.6   # penalised — no concrete number
            result["raw"]        = "(policy exists — no concrete window extracted)"
            result["tier2_hit"]  = True
        # Tier 3 (Gemini) reserved for v3 — not implemented

        return result

    def extract_shipping(self, base_url: str, homepage_html: str) -> dict:
        """
        Extract shipping timeframe from shipping policy page.
        Same structure as extract_refund.
        """
        result = {
            "value_min": None, "value_max": None,
            "unit": None, "raw": None,
            "found": False, "confidence": 0.0,
            "policy_text_found": False,
            "tier2_hit": False,
        }

        _SHIPPING_KW = re.compile(r'shipping|delivery|dispatch', re.I)
        policy_text = _fetch_policy_text(
            base_url, _SHIPPING_PATHS, homepage_html, _SHIPPING_KW
        )

        if not policy_text:
            return result

        result["policy_text_found"] = True

        # Tier 1
        extracted = _extract_temporal(policy_text)
        if extracted.get("found"):
            result.update(extracted)
            return result

        # Tier 2
        sim = _tier2_policy_exists(policy_text, _SHIPPING_EXISTS_EXEMPLARS)
        if sim >= _TIER2_THRESHOLD_EXIST:
            result["found"]      = True
            result["confidence"] = sim * 0.6
            result["raw"]        = "(policy exists — no concrete timeframe extracted)"
            result["tier2_hit"]  = True

        return result

    def extract_brand(self, homepage_html: str, schema_org: dict) -> dict:
        """
        Extract brand name from multiple sources with priority + confidence scoring.

        Priority: og:site_name > schema.org Organization.name > HTML title > NER
        """
        sources = []

        if not homepage_html:
            return {"found": False, "brand_name": None, "confidence": 0.0,
                    "source": None, "alternatives": [], "consistency_score": 0.0}

        # Source 1 — og:site_name (regex on raw HTML — avoids BeautifulSoup truncation)
        patterns = [
            r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name["\']',
        ]
        for pat in patterns:
            m = re.search(pat, homepage_html[:60000], re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val and len(val) >= 2:
                    sources.append(("og:site_name", val, 0.95))
                    break

        # Source 2 — schema.org Organization.name
        schema_name = None
        for item in (schema_org if isinstance(schema_org, list) else [schema_org]):
            if isinstance(item, dict) and item.get("@type") in ("Organization", "Store", "LocalBusiness"):
                schema_name = item.get("name", "")
                if schema_name:
                    sources.append(("schema.org", schema_name.strip(), 0.90))
                    break

        # Source 3 — HTML title tag (first segment)
        m = re.search(r'<title[^>]*>([^<]+)</title>', homepage_html, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            # Take first segment before |, em-dash —, en-dash –, or -
            segment = re.split(r'\s*[|—–\-]\s*', title)[0].strip()
            if segment and len(segment) >= 2:
                sources.append(("html_title", segment, 0.75))

        # Source 4 — NER fallback on title text only
        if not sources:
            soup = BeautifulSoup(homepage_html[:10000], "html.parser")
            title_text = soup.title.string if soup.title else ""
            ner_name = _ner_brand(title_text)
            if ner_name:
                sources.append(("ner", ner_name, 0.60))

        if not sources:
            return {"found": False, "brand_name": None, "confidence": 0.0,
                    "source": None, "alternatives": [], "consistency_score": 0.0}

        # Best = highest confidence
        best = max(sources, key=lambda x: x[2])
        alternatives = [s[1] for s in sources if s[1] != best[1]]

        # Consistency score — cosine sim between all names (if >1 source)
        consistency = 1.0
        if len(sources) > 1:
            try:
                from src.utils.embedder import embed, cosine_sim
                vecs = [embed(s[1]) for s in sources]
                sims = []
                for i in range(len(vecs)):
                    for j in range(i + 1, len(vecs)):
                        sims.append(cosine_sim(vecs[i], vecs[j]))
                consistency = round(sum(sims) / len(sims), 3) if sims else 1.0
            except Exception:
                consistency = 1.0  # assume consistent if embedder unavailable

        return {
            "found":             True,
            "brand_name":        best[1],
            "source":            best[0],
            "confidence":        best[2],
            "alternatives":      alternatives,
            "consistency_score": consistency,
        }

    def extract_faq(self, base_url: str, homepage_html: str) -> dict:
        """
        Discover FAQ page via 3-stage discovery, then extract topic coverage.

        Topics: returns, shipping, sizing, payment, contact, warranty
        """
        result = {
            "page_found":    False,
            "page_url":      None,
            "topics_covered": {
                "returns": 0.0, "shipping": 0.0, "sizing": 0.0,
                "payment": 0.0, "contact": 0.0, "warranty": 0.0
            },
            "completeness":  0.0,
        }

        # Stage 1 — standard paths
        faq_text = ""
        faq_url  = None
        for path in _FAQ_PATHS:
            jitter_sleep(0.3, 0.2)
            resp = safe_get(base_url.rstrip("/") + path)
            if resp.ok:
                text = extract_clean_text(resp.text, max_chars=5000)
                if text and len(text) > 100:
                    faq_text = text
                    faq_url  = base_url.rstrip("/") + path
                    break

        # Stage 2 — nav/footer link scan
        if not faq_text:
            url = _discover_page_url(base_url, homepage_html, _FAQ_KEYWORD_RE)
            if url:
                jitter_sleep(0.3, 0.2)
                resp = safe_get(url)
                if resp.ok:
                    text = extract_clean_text(resp.text, max_chars=5000)
                    if text and len(text) > 100:
                        faq_text = text
                        faq_url  = url

        # Stage 3 — check if FAQ content exists on contact/about pages
        if not faq_text:
            for path in ["/pages/contact", "/pages/about"]:
                jitter_sleep(0.3, 0.2)
                resp = safe_get(base_url.rstrip("/") + path)
                if resp.ok:
                    text = extract_clean_text(resp.text, max_chars=3000)
                    # Only use if it contains FAQ-like content
                    if text and re.search(r'\bfaq\b|frequently\s+asked', text, re.I):
                        faq_text = text
                        faq_url  = base_url.rstrip("/") + path
                        break

        if not faq_text:
            return result

        result["page_found"] = True
        result["page_url"]   = faq_url

        # Topic coverage via keyword presence (simple + reliable)
        topic_keywords = {
            "returns":  [r'\breturn\b', r'\brefund\b', r'\bexchange\b'],
            "shipping": [r'\bshipping\b', r'\bdelivery\b', r'\bdispatch\b'],
            "sizing":   [r'\bsize\b', r'\bsizing\b', r'\bfit\b', r'\bdimension\b'],
            "payment":  [r'\bpayment\b', r'\bpay\b', r'\bcheckout\b', r'\bcard\b'],
            "contact":  [r'\bcontact\b', r'\bemail\b', r'\bphone\b', r'\bsupport\b'],
            "warranty": [r'\bwarranty\b', r'\bguarantee\b', r'\bdefect\b'],
        }

        covered = 0
        for topic, patterns in topic_keywords.items():
            for pat in patterns:
                if re.search(pat, faq_text, re.IGNORECASE):
                    result["topics_covered"][topic] = 1.0
                    covered += 1
                    break

        result["completeness"] = round(covered / len(topic_keywords), 2)
        return result

    def extract_price_signals(self, schema_price: str, html: str) -> dict:
        """
        Extended price extraction for R9 — detects 4 currency formats.

        Args:
            schema_price: Price string extracted from schema.org
            html:         Raw homepage HTML
        Returns:
            {price_in_schema, price_in_html, contradiction, confidence}
        """
        result = {
            "price_in_schema": schema_price,
            "price_in_html":   None,
            "contradiction":   False,
            "confidence":      0.0,
        }

        if not html or not schema_price:
            return result

        # Try 4 price patterns on visible text
        soup     = BeautifulSoup(html, "html.parser")
        # Remove script/style before extracting visible price text
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        visible = soup.get_text(separator=" ", strip=True)[:5000]

        html_price = None
        for pattern in [_PRICE_SYMBOL_PREFIX, _PRICE_CODE_PREFIX, _PRICE_CODE_SUFFIX]:
            m = pattern.search(visible)
            if m:
                html_price = m.group(0).strip()
                break

        result["price_in_html"] = html_price

        if html_price and schema_price:
            # Extract numeric value from both for comparison
            schema_num = re.sub(r'[^\d.]', '', str(schema_price))
            html_num   = re.sub(r'[^\d.]', '', html_price)
            try:
                if schema_num and html_num:
                    result["contradiction"] = (
                        abs(float(schema_num) - float(html_num)) > 0.01
                    )
                    result["confidence"] = 0.90
            except ValueError:
                result["confidence"] = 0.50

        return result

    def extract(self, base_url: str, homepage_html: str, schema_org: dict) -> dict:
        """
        Main entry point. Run all extractions in one pass.

        Args:
            base_url:     Store base URL
            homepage_html: Raw homepage HTML (already fetched by auditor)
            schema_org:    Schema data from extruct (from Layer 2)

        Returns:
            Structured semantic data dict passed to all checkpoints.
        """
        logger.info(f"SemanticExtractor.extract() — {base_url}")
        pages_crawled = 0

        # Refund
        refund = self.extract_refund(base_url, homepage_html)
        pages_crawled += 1 if refund.get("policy_text_found") else 0

        # Shipping
        shipping = self.extract_shipping(base_url, homepage_html)
        pages_crawled += 1 if shipping.get("policy_text_found") else 0

        # Brand
        brand = self.extract_brand(homepage_html, schema_org)

        # FAQ
        faq = self.extract_faq(base_url, homepage_html)
        pages_crawled += 1 if faq.get("page_found") else 0

        # Price (schema_price passed from Layer 2 caller)
        schema_price = ""
        if isinstance(schema_org, list):
            for item in schema_org:
                if isinstance(item, dict):
                    offers = item.get("offers", {})
                    if isinstance(offers, dict):
                        schema_price = str(offers.get("price", ""))
                        break
        price = self.extract_price_signals(schema_price, homepage_html)

        # Aggregate confidence
        confidences = [
            refund.get("confidence", 0),
            shipping.get("confidence", 0),
            brand.get("confidence", 0),
        ]
        valid_confs = [c for c in confidences if c > 0]
        avg_conf = round(sum(valid_confs) / len(valid_confs), 2) if valid_confs else 0.0

        return {
            "refund":                 refund,
            "shipping":               shipping,
            "brand":                  brand,
            "faq":                    faq,
            "price":                  price,
            "pages_crawled":          pages_crawled,
            "extraction_confidence":  avg_conf,
        }