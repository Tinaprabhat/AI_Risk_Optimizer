"""
src/profiles/__init__.py
─────────────────────────
Domain profiles. One config object per audited business type, so the layers
never need `if domain == ...` branches scattered through them.

  shopify — original v2.0 behaviour (commerce store)  [default, regression-safe]
  agency  — IT-services agency discoverability (Cynbit)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CheckSpec:
    code: str
    label: str
    layer: str        # "L1".."L5"
    tier: str         # VERIFIED | CORRELATED | HYPOTHESIS | FORWARD-LOOKING
    kind: str         # scored | checklist | provisional | informational
    max_score: float


@dataclass(frozen=True)
class Profile:
    name: str
    title: str                       # UI title
    caption: str                     # UI caption
    entity_noun: str                 # "store" | "agency"
    checks: tuple
    mcq_options: dict                # UI choices (ordered)
    mcq_labels: dict                 # UI label per mcq key
    mcq_templates: dict              # L6 sentence templates
    l6_page_keys: tuple              # page_texts keys that feed L6 website vector
    layer_names: dict
    faq_topics: tuple
    faq_min_pass: int
    free_text_placeholder: str
    conclusion_system_prompt: str
    fix_persona: str
    templates: Optional[dict] = field(default=None, hash=False, compare=False)

    # ── derived helpers ──────────────────────────────────────────────────────
    def spec(self, code: str) -> Optional[CheckSpec]:
        for c in self.checks:
            if c.code == code:
                return c
        return None

    @property
    def check_order(self) -> list:
        return [c.code for c in self.checks]

    @property
    def labels(self) -> dict:
        return {c.code: c.label for c in self.checks}

    @property
    def layers(self) -> dict:
        return {c.code: c.layer for c in self.checks}

    def max_of(self, kind: str) -> float:
        return sum(c.max_score for c in self.checks if c.kind == kind)


def get_profile(name: str = "shopify") -> Profile:
    name = (name or "shopify").lower()
    if name == "agency":
        from src.profiles.agency import AGENCY
        return AGENCY
    if name == "shopify":
        from src.profiles.shopify import SHOPIFY
        return SHOPIFY
    raise ValueError(f"Unknown profile: {name!r} (expected 'shopify' or 'agency')")


AVAILABLE_PROFILES = ("agency", "shopify")
