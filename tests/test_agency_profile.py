"""
tests/test_agency_profile.py
─────────────────────────────
Offline tests for the agency profile (no network): R7 agency schema variant, R32,
scoring/plumbing, page discovery helpers and fix templates.

Run:  pytest tests/test_agency_profile.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.profiles import get_profile
from src.layer_agency.agency_checks import check_r32
from src.layer2.r7_r9_r11 import check_r7
from src.layer7.aggregator import compute_score, get_failed_checks

ORG_SCHEMA_HTML = """
<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@type":"ProfessionalService","name":"Example Agency",
 "url":"https://example.com","description":"Jaipur software agency building web apps for startups.",
 "address":{"@type":"PostalAddress","addressLocality":"Jaipur"},
 "contactPoint":{"@type":"ContactPoint","email":"hello@example.com"},
 "sameAs":["https://www.linkedin.com/company/example"],
 "hasOfferCatalog":{"@type":"OfferCatalog","itemListElement":[
   {"@type":"Offer","itemOffered":{"@type":"Service","name":"Web Development"}}]}}
</script></head><body>x</body></html>
"""


class TestProfiles:
    def test_shopify_parity_with_v2(self):
        p = get_profile("shopify")
        assert p.max_of("scored") == 60 and p.max_of("checklist") == 9
        assert p.max_of("scored") + p.max_of("checklist") == 69

    def test_agency_maxima(self):
        p = get_profile("agency")
        assert p.max_of("scored") == 20          # R7 + R13
        assert p.max_of("checklist") == 8        # R1 R3 R5 R6 R11 R15 R23 R25
        assert p.max_of("provisional") == 0      # A1-A4 discarded
        assert [c.code for c in p.checks if c.kind == "informational"] == ["R32"]
        assert not [c for c in p.checks if c.code.startswith("A")]

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError):
            get_profile("nope")

    def test_agency_full_pass_scores_28(self):
        p = get_profile("agency")
        checks = {c.code: {"status": "PASS", "score": c.max_score} for c in p.checks
                  if c.kind != "informational"}
        info = compute_score(checks, p)
        assert info["grand_total"] == 28 and info["max_total"] == 28 and info["pct"] == 100.0
        assert info["max_provisional"] == 0

    def test_forward_looking_never_scored_or_failed(self):
        p = get_profile("agency")
        assert compute_score({"R32": {"status": "FORWARD-LOOKING", "score": 5}}, p)["grand_total"] == 0
        assert get_failed_checks({"R32": {"status": "FAIL"}}, p) == []

    def test_db_hash_keeps_shopify_rows_reachable(self):
        from src.utils.db import url_hash
        assert url_hash("https://x.com") == url_hash("https://x.com", "shopify")
        assert url_hash("https://x.com", "agency") != url_hash("https://x.com")


class TestR7Agency:
    def test_agency_schema_passes(self):
        r = check_r7(ORG_SCHEMA_HTML, profile_name="agency")
        assert r["status"] == "PASS" and r["score"] == 10

    def test_agency_schema_missing(self):
        r = check_r7("<html><body>none</body></html>", profile_name="agency")
        assert r["status"] == "FAIL" and "agency" in r["detail"]

    def test_product_only_schema_fails_for_agency(self):
        html = ('<html><head><script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"Product","name":"X"}</script></head></html>')
        assert check_r7(html, profile_name="agency")["status"] == "FAIL"

    def test_shopify_path_unchanged(self):
        assert check_r7(ORG_SCHEMA_HTML)["check"] == "R7"


class TestR32:
    def test_absent(self, monkeypatch):
        class F:  # noqa
            ok = False
            text = ""
            status_code = 404
        monkeypatch.setattr("src.layer_agency.agency_checks.safe_get", lambda u: F())
        r = check_r32("https://e.com")
        assert r["status"] == "FORWARD-LOOKING" and r["score"] == 0 and r["observability"]

    def test_present_but_html_page_is_not_llms_txt(self, monkeypatch):
        class F:  # noqa
            ok = True
            text = "<html><body>Not found, but 200 OK</body></html>" * 3
            status_code = 200
        monkeypatch.setattr("src.layer_agency.agency_checks.safe_get", lambda u: F())
        assert "No llms.txt" in check_r32("https://e.com")["detail"]

    def test_present(self, monkeypatch):
        class F:  # noqa
            ok = True
            text = "# Example\n> We build software for startups."
            status_code = 200
        monkeypatch.setattr("src.layer_agency.agency_checks.safe_get", lambda u: F())
        assert "found" in check_r32("https://e.com")["detail"]


class TestPageDiscovery:
    HOME = ("<html><body><nav><a href='/our-services'>Services</a><a href='/case-studies'>Work</a>"
            "<a href='https://other.com/services'>Ext</a></nav></body></html>")

    def test_discovers_same_site_links_only(self):
        from src.utils.agency_extractor import _discover, _SERVICES_NAV_RE
        assert _discover("https://e.com", self.HOME, _SERVICES_NAV_RE) == "https://e.com/our-services"
        only_ext = "<html><body><nav><a href='https://other.com/services'>S</a></nav></body></html>"
        assert _discover("https://e.com", only_ext, _SERVICES_NAV_RE) is None

    def test_extract_agency_returns_texts(self, monkeypatch):
        from src.utils import agency_extractor as ax

        class R:
            ok = True
            text = "<html><body><h1>Services</h1><p>" + "We build React apps. " * 30 + "</p></body></html>"
        monkeypatch.setattr(ax, "safe_get", lambda u: R())
        monkeypatch.setattr(ax, "jitter_sleep", lambda *a, **k: None)
        out = ax.extract_agency("https://e.com", "")
        assert out["pages"]["services"].endswith("/services")
        assert "React" in out["page_texts"]["services"]


class TestFixTemplates:
    def test_every_agency_check_has_a_template(self):
        from src.part2.fix_engine import get_fix_template
        for c in get_profile("agency").checks:
            t = get_fix_template(c.code, "agency")
            assert t and t["title"] and t["steps"], c.code

    def test_shopify_templates_still_served_by_default(self):
        from src.part2.fix_engine import get_fix_template
        assert "Shopify" in " ".join(get_fix_template("R16")["steps"])
