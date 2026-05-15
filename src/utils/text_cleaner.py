"""
utils/text_cleaner.py  — NEW in v2
──────────────────────────────────────────────────────────────────────────────
Central clean-text extractor used by ALL layers that call get_text().

Problem fixed:
  Modern Shopify/Next.js stores embed massive JSON blobs in <script> tags:
    window.__NUXT__ = {...}
    window.__INITIAL_STATE__ = {...}
    JSON.parse('...')
  BeautifulSoup's get_text() pulls this raw JS/JSON content as text,
  producing garbage characters in the semantic gap output and policy checks.

Solution:
  Strip <script>, <style>, <noscript>, <svg>, <path>, <template> tags
  BEFORE calling get_text(). Then collapse whitespace.

Usage (replaces all raw soup.get_text() calls):
  from src.utils.text_cleaner import extract_clean_text, soup_to_clean_text

  # From raw HTML string:
  text = extract_clean_text(html_string)

  # From existing BeautifulSoup object:
  text = soup_to_clean_text(soup)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import re
from bs4 import BeautifulSoup

# Tags whose content is never human-readable text
_STRIP_TAGS = [
    "script", "style", "noscript", "svg", "path",
    "template", "iframe", "canvas", "video", "audio",
]

# Regex to collapse whitespace
_WHITESPACE = re.compile(r"\s+")


def soup_to_clean_text(soup: BeautifulSoup, max_chars: int = 0) -> str:
    """
    Extract clean human-readable text from a BeautifulSoup object.
    Strips script/style/svg tags before extraction.

    Args:
        soup:      BeautifulSoup object (will be modified in place — pass a copy if needed)
        max_chars: If > 0, truncate output to this many characters.

    Returns:
        Clean plain text string.
    """
    # Decompose all non-text tags (modifies soup in place)
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = text.replace("\x00", "")          # strip null bytes that pass through BS4
    text = _WHITESPACE.sub(" ", text).strip()

    if max_chars > 0:
        text = text[:max_chars]

    return text


def extract_clean_text(html: str, max_chars: int = 0) -> str:
    """
    Parse HTML and extract clean text in one call.

    Args:
        html:      Raw HTML string.
        max_chars: If > 0, truncate output to this many characters.

    Returns:
        Clean plain text string.
    """
    if not html or not html.strip():
        return ""

    # Encode fix: ensure we have a proper string, not bytes
    if isinstance(html, bytes):
        try:
            html = html.decode("utf-8")
        except UnicodeDecodeError:
            html = html.decode("latin-1", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    return soup_to_clean_text(soup, max_chars=max_chars)