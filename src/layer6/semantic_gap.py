"""
layer6/semantic_gap.py
───────────────────────
Layer 6 — 3-Way Semantic Gap Engine

Computes the semantic distance between 3 sources of store identity:
  V1 = Merchant intent  (free text + MCQ answers)
  V2 = Website content  (homepage + about + product + FAQ + policies)
  V3 = Schema content   (JSON-LD descriptions + FAQ answers — from Layer 2)

Three gaps:
  gap_IW = 1 - cosine_sim(V1, V2)  → does your site reflect what you think it says?
  gap_IS = 1 - cosine_sim(V1, V3)  → does your schema reflect your intent?
  gap_WS = 1 - cosine_sim(V2, V3)  → are website and schema consistent?

Thresholds:
  < 0.15   → ALIGNED
  0.15–0.30 → DRIFT
  > 0.30   → MISALIGNED

Output format: 4×5 matrix (4 MCQ dimensions × 5 page types)
  + 3 scalar gap scores
  + plain-text summary for Layer 7

No LLM. No new HTTP fetches. Pure embedding computation. ~0.15s runtime.
"""

import logging
from typing import Optional

import extruct
from bs4 import BeautifulSoup

from src.utils.embedder import embed, cosine_sim, chunk_text

logger = logging.getLogger(__name__)

# ── MCQ → NATURAL LANGUAGE ───────────────────────────────────────────────────

# Converts MCQ selections into natural language sentences for embedding
_MCQ_TEMPLATES = {
    "category": "This is a {value} store.",
    "customer": "Our primary customer is {value}.",
    "differentiator": "Our main differentiator is {value}.",
    "tone": "Our brand tone is {value}.",
}

# ── GAP THRESHOLDS ────────────────────────────────────────────────────────────

def _classify_gap(gap: float) -> str:
    if gap < 0.15:
        return "ALIGNED"
    elif gap < 0.30:
        return "DRIFT"
    else:
        return "MISALIGNED"


# ── VECTOR BUILDERS ───────────────────────────────────────────────────────────

def _build_v1(free_text: str, mcq: dict) -> tuple:
    """
    Build V1 — merchant intent vector.

    Args:
        free_text: 'Describe your store in 2–3 sentences'
        mcq: dict with keys: category, customer, differentiator, tone

    Returns:
        (vector, intent_text) where intent_text is the full string used for embedding
    """
    mcq_sentences = [
        _MCQ_TEMPLATES[k].format(value=v)
        for k, v in mcq.items()
        if k in _MCQ_TEMPLATES and v
    ]
    intent_text = free_text.strip() + " " + " ".join(mcq_sentences)
    intent_text = chunk_text(intent_text, max_sentences=10)
    return embed(intent_text), intent_text


def _build_v2(page_texts: dict) -> tuple:
    """
    Build V2 — website content vector.

    Args:
        page_texts: dict with keys: homepage, about, product, faq, policies
                    (any subset is fine — missing pages are skipped)

    Returns:
        (vector, combined_text)
    """
    combined = " ".join(
        chunk_text(text, max_sentences=10)
        for key in ("homepage", "about", "product", "faq", "policies")
        for text in [page_texts.get(key, "")]
        if text.strip()
    )
    if not combined.strip():
        return None, ""
    return embed(combined), combined[:500]


def _build_v3(html: str, base_url: str) -> tuple:
    """
    Build V3 — schema content vector.
    Extracts JSON-LD descriptions and FAQ answers already on the page.

    Returns:
        (vector, schema_text)
    """
    schema_texts = []

    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        for item in data.get("json-ld", []):
            # Product description
            desc = item.get("description", "")
            if desc:
                schema_texts.append(desc)

            # Organization description
            if item.get("@type") in ("Organization", "Store", "LocalBusiness"):
                for field in ("description", "slogan"):
                    val = item.get(field, "")
                    if val:
                        schema_texts.append(val)

            # FAQ answers
            if item.get("@type") == "FAQPage":
                for qa in item.get("mainEntity", []):
                    answer = qa.get("acceptedAnswer", {}).get("text", "")
                    if answer:
                        schema_texts.append(answer[:200])
    except Exception as e:
        logger.debug(f"extruct error in Layer 6 V3: {e}")

    schema_text = chunk_text(" ".join(schema_texts), max_sentences=15)
    if not schema_text.strip():
        return None, ""
    return embed(schema_text), schema_text[:500]


# ── MAIN ENTRY POINT ─────────────────────────────────────────────────────────

