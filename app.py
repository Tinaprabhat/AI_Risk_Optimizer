"""
app.py
───────
Streamlit UI — AI Representation Optimizer

Profiles (sidebar):  agency (default, IT-services / Cynbit)  |  shopify (commerce)

Layout:
  1. Input form (URL + description + 4 profile-specific MCQs)
  2. Run audit button → progress bar
  3. Output:
     a. Score card  (headline X/max  +  provisional score for unvalidated checks)
     b. Semantic gap display (L6)
     c. Conclusion paragraph (L7)
     d. Full checklist (all checks of the profile, provisional ones flagged)
     e. Markdown report download
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
from src.profiles import get_profile, AVAILABLE_PROFILES

STATUS_ICON = {
    "PASS": "✅", "FAIL": "❌", "WARN": "⚠️",
    "UNKNOWN": "❓", "ERROR": "💥",
    "FORWARD-LOOKING": "🔮", "NOT-APPLICABLE": "—", "INFORMATIONAL": "ℹ️",
}

# Sidebar profile selector. APP_PROFILE env var sets the default (agency = Cynbit deployment).
_default_profile = os.getenv("APP_PROFILE", "agency").lower()
if _default_profile not in AVAILABLE_PROFILES:
    _default_profile = "agency"
with st.sidebar:
    st.header("Audit profile")
    profile_name = st.selectbox(
        "What are you auditing?",
        AVAILABLE_PROFILES,
        index=AVAILABLE_PROFILES.index(_default_profile),
        format_func=lambda p: {"agency": "IT-services agency", "shopify": "Shopify store"}.get(p, p),
    )
    st.caption("Checks tagged **provisional** are unvalidated hypotheses. They are reported "
               "separately and do not count toward the headline score.")

PROFILE = get_profile(profile_name)
MCQ_OPTIONS = PROFILE.mcq_options


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — INPUT FORM
# ═════════════════════════════════════════════════════════════════════════════

st.title(f"🔍 {PROFILE.title}")
st.caption(PROFILE.caption)

if not os.getenv("GEMINI_API_KEY"):
    st.warning("⚠️ GEMINI_API_KEY not set. Add it to your .env file. Ollama Mistral will be used as fallback.")

if not status["ollama_ok"]:
    st.info("ℹ️ Ollama not running locally. If Gemini fails, rule-based fallbacks will be used for conclusions.")

st.divider()

with st.form("audit_form"):
    store_url = st.text_input(
        f"{PROFILE.entity_noun.capitalize()} URL",
        placeholder="https://yourdomain.com",
        help="Full URL including https://",
    )

    free_text = st.text_area(
        f"Describe your {PROFILE.entity_noun} in 2–3 sentences",
        placeholder=PROFILE.free_text_placeholder,
        height=100,
    )

    mcq_values = {}
    col1, col2 = st.columns(2)
    for i, key in enumerate(PROFILE.mcq_options.keys()):
        with (col1 if i % 2 == 0 else col2):
            mcq_values[key] = st.selectbox(PROFILE.mcq_labels[key], PROFILE.mcq_options[key])

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

    mcq = dict(mcq_values)

    # Progress display
    progress_bar = st.progress(0, text="Starting audit...")
    status_text  = st.empty()
    step_count   = [0]
    TOTAL_STEPS  = 10

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
            profile=PROFILE.name,
        )
        progress_bar.progress(100, text="Audit complete.")
        status_text.empty()
        st.session_state["result"] = result
        st.session_state["store_url"] = store_url
        # Fix-chat state from a previous audit must not leak into this one
        for _k in [k for k in st.session_state if k.startswith("chat_")]:
            del st.session_state[_k]

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
RPROF     = get_profile(result.get("profile", "shopify"))   # profile the result was produced with
if RPROF.name != PROFILE.name:
    st.warning(f"Showing results from the **{RPROF.name}** profile. Run a new audit to use **{PROFILE.name}**.")
CHECK_LABELS = RPROF.labels
CHECK_ORDER  = RPROF.check_order
LAYER_LABELS = RPROF.layers
store_url = st.session_state.get("store_url", result["store_url"])
score     = result["score"]
gap       = result["gap"]
checks    = result["checks"]
failed    = result["failed"]

st.divider()

# ── 3a. SCORE CARD ────────────────────────────────────────────────────────────
has_prov = score.get("max_provisional", 0) > 0
cols = st.columns(4 if has_prov else 3)
with cols[0]:
    st.metric("Total Score", f"{score['grand_total']:g} / {score['max_total']:g}", f"{score['pct']}%")
with cols[1]:
    st.metric(f"Scored checks (0–{score['max_scored']:g})", f"{score['scored_total']:g} / {score['max_scored']:g}")
with cols[2]:
    st.metric(f"Checklist (0–{score['max_checklist']:g})", f"{score['checklist_total']:g} / {score['max_checklist']:g}")
if has_prov:
    with cols[3]:
        st.metric("Provisional (unvalidated)", f"{score['provisional_total']:g} / {score['max_provisional']:g}",
                  f"{score.get('provisional_pct', 0)}%", delta_color="off")

llm_note = {"gemini": "✦ Gemini", "ollama_mistral": "✦ Ollama Mistral", "fallback": "✦ Rule-based"}.get(
    result.get("conclusion_source", result.get("llm_source", "")), "")

# ── 3b. CONCLUSION ────────────────────────────────────────────────────────────
st.subheader(f"What this means for your {RPROF.entity_noun}")
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
st.subheader(f"📋 All {len(RPROF.checks)} Checks")

prev_layer = None
for code in CHECK_ORDER:
    check_res = checks.get(code, {})
    layer     = LAYER_LABELS.get(code, "")

    # Layer header
    if layer != prev_layer:
        st.markdown(f"**{RPROF.layer_names.get(layer, layer)}**")
        prev_layer = layer

    status_val = check_res.get("status", "UNKNOWN")
    icon       = STATUS_ICON.get(status_val, "❓")
    score_val  = check_res.get("score", 0)
    spec       = RPROF.spec(code)
    max_val    = f"{spec.max_score:g}" if spec else "-"
    is_prov    = bool(spec and spec.kind == "provisional")
    detail     = check_res.get("detail", "")
    tier       = check_res.get("tier", "")

    col_icon, col_code, col_label, col_score, col_detail = st.columns([0.5, 0.8, 3, 1, 4])
    with col_icon:
        st.write(icon)
    with col_code:
        st.write(f"`{code}`")
    with col_label:
        st.write(CHECK_LABELS.get(code, code) + (" 🧪 *provisional*" if is_prov else ""))
    with col_score:
        st.write("—" if (spec and spec.kind == "informational") else f"{score_val}/{max_val}")
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

def build_markdown_report() -> str:
    """Assemble a shareable Markdown report from the stored result."""
    lines = [f"# {RPROF.title} — {result['store_url']}", ""]
    lines.append(f"**Score:** {score['grand_total']:g} / {score['max_total']:g} ({score['pct']}%)")
    if score.get("max_provisional", 0):
        lines.append(f"**Provisional (unvalidated checks):** {score['provisional_total']:g} / "
                     f"{score['max_provisional']:g} ({score.get('provisional_pct', 0)}%)")
    lines += ["", "## Conclusion", result.get("conclusion", ""), "", "## Checks", "",
              "| Code | Check | Tier | Status | Score | Detail |", "|---|---|---|---|---|---|"]
    for code in CHECK_ORDER:
        c = checks.get(code, {})
        sp = RPROF.spec(code)
        mx = "-" if (sp and sp.kind == "informational") else f"{sp.max_score:g}" if sp else "-"
        detail = (c.get("detail", "") or "").replace("|", "/").replace("\n", " ")
        lines.append(f"| {code} | {CHECK_LABELS.get(code, code)} | {sp.tier if sp else ''} | "
                     f"{c.get('status', 'UNKNOWN')} | {c.get('score', 0)}/{mx} | {detail} |")
    if failed:
        lines += ["", "## Fixes"]
        for item in failed:
            t = get_fix_template(item["code"], RPROF.name)
            lines += ["", f"### {item['code']} — {t['title'] if t else item['code']}",
                      f"*Found:* {item['detail']}"]
            if t:
                lines += [""] + [f"{i}. {st_}" for i, st_ in enumerate(t["steps"], 1)]
                if t.get("template"):
                    lines += ["", "```", t["template"], "```"]
    lines += ["", gap.get("summary", "")]
    return "\n".join(lines)


from src.part2.fix_engine import (
    get_fix_template, chatbot_first_message, chatbot_reply
)

st.download_button(
    "⬇️ Download report (Markdown)",
    data=build_markdown_report(),
    file_name=f"ai_visibility_{RPROF.name}_{result['store_url'].split('//')[-1].replace('/', '_')}.md",
    mime="text/markdown",
)

if not failed:
    st.success(f"✅ No critical issues found. Your {RPROF.entity_noun} is well-configured for AI discovery.")
    st.stop()

st.subheader(f"🔧 Fix {len(failed)} Issue(s)")
st.caption("Each issue below has a step-by-step fix guide. Click to open.")

from src.utils.db import (
    save_chat_message, load_chat_history, clear_chat_history
)

for item in failed:
    code   = item["code"]
    detail = item["detail"]
    fix    = item["fix"]
    icon   = STATUS_ICON.get(item["status"], "❓")
    tmpl   = get_fix_template(code, RPROF.name)
    title  = tmpl["title"] if tmpl else f"Fix {code}"
    if item.get("kind") == "provisional":
        title += " (provisional)"

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

        chat_key = f"chat_{RPROF.name}_{code}"

        # Init chat if empty — show first message
        if chat_key not in st.session_state:
            first_msg = chatbot_first_message(code, detail, RPROF.name)
            # Load from DB (resumable)
            history = load_chat_history(store_url, code, RPROF.name)
            if not history:
                save_chat_message(store_url, code, "bot", first_msg, RPROF.name)
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
            save_chat_message(store_url, code, "user", user_input, RPROF.name)

            # Get LLM reply
            with st.spinner("Thinking..."):
                reply, source = chatbot_reply(
                    check_code=code,
                    check_detail=detail,
                    check_fix=fix,
                    store_url=store_url,
                    user_message=user_input,
                    history=st.session_state[chat_key],
                    profile=RPROF.name,
                )

            # Save bot reply
            st.session_state[chat_key].append({"role": "bot", "message": reply})
            save_chat_message(store_url, code, "bot", reply, RPROF.name)
            st.rerun()

        # Clear chat button
        if st.button(f"Clear conversation", key=f"clear_{code}"):
            clear_chat_history(store_url, code, RPROF.name)
            if chat_key in st.session_state:
                del st.session_state[chat_key]
            st.rerun()

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("AI Representation Optimizer · v2.0 · Scores are directional indicators, not guarantees of AI recommendation behavior.")