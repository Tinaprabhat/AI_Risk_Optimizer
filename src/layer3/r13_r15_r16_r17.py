"""
src/layer3/r13_r15_r16_r17.py
───────────────────────────────
Layer 3 — Semantic Content checks.

v2.0 changes:
  R15 — check_r15() now receives semantic_data["faq"] (3-stage discovery)
  R16 — check_r16() now receives semantic_data["refund"] (unit-normalised)
  R17 — check_r17() now receives semantic_data["shipping"] (unit-normalised)
  R13 — unchanged (embedding-based vagueness detection)

R15, R16, R17 no longer run their own page fetches or regex.
They score pre-extracted semantic data from SemanticExtractor.
"""

import re
import logging
import numpy as np

from src.utils.embedder import embed, embed_batch, cosine_sim, chunk_text

logger = logging.getLogger(__name__)

# ── Unit normalisation (mirrors semantic_extractor.py) ────────────────────────

TEMPORAL_UNIT_TO_DAYS = {
    "day": 1,       "days": 1,
    "week": 7,      "weeks": 7,
    "fortnight": 14, "fortnights": 14,
    "month": 30,    "months": 30,
    "year": 365,    "years": 365,
    "business day": 1, "business days": 1,
}

def _to_days(value: int, unit: str) -> int:
    """Convert extracted value + unit to approximate day count."""
    mult = TEMPORAL_UNIT_TO_DAYS.get(unit.lower().strip(), 1)
    return value * mult


# ── R13 — Description Vagueness ───────────────────────────────────────────────
# Unchanged from v1 — embedding-based, no pattern issues.

_VAGUE_EXEMPLARS = [
    "premium quality product",
    "best in class",
    "made with care",
    "exceptional craftsmanship",
    "high quality materials",
    "you will love it",
]

_SPECIFIC_EXEMPLARS = [
    "aircraft-grade 6061 aluminium, 2.3 kg, 45 cm x 30 cm",
    "100% organic cotton, GOTS certified, 180 GSM",
    "stainless steel 316L, water resistant to 50m",
    "cold brew for 18 hours at 4°C, 200mg caffeine per 250ml",
]


def check_r13(homepage_text: str, product_text: str) -> dict:
    """
    R13 — Vague product descriptions.

    Measures semantic distance from VAGUE vs SPECIFIC exemplars.
    vagueness_delta > 0.20 = VAGUE (fail)

    Args:
        homepage_text: Cleaned homepage text
        product_text:  Cleaned product page text

    Returns:
        Standard check result dict.
    """
    result = {
        "check":    "R13",
        "status":   "PASS",
        "score":    10,
        "detail":   "",
        "evidence": "",
    }

    combined = " ".join(filter(None, [homepage_text, product_text]))
    if not combined.strip():
        result.update({"status": "WARN", "score": 5,
                       "detail": "No product text found to analyse"})
        return result

    text = chunk_text(combined, max_sentences=20)
    if not text:
        return result

    try:
        # Embed sample text and exemplars
        text_vec     = embed(text)
        vague_vecs   = embed_batch(_VAGUE_EXEMPLARS)
        specific_vecs = embed_batch(_SPECIFIC_EXEMPLARS)

        sim_vague    = float(np.max([cosine_sim(text_vec, v) for v in vague_vecs]))
        sim_specific = float(np.max([cosine_sim(text_vec, v) for v in specific_vecs]))
        vagueness    = sim_vague - sim_specific

        result["evidence"] = (
            f"vagueness_delta={vagueness:.3f} "
            f"(sim_vague={sim_vague:.3f}, sim_specific={sim_specific:.3f})"
        )

        if vagueness > 0.20:
            result.update({
                "status": "FAIL",
                "score":  0,
                "detail": f"Descriptions read as vague to AI (delta={vagueness:.2f}). "
                           "Add materials, dimensions, use-case specifics.",
            })
        elif vagueness > 0.10:
            result.update({
                "status": "WARN",
                "score":  5,
                "detail": f"Some vagueness detected (delta={vagueness:.2f}). "
                           "Consider adding more specific product attributes.",
            })
        else:
            result.update({
                "status": "PASS",
                "score":  10,
                "detail": f"Descriptions appear specific and informative (delta={vagueness:.2f}).",
            })

    except Exception as e:
        logger.warning(f"R13 embedding failed: {e}")
        result.update({"status": "WARN", "score": 5,
                       "detail": f"Embedding analysis unavailable: {e}"})

    return result


