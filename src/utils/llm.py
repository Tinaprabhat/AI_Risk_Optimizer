"""
utils/llm.py
────────────
LLM call wrapper. Tries Gemini first, falls back to local Ollama Mistral.

Call order:
  1. Gemini 2.5 Flash (google-generativeai)  — free tier, fast, cloud
  2. Ollama Mistral (local)                  — fallback if Gemini fails for any reason

Gemini failure triggers:
  - API key missing or invalid
  - Rate limit (429)
  - Any exception from the SDK

Ollama failure triggers:
  - Ollama not running locally
  - Model not pulled
  - Any exception from the ollama package

If BOTH fail → returns the hardcoded rule-based fallback string passed by caller.

Usage:
    from src.utils.llm import call_llm
    result = call_llm(prompt, fallback_text="[could not generate]")
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── CONFIG ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = "gemini-2.5-flash"   # preview-04-17 was deprecated ~Oct 2025
OLLAMA_HOST     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral")

# ── GEMINI ─────────────────────────────────────────────────────────────────
def _call_gemini(prompt: str, system: str) -> Optional[str]:
    """
    Call Gemini 2.5 Flash.
    Returns response text or None on any failure.
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping Gemini")
        return None
    try:
        import google.generativeai as genai  # import here to avoid hard dep at module load
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=1024,
                temperature=0.3,
            ),
        )
        text = response.text.strip()
        logger.info(f"Gemini OK ({len(text)} chars)")
        return text
    except Exception as e:
        msg = str(e)
        if "API_KEY" in msg.upper() or "invalid" in msg.lower() or "403" in msg:
            logger.warning(f"Gemini FAILED — API key invalid or revoked: {e}")
        elif "deprecated" in msg.lower() or "not found" in msg.lower() or "404" in msg:
            logger.warning(f"Gemini FAILED — model not found (update GEMINI_MODEL): {e}")
        elif "quota" in msg.lower() or "429" in msg:
            logger.warning(f"Gemini FAILED — quota/rate limit exceeded: {e}")
        else:
            logger.warning(f"Gemini FAILED: {e}")
        return None


# ── OLLAMA MISTRAL ─────────────────────────────────────────────────────────
def _call_ollama(prompt: str, system: str) -> Optional[str]:
    """
    Call local Ollama Mistral.
    Returns response text or None if Ollama is not available.
    """
    try:
        import ollama  # import here — ollama package
        client = ollama.Client(host=OLLAMA_HOST)
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
        )
        text = response["message"]["content"].strip()
        logger.info(f"Ollama Mistral OK ({len(text)} chars)")
        return text
    except Exception as e:
        logger.warning(f"Ollama FAILED: {e}")
        return None


def ollama_available() -> bool:
    """Check if Ollama is running and Mistral model is pulled. Used at startup."""
    try:
        import ollama
        client = ollama.Client(host=OLLAMA_HOST)
        models = client.list()
        names  = [m["name"] for m in models.get("models", [])]
        return any(OLLAMA_MODEL in n for n in names)
    except Exception:
        return False


# ── PUBLIC INTERFACE ───────────────────────────────────────────────────────
def call_llm(
    prompt: str,
    system: str = "You are a helpful expert AI commerce auditor. Be concise and specific.",
    fallback_text: str = "[LLM unavailable — showing rule-based fallback]",
) -> tuple[str, str]:
    """
    Try Gemini → Ollama Mistral → hardcoded fallback.

    Returns:
        (response_text, source) where source is one of:
        "gemini" | "ollama_mistral" | "fallback"
    """
    # 1. Try Gemini
    result = _call_gemini(prompt, system)
    if result:
        return result, "gemini"

    # 2. Try Ollama Mistral
    result = _call_ollama(prompt, system)
    if result:
        return result, "ollama_mistral"

    # 3. Rule-based fallback
    logger.error("Both Gemini and Ollama failed — using hardcoded fallback")
    return fallback_text, "fallback"
