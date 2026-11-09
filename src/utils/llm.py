"""
utils/llm.py
────────────
LLM call wrapper. Tries Groq first, then Gemini, then local Ollama Mistral.

Call order:
  1. Groq (openai/gpt-oss-120b)             — primary, fast, cloud (GROQ_API_KEY)
  2. Gemini 2.5 Flash (google-genai)         — fallback if Groq fails / no key
  3. Ollama Mistral (local)                  — fallback if both cloud providers fail

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
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # make sure .env is loaded even if this module is imported first

logger = logging.getLogger(__name__)

# ── CONFIG ─────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL      = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = "gemini-2.5-flash"   # preview-04-17 was deprecated ~Oct 2025
OLLAMA_HOST     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "mistral")

# ── GROQ ───────────────────────────────────────────────────────────────────
def _call_groq(prompt: str, system: str) -> Optional[str]:
    """Call Groq chat completions. Returns response text or None on any failure."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — skipping Groq")
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=2048,   # headroom: gpt-oss spends part of the budget on reasoning
            temperature=0.3,
            reasoning_effort="low",
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise ValueError("empty Groq response")
        logger.info(f"Groq OK ({len(text)} chars)")
        return text
    except Exception as e:
        logger.warning(f"Groq FAILED: {e}")
        return None


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
        try:
            # Current SDK: pip install google-genai
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=1024,
                    temperature=0.3,
                ),
            )
        except ImportError:
            # Legacy SDK: pip install google-generativeai
            import google.generativeai as genai
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
        text = (response.text or "").strip()
        if not text:
            raise ValueError("empty Gemini response")
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
        items  = models["models"] if isinstance(models, dict) else getattr(models, "models", [])
        names  = []
        for m in items:
            # ollama>=0.4 returns objects with .model; older versions return dicts with "name"
            names.append(m.get("name") or m.get("model") if isinstance(m, dict) else getattr(m, "model", ""))
        return any(OLLAMA_MODEL in (n or "") for n in names)
    except Exception:
        return False


# ── PUBLIC INTERFACE ───────────────────────────────────────────────────────
def call_llm(
    prompt: str,
    system: str = "You are a helpful expert AI commerce auditor. Be concise and specific.",
    fallback_text: str = "[LLM unavailable — showing rule-based fallback]",
) -> tuple[str, str]:
    """
    Try Groq → Gemini → Ollama Mistral → hardcoded fallback.

    Returns:
        (response_text, source) where source is one of:
        "groq" | "gemini" | "ollama_mistral" | "fallback"
    """
    # 0. Try Groq (primary)
    result = _call_groq(prompt, system)
    if result:
        return result, "groq"

    # 1. Try Gemini
    result = _call_gemini(prompt, system)
    if result:
        return result, "gemini"

    # 2. Try Ollama Mistral
    result = _call_ollama(prompt, system)
    if result:
        return result, "ollama_mistral"

    # 3. Rule-based fallback
    logger.error("All LLM providers failed — using hardcoded fallback")
    return fallback_text, "fallback"
