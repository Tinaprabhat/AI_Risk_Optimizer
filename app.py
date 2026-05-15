"""
app.py
───────
Streamlit UI — AI Representation Optimizer

Layout:
  1. Input form (URL + description + 4 MCQs)
  2. Run audit button → progress bar
  3. Output:
     a. Score card  (X/79)
     b. Semantic gap display (L6)
     c. Conclusion paragraph (L7)
     d. Full checklist (all 16 checks with scores)
  4. Fix section — one expander per failed check → chatbot inside

Minimal design. No decorative elements. Information first.
"""

import os
import logging
import streamlit as st
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Representation Optimizer",
    page_icon="🔍",
    layout="wide",
)

# ── STARTUP CHECKS ────────────────────────────────────────────────────────────
@st.cache_resource
def startup():
    """Run once at app startup. Init DB, check Ollama availability."""
    from src.utils.db import init_db
    from src.utils.llm import ollama_available
    init_db()
    ollama_ok = ollama_available()
    return {"ollama_ok": ollama_ok}

status = startup()

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
MCQ_OPTIONS = {
    "category":      ["Fashion", "Beauty", "Home & Living", "Electronics", "Food & Beverage",
                      "Sports & Fitness", "Baby & Kids", "Jewellery", "Other"],
    "customer":      ["Budget-conscious", "Quality-first", "Eco-conscious", "Gift buyers", "B2B buyers"],
    "differentiator":["Price", "Speed of delivery", "Quality / Craftsmanship",
                      "Sustainability", "Uniqueness / Handmade"],
    "tone":          ["Premium / Luxury", "Friendly / Casual", "Technical / Expert", "Playful / Fun"],
}

STATUS_ICON = {
    "PASS": "✅", "FAIL": "❌", "WARN": "⚠️",
    "UNKNOWN": "❓", "ERROR": "💥",
    "FORWARD-LOOKING": "🔮", "NOT-APPLICABLE": "—",
}

CHECK_LABELS = {
    "R1":  "robots.txt — AI crawler access",
    "R3":  "sitemap.xml — exists + product URLs",
    "R5":  "Bot protection blocking AI agents",
    "R6":  "SSL valid",
    "R7":  "schema.org commerce types",
    "R9":  "Price signal visible to crawler",
    "R11": "JSON-LD valid",
    "R13": "Product descriptions — specific not vague",
    "R15": "FAQ page — covers buyer topics",
    "R16": "Refund window — concrete days ★",
    "R17": "Shipping — concrete timeframe ★",
    "R23": "Contact page — branded email",
    "R25": "Brand name — consistent",
    "R28": "UCP profile",
    "R30": "ACP feed quality (Shopify)",
    "R31": "GMC homepage signals",
}

CHECK_ORDER = [
    "R1","R3","R5","R6",       # L1
    "R7","R9","R11",            # L2
    "R13","R15","R16","R17",    # L3
    "R23","R25",                # L4
    "R28","R30","R31",          # L5
]

LAYER_LABELS = {
    "R1":"L1","R3":"L1","R5":"L1","R6":"L1",
    "R7":"L2","R9":"L2","R11":"L2",
    "R13":"L3","R15":"L3","R16":"L3","R17":"L3",
    "R23":"L4","R25":"L4",
    "R28":"L5","R30":"L5","R31":"L5",
}


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — INPUT FORM
# ═════════════════════════════════════════════════════════════════════════════

st.title("🔍 AI Representation Optimizer")
st.caption("Audit how AI shopping agents see your Shopify store — and fix what's blocking you.")

if not os.getenv("GEMINI_API_KEY"):
    st.warning("⚠️ GEMINI_API_KEY not set. Add it to your .env file. Ollama Mistral will be used as fallback.")

if not status["ollama_ok"]:
    st.info("ℹ️ Ollama not running locally. If Gemini fails, rule-based fallbacks will be used for conclusions.")