def compute_gap(
    free_text: str,
    mcq: dict,
    page_texts: dict,
    homepage_html: str,
    base_url: str,
) -> dict:
    """
    Compute the 3-way semantic gap.

    Args:
        free_text:     Merchant's free-text description
        mcq:           Dict with category/customer/differentiator/tone
        page_texts:    Dict with homepage/about/product/faq/policies page text
        homepage_html: Raw HTML of homepage (for V3 schema extraction)
        base_url:      Store base URL

    Returns:
        dict with gap scores, classifications, vectors summary, and display text
    """
    result = {
        "gap_IW": None, "gap_IS": None, "gap_WS": None,
        "IW_label": "UNKNOWN", "IS_label": "UNKNOWN", "WS_label": "UNKNOWN",
        "intent_text":  "",
        "website_text": "",
        "schema_text":  "",
        "matrix":       {},   # 4×5 dimension × page_type gaps
        "summary":      "",   # plain text for Layer 7 → UI display
        "error":        None,
    }

    # Build vectors
    try:
        v1, intent_text = _build_v1(free_text, mcq)
    except Exception as e:
        result["error"] = f"V1 build failed: {e}"
        return result

    v2, website_text = _build_v2(page_texts)
    v3, schema_text  = _build_v3(homepage_html, base_url)

    result["intent_text"]  = intent_text
    result["website_text"] = website_text
    result["schema_text"]  = schema_text

    # Compute scalar gaps
    if v2 is not None:
        gap_IW = round(1 - cosine_sim(v1, v2), 3)
        result["gap_IW"]   = gap_IW
        result["IW_label"] = _classify_gap(gap_IW)
    else:
        result["IW_label"] = "NO-WEBSITE-TEXT"

    if v3 is not None:
        gap_IS = round(1 - cosine_sim(v1, v3), 3)
        result["gap_IS"]   = gap_IS
        result["IS_label"] = _classify_gap(gap_IS)
    else:
        result["IS_label"] = "NO-SCHEMA-TEXT"

    if v2 is not None and v3 is not None:
        gap_WS = round(1 - cosine_sim(v2, v3), 3)
        result["gap_WS"]   = gap_WS
        result["WS_label"] = _classify_gap(gap_WS)

    # Build 4×5 matrix — per MCQ dimension × per page type
    # Each cell = gap between that dimension anchor and that page's embedding
    dimensions = {k: v for k, v in mcq.items() if k in _MCQ_TEMPLATES}
    pages      = {k: v for k, v in page_texts.items() if v.strip()}

    matrix = {}
    for dim_name, dim_val in dimensions.items():
        dim_text  = _MCQ_TEMPLATES[dim_name].format(value=dim_val)
        dim_embed = embed(dim_text)
        matrix[dim_name] = {}
        for page_name, page_text in pages.items():
            page_embed = embed(chunk_text(page_text, 8))
            gap        = round(1 - cosine_sim(dim_embed, page_embed), 3)
            matrix[dim_name][page_name] = {
                "gap":   gap,
                "label": _classify_gap(gap),
            }

    result["matrix"] = matrix

    # Build plain-text summary for display
    result["summary"] = _build_summary(result, free_text)

    return result