# ── R15 — FAQ Coverage ────────────────────────────────────────────────────────
# v2.0: Receives semantic_data["faq"] from SemanticExtractor.
# No longer runs its own fetch or URL discovery.

_FAQ_TOPICS = ["returns", "shipping", "sizing", "payment", "contact", "warranty"]
_MIN_TOPICS_PASS = 4   # must cover >= 4/6 topics to PASS


def check_r15(semantic_data: dict) -> dict:
    """
    R15 — FAQ page coverage.

    v2.0: Receives semantic_data["faq"] — scored on pre-extracted topic coverage.

    Args:
        semantic_data: Full semantic_data dict from SemanticExtractor.

    Returns:
        Standard check result dict.
    """
    result = {
        "check":    "R15",
        "status":   "FAIL",
        "score":    0,
        "detail":   "",
        "evidence": "",
    }

    faq = semantic_data.get("faq", {})

    if not faq.get("page_found"):
        result.update({
            "detail": "No FAQ or Help page found. "
                      "AI cannot answer buyer questions from your store.",
        })
        return result

    topics   = faq.get("topics_covered", {})
    covered  = [t for t, score in topics.items() if score > 0]
    missing  = [t for t, score in topics.items() if score == 0]
    coverage = faq.get("completeness", 0.0)
    page_url = faq.get("page_url", "")

    result["evidence"] = f"FAQ found at {page_url}. Covered: {', '.join(covered) or 'none'}"

    if len(covered) >= _MIN_TOPICS_PASS:
        result.update({
            "status": "PASS",
            "score":  1,
            "detail": f"FAQ covers {len(covered)}/6 topics ({', '.join(covered)}).",
        })
    elif len(covered) >= 2:
        result.update({
            "status": "WARN",
            "score":  0,
            "detail": f"FAQ found but thin — covers {len(covered)}/6 topics. "
                       f"Missing: {', '.join(missing)}.",
        })
    else:
        result.update({
            "status": "FAIL",
            "score":  0,
            "detail": f"FAQ page found but nearly empty — only {len(covered)}/6 topics. "
                       f"Add answers for: {', '.join(missing)}.",
        })

    return result


# ── R16 — Refund Timeframe ────────────────────────────────────────────────────
# v2.0: Receives semantic_data["refund"] — scores unit-normalised extracted value.

def check_r16(semantic_data: dict) -> dict:
    """
    R16 — Refund window concrete and stated.

    v2.0: Receives semantic_data["refund"] from SemanticExtractor.
    Units are normalised to days before scoring — "2 weeks" and "14 days"
    both score identically.

    Tier 2 (policy exists but no concrete window): returns WARN, not FAIL.
    This is the key improvement — stores with vague-but-real policies
    are no longer penalised with a binary FAIL.

    Args:
        semantic_data: Full semantic_data dict from SemanticExtractor.

    Returns:
        Standard check result dict.
    """
    result = {
        "check":    "R16",
        "status":   "FAIL",
        "score":    0,
        "detail":   "",
        "evidence": "",
    }

    refund = semantic_data.get("refund", {})

    # No policy page found at all
    if not refund.get("policy_text_found"):
        result.update({
            "detail": "No refund or return policy page found. "
                       "AI cannot verify your return terms.",
        })
        return result

    # Policy page found but no concrete timeframe (Tier 2 hit or nothing)
    if not refund.get("found"):
        if refund.get("tier2_hit"):
            result.update({
                "status": "WARN",
                "score":  2,
                "detail": "Refund policy page exists but no concrete timeframe found. "
                           "Add an explicit return window (e.g. '30 days').",
                "evidence": refund.get("raw", ""),
            })
        else:
            result.update({
                "detail": "Refund policy exists but no timeframe extracted. "
                           "State a concrete return window in your policy.",
            })
        return result

    # Concrete timeframe found — score by day-equivalent
    raw      = refund.get("raw", "")
    v_min    = refund.get("value_min", 0) or 0
    v_max    = refund.get("value_max", 0) or 0
    unit     = refund.get("unit", "days")
    unit_days = TEMPORAL_UNIT_TO_DAYS.get(unit.lower().strip(), 1)
    min_days = v_min * unit_days
    max_days = v_max * unit_days
    avg_days = (min_days + max_days) / 2

    result["evidence"] = f"Extracted: '{raw}' → ~{int(avg_days)} days"

    if avg_days >= 30:
        result.update({
            "status": "PASS",
            "score":  10,
            "detail": f"Strong return window: {raw} (~{int(avg_days)} days). "
                       "AI can cite this clearly.",
        })
    elif avg_days >= 14:
        result.update({
            "status": "PASS",
            "score":  9,
            "detail": f"Return window found: {raw} (~{int(avg_days)} days).",
        })
    elif avg_days >= 7:
        result.update({
            "status": "WARN",
            "score":  6,
            "detail": f"Short return window: {raw} ({int(avg_days)} days). "
                       "Consider extending — 30 days is the AI-visible standard.",
        })
    else:
        result.update({
            "status": "WARN",
            "score":  3,
            "detail": f"Very short return window: {raw} ({int(avg_days)} days). "
                       "This may reduce AI recommendation confidence.",
        })

    return result


