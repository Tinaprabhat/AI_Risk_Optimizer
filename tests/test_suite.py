"""
tests/test_suite.py  — v2
──────────────────────────────────────────────────────────────────────────────
Modular test suite for AI Representation Optimizer v2.

Sections:
  1. UNIT TESTS     — each check in isolation (no HTTP, mocked HTML)
  2. INTEGRATION    — live URL tests on known-good stores
  3. LLM TESTS      — Gemini response quality: hallucination rate, answer rate
  4. SCORING TESTS  — validate score math matches validate.py v2.1

Run:
  pip install pytest
  pytest tests/test_suite.py -v

  # Run only unit tests (no HTTP):
  pytest tests/test_suite.py -v -m unit

  # Run only LLM tests (requires GEMINI_API_KEY in .env):
  pytest tests/test_suite.py -v -m llm

  # Run integration (hits live URLs):
  pytest tests/test_suite.py -v -m integration
"""

import os
import sys
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES — synthetic HTML snippets used in unit tests
# ═══════════════════════════════════════════════════════════════════════════════

SHOPIFY_HTML_BASE = """
<html>
<head>
  <title>Test Store – Official Site</title>
  <meta property="og:site_name" content="Test Store" />
  <meta property="og:type" content="website" />
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Organization","name":"Test Store","url":"https://teststore.com"}
  </script>
</head>
<body>
  <script src="https://cdn.shopify.com/s/files/1/shopify.js"></script>
  <p>Buy now for $49.99</p>
</body>
</html>
"""

HTML_NO_OG_NO_SCHEMA = """
<html>
<head><title>My Brand – Best Products</title></head>
<body><p>Welcome to our store.</p></body>
</html>
"""

HTML_BRAND_MISMATCH = """
<html>
<head>
  <title>Brand X – Store</title>
  <meta property="og:site_name" content="BrandX Official" />
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Organization","name":"BrandXYZ International Ltd"}
  </script>
</head>
<body></body>
</html>
"""

HTML_WITH_SCHEMA_DESCRIPTION = """
<html>
<head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization","name":"CoffeeCo","description":"We sell specialty single-origin coffee beans sourced directly from farms in Ethiopia and Colombia."}
</script>
</head>
<body><p>Fresh roasted coffee delivered to your door.</p></body>
</html>
"""

REFUND_POLICY_CLEAR = "We offer a 30-day money back guarantee on all products. Return within 30 days for a full refund."
REFUND_POLICY_VAGUE = "Returns are subject to our discretion. We may or may not accept returns depending on the situation."
SHIPPING_POLICY_CLEAR = "All orders ship within 1-3 business days. Standard delivery takes 5-7 business days."
SHIPPING_POLICY_VAGUE = "We try to ship orders as quickly as possible. Delivery times may vary."


# ═══════════════════════════════════════════════════════════════════════════════
# 1. UNIT TESTS — R25 Brand Consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestR25BrandConsistency:

    @pytest.mark.unit
    def test_consistent_brands_pass(self):
        from src.layer4.r23_r25 import check_r25
        result = check_r25("https://teststore.com", SHOPIFY_HTML_BASE)
        assert result["status"] == "PASS", f"Expected PASS, got {result['status']} | {result['detail']}"
        assert result["score"] == 1

    @pytest.mark.unit
    def test_title_tag_fallback_used(self):
        """When og:site_name and schema missing, title tag should be used as source."""
        from src.layer4.r23_r25 import check_r25
        result = check_r25("https://teststore.com", HTML_NO_OG_NO_SCHEMA)
        # Only 1 source (title_tag) — should be UNKNOWN, not FAIL
        assert result["status"] == "UNKNOWN", f"Expected UNKNOWN (only 1 source), got {result['status']}"
        assert "title_tag" in result["evidence"]

    @pytest.mark.unit
    def test_brand_mismatch_fail(self):
        from src.layer4.r23_r25 import check_r25
        result = check_r25("https://teststore.com", HTML_BRAND_MISMATCH)
        assert result["status"] in ("FAIL", "WARN"), f"Expected FAIL or WARN, got {result['status']}"

    @pytest.mark.unit
    def test_warn_scores_half_point(self):
        """WARN should now give score=0.5 (partial credit in v2)."""
        from src.layer4.r23_r25 import check_r25
        result = check_r25("https://teststore.com", HTML_BRAND_MISMATCH)
        if result["status"] == "WARN":
            assert result["score"] == 0.5, f"WARN should score 0.5, got {result['score']}"

    @pytest.mark.unit
    def test_observability_present(self):
        from src.layer4.r23_r25 import check_r25
        result = check_r25("https://teststore.com", SHOPIFY_HTML_BASE)
        obs = result.get("observability", {})
        assert obs, "Observability block should not be empty"
        assert "what_we_did" in obs
        assert "what_AI_sees" in obs
        assert "raw_evidence" in obs


