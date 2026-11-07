"""
tests/test_fixes.py — regression tests for the calibration / robustness fixes.
Offline; no network.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGapThresholds:
    def test_labels_follow_calibrated_cutoffs(self):
        from src.layer6.semantic_gap import _classify_gap, GAP_ALIGNED_MAX, GAP_DRIFT_MAX
        assert _classify_gap(GAP_ALIGNED_MAX - 0.01) == "ALIGNED"
        assert _classify_gap(GAP_ALIGNED_MAX) == "DRIFT"
        assert _classify_gap(GAP_DRIFT_MAX - 0.01) == "DRIFT"
        assert _classify_gap(GAP_DRIFT_MAX) == "MISALIGNED"

    def test_typical_same_site_gap_is_not_misaligned(self):
        """Median same-site gap in the logged audits is ~0.66; it must not read as MISALIGNED."""
        from src.layer6.semantic_gap import _classify_gap
        assert _classify_gap(0.66) != "MISALIGNED"
        assert _classify_gap(0.85) == "MISALIGNED"   # median cross-site gap


class TestEnsureObservability:
    def test_fills_missing_block(self):
        from src.utils.observability import ensure_observability
        r = ensure_observability("R9", {"status": "FAIL", "detail": "no price", "fix": "add"})
        assert r["observability"]["severity"] == "HIGH"
        assert r["observability"]["what_AI_sees"] == "no price"

    def test_keeps_existing_block(self):
        from src.utils.observability import ensure_observability
        r = ensure_observability("R1", {"status": "PASS", "observability": {"x": 1}})
        assert r["observability"] == {"x": 1}


class TestLlmHelpers:
    def test_ollama_available_handles_object_and_dict_listings(self, monkeypatch):
        import types, sys
        from src.utils import llm

        class _M:  # ollama>=0.4 object style
            model = "mistral:latest"

        class _Client:
            def __init__(self, host=None): pass
            def list(self): return types.SimpleNamespace(models=[_M()])

        fake = types.SimpleNamespace(Client=_Client)
        monkeypatch.setitem(sys.modules, "ollama", fake)
        assert llm.ollama_available() is True

        class _Client2(_Client):
            def list(self): return {"models": [{"name": "mistral:7b"}]}
        fake.Client = _Client2
        assert llm.ollama_available() is True

    def test_gemini_skipped_without_key(self, monkeypatch):
        from src.utils import llm
        monkeypatch.setattr(llm, "GEMINI_API_KEY", "")
        assert llm._call_gemini("p", "s") is None


class TestTitleSplit:
    def test_en_dash_title_split(self):
        from src.utils.semantic_extractor import SemanticExtractor
        html = "<html><head><title>Acme \u2013 Best Widgets</title></head></html>"
        assert SemanticExtractor().extract_brand(html, [])["brand_name"] == "Acme"


class TestConclusionNormalisation:
    def test_agency_noun_forced(self):
        from src.layer7.aggregator import _normalize_noun
        out = _normalize_noun("Your store's score is high; the merchant should fix it. Store owners win.", "agency")
        assert "store" not in out.lower() and "merchant" not in out.lower()
        assert "agency's score" in out

    def test_shopify_unchanged(self):
        from src.layer7.aggregator import _normalize_noun
        assert _normalize_noun("Your store is fine.", "store") == "Your store is fine."


class TestFaqTopicKeywords:
    def test_patterns_have_no_control_chars_and_match(self):
        import re
        from src.utils.semantic_extractor import AGENCY_TOPIC_KEYWORDS, _SHOPIFY_TOPIC_KEYWORDS
        for table in (AGENCY_TOPIC_KEYWORDS, _SHOPIFY_TOPIC_KEYWORDS):
            for topic, pats in table.items():
                for pat in pats:
                    assert "\x08" not in pat, (topic, pat)
                    re.compile(pat)
        assert re.search(AGENCY_TOPIC_KEYWORDS["pricing"][0], "What is your pricing?", re.I)
        assert re.search(_SHOPIFY_TOPIC_KEYWORDS["returns"][0], "Can I return an item?", re.I)

    def test_extract_faq_scores_topics(self, monkeypatch):
        from src.utils import semantic_extractor as se

        class R:
            ok = True
            text = ("<html><body><p>" + "FAQ pricing cost timeline weeks process agile support maintenance "
                    "technology react contract NDA " * 8 + "</p></body></html>")
        monkeypatch.setattr(se, "safe_get", lambda u: R())
        monkeypatch.setattr(se, "jitter_sleep", lambda *a, **k: None)
        out = se.SemanticExtractor().extract_faq(
            "https://e.com", "", topic_keywords=se.AGENCY_TOPIC_KEYWORDS, faq_paths=["/faq"])
        assert out["page_found"] and out["completeness"] == 1.0


class TestEnsureActionable:
    FAILED = [{"code": "R15", "detail": "No FAQ found.", "fix": "State ranges."}]

    def test_appends_when_failures_not_named(self):
        from src.layer7.aggregator import _ensure_actionable
        out = _ensure_actionable("Your agency does well overall.", self.FAILED)
        assert "R15" in out and out.startswith("Your agency does well overall.")

    def test_untouched_when_named_or_no_failures(self):
        from src.layer7.aggregator import _ensure_actionable
        assert _ensure_actionable("Fix R15 first.", self.FAILED) == "Fix R15 first."
        assert _ensure_actionable("All good.", []) == "All good."