# ── R17 — Shipping Timeframe ──────────────────────────────────────────────────
# v2.0: Receives semantic_data["shipping"] — identical structure to R16.

def check_r17(semantic_data: dict) -> dict:
    """
    R17 — Shipping timeframe concrete and stated.

    v2.0: Receives semantic_data["shipping"] from SemanticExtractor.
    Units normalised to days. Tier 2 hits return WARN, not FAIL.

    Args:
        semantic_data: Full semantic_data dict from SemanticExtractor.

    Returns:
        Standard check result dict.
    """
    result = {
        "check":    "R17",
        "status":   "FAIL",
        "score":    0,
        "detail":   "",
        "evidence": "",
    }

    shipping = semantic_data.get("shipping", {})

    # No policy page
    if not shipping.get("policy_text_found"):
        result.update({
            "detail": "No shipping or delivery policy page found. "
                       "AI cannot tell buyers when their order arrives.",
        })
        return result

    # Policy found but no concrete timeframe
    if not shipping.get("found"):
        if shipping.get("tier2_hit"):
            result.update({
                "status": "WARN",
                "score":  2,
                "detail": "Shipping policy exists but no concrete timeframe found. "
                           "Add an explicit delivery estimate (e.g. '3-5 business days').",
                "evidence": shipping.get("raw", ""),
            })
        else:
            result.update({
                "detail": "Shipping policy exists but no timeframe extracted. "
                           "State a concrete delivery window.",
            })
        return result

    # Concrete timeframe found
    raw      = shipping.get("raw", "")
    v_min    = shipping.get("value_min", 0) or 0
    v_max    = shipping.get("value_max", 0) or 0
    unit     = shipping.get("unit", "days")
    unit_days = TEMPORAL_UNIT_TO_DAYS.get(unit.lower().strip(), 1)
    min_days = v_min * unit_days
    max_days = v_max * unit_days

    result["evidence"] = f"Extracted: '{raw}' → {int(min_days)}-{int(max_days)} days"

    if max_days <= 7:
        result.update({
            "status": "PASS",
            "score":  10,
            "detail": f"Fast shipping stated: {raw} ({int(min_days)}-{int(max_days)} days). "
                       "AI can cite this as a positive signal.",
        })
    elif max_days <= 14:
        result.update({
            "status": "PASS",
            "score":  9,
            "detail": f"Shipping timeframe found: {raw} ({int(min_days)}-{int(max_days)} days).",
        })
    elif max_days <= 30:
        result.update({
            "status": "WARN",
            "score":  6,
            "detail": f"Slow shipping: {raw} ({int(max_days)} days max). "
                       "AI may flag this for time-sensitive buyers.",
        })
    else:
        result.update({
            "status": "WARN",
            "score":  3,
            "detail": f"Very slow shipping: {raw} ({int(max_days)} days max). "
                       "Consider adding express shipping options.",
        })

    return result