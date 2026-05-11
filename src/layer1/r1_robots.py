"""
layer1/r1_robots.py
───────────────────
R1 — robots.txt: are AI crawlers allowed?
Tier: VERIFIED
Score type: 0/1 binary

Logic:
  - Fetch /robots.txt
  - 404 → PASS (no robots.txt = allow all, per RFC)
  - 403 → BLOCKED (store is blocking crawlers)
  - Parse directives for 20+ known AI user-agents
  - Any Disallow: / or Disallow: /* for an AI agent = FAIL
"""

import logging
from urllib.robotparser import RobotFileParser
from io import StringIO

from src.utils.fetcher import safe_get, FetchResult

logger = logging.getLogger(__name__)

# All known AI crawler user-agents as of 2026
AI_CRAWLERS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "Claude-SearchBot", "anthropic-ai",
    "Google-Extended", "Gemini-Deep-Research",
    "PerplexityBot", "Perplexity-User",
    "Meta-ExternalAgent", "CCBot",
    "Applebot-Extended", "Bytespider",
    "cohere-ai", "YouBot", "PetalBot",
    "Amazonbot", "DuckDuckBot", "Diffbot",
]


def check(base_url: str) -> dict:
    """
    Run R1 — robots.txt check.

    Args:
        base_url: Store base URL e.g. https://example.com

    Returns:
        dict with keys: check, tier, status, score, detail, evidence, fix
    """
    robots_url = base_url.rstrip("/") + "/robots.txt"
    result = {
        "check":    "R1",
        "tier":     "VERIFIED",
        "status":   "FAIL",
        "score":    0,         # 0 or 1
        "detail":   "",
        "evidence": "",
        "fix":      "",
    }

    fetch = safe_get(robots_url)

    # ── 404: no robots.txt → allow all ──────────────────────────────────────
    if fetch.status_code == 404:
        result.update(
            status="PASS",
            score=1,
            detail="No robots.txt — all crawlers allowed by default (per RFC 9309)",
            evidence="HTTP 404 on /robots.txt",
            fix="",
        )
        return result

    # ── Store actively blocked us ────────────────────────────────────────────
    if fetch.blocked:
        result.update(
            status="FAIL",
            score=0,
            detail=f"Store blocked our fetch of robots.txt (HTTP {fetch.status_code})",
            evidence=fetch.error or "",
            fix="Ensure /robots.txt is publicly accessible. If behind Cloudflare, whitelist common user-agents.",
        )
        return result

    # ── Timeout ──────────────────────────────────────────────────────────────
    if fetch.timed_out:
        result.update(
            status="UNKNOWN",
            score=0,
            detail="Timed out fetching robots.txt — store may be slow or down",
            evidence="Timeout after 15s",
            fix="",
        )
        return result

    # ── Fetch failed for other reason ────────────────────────────────────────
    if not fetch.ok:
        result.update(
            status="UNKNOWN",
            score=0,
            detail=f"Could not fetch robots.txt: {fetch.error}",
            evidence=fetch.error or "",
            fix="",
        )
        return result

    # ── Parse robots.txt ─────────────────────────────────────────────────────
    content = fetch.text
    result["evidence"] = content[:800]

    blocked_agents = _parse_blocked_agents(content, robots_url)

    if blocked_agents:
        result.update(
            status="FAIL",
            score=0,
            detail=f"AI crawlers blocked: {', '.join(blocked_agents)}",
            fix=(
                "In your robots.txt, remove or modify the Disallow rules for AI agents.\n"
                "Minimum fix — add these lines to robots.txt:\n\n"
                "User-agent: GPTBot\nAllow: /\n\n"
                "User-agent: ClaudeBot\nAllow: /\n\n"
                "User-agent: Google-Extended\nAllow: /\n\n"
                "Full list of agents to allow: " + ", ".join(AI_CRAWLERS)
            ),
        )
    else:
        result.update(
            status="PASS",
            score=1,
            detail="No AI crawlers blocked in robots.txt",
            fix="",
        )

    return result


def _parse_blocked_agents(content: str, url: str) -> list[str]:
    """
    Parse robots.txt and return list of AI agents that are blocked from /.

    Uses Python's RobotFileParser for correctness, then cross-checks
    each AI agent against the parsed rules.
    """
    blocked = []

    # Use stdlib parser
    parser = RobotFileParser()
    parser.parse(content.splitlines())

    for agent in AI_CRAWLERS:
        # Check if the agent can access the root path
        if not parser.can_fetch(agent, "/"):
            blocked.append(agent)

    return list(set(blocked))  # deduplicate
