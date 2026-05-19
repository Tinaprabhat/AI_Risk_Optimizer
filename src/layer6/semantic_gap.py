"""
layer6/semantic_gap.py  — v2
──────────────────────────────────────────────────────────────────────────────
CHANGES FROM v1:
  V3 FALLBACK — When JSON-LD schema is empty/missing, V3 is now built from
                crawled page content (homepage + about text). This means the
                gap_IS and gap_WS are still computed rather than returning N/A.
                Labeled as "CRAWLED_FALLBACK" in output so merchant knows.

  OBSERVABILITY — Each gap score now includes a trace: what text was embedded,
                  what the gap means, and what to do.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import Optional

import extruct
from bs4 import BeautifulSoup

from src.utils.embedder     import embed, cosine_sim, chunk_text

logger = logging.getLogger(__name__)

_MCQ_TEMPLATES = {
    "category":      "This is a {value} store.",
    "customer":      "Our primary customer is {value}.",
    "differentiator": "Our main differentiator is {value}.",
    "tone":          "Our brand tone is {value}.",
}


def _classify_gap(gap: float) -> str:
    if gap < 0.15:   return "ALIGNED"
    elif gap < 0.30: return "DRIFT"
    else:            return "MISALIGNED"


def _build_v1(free_text: str, mcq: dict) -> tuple:
    mcq_sentences = [
        _MCQ_TEMPLATES[k].format(value=v)
        for k, v in mcq.items()
        if k in _MCQ_TEMPLATES and v
    ]
    intent_text = free_text.strip() + " " + " ".join(mcq_sentences)
    intent_text = chunk_text(intent_text, max_sentences=10)
    return embed(intent_text), intent_text


def _build_v2(page_texts: dict) -> tuple:
    combined = " ".join(
        chunk_text(text, max_sentences=10)
        for key in ("homepage", "about", "product", "faq", "policies")
        for text in [page_texts.get(key, "")]
        if text.strip()
    )
    if not combined.strip():
        return None, ""
    return embed(combined), combined[:500]


def _build_v3_from_schema(html: str, base_url: str) -> tuple:
    """Extract V3 from JSON-LD schema. Returns (vector, text, source_label)."""
    schema_texts = []
    try:
        # Use clean HTML (strip scripts) before passing to extruct
        soup = BeautifulSoup(html, "html.parser")
        # extruct needs raw html — use original, but extract descriptions cleanly
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
        for item in data.get("json-ld", []):
            desc = item.get("description", "")
            if desc and isinstance(desc, str):
                schema_texts.append(desc)
            if item.get("@type") in ("Organization", "Store", "LocalBusiness"):
                for field in ("description", "slogan"):
                    val = item.get(field, "")
                    if val and isinstance(val, str):
                        schema_texts.append(val)
            if item.get("@type") == "FAQPage":
                for qa in item.get("mainEntity", []):
                    answer = qa.get("acceptedAnswer", {}).get("text", "")
                    if answer and isinstance(answer, str):
                        schema_texts.append(answer[:200])
    except Exception as e:
        logger.debug(f"extruct error in L6 V3: {e}")

    schema_text = chunk_text(" ".join(schema_texts), max_sentences=15)
    if not schema_text.strip():
        return None, "", "SCHEMA_EMPTY"
    return embed(schema_text), schema_text[:500], "SCHEMA"


def _build_v3_fallback(page_texts: dict) -> tuple:
    """
    V3 FALLBACK — when JSON-LD missing, build from crawled page text.
    page_texts values are already cleaned by auditor via extract_clean_text.
    """
    fallback_texts = []
    for key in ("homepage", "about"):
        t = page_texts.get(key, "")
        if t.strip():
            fallback_texts.append(chunk_text(t, max_sentences=5))

    combined = " ".join(fallback_texts)
    if not combined.strip():
        return None, "", "NO_CONTENT"

    return embed(combined), combined[:500], "CRAWLED_FALLBACK"


def _obs_gap(gap_name, gap_val, label, v_a_preview, v_b_preview, source_a, source_b):
    """Observability trace for a single gap score."""
    explanations = {
        "IW": "Does your website reflect what you think your store says?",
        "IS": "Does your structured data (schema/crawl) reflect your intent?",
        "WS": "Are your website content and schema/crawl consistent with each other?",
    }
    return {
        "gap":         gap_val,
        "label":       label,
        "question":    explanations.get(gap_name, ""),
        "source_A":    source_a,
        "source_B":    source_b,
        "preview_A":   v_a_preview[:200],
        "preview_B":   v_b_preview[:200],
        "interpretation": (
            f"{label}: {'No action needed.' if label == 'ALIGNED' else 'Review sources below — they describe different things.' if label == 'MISALIGNED' else 'Minor drift — check specific dimension matrix.'}"
        ),
    }


def compute_gap(
    free_text: str,
    mcq: dict,
    page_texts: dict,
    homepage_html: str,
    base_url: str,
) -> dict:
    result = {
        "gap_IW": None, "gap_IS": None, "gap_WS": None,
        "IW_label": "UNKNOWN", "IS_label": "UNKNOWN", "WS_label": "UNKNOWN",
        "intent_text":  "",
        "website_text": "",
        "schema_text":  "",
        "schema_source": "",    # NEW: "SCHEMA" | "CRAWLED_FALLBACK" | "NO_CONTENT"
        "matrix":       {},
        "summary":      "",
        "observability": {},
        "error":        None,
    }

    # Build V1
    try:
        v1, intent_text = _build_v1(free_text, mcq)
    except Exception as e:
        result["error"] = f"V1 build failed: {e}"
        return result

    # Build V2
    v2, website_text = _build_v2(page_texts)

    # Build V3 — schema first, fallback to crawled content
    v3, schema_text, schema_source = _build_v3_from_schema(homepage_html, base_url)
    if v3 is None:
        logger.info("L6: No JSON-LD schema found — using crawled content fallback for V3")
        v3, schema_text, schema_source = _build_v3_fallback(page_texts)

    result.update(
        intent_text=intent_text,
        website_text=website_text,
        schema_text=schema_text,
        schema_source=schema_source,
    )

    obs = {}

    # gap_IW
    if v2 is not None:
        gap_IW = round(1 - cosine_sim(v1, v2), 3)
        result.update(gap_IW=gap_IW, IW_label=_classify_gap(gap_IW))
        obs["IW"] = _obs_gap("IW", gap_IW, _classify_gap(gap_IW),
                             intent_text, website_text, "merchant_intent", "website_content")
    else:
        result["IW_label"] = "NO-WEBSITE-TEXT"

    # gap_IS
    if v3 is not None:
        gap_IS = round(1 - cosine_sim(v1, v3), 3)
        result.update(gap_IS=gap_IS, IS_label=_classify_gap(gap_IS))
        obs["IS"] = _obs_gap("IS", gap_IS, _classify_gap(gap_IS),
                             intent_text, schema_text, "merchant_intent", schema_source)
    else:
        result["IS_label"] = "NO-SCHEMA-TEXT"

    # gap_WS
    if v2 is not None and v3 is not None:
        gap_WS = round(1 - cosine_sim(v2, v3), 3)
        result.update(gap_WS=gap_WS, WS_label=_classify_gap(gap_WS))
        obs["WS"] = _obs_gap("WS", gap_WS, _classify_gap(gap_WS),
                             website_text, schema_text, "website_content", schema_source)

    result["observability"] = obs

    # 4×5 dimension × page matrix
    dimensions = {k: v for k, v in mcq.items() if k in _MCQ_TEMPLATES}
    pages      = {k: v for k, v in page_texts.items() if v.strip()}
    matrix     = {}
    for dim_name, dim_val in dimensions.items():
        dim_text  = _MCQ_TEMPLATES[dim_name].format(value=dim_val)
        dim_embed = embed(dim_text)
        matrix[dim_name] = {}
        for page_name, page_text in pages.items():
            page_embed = embed(chunk_text(page_text, 8))
            gap        = round(1 - cosine_sim(dim_embed, page_embed), 3)
            matrix[dim_name][page_name] = {"gap": gap, "label": _classify_gap(gap)}
    result["matrix"] = matrix

    result["summary"] = _build_summary(result, free_text)
    return result


def _build_summary(result: dict, free_text: str) -> str:
    lines = []
    lines.append("━━ WHAT YOU THINK YOUR STORE SAYS ━━")
    lines.append(result["intent_text"] or free_text or "(not provided)")
    lines.append("")

    lines.append("━━ WHAT AI READS FROM YOUR WEBSITE ━━")
    lines.append(result["website_text"] or "(could not extract website text)")
    lines.append("")

    schema_label = result.get("schema_source", "")
    if schema_label == "CRAWLED_FALLBACK":
        lines.append("━━ WHAT AI READS FROM YOUR STRUCTURED DATA [CRAWLED_FALLBACK: no JSON-LD found] ━━")
    elif schema_label == "SCHEMA":
        lines.append("━━ WHAT AI READS FROM YOUR SCHEMA (JSON-LD) ━━")
    else:
        lines.append("━━ WHAT AI READS FROM YOUR STRUCTURED DATA ━━")
    lines.append(result["schema_text"] or "(no schema or crawlable content found)")
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
        else "Intent vs Schema  : N/A (no schema/crawl content)"
    )
    lines.append(
        f"Website vs Schema : {result['gap_WS']}  →  {result['WS_label']}"
        if result["gap_WS"] is not None
        else "Website vs Schema : N/A"
    )

    if result.get("schema_source") == "CRAWLED_FALLBACK":
        lines.append("")
        lines.append(
            "⚠ Schema gap computed from crawled page content (no JSON-LD found). "
            "Add schema.org markup for a precise gap score."
        )

    return "\n".join(lines)