def _interpret_gaps(result: dict) -> str:
    """
    Plain-English narrative of what the gap scores mean for the merchant.
    No LLM — deterministic from gap scores + matrix. Always produces output.
    """
    parts = []

    iw_gap   = result.get("gap_IW")
    iw_label = result.get("IW_label", "UNKNOWN")
    is_gap   = result.get("gap_IS")
    is_label = result.get("IS_label", "UNKNOWN")
    ws_gap   = result.get("gap_WS")
    ws_label = result.get("WS_label", "UNKNOWN")

    # Intent vs Website — primary signal
    if iw_label == "NO-WEBSITE-TEXT":
        parts.append(
            "Website text could not be extracted — unable to compare your store description "
            "to what AI reads from your site. Check that your homepage is publicly accessible."
        )
    elif iw_label == "ALIGNED":
        parts.append(
            "Your website content closely reflects how you describe your store. "
            "AI shopping agents should understand your brand positioning accurately."
        )
    elif iw_label == "DRIFT":
        parts.append(
            f"Your website partially matches how you describe your store (gap: {iw_gap}). "
            "Some of your brand positioning is not coming through clearly in your page content — "
            "AI agents may give buyers an incomplete or blurred picture of what you offer."
        )
    elif iw_label == "MISALIGNED":
        parts.append(
            f"Your website content significantly diverges from how you describe your store (gap: {iw_gap}). "
            "AI shopping agents are likely reading a very different brand story than you intend to tell. "
            "Your homepage and product pages need to reflect your actual positioning more explicitly."
        )

    # Intent vs Schema
    if is_label == "NO-SCHEMA-TEXT":
        parts.append(
            "No schema markup descriptions found on your homepage. "
            "AI agents relying on structured data have no identity signal for your store — "
            "add an Organization or Product schema with a description field."
        )
    elif is_label == "ALIGNED":
        parts.append(
            "Your schema markup aligns with your stated intent. "
            "Structured data is correctly signaling your brand to AI crawlers."
        )
    elif is_label == "DRIFT":
        parts.append(
            f"Your schema markup partially reflects your brand intent (gap: {is_gap}). "
            "Some positioning signals are weak or missing in your structured data — "
            "update your JSON-LD description fields to mirror your actual brand language."
        )
    elif is_label == "MISALIGNED":
        parts.append(
            f"Your schema markup tells a very different story from your brand intent (gap: {is_gap}). "
            "AI agents parsing your structured data will form a misleading picture of your store. "
            "Rewrite your JSON-LD Organization/Product descriptions to match your actual positioning."
        )

    # Website vs Schema consistency
    if ws_gap is not None:
        if ws_label == "ALIGNED":
            parts.append(
                "Your website text and schema are internally consistent — AI sees a coherent store identity."
            )
        elif ws_label == "DRIFT":
            parts.append(
                f"Mild inconsistency between your website text and schema (gap: {ws_gap}). "
                "The two sources give slightly different signals — align your schema descriptions "
                "with your on-page copy."
            )
        elif ws_label == "MISALIGNED":
            parts.append(
                f"Major inconsistency between your website text and schema (gap: {ws_gap}). "
                "AI agents parsing both sources get conflicting signals — "
                "your schema is essentially describing a different store than your website."
            )

    # Matrix — find worst-performing MCQ dimension
    matrix = result.get("matrix", {})
    if matrix:
        worst_gap   = -1.0
        worst_dim   = worst_page = worst_label = None
        for dim, pages in matrix.items():
            for page, cell in pages.items():
                if cell.get("gap", 0) > worst_gap:
                    worst_gap   = cell["gap"]
                    worst_dim   = dim
                    worst_page  = page
                    worst_label = cell["label"]

        if worst_dim and worst_gap >= 0.15:
            dim_labels  = {
                "category":      "store category",
                "customer":      "target customer",
                "differentiator":"key differentiator",
                "tone":          "brand tone",
            }
            page_labels = {
                "homepage": "homepage", "about": "about page",
                "product":  "product pages", "faq": "FAQ page", "policies": "policy pages",
            }
            parts.append(
                f"Biggest single gap: your {dim_labels.get(worst_dim, worst_dim)} signal "
                f"on your {page_labels.get(worst_page, worst_page)} is "
                f"{worst_label} (gap: {worst_gap}) — prioritise fixing this page first."
            )

    return "\n\n".join(parts) if parts else "Gap analysis complete — see scores above."


def _build_summary(result: dict, free_text: str) -> str:
    """Generate the plain-text summary shown to merchant in Layer 7 output."""
    lines = []

    lines.append("━━ WHAT YOU THINK YOUR STORE SAYS ━━")
    lines.append(result["intent_text"] or free_text or "(not provided)")
    lines.append("")

    lines.append("━━ WHAT AI READS FROM YOUR WEBSITE ━━")
    lines.append(result["website_text"] or "(could not extract website text)")
    lines.append("")

    lines.append("━━ WHAT AI READS FROM YOUR SCHEMA ━━")
    lines.append(result["schema_text"] or "(no schema descriptions found)")
    lines.append("")

    lines.append("━━ GAP SCORES ━━")
    lines.append(
        f"Intent vs Website : {result['gap_IW']}  →  {result['IW_label']}"
        if result["gap_IW"] is not None
        else "Intent vs Website : N/A (no website text)"
    )
    lines.append(
        f"Intent vs Schema  : {result['gap_IS']}  →  {result['IS_label']}"
        if result["gap_IS"] is not None
        else "Intent vs Schema  : N/A (no schema text)"
    )
    lines.append(
        f"Website vs Schema : {result['gap_WS']}  →  {result['WS_label']}"
        if result["gap_WS"] is not None
        else "Website vs Schema : N/A"
    )
    lines.append("")

    lines.append("━━ WHAT THIS MEANS ━━")
    lines.append(_interpret_gaps(result))

    return "\n".join(lines)
