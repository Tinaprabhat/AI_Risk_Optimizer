"""Shopify profile — the original v2.0 configuration, extracted verbatim."""

from src.profiles import Profile, CheckSpec

_C = CheckSpec

SHOPIFY = Profile(
    name="shopify",
    title="AI Representation Optimizer",
    caption="Audit how AI shopping agents see your Shopify store — and fix what's blocking you.",
    entity_noun="store",
    checks=(
        _C("R1",  "robots.txt — AI crawler access",          "L1", "VERIFIED",   "checklist", 1),
        _C("R3",  "sitemap.xml — exists + product URLs",     "L1", "VERIFIED",   "checklist", 1),
        _C("R5",  "Bot protection blocking AI agents",       "L1", "CORRELATED", "checklist", 1),
        _C("R6",  "SSL valid",                               "L1", "VERIFIED",   "checklist", 1),
        _C("R7",  "schema.org commerce types",               "L2", "CORRELATED", "scored",    10),
        _C("R9",  "Price signal visible to crawler",         "L2", "CORRELATED", "scored",    10),
        _C("R11", "JSON-LD valid",                           "L2", "CORRELATED", "checklist", 1),
        _C("R13", "Product descriptions — specific not vague", "L3", "CORRELATED", "scored",  10),
        _C("R15", "FAQ page — covers buyer topics",          "L3", "CORRELATED", "checklist", 1),
        _C("R16", "Refund window — concrete days ★",         "L3", "CORRELATED", "scored",    10),
        _C("R17", "Shipping — concrete timeframe ★",         "L3", "CORRELATED", "scored",    10),
        _C("R23", "Contact page — branded email",            "L4", "CORRELATED", "checklist", 1),
        _C("R25", "Brand name — consistent",                 "L4", "CORRELATED", "checklist", 1),
        _C("R28", "UCP profile",                             "L5", "CORRELATED", "checklist", 1),
        _C("R30", "ACP feed quality (Shopify)",              "L5", "VERIFIED",   "informational", 0),
        _C("R31", "GMC homepage signals",                    "L5", "CORRELATED", "scored",    10),
    ),
    mcq_options={
        "category":      ["Fashion", "Beauty", "Home & Living", "Electronics", "Food & Beverage",
                          "Sports & Fitness", "Baby & Kids", "Jewellery", "Other"],
        "customer":      ["Budget-conscious", "Quality-first", "Eco-conscious", "Gift buyers", "B2B buyers"],
        "differentiator": ["Price", "Speed of delivery", "Quality / Craftsmanship",
                           "Sustainability", "Uniqueness / Handmade"],
        "tone":          ["Premium / Luxury", "Friendly / Casual", "Technical / Expert", "Playful / Fun"],
    },
    mcq_labels={
        "category": "Store category", "customer": "Primary customer",
        "differentiator": "Main differentiator", "tone": "Brand tone",
    },
    mcq_templates={
        "category":       "This is a {value} store.",
        "customer":       "Our primary customer is {value}.",
        "differentiator": "Our main differentiator is {value}.",
        "tone":           "Our brand tone is {value}.",
    },
    l6_page_keys=("homepage", "about", "product", "faq", "policies"),
    layer_names={
        "L1": "Layer 1 — Crawlability",
        "L2": "Layer 2 — Structured Data",
        "L3": "Layer 3 — Semantic Content",
        "L4": "Layer 4 — Trust Signals",
        "L5": "Layer 5 — AI-Era Protocols",
    },
    faq_topics=("returns", "shipping", "sizing", "payment", "contact", "warranty"),
    faq_min_pass=4,
    free_text_placeholder=(
        "We sell handmade leather wallets for professionals who value quality over price. "
        "Our products are made from full-grain leather, handcrafted in small batches."
    ),
    conclusion_system_prompt=(
        "You are an expert AI commerce auditor. "
        "Write a 3–4 sentence conclusion paragraph for a merchant about their store's AI visibility. "
        "Be specific, honest, plain English. No jargon. No generic advice. "
        "Name the exact checks that failed. Tell them the impact. "
        "End with the single most important fix."
    ),
    fix_persona="a helpful Shopify store advisor",
    templates=None,   # None → fix_engine's built-in Shopify TEMPLATES
)
