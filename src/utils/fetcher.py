"""
utils/fetcher.py
────────────────
Central HTTP fetcher used by ALL layers.

Timeout strategy:
  connect=8s  — time to establish TCP connection
  read=15s    — time to receive first byte after connecting
  
  Why these values:
  - Cloudflare CDN (most Shopify stores) responds in <2s normally
  - Slow stores (Southeast Asia, shared hosting) can take 5–8s to connect
  - 15s read covers slow TTFB on large HTML pages
  - If a store blocks us: we get 403/429 immediately — not a timeout
  - We do NOT retry on timeout — if it times out twice, the store is either
    down or actively rate-limiting us. Log it and move on.

Retry logic:
  - Retry on: 429 (rate limit), 503 (overloaded), 504 (gateway timeout)
  - NO retry on: 403 (blocked), 404 (missing), 401 (auth required)
  - Max 3 attempts with exponential backoff: 0s → 2s → 8s + jitter
"""

import time
import random
import logging
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.exceptions import (
    ConnectionError as ReqConnectionError,
    Timeout,
    TooManyRedirects,
    SSLError,
)

logger = logging.getLogger(__name__)

# ── USER AGENT ─────────────────────────────────────────────────────────────
# Standard Chrome UA — avoids trivial bot detection while being honest
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# ── RETRY CONFIG ───────────────────────────────────────────────────────────
_RETRY_ON_STATUS   = {429, 503, 504}
_NO_RETRY_STATUS   = {400, 401, 403, 404, 410}
_BACKOFF_SECONDS   = [0, 2, 8]   # attempt 1 → immediate, 2 → 2s, 3 → 8s
_JITTER_MAX        = 0.8          # ±0.8s random jitter on each backoff

# ── TIMEOUT ────────────────────────────────────────────────────────────────
# Tuple: (connect_timeout, read_timeout)
_TIMEOUT = (8, 15)


class FetchResult:
    """Typed result returned by safe_get. Always check .ok before using .text."""

    def __init__(
        self,
        url: str,
        status_code: Optional[int],
        text: str,
        ok: bool,
        error: Optional[str],
        blocked: bool,
        timed_out: bool,
    ):
        self.url        = url
        self.status_code = status_code
        self.text       = text
        self.ok         = ok           # True only if 200
        self.error      = error        # human-readable error string
        self.blocked    = blocked      # True if 403/401 — store blocked us
        self.timed_out  = timed_out    # True if connect or read timed out


def safe_get(url: str, ua_override: Optional[str] = None) -> FetchResult:
    """
    Fetch a URL with retry logic, correct timeouts, and full error categorisation.

    Args:
        url:         Full URL to fetch.
        ua_override: Optional User-Agent string (used for R1 bot-specific checks).

    Returns:
        FetchResult — always returns, never raises.
    """
    headers = dict(_HEADERS)
    if ua_override:
        headers["User-Agent"] = ua_override

    last_error: Optional[str] = None
    last_status: Optional[int] = None

    for attempt, backoff in enumerate(_BACKOFF_SECONDS):
        # Apply backoff + jitter between retries
        if attempt > 0:
            sleep_time = backoff + random.uniform(0, _JITTER_MAX)
            logger.debug(f"Retry {attempt} for {url} — sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)

        try:
            resp = requests.get(
                url,
                headers=headers,
                timeout=_TIMEOUT,
                allow_redirects=True,
            )

            # Definitive block — do not retry
            if resp.status_code in _NO_RETRY_STATUS:
                blocked = resp.status_code in {401, 403}
                logger.warning(f"[{resp.status_code}] {url} — {'BLOCKED' if blocked else 'NOT FOUND'}")
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    text=resp.text[:500],  # small snippet for evidence
                    ok=False,
                    error=f"HTTP {resp.status_code}",
                    blocked=blocked,
                    timed_out=False,
                )

            # Success
            if resp.status_code == 200:
                return FetchResult(
                    url=url,
                    status_code=200,
                    text=resp.text,
                    ok=True,
                    error=None,
                    blocked=False,
                    timed_out=False,
                )

            # Retryable status
            if resp.status_code in _RETRY_ON_STATUS:
                last_status = resp.status_code
                last_error  = f"HTTP {resp.status_code} — retrying"
                logger.warning(f"[{resp.status_code}] {url} — will retry")
                continue

            # Any other status (301 without redirect, 500, etc.)
            last_status = resp.status_code
            last_error  = f"HTTP {resp.status_code}"
            logger.warning(f"[{resp.status_code}] {url}")

        except Timeout:
            # connect or read timed out — do NOT retry (see module docstring)
            logger.warning(f"TIMEOUT {url}")
            return FetchResult(
                url=url,
                status_code=None,
                text="",
                ok=False,
                error="Request timed out (connect=8s, read=15s)",
                blocked=False,
                timed_out=True,
            )

        except SSLError as e:
            # SSL failure is a definitive finding — no retry
            logger.warning(f"SSL ERROR {url}: {e}")
            return FetchResult(
                url=url,
                status_code=None,
                text="",
                ok=False,
                error=f"SSL error: {e}",
                blocked=False,
                timed_out=False,
            )

        except TooManyRedirects:
            logger.warning(f"TOO MANY REDIRECTS {url}")
            return FetchResult(
                url=url,
                status_code=None,
                text="",
                ok=False,
                error="Too many redirects",
                blocked=False,
                timed_out=False,
            )

        except ReqConnectionError as e:
            # DNS failure or connection refused — retryable
            last_error = f"Connection error: {e}"
            logger.warning(f"CONNECTION ERROR {url}: {e}")
            continue

        except Exception as e:
            last_error = f"Unexpected error: {e}"
            logger.error(f"UNEXPECTED {url}: {e}")
            continue

    # All retries exhausted
    return FetchResult(
        url=url,
        status_code=last_status,
        text="",
        ok=False,
        error=last_error or "All retries exhausted",
        blocked=False,
        timed_out=False,
    )


def jitter_sleep(base: float = 0.5, spread: float = 0.5) -> None:
    """Sleep for base ± spread seconds. Call between requests to same domain."""
    time.sleep(base + random.uniform(-spread, spread))
