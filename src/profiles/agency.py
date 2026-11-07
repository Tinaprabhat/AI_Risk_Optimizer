"""Agency profile — IT-services agency discoverability (Cynbit, Jaipur)."""

from src.profiles import Profile, CheckSpec
from src.profiles.agency_templates import AGENCY_TEMPLATES

_C = CheckSpec

AGENCY = Profile(
    name="agency",
    title="AI Visibility Analyzer — IT Services",
    caption="Audit how AI assistants see your agency when buyers ask for web, app, AI/ML or SEO partners — and fix what's blocking you.",
    entity_noun="agency",
    checks=(
        _C("R1",  "robots.txt — AI crawler access",               "L1", "VERIFIED",        "checklist",     1),
        _C("R3",  "sitemap — exists + service/portfolio URLs",    "L1", "VERIFIED",        "checklist",     1),
        _C("R5",  "Bot protection blocking AI agents",            "L1", "CORRELATED",      "checklist",     1),
        _C("R6",  "SSL valid",                                    "L1", "VERIFIED",        "checklist",     1),
        _C("R7",  "schema.org Organization / Service markup",     "L2", "CORRELATED",      "scored",        10),
        _C("R11", "JSON-LD valid",                                "L2", "CORRELATED",      "checklist",     1),
        _C("R13", "Service descriptions — specific not vague",    "L3", "CORRELATED",      "scored",        10),
        _C("R15", "FAQ page — covers buyer questions",            "L3", "CORRELATED",      "checklist",     1),
        _C("R23", "Contact — branded email / phone",              "L4", "CORRELATED",      "checklist",     1),
        _C("R25", "Brand name — consistent on-site",              "L4", "CORRELATED",      "checklist",     1),
        _C("R32", "llms.txt present (forward-looking, unscored)", "L5", "FORWARD-LOOKING", "informational", 0),
    ),
    mcq_options={
        "service":        ["Web development", "App development", "AI / ML", "SEO / marketing",
                           "UI/UX design", "Cloud / DevOps", "Other"],
        "client":         ["Startups", "SMEs", "Enterprise", "E-commerce brands", "Agencies (white-label)"],
        "differentiator": ["Price", "Speed of delivery", "Technical depth", "Domain expertise",
                           "Post-launch support"],
        "engagement":     ["Fixed price", "Time & materials", "Monthly retainer", "Dedicated team"],
    },
    mcq_labels={
        "service": "Primary service line", "client": "Primary client type",
        "differentiator": "Main differentiator", "engagement": "Typical engagement model",
    },
    mcq_templates={
        "service":        "We are an IT services agency specialising in {value}.",
        "client":         "Our primary clients are {value}.",
        "differentiator": "Our main differentiator is {value}.",
        "engagement":     "We typically work on a {value} basis.",
    },
    l6_page_keys=("homepage", "about", "services", "portfolio", "faq"),
    layer_names={
        "L1": "Layer 1 — Crawlability",
        "L2": "Layer 2 — Structured Data",
        "L3": "Layer 3 — Semantic Content",
        "L4": "Layer 4 — Trust Signals",
        "L5": "Layer 5 — Agent-Readiness (forward-looking)",
    },
    faq_topics=("pricing", "timeline", "process", "support", "technology", "contract"),
    faq_min_pass=4,
    free_text_placeholder=(
        "We are a Jaipur-based software agency building web and mobile apps for startups and SMEs. "
        "We focus on React, Node.js and Flutter with fixed-scope delivery and post-launch support."
    ),
    conclusion_system_prompt=(
        "You are an expert AI-visibility auditor for IT services agencies. "
        "Write a 3–4 sentence conclusion paragraph for an agency owner about how visible and "
        "recommendable their agency is to AI assistants (ChatGPT, Gemini, Perplexity). "
        "Always call the business 'your agency' — never 'store'. State scores as points out of the maximum, not as percentages of checks. "
        "Be specific, honest, plain English. No jargon. No generic advice. "
        "Name the exact checks that failed. Tell them the impact. "
        "End with the single most important fix."
    ),
    fix_persona="a helpful advisor for IT-services agencies improving their AI discoverability",
    templates=AGENCY_TEMPLATES,
)