st.divider()

with st.form("audit_form"):
    store_url = st.text_input(
        "Store URL",
        placeholder="https://yourstore.com",
        help="Full URL including https://",
    )

    free_text = st.text_area(
        "Describe your store in 2–3 sentences",
        placeholder="We sell handmade leather wallets for professionals who value quality over price. Our products are made from full-grain leather, handcrafted in small batches.",
        height=100,
    )

    col1, col2 = st.columns(2)
    with col1:
        cat  = st.selectbox("Store category",       MCQ_OPTIONS["category"])
        cust = st.selectbox("Primary customer",      MCQ_OPTIONS["customer"])
    with col2:
        diff = st.selectbox("Main differentiator",   MCQ_OPTIONS["differentiator"])
        tone = st.selectbox("Brand tone",            MCQ_OPTIONS["tone"])

    submitted = st.form_submit_button("Run Audit", type="primary", use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RUN AUDIT
# ═════════════════════════════════════════════════════════════════════════════

if submitted:
    if not store_url:
        st.error("Please enter a store URL.")
        st.stop()
    if not free_text:
        st.error("Please describe your store.")
        st.stop()

    mcq = {
        "category":       cat,
        "customer":       cust,
        "differentiator": diff,
        "tone":           tone,
    }

    # Progress display
    progress_bar = st.progress(0, text="Starting audit...")
    status_text  = st.empty()
    step_count   = [0]
    TOTAL_STEPS  = 8

    def update_progress(msg: str):
        step_count[0] += 1
        pct = min(int((step_count[0] / TOTAL_STEPS) * 100), 95)
        progress_bar.progress(pct, text=msg)
        status_text.caption(f"⏳ {msg}")

    try:
        from src.auditor import run_audit
        result = run_audit(
            store_url=store_url,
            free_text=free_text,
            mcq=mcq,
            use_cache=True,
            progress_cb=update_progress,
        )
        progress_bar.progress(100, text="Audit complete.")
        status_text.empty()
        st.session_state["result"] = result
        st.session_state["store_url"] = store_url

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Audit failed: {e}")
        logger.exception("Audit failed")
        st.stop()


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — RESULTS
# ═════════════════════════════════════════════════════════════════════════════

if "result" not in st.session_state:
    st.stop()

result    = st.session_state["result"]
store_url = st.session_state.get("store_url", result["store_url"])
score     = result["score"]
gap       = result["gap"]
checks    = result["checks"]
failed    = result["failed"]

st.divider()

# ── 3a. SCORE CARD ────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Total Score", f"{score['grand_total']} / {score['max_total']}", f"{score['pct']}%")
with c2:
    st.metric("Scored checks (0–70)", f"{score['scored_total']} / {score['max_scored']}")
with c3:
    st.metric("Checklist (0–9)", f"{score['checklist_total']} / {score['max_checklist']}")

llm_note = {"gemini": "✦ Gemini", "ollama_mistral": "✦ Ollama Mistral", "fallback": "✦ Rule-based"}.get(result.get("llm_source", ""), "")

# ── 3b. CONCLUSION ────────────────────────────────────────────────────────────
st.subheader("What this means for your store")
st.info(result.get("conclusion", "Conclusion unavailable."))
if llm_note:
    st.caption(f"Generated by: {llm_note}")

st.divider()

# ── 3c. SEMANTIC GAP ─────────────────────────────────────────────────────────
with st.expander("🧠 Semantic Gap — What you think vs what AI reads", expanded=True):
    if gap.get("error"):
        st.warning(f"Semantic gap computation error: {gap['error']}")
    else:
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            v = gap.get("gap_IW")
            label = gap.get("IW_label", "N/A")
            color = "🟢" if label == "ALIGNED" else "🟡" if label == "DRIFT" else "🔴"
            st.metric("Intent vs Website", f"{v}" if v is not None else "N/A", label)
            st.caption(f"{color} {label}")
        with col_b:
            v = gap.get("gap_IS")
            label = gap.get("IS_label", "N/A")
            color = "🟢" if label == "ALIGNED" else "🟡" if label == "DRIFT" else "🔴"
            st.metric("Intent vs Schema", f"{v}" if v is not None else "N/A", label)
            st.caption(f"{color} {label}")
        with col_c:
            v = gap.get("gap_WS")
            label = gap.get("WS_label", "N/A")
            color = "🟢" if label == "ALIGNED" else "🟡" if label == "DRIFT" else "🔴"
            st.metric("Website vs Schema", f"{v}" if v is not None else "N/A", label)
            st.caption(f"{color} {label}")

        st.divider()
        st.text(gap.get("summary", "No summary available."))

st.divider()

# ── 3d. FULL CHECKLIST ────────────────────────────────────────────────────────
st.subheader("📋 All 16 Checks")

prev_layer = None
for code in CHECK_ORDER:
    check_res = checks.get(code, {})
    layer     = LAYER_LABELS.get(code, "")

    # Layer header
    if layer != prev_layer:
        layer_names = {
            "L1": "Layer 1 — Crawlability",
            "L2": "Layer 2 — Structured Data",
            "L3": "Layer 3 — Semantic Content",
            "L4": "Layer 4 — Trust Signals",
            "L5": "Layer 5 — AI-Era Protocols",
        }
        st.markdown(f"**{layer_names.get(layer, layer)}**")
        prev_layer = layer

    status_val = check_res.get("status", "UNKNOWN")
    icon       = STATUS_ICON.get(status_val, "❓")
    score_val  = check_res.get("score", 0)
    max_val    = 1 if code in {"R1","R3","R5","R6","R11","R15","R23","R25","R28"} else 10
    detail     = check_res.get("detail", "")
    tier       = check_res.get("tier", "")

    col_icon, col_code, col_label, col_score, col_detail = st.columns([0.5, 0.8, 3, 1, 4])
    with col_icon:
        st.write(icon)
    with col_code:
        st.write(f"`{code}`")
    with col_label:
        st.write(CHECK_LABELS.get(code, code))
    with col_score:
        st.write(f"{score_val}/{max_val}")
    with col_detail:
        st.caption(detail[:80] + "…" if len(detail) > 80 else detail)

st.divider()

# ── 3e. OBSERVABILITY — How we checked this ────────────────────────────────────
st.subheader("🔍 Observability — How we validated each check")
obs_block = result.get("observability", {})

if obs_block:
    per_check_traces = obs_block.get("per_check_traces", {})
    
    if per_check_traces:
        st.caption("Expand any check below to see the raw evidence and reasoning behind the result.")
        
        for check_code in sorted(per_check_traces.keys()):
            if check_code.startswith("L"):  # Skip L6_gaps for now
                continue
            
            trace = per_check_traces.get(check_code, {})
            check_name = CHECK_LABELS.get(check_code, check_code)
            status = trace.get("status", "?")
            
            with st.expander(f"**{check_code}** — {check_name} ({status})", expanded=False):
                cols = st.columns(2)
                with cols[0]:
                    st.markdown("**What we did:**")
                    st.text(trace.get("what_we_did", "(not recorded)"))
                with cols[1]:
                    st.markdown("**What AI sees:**")
                    st.text(trace.get("what_AI_sees", "(not recorded)"))
                
                st.markdown("---")
                st.markdown("**Raw evidence:**")
                st.code(trace.get("raw_evidence", "(not recorded)")[:500], language="text")
    
    # Gap observability
    gap_obs = obs_block.get("L6_gaps", {})
    if gap_obs:
        st.markdown("**Layer 6 — Semantic Gap Details:**")
        for gap_name in ["IW", "IS", "WS"]:
            if gap_name in gap_obs:
                g = gap_obs[gap_name]
                with st.expander(f"Gap {gap_name}: {g.get('label', '?')}", expanded=False):
                    st.caption(g.get("question", ""))
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**Source A:**")
                        st.caption(g.get("source_A", ""))
                        st.text(g.get("preview_A", "")[:300])
                    with col_b:
                        st.markdown("**Source B:**")
                        st.caption(g.get("source_B", ""))
                        st.text(g.get("preview_B", "")[:300])
else:
    st.info("Observability data not available for this audit.")

st.divider()

# ── 3f. OBSERVABILITY LOG ─────────────────────────────────────────────────────
log_path = result.get("log_path", "")
if log_path:
    st.caption(f"📄 Observability log written to: `{log_path}`")
    st.caption("Log contains: raw evidence, causality traces, what AI sees — per check.")

st.divider()

# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — FIX ENGINE
# ═════════════════════════════════════════════════════════════════════════════

if not failed:
    st.success("✅ No critical issues found. Your store is well-configured for AI discovery.")
    st.stop()

st.subheader(f"🔧 Fix {len(failed)} Issue(s)")
st.caption("Each issue below has a step-by-step fix guide. Click to open.")

from src.part2.fix_engine import (
    get_fix_template, chatbot_first_message, chatbot_reply
)
from src.utils.db import (
    save_chat_message, load_chat_history, clear_chat_history
)

for item in failed:
    code   = item["code"]
    detail = item["detail"]
    fix    = item["fix"]
    icon   = STATUS_ICON.get(item["status"], "❓")
    tmpl   = get_fix_template(code)
    title  = tmpl["title"] if tmpl else f"Fix {code}"

    with st.expander(f"{icon} {code} — {title}"):

        # Show what was found
        st.caption(f"**Found:** {detail}")

        # Show template / copy-paste fix
        if tmpl:
            st.markdown("**Steps:**")
            for i, step in enumerate(tmpl["steps"], 1):
                st.write(f"{i}. {step}")

            if tmpl.get("template"):
                st.markdown("**Template / Copy-paste:**")
                st.code(tmpl["template"], language="text")

        st.divider()

        # ── CHATBOT ───────────────────────────────────────────────────────────
        st.markdown("**💬 Ask the Fix Assistant**")

        chat_key = f"chat_{code}"

        # Init chat if empty — show first message
        if chat_key not in st.session_state:
            first_msg = chatbot_first_message(code, detail)
            # Load from DB (resumable)
            history = load_chat_history(store_url, code)
            if not history:
                save_chat_message(store_url, code, "bot", first_msg)
                history = [{"role": "bot", "message": first_msg}]
            st.session_state[chat_key] = history

        # Display chat history
        for msg in st.session_state[chat_key]:
            role    = msg["role"]
            content = msg["message"]
            if role == "bot":
                st.chat_message("assistant").write(content)
            else:
                st.chat_message("user").write(content)

        # User input
        user_input = st.chat_input(
            f"Ask about fixing {code}...",
            key=f"input_{code}",
        )

        if user_input:
            # Save user message
            st.session_state[chat_key].append({"role": "user", "message": user_input})
            save_chat_message(store_url, code, "user", user_input)

            # Get LLM reply
            with st.spinner("Thinking..."):
                reply, source = chatbot_reply(
                    check_code=code,
                    check_detail=detail,
                    check_fix=fix,
                    store_url=store_url,
                    user_message=user_input,
                    history=st.session_state[chat_key],
                )

            # Save bot reply
            st.session_state[chat_key].append({"role": "bot", "message": reply})
            save_chat_message(store_url, code, "bot", reply)
            st.rerun()

        # Clear chat button
        if st.button(f"Clear conversation", key=f"clear_{code}"):
            clear_chat_history(store_url, code)
            if chat_key in st.session_state:
                del st.session_state[chat_key]
            st.rerun()

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("AI Representation Optimizer · v2.0 · Scores are directional indicators, not guarantees of AI recommendation behavior.")