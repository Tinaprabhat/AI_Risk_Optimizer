"""
part2/fix_engine.py
────────────────────
Part 2 — Recommendation & Fix Engine

For each failed check:
  1. Hardcoded fix template (90% of fixes — deterministic, no LLM)
  2. Gemini (→ Ollama fallback) explains template + handles follow-up questions
  3. Conversation history stored in SQLite — resumable

Template lookup: TEMPLATES[check_code] → dict with steps and context
LLM scope rule: system prompt restricts Gemini/Ollama to current fix topic only
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import Optional

from src.utils.llm import call_llm
from src.utils.db import save_chat_message, load_chat_history, clear_chat_history

logger = logging.getLogger(__name__)

# ── HARDCODED FIX TEMPLATES ───────────────────────────────────────────────────

TEMPLATES = {
    "R1": {
        "title":   "Remove AI crawler blocks from robots.txt",
        "summary": "Your robots.txt is blocking AI agents from indexing your store. This means ChatGPT, Gemini, and Perplexity cannot see your products.",
        "steps": [
            "Open your robots.txt file (usually at yourstore.com/robots.txt)",
            "Find any 'Disallow: /' rules under AI user-agents (GPTBot, ClaudeBot, Google-Extended)",
            "Change 'Disallow: /' to 'Allow: /' for each AI agent",
            "Save the file and verify at yourstore.com/robots.txt",
        ],
        "template": (
            "# Add these lines to allow AI crawlers:\n"
            "User-agent: GPTBot\nAllow: /\n\n"
            "User-agent: ClaudeBot\nAllow: /\n\n"
            "User-agent: Google-Extended\nAllow: /\n\n"
            "User-agent: PerplexityBot\nAllow: /\n"
        ),
    },
    "R3": {
        "title":   "Fix or generate your sitemap.xml",
        "summary": "Your sitemap.xml is missing or malformed. AI crawlers use sitemaps to discover all your product pages.",
        "steps": [
            "In Shopify: go to Online Store → Preferences → scroll to 'Sitemap'",
            "Your sitemap is auto-generated at yourstore.com/sitemap.xml",
            "If it's missing, try: Settings → Search engine listing → regenerate",
            "Submit sitemap to Google Search Console for verification",
        ],
        "template": "Shopify auto-generates sitemap at: {store_url}/sitemap.xml",
    },
    "R5": {
        "title":   "Allow AI crawlers through bot protection",
        "summary": "Your Cloudflare or bot protection is blocking AI crawlers. They are treated the same as malicious bots.",
        "steps": [
            "Log into Cloudflare Dashboard",
            "Go to Security → Bots",
            "Enable 'Allow verified bots' option",
            "Alternatively: Create a WAF rule to allow specific AI user-agents",
        ],
        "template": (
            "Cloudflare WAF rule to allow AI crawlers:\n"
            "Field: User Agent\n"
            "Operator: contains\n"
            "Value: GPTBot OR ClaudeBot OR Google-Extended OR PerplexityBot\n"
            "Action: Allow"
        ),
    },
    "R6": {
        "title":   "Fix SSL certificate",
        "summary": "Your SSL certificate is invalid or expired. AI agents refuse to fetch stores with SSL errors.",
        "steps": [
            "In Shopify: go to Online Store → Domains",
            "Click on your domain → Enable SSL certificate",
            "Shopify provides free SSL — this should be automatic",
            "If on custom hosting: contact your provider to renew SSL",
        ],
        "template": "Shopify: Online Store → Domains → [your domain] → Enable SSL (free, automatic)",
    },
    "R7": {
        "title":   "Add schema.org Organization markup",
        "summary": "Your store has no schema.org Organization type. AI agents use this to understand who you are and what you sell.",
        "steps": [
            "Go to your Shopify theme editor: Online Store → Themes → Edit code",
            "Open theme.liquid (or layout/theme.liquid)",
            "Add the JSON-LD block inside the <head> tag",
            "Replace YOUR_STORE_NAME and YOUR_URL with actual values",
            "Save and verify at: https://validator.schema.org/",
        ],
        "template": (
            '<script type="application/ld+json">\n'
            '{\n'
            '  "@context": "https://schema.org",\n'
            '  "@type": "Organization",\n'
            '  "name": "YOUR_STORE_NAME",\n'
            '  "url": "YOUR_URL",\n'
            '  "description": "YOUR_1_SENTENCE_DESCRIPTION",\n'
            '  "contactPoint": {\n'
            '    "@type": "ContactPoint",\n'
            '    "email": "support@yourdomain.com",\n'
            '    "contactType": "customer service"\n'
            '  }\n'
            '}\n'
            '</script>'
        ),
    },
    "R9": {
        "title":   "Add price data to schema markup",
        "summary": "AI crawlers cannot find pricing information for your products. Price in schema is the strongest price signal.",
        "steps": [
            "Shopify auto-adds Product schema with price on product pages",
            "Check that your theme is not suppressing schema output",
            "For homepage: add og:product:price meta tag",
            "Verify on a product page at: https://validator.schema.org/",
        ],
        "template": (
            "Add to product page <head>:\n"
            '<meta property="og:price:amount" content="PRICE_HERE">\n'
            '<meta property="og:price:currency" content="INR">'
        ),
    },
    "R11": {
        "title":   "Fix malformed JSON-LD blocks",
        "summary": "Your JSON-LD schema has syntax errors. Malformed JSON-LD is silently ignored by all crawlers — the data does not exist for AI purposes.",
        "steps": [
            "Open your page source (Ctrl+U in browser)",
            "Find all <script type='application/ld+json'> blocks",
            "Copy each block to https://jsonlint.com/ to find syntax errors",
            "Common fixes: remove trailing commas, escape internal quotes",
            "Validate the corrected schema at https://validator.schema.org/",
        ],
        "template": "Validate at: https://jsonlint.com/ and https://validator.schema.org/",
    },
    "R13": {
        "title":   "Make product descriptions specific",
        "summary": "Your product descriptions are too vague for AI to extract facts. AI cannot recommend products it cannot describe precisely.",
        "steps": [
            "For each product, identify: material, dimensions, weight, compatibility, certification",
            "Replace vague adjectives with measurements",
            "Add at least 3 concrete facts per product",
            "Use numbers wherever possible",
        ],
        "template": (
            "Instead of: 'Made from premium quality materials'\n"
            "Write: 'Made from [MATERIAL], [WEIGHT]g, [DIMENSION]cm × [DIMENSION]cm'\n\n"
            "Instead of: 'Suitable for all skin types'\n"
            "Write: 'Dermatologist tested, pH balanced (5.5), suitable for sensitive skin, fragrance-free'"
        ),
    },
    "R15": {
        "title":   "Create or expand your FAQ page",
        "summary": "Your store has no FAQ page or it is too thin. AI agents use FAQ content to answer buyer questions directly.",
        "steps": [
            "Create a page at yourstore.com/pages/faq",
            "Add answers to all 6 core topics",
            "Use clear Q&A format with actual answers (not redirects to 'contact us')",
            "Link the FAQ page from your navigation menu",
        ],
        "template": (
            "Minimum FAQ structure:\n\n"
            "Q: What is your return policy?\n"
            "A: We accept returns within 30 days of delivery. [Details]\n\n"
            "Q: How long does shipping take?\n"
            "A: We ship within 1–2 business days. Delivery: 3–5 days. [Details]\n\n"
            "Q: What payment methods do you accept?\n"
            "A: We accept [list]. [Details]\n\n"
            "Q: How do I contact support?\n"
            "A: Email support@yourdomain.com. We reply within 24 hours.\n\n"
            "Q: Do you offer a warranty?\n"
            "A: Yes, [X] months warranty on all products. [Details]"
        ),
    },
    "R16": {
        "title":   "Add concrete return window to refund policy",
        "summary": "Your refund policy doesn't state a specific number of days. AI agents cannot answer 'how many days to return?' about your store.",
        "steps": [
            "Go to Shopify: Settings → Policies → Refund Policy",
            "Add a specific number of days to your return window",
            "State it clearly at the top of the policy",
            "Save and verify the page is accessible at /policies/refund-policy",
        ],
        "template": (
            "Add this sentence to the top of your refund policy:\n\n"
            "'We accept returns within [30] days of delivery. Items must be unused "
            "and in original packaging. To initiate a return, email support@yourdomain.com "
            "with your order number.'"
        ),
    },
    "R17": {
        "title":   "Add concrete shipping timeframe to shipping policy",
        "summary": "Your shipping policy has no specific delivery timeframe. AI cannot answer 'how long does delivery take?' for your store.",
        "steps": [
            "Go to Shopify: Settings → Policies → Shipping Policy",
            "Add explicit dispatch time and delivery time range",
            "Include regional breakdown if possible (domestic vs international)",
            "Save and verify at /policies/shipping-policy",
        ],
        "template": (
            "Add this to your shipping policy:\n\n"
            "'Orders are processed within [1–2] business days of payment confirmation. "
            "Standard delivery within India takes [3–5] business days. "
            "Express delivery: [1–2] business days (additional charges apply). "
            "International orders: [7–14] business days.'"
        ),
    },
    "R23": {
        "title":   "Create a contact page with branded email",
        "summary": "Your store has no contact page or only a free email (Gmail/Yahoo). AI agents use this to verify store accountability.",
        "steps": [
            "In Shopify: Online Store → Pages → Add page → Title: 'Contact Us'",
            "Add your email address — must be branded (support@yourdomain.com)",
            "Add a response time commitment",
            "Link the page from your footer navigation",
        ],
        "template": (
            "Contact page template:\n\n"
            "**Get in touch**\n\n"
            "Email: support@yourdomain.com\n"
            "We reply within 24 business hours.\n\n"
            "For order issues, include your order number.\n"
            "Business hours: Monday–Friday, 9am–6pm IST."
        ),
    },
    "R25": {
        "title":   "Make your brand name consistent",
        "summary": "AI sees your store under multiple different names and treats them as separate entities. This fragments your brand identity.",
        "steps": [
            "Decide on ONE canonical brand name",
            "Update og:site_name meta tag in your theme.liquid",
            "Update schema.org Organization name field",
            "Update your page title tags to match",
        ],
        "template": (
            "In theme.liquid <head>, add/update:\n\n"
            '<meta property="og:site_name" content="YOUR_CANONICAL_BRAND_NAME">\n\n'
            "In your Organization schema:\n"
            '"name": "YOUR_CANONICAL_BRAND_NAME"'
        ),
    },
    "R28": {
        "title":   "Enable UCP profile for AI commerce agents",
        "summary": "Your store does not have a UCP profile. This is required for AI shopping agents to transact on behalf of customers.",
        "steps": [
            "In Shopify Admin: Settings → Apps and sales channels",
            "Look for 'AI shopping agents' or 'Universal Checkout Protocol'",
            "Enable the feature — UCP profile auto-generates at /.well-known/ucp",
            "Verify at: yourstore.com/.well-known/ucp",
        ],
        "template": "Shopify Admin → Settings → Apps and sales channels → Enable AI shopping agents",
    },
    "R30": {
        "title":   "Improve ACP feed quality",
        "summary": "Your Shopify product feed has quality issues that reduce your ranking in ChatGPT and AI shopping results.",
        "steps": [
            "For each product in Shopify Admin: Products → [product]",
            "Add barcode (GTIN/EAN/UPC) — required for ACP",
            "Ensure title is descriptive (at least 3 meaningful words)",
            "Set availability status correctly (In stock / Out of stock)",
            "Ensure price is set in schema (Shopify does this automatically)",
        ],
        "template": (
            "Per product checklist:\n"
            "☐ Title: [Brand] + [Product Type] + [Key Feature] (min 3 words)\n"
            "☐ Barcode (GTIN): 8, 12, or 13 digit number\n"
            "☐ Price: set and published\n"
            "☐ Availability: 'In stock' or 'Out of stock'\n"
            "☐ Description: at least 50 words with specific facts"
        ),
    },
    "R31": {
        "title":   "Add Google Merchant Center signals",
        "summary": "Your store is missing key signals that Google Merchant Center (and Gemini) use to surface products.",
        "steps": [
            "Verify your store with Google Search Console at search.google.com/search-console",
            "Add the verification meta tag to your theme.liquid <head>",
            "Ensure og:type=product is set on product pages",
            "Add Organization schema if missing (see R7 fix)",
        ],
        "template": (
            "Add to theme.liquid <head>:\n\n"
            "<!-- Google Search Console verification -->\n"
            '<meta name="google-site-verification" content="YOUR_VERIFICATION_CODE">\n\n'
            "<!-- Product type signal -->\n"
            '<meta property="og:type" content="product">'
        ),
    },
}


# ── CHATBOT ───────────────────────────────────────────────────────────────────

def get_fix_template(check_code: str) -> Optional[dict]:
    """Return the hardcoded fix template for a check code."""
    return TEMPLATES.get(check_code)


def chatbot_first_message(check_code: str, check_detail: str) -> str:
    """
    Generate the first chatbot message for a fix conversation.
    Deterministic — no LLM needed for opening message.
    """
    template = get_fix_template(check_code)
    if not template:
        return f"I'll help you fix {check_code}. Issue: {check_detail}\n\nAre you ready to start?"

    return (
        f"**{template['title']}**\n\n"
        f"{template['summary']}\n\n"
        f"Issue found: {check_detail}\n\n"
        f"Are you ready to fix this? I'll walk you through it step by step."
    )


def chatbot_reply(
    check_code: str,
    check_detail: str,
    check_fix: str,
    store_url: str,
    user_message: str,
    history: list[dict],
) -> tuple[str, str]:
    """
    Generate chatbot reply using LLM (Gemini → Ollama → fallback).

    Args:
        check_code:   e.g. "R16"
        check_detail: What was found during audit
        check_fix:    The fix text from the check result
        store_url:    Merchant's store URL
        user_message: Latest message from merchant
        history:      List of {"role": "user"|"bot", "message": str}

    Returns:
        (reply_text, llm_source)
    """
    template = get_fix_template(check_code)

    system_prompt = (
        f"You are a helpful Shopify store advisor fixing one specific issue: {check_code} — {template['title'] if template else check_code}.\n"
        f"Store URL: {store_url}\n\n"
        f"Issue found: {check_detail}\n\n"
        f"Fix guide:\n{check_fix}\n\n"
        f"{'Steps: ' + chr(10).join(f'{i+1}. {s}' for i, s in enumerate(template['steps'])) if template else ''}\n\n"
        f"SCOPE RULE: Only answer questions about this specific fix ({check_code}). "
        f"If the merchant asks about something else, politely redirect them back to this fix. "
        f"Give one step at a time. Be encouraging. Keep replies under 150 words."
    )

    # Build conversation context
    conv_context = "\n".join(
        f"{'Merchant' if m['role'] == 'user' else 'Advisor'}: {m['message']}"
        for m in history[-6:]  # last 6 messages for context
    )

    user_prompt = (
        f"Conversation so far:\n{conv_context}\n\n"
        f"Merchant says: {user_message}\n\n"
        f"Reply as the advisor (one step at a time, under 150 words):"
    )

    fallback = (
        f"Let's continue with the fix for {check_code}.\n\n"
        f"{'Next step: ' + template['steps'][1] if template and len(template['steps']) > 1 else check_fix[:200]}\n\n"
        "Let me know when you've done this or if you have questions."
    )

    return call_llm(user_prompt, system=system_prompt, fallback_text=fallback)