# ═══════════════════════════════════════════════════════════════════════════════
# 2. UNIT TESTS — R30 (Informational, not scored)
# ═══════════════════════════════════════════════════════════════════════════════

class TestR30Informational:

    @pytest.mark.unit
    def test_r30_never_scored(self):
        """R30 should always have score=0 and scored=False in v2."""
        from src.layer5.r28_r30_r31 import check_r30
        result = check_r30("https://teststore.com", SHOPIFY_HTML_BASE)
        assert result["score"] == 0, f"R30 should always score 0, got {result['score']}"
        assert result.get("scored") is False, "R30.scored should be False"

    @pytest.mark.unit
    def test_r30_status_informational(self):
        from src.layer5.r28_r30_r31 import check_r30
        result = check_r30("https://teststore.com", SHOPIFY_HTML_BASE)
        assert result["status"] == "INFORMATIONAL"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. UNIT TESTS — Scoring / Aggregator
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoring:

    def _make_checks(self, overrides: dict = None) -> dict:
        """Build a minimal all-checks dict (all PASS) with optional overrides."""
        base = {
            "R1":  {"score": 1, "status": "PASS", "detail": "", "tier": "VERIFIED"},
            "R3":  {"score": 1, "status": "PASS", "detail": "", "tier": "VERIFIED"},
            "R5":  {"score": 1, "status": "PASS", "detail": "", "tier": "VERIFIED"},
            "R6":  {"score": 1, "status": "PASS", "detail": "", "tier": "VERIFIED"},
            "R7":  {"score": 10, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R9":  {"score": 10, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R11": {"score": 1, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R13": {"score": 10, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R15": {"score": 1, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R16": {"score": 10, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R17": {"score": 10, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R23": {"score": 1, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R25": {"score": 1, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R28": {"score": 1, "status": "PASS", "detail": "", "tier": "CORRELATED"},
            "R30": {"score": 0, "status": "INFORMATIONAL", "detail": "", "tier": "VERIFIED", "scored": False},
            "R31": {"score": 10, "status": "PASS", "detail": "", "tier": "CORRELATED"},
        }
        if overrides:
            for k, v in overrides.items():
                base[k].update(v)
        return base

    @pytest.mark.unit
    def test_max_total_is_69(self):
        from src.layer7.aggregator import MAX_TOTAL
        assert MAX_TOTAL == 69, f"MAX_TOTAL should be 69 (R30 removed), got {MAX_TOTAL}"

    @pytest.mark.unit
    def test_perfect_score(self):
        from src.layer7.aggregator import compute_score
        checks = self._make_checks()
        info   = compute_score(checks)
        assert info["grand_total"] == 69.0, f"Perfect score should be 69, got {info['grand_total']}"
        assert info["pct"] == 100.0

    @pytest.mark.unit
    def test_r30_excluded_from_total(self):
        from src.layer7.aggregator import compute_score
        # Even if R30 somehow had score=10, it should not count
        checks = self._make_checks({"R30": {"score": 10, "status": "PASS"}})
        info   = compute_score(checks)
        assert info["grand_total"] == 69.0, "R30 should never add to total"

    @pytest.mark.unit
    def test_r25_warn_scores_half(self):
        from src.layer7.aggregator import compute_score
        checks = self._make_checks({"R25": {"score": 0.5, "status": "WARN"}})
        info   = compute_score(checks)
        assert info["checklist_total"] == 8.5, f"R25 WARN should give 0.5, total checklist={info['checklist_total']}"

    @pytest.mark.unit
    def test_forward_looking_scores_zero(self):
        from src.layer7.aggregator import compute_score
        checks = self._make_checks({"R28": {"score": 1, "status": "FORWARD-LOOKING"}})
        info   = compute_score(checks)
        bd     = info["breakdown"]["R28"]
        assert bd["score"] == 0, "FORWARD-LOOKING should score 0"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. UNIT TESTS — Layer 6 Semantic Gap V3 Fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestLayer6Fallback:

    @pytest.mark.unit
    def test_v3_fallback_when_no_schema(self):
        """When homepage has no JSON-LD, V3 should fall back to crawled content."""
        from src.layer6.semantic_gap import compute_gap
        page_texts = {
            "homepage": "We sell organic coffee directly from farms in Ethiopia.",
            "about":    "Founded in 2020. We are a specialty coffee brand.",
        }
        result = compute_gap(
            free_text="We sell specialty coffee",
            mcq={"category": "Food", "customer": "Quality-first", "differentiator": "Quality", "tone": "Friendly"},
            page_texts=page_texts,
            homepage_html="<html><body>No schema here</body></html>",
            base_url="https://testcoffee.com",
        )
        assert result["schema_source"] == "CRAWLED_FALLBACK", (
            f"Expected CRAWLED_FALLBACK, got {result['schema_source']}"
        )
        assert result["gap_IS"] is not None, "gap_IS should be computed even with fallback"
        assert "CRAWLED_FALLBACK" in result["summary"]

    @pytest.mark.unit
    def test_v3_uses_schema_when_present(self):
        from src.layer6.semantic_gap import compute_gap
        page_texts = {"homepage": "Specialty coffee from single-origin farms."}
        result = compute_gap(
            free_text="We sell specialty coffee",
            mcq={"category": "Food", "customer": "Quality-first", "differentiator": "Quality", "tone": "Friendly"},
            page_texts=page_texts,
            homepage_html=HTML_WITH_SCHEMA_DESCRIPTION,
            base_url="https://coffeeco.com",
        )
        assert result["schema_source"] == "SCHEMA", (
            f"Expected SCHEMA when JSON-LD present, got {result['schema_source']}"
        )

    @pytest.mark.unit
    def test_observability_in_gap(self):
        from src.layer6.semantic_gap import compute_gap
        page_texts = {"homepage": "We sell organic skincare products."}
        result = compute_gap(
            free_text="Organic skincare store",
            mcq={"category": "Beauty", "customer": "Eco-conscious", "differentiator": "Sustainability", "tone": "Friendly"},
            page_texts=page_texts,
            homepage_html="<html><body>Organic skincare products for sensitive skin.</body></html>",
            base_url="https://skincare.com",
        )
        obs = result.get("observability", {})
        assert "IW" in obs, "IW observability should be present"
        assert "gap" in obs["IW"]
        assert "question" in obs["IW"]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LLM TESTS — Gemini response quality
# ═══════════════════════════════════════════════════════════════════════════════

class TestLLMQuality:
    """
    Requires GEMINI_API_KEY set in environment or .env file.
    Tests hallucination rate and answer rate on structured Q&A.
    Thresholds from spec: hallucination_rate < 10%, answer_rate > 85%.
    """

    STORE_CONTENT = """
    CoffeeCo sells specialty single-origin coffee beans sourced from Ethiopia and Colombia.
    All orders ship within 1-3 business days.
    We offer a 30-day money back guarantee.
    Price range: $15-$45 per bag.
    Contact: support@coffeeco.com
    """

    QUESTIONS = [
        ("What does this store sell?",          "coffee"),
        ("What is the return policy?",          "30"),
        ("How long does shipping take?",        "business days"),
        ("What is the price range?",            "$"),
        ("What is the contact email?",          "coffeeco.com"),
        ("Does this store sell electronics?",   None),   # should be NOT FOUND
    ]

    @pytest.mark.llm
    def test_gemini_answer_rate(self):
        """≥ 85% of answerable questions should be answered correctly."""
        from src.utils.llm import GEMINI_API_KEY, ollama_available, call_llm
        if not GEMINI_API_KEY and not ollama_available():
            pytest.skip("No LLM available — set GEMINI_API_KEY or start Ollama to run this test")

        answerable = [q for q, expected in self.QUESTIONS if expected is not None]
        correct    = 0

        for question, expected_keyword in [(q, e) for q, e in self.QUESTIONS if e is not None]:
            prompt = (
                f"Store content:\n{self.STORE_CONTENT}\n\n"
                f"Question: {question}\n"
                f"Answer only from the store content above. "
                f"If the answer is not in the content, respond with exactly: NOT FOUND"
            )
            answer, _ = call_llm(prompt, system="You are a factual Q&A bot.", fallback_text="NOT FOUND")
            if expected_keyword.lower() in answer.lower():
                correct += 1
            else:
                print(f"  WRONG: Q='{question}' | Expected keyword='{expected_keyword}' | Got='{answer[:100]}'")

        rate = correct / len(answerable)
        assert rate >= 0.85, f"Answer rate {rate:.0%} < 85% threshold. Revise LLM prompt."

    @pytest.mark.llm
    def test_gemini_hallucination_rate(self):
        """< 10% of answers should contain facts not in the store content."""
        from src.utils.llm import call_llm

        hallucinations = 0
        total          = len(self.QUESTIONS)

        # Hallucination check questions — answers should be NOT FOUND
        unanswerable = [
            "Does this store offer free shipping?",
            "What is the store's Instagram handle?",
            "Do they sell subscriptions?",
        ]

        for question in unanswerable:
            prompt = (
                f"Store content:\n{self.STORE_CONTENT}\n\n"
                f"Question: {question}\n"
                f"Answer ONLY from the store content above. "
                f"If the answer is not in the content, respond with exactly: NOT FOUND"
            )
            answer, _ = call_llm(prompt, system="You are a factual Q&A bot.", fallback_text="NOT FOUND")
            if "NOT FOUND" not in answer.upper():
                hallucinations += 1
                print(f"  HALLUCINATION: Q='{question}' | Got='{answer[:100]}'")

        rate = hallucinations / len(unanswerable)
        assert rate < 0.10, f"Hallucination rate {rate:.0%} >= 10% threshold. Revise system prompt."

    @pytest.mark.llm
    def test_conclusion_paragraph_length(self):
        """Conclusion should be 3–4 sentences (100–400 words)."""
        from src.layer7.aggregator import build_conclusion

        dummy_checks = {
            "R16": {"score": 0, "status": "FAIL", "detail": "No refund timeframe found", "fix": "Add 30-day return policy.", "tier": "CORRELATED", "observability": {}},
            "R17": {"score": 0, "status": "FAIL", "detail": "No shipping timeframe found", "fix": "Add shipping days.", "tier": "CORRELATED", "observability": {}},
            "R25": {"score": 0, "status": "FAIL", "detail": "Brand names inconsistent", "fix": "Standardize brand name.", "tier": "CORRELATED", "observability": {}},
        }
        score_info = {
            "grand_total": 20, "max_total": 69, "pct": 29.0,
            "scored_total": 15, "checklist_total": 5,
            "max_scored": 60, "max_checklist": 9, "breakdown": {},
        }
        conclusion, source, _ = build_conclusion(
            all_checks=dummy_checks,
            score_info=score_info,
            gap_summary="Intent vs Website: 0.35 → MISALIGNED",
            merchant_intent="We sell handmade leather goods.",
        )
        word_count = len(conclusion.split())
        assert 30 <= word_count <= 500, f"Conclusion word count {word_count} out of expected range 30–500"
        print(f"  Conclusion ({word_count} words, source={source}):\n  {conclusion}")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. INTEGRATION TESTS — Live stores
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """
    Hits live URLs. Requires network access.
    Uses huel.com (78% in validation — should score high) and
    liquiddeath.com (28% — should score low).
    """

    @pytest.mark.integration
    def test_huel_scores_above_50_pct(self):
        from src.auditor import run_audit
        result = run_audit(
            store_url="https://huel.com",
            free_text="We sell nutritionally complete food products.",
            mcq={"category": "Food", "customer": "Quality-first", "differentiator": "Quality", "tone": "Technical"},
            use_cache=False,
        )
        pct = result["score"]["pct"]
        assert pct >= 40, f"huel.com should score >= 40%, got {pct}%"
        print(f"  huel.com score: {pct}%")

    @pytest.mark.integration
    def test_huel_beats_liquiddeath(self):
        """Rank ordering: huel should outscore liquiddeath."""
        from src.auditor import run_audit

        huel = run_audit(
            store_url="https://huel.com",
            free_text="Nutritionally complete food products.",
            mcq={"category": "Food", "customer": "Quality-first", "differentiator": "Quality", "tone": "Technical"},
            use_cache=True,
        )
        ld = run_audit(
            store_url="https://liquiddeath.com",
            free_text="Canned water brand.",
            mcq={"category": "Food", "customer": "Budget", "differentiator": "Uniqueness", "tone": "Playful"},
            use_cache=True,
        )
        assert huel["score"]["pct"] > ld["score"]["pct"], (
            f"huel ({huel['score']['pct']}%) should beat liquiddeath ({ld['score']['pct']}%)"
        )

    @pytest.mark.integration
    def test_observability_block_present(self):
        """Every audit result should have an observability block."""
        from src.auditor import run_audit
        result = run_audit(
            store_url="https://huel.com",
            free_text="Complete nutrition.",
            mcq={"category": "Food", "customer": "Quality-first", "differentiator": "Quality", "tone": "Technical"},
            use_cache=True,
        )
        obs = result.get("observability", {})
        assert obs, "Observability block should not be empty"
        assert "per_check_traces" in obs
        print(f"  Checks with observability: {list(obs['per_check_traces'].keys())}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import subprocess
    subprocess.run(["pytest", __file__, "-v", "--tb=short", "-m", "unit"], check=False)
