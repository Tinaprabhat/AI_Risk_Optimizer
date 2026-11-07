"""Hardcoded fix templates for the agency profile (zero-hallucination layer)."""

AGENCY_TEMPLATES = {
    "R1": {
        "title": "Remove AI crawler blocks from robots.txt",
        "summary": "Your robots.txt blocks AI agents, so ChatGPT, Gemini and Perplexity cannot read your services or case studies.",
        "steps": [
            "Open yourdomain.com/robots.txt (in WordPress: SEO plugin → File editor)",
            "Find 'Disallow: /' rules under AI user-agents (GPTBot, ClaudeBot, Google-Extended, PerplexityBot)",
            "Change them to 'Allow: /'",
            "Reload robots.txt and confirm the change is live",
        ],
        "template": (
            "User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /\n\n"
            "User-agent: Google-Extended\nAllow: /\n\nUser-agent: PerplexityBot\nAllow: /\n"
        ),
    },
    "R3": {
        "title": "Publish a sitemap that lists services and portfolio pages",
        "summary": "AI crawlers use sitemap.xml to discover your service, portfolio and case-study pages. Missing or thin sitemaps hide them.",
        "steps": [
            "Generate a sitemap (WordPress: Yoast/RankMath; Next.js: next-sitemap; static sites: any sitemap generator)",
            "Make sure service, portfolio/case-study and about pages are included",
            "Serve it at yourdomain.com/sitemap.xml and reference it in robots.txt",
            "Submit it in Google Search Console",
        ],
        "template": "Sitemap: https://yourdomain.com/sitemap.xml   # add this line to robots.txt",
    },
    "R5": {
        "title": "Allow AI crawlers through bot protection",
        "summary": "Cloudflare or another WAF is treating AI crawlers as malicious bots.",
        "steps": [
            "Open your CDN/WAF dashboard (e.g. Cloudflare → Security → Bots)",
            "Enable 'Allow verified bots' / allow-list GPTBot, ClaudeBot, PerplexityBot, Google-Extended",
            "Re-test by fetching the homepage with an AI user-agent",
        ],
        "template": "",
    },
    "R6": {
        "title": "Fix your SSL certificate",
        "summary": "An invalid or expired certificate disqualifies a site from being recommended.",
        "steps": [
            "Check expiry at your host or via an SSL checker",
            "Renew / enable auto-renew (Let's Encrypt or your host's managed certificate)",
            "Force HTTPS redirects site-wide",
        ],
        "template": "",
    },
    "R7": {
        "title": "Add Organization / ProfessionalService schema",
        "summary": "Without machine-readable markup, AI has to guess who you are, where you operate and what you sell.",
        "steps": [
            "Paste the JSON-LD block below into the <head> of your homepage",
            "Replace every placeholder with your real details (keep it identical to what visitors see)",
            "Validate at validator.schema.org, then re-run this audit",
        ],
        "template": (
            '<script type="application/ld+json">\n'
            '{\n'
            '  "@context": "https://schema.org",\n'
            '  "@type": "ProfessionalService",\n'
            '  "name": "Your Agency Name",\n'
            '  "url": "https://yourdomain.com",\n'
            '  "logo": "https://yourdomain.com/logo.png",\n'
            '  "description": "One specific sentence: what you build, for whom, with which stack.",\n'
            '  "address": {"@type": "PostalAddress", "addressLocality": "Jaipur", "addressRegion": "Rajasthan", "addressCountry": "IN"},\n'
            '  "areaServed": ["Jaipur", "India"],\n'
            '  "contactPoint": {"@type": "ContactPoint", "email": "hello@yourdomain.com", "contactType": "sales"},\n'
            '  "sameAs": ["https://www.linkedin.com/company/yourcompany", "https://clutch.co/profile/yourcompany"],\n'
            '  "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Services", "itemListElement": [\n'
            '    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Web Development"}},\n'
            '    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Mobile App Development"}}\n'
            '  ]}\n'
            '}\n'
            '</script>'
        ),
    },
    "R11": {
        "title": "Repair malformed JSON-LD",
        "summary": "Crawlers silently ignore JSON-LD that fails to parse, so your markup does nothing.",
        "steps": [
            "Copy each ld+json script block into a JSON validator",
            "Fix trailing commas, unescaped quotes and missing brackets",
            "Re-validate at validator.schema.org",
        ],
        "template": "",
    },
    "R13": {
        "title": "Make service descriptions specific",
        "summary": "Phrases like 'innovative solutions' or 'end-to-end services' give AI nothing to match against a buyer's request.",
        "steps": [
            "For each service, state: what you build, the stack, typical timeline, and who it is for",
            "Replace adjectives with facts (numbers, technologies, deliverables)",
            "Keep one service per page with a descriptive H1",
        ],
        "template": (
            "Bad : \"We provide dynamic and innovative web solutions.\"\n"
            "Good: \"We build React + Node.js web apps for startups: MVPs in 6-10 weeks, "
            "fixed scope, deployed on AWS, with 3 months of post-launch support.\""
        ),
    },
    "R15": {
        "title": "Publish an FAQ that answers buyer questions",
        "summary": "AI answers buyer questions from pages it can read. No FAQ means it answers from competitors instead.",
        "steps": [
            "Create /faq with at least 8 real questions",
            "Cover pricing, timeline, process, support, technology and contract terms",
            "Add FAQPage JSON-LD for the same questions",
        ],
        "template": (
            "Q: How much does a website cost?\nA: Projects typically start at Rs X for ... and go up to Rs Y for ...\n\n"
            "Q: How long does a project take?\nA: A standard business site takes 3-5 weeks; an MVP app 8-12 weeks.\n\n"
            "Q: What happens after launch?\nA: 30 days of free bug-fixes, then optional monthly support."
        ),
    },
    "R23": {
        "title": "Add a contact page with a branded email",
        "summary": "A reachable, accountable business is a trust signal. A form-only page or a Gmail address weakens it.",
        "steps": [
            "Create /contact with a branded email (name@yourdomain.com), phone and office address",
            "Link it in the header or footer",
            "Mirror the details in your ContactPoint schema",
        ],
        "template": "Email: hello@yourdomain.com\nPhone: +91 XXXXX XXXXX\nAddress: <street>, Jaipur, Rajasthan, India",
    },
    "R25": {
        "title": "Use one consistent brand name",
        "summary": "Variants of your name (e.g. 'Cynbit' vs 'Cybit' vs 'Cynbit Technologies') can make AI treat you as separate entities.",
        "steps": [
            "Pick one canonical name",
            "Set og:site_name, Organization.name and the <title> prefix to exactly that name",
            "Update directory profiles (LinkedIn, Clutch, Google Business) to match — this audit only checks your own site",
        ],
        "template": '<meta property="og:site_name" content="Your Agency Name" />',
    },
    "R32": {
        "title": "Add an llms.txt file (forward-looking)",
        "summary": "llms.txt is an emerging convention for telling AI systems what your site is about. No proven effect yet; it is not scored.",
        "steps": [
            "Create /llms.txt at your domain root",
            "Summarise who you are and link to your key pages",
        ],
        "template": (
            "# Your Agency Name\n"
            "> Jaipur-based software agency building web, mobile and AI products for startups and SMEs.\n\n"
            "## Services\n- [Web Development](https://yourdomain.com/services/web)\n"
            "- [Mobile Apps](https://yourdomain.com/services/mobile)\n\n"
            "## Proof\n- [Case studies](https://yourdomain.com/case-studies)\n\n"
            "## Contact\n- hello@yourdomain.com"
        ),
    },
}
