"""
layer1/r3_r5_r6.py
───────────────────
R3 — sitemap.xml:     VERIFIED   0/1 binary
R5 — bot protection:  CORRELATED 0/1 binary
R6 — SSL valid:       VERIFIED   0/1 binary
"""

import re
import ssl
import socket
import logging
from urllib.parse import urlparse

from src.utils.fetcher import safe_get, jitter_sleep

logger = logging.getLogger(__name__)

# ── R3 — SITEMAP ─────────────────────────────────────────────────────────────

def check_r3(base_url: str) -> dict:
    """
    R3 — Does sitemap.xml exist and contain product URLs?
    """
    result = {
        "check": "R3", "tier": "VERIFIED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    fetch = safe_get(sitemap_url)

    if fetch.timed_out:
        result.update(status="UNKNOWN", detail="Timed out fetching sitemap.xml")
        return result

    if fetch.blocked:
        result.update(
            status="FAIL",
            detail=f"sitemap.xml blocked (HTTP {fetch.status_code})",
            fix="Ensure /sitemap.xml is publicly accessible.",
        )
        return result

    if not fetch.ok:
        result.update(
            status="FAIL",
            detail=f"sitemap.xml not found ({fetch.error})",
            fix=(
                "Add a sitemap.xml to your store root.\n"
                "Shopify: Settings → Search engine listing → Sitemap is auto-generated at /sitemap.xml\n"
                "Verify it is accessible at: " + sitemap_url
            ),
        )
        return result

    content = fetch.text[:10000]
    result["evidence"] = content[:400]

    # Check it looks like XML, not HTML error page
    if "<loc>" not in content and "<url>" not in content and "<sitemap>" not in content:
        result.update(
            status="WARN",
            score=0,
            detail="sitemap.xml found but appears malformed (no <loc> tags)",
            fix="Regenerate your sitemap. In Shopify: Online Store → Preferences → Resubmit sitemap.",
        )
        return result

    url_count   = content.count("<loc>")
    products    = len(re.findall(r"/products?/", content, re.I))
    collections = len(re.findall(r"/collections?/", content, re.I))

    result.update(
        status="PASS",
        score=1,
        detail=f"{url_count} URLs found | products: {products} | collections: {collections}",
    )
    return result


# ── R5 — BOT PROTECTION ───────────────────────────────────────────────────────

# Cloudflare / bot-protection fingerprints in HTML
_BOT_MARKERS = [
    "cf-ray",               # Cloudflare response header marker in HTML
    "cf_clearance",         # Cloudflare cookie challenge
    "just a moment",        # Cloudflare challenge page title
    "enable javascript",    # Bot challenge fallback text
    "captcha",
    "please wait",
    "ddos-guard",
    "perimeterx",
    "_pxhd",
]

_BOT_STATUS_CODES = {403, 429, 503}

def check_r5(base_url: str, homepage_fetch=None) -> dict:
    """
    R5 — Is the store blocking AI crawlers via bot protection?

    Checks for Cloudflare challenges, CAPTCHA, 403/429 responses.
    Uses homepage_fetch if already available (avoids duplicate request).
    """
    result = {
        "check": "R5", "tier": "CORRELATED",
        "status": "PASS", "score": 1,   # default pass — proven blocked = fail
        "detail": "", "evidence": "", "fix": "",
    }

    # Use already-fetched homepage if available
    if homepage_fetch is None:
        jitter_sleep()
        homepage_fetch = safe_get(base_url)

    html_lower = homepage_fetch.text.lower()[:20000]

    # Status code signals
    if homepage_fetch.status_code in _BOT_STATUS_CODES:
        result.update(
            status="FAIL",
            score=0,
            detail=f"Bot protection active — HTTP {homepage_fetch.status_code} on homepage",
            evidence=f"Status: {homepage_fetch.status_code}",
            fix=(
                "AI crawlers are being blocked by your bot protection.\n"
                "Cloudflare fix: Security → Bots → Allow verified bots\n"
                "Alternatively: Add known AI crawler IPs to your allowlist."
            ),
        )
        return result

    # HTML content signals
    triggered = [m for m in _BOT_MARKERS if m in html_lower]
    if triggered:
        result.update(
            status="WARN",
            score=0,
            detail=f"Possible bot challenge page detected — markers: {triggered}",
            evidence=str(triggered),
            fix=(
                "Cloudflare may be serving a challenge page to AI crawlers.\n"
                "Fix: Cloudflare Dashboard → Security → Bots → Bot Fight Mode → Disable or whitelist."
            ),
        )
        return result

    result.update(
        status="PASS",
        score=1,
        detail="No bot protection blocking detected",
    )
    return result


# ── R6 — SSL ─────────────────────────────────────────────────────────────────

def check_r6(base_url: str) -> dict:
    """
    R6 — Is the SSL certificate valid and not expired?
    """
    result = {
        "check": "R6", "tier": "VERIFIED",
        "status": "FAIL", "score": 0,
        "detail": "", "evidence": "", "fix": "",
    }

    parsed = urlparse(base_url)
    hostname = parsed.hostname

    # HTTP store — instant fail
    if parsed.scheme == "http":
        result.update(
            status="FAIL",
            detail="Store uses HTTP not HTTPS — SSL not configured",
            fix=(
                "Enable HTTPS on your store.\n"
                "Shopify: Online Store → Domains → Enable SSL certificate (free, automatic)."
            ),
        )
        return result

    # Verify SSL certificate
    try:
        ctx  = ssl.create_default_context()
        conn = ctx.wrap_socket(
            socket.create_connection((hostname, 443), timeout=8),
            server_hostname=hostname,
        )
        cert = conn.getpeercert()
        conn.close()

        result.update(
            status="PASS",
            score=1,
            detail=f"SSL valid for {hostname}",
            evidence=f"Subject: {cert.get('subject', 'N/A')}",
        )

    except ssl.SSLCertVerificationError as e:
        result.update(
            status="FAIL",
            detail=f"SSL certificate verification failed: {e}",
            fix="Renew or re-issue your SSL certificate. Shopify handles this automatically for managed domains.",
        )

    except ssl.SSLError as e:
        result.update(
            status="FAIL",
            detail=f"SSL error: {e}",
            fix="Contact your hosting provider to fix the SSL configuration.",
        )

    except (socket.timeout, OSError) as e:
        result.update(
            status="UNKNOWN",
            detail=f"Could not connect to check SSL: {e}",
        )

    return result
