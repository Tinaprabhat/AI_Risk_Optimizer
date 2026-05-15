"""
utils/embedder.py
─────────────────
Singleton wrapper for all-MiniLM-L6-v2 embeddings.

Model is loaded ONCE at first call and cached.
CPU-only — no GPU required.
Context window: 256 tokens (hard limit — we chunk before embedding).
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

_model = None  # module-level singleton


def _get_model():
    """Load model once and cache it. Thread-safe for single-process Streamlit."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading all-MiniLM-L6-v2 (first call — ~2s)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Model loaded.")
    return _model


def embed(text: str) -> np.ndarray:
    """
    Embed a single text string.
    Text is truncated to 256 tokens by the model internally.

    Args:
        text: Input string to embed.

    Returns:
        1D numpy array (384 dimensions).
    """
    model = _get_model()
    return model.encode(text, convert_to_numpy=True)


def embed_batch(texts: List[str]) -> np.ndarray:
    """
    Embed a list of strings in one batch call (faster than calling embed() N times).

    Args:
        texts: List of strings.

    Returns:
        2D numpy array, shape (len(texts), 384).
    """
    model = _get_model()
    return model.encode(texts, convert_to_numpy=True, batch_size=32)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two 1D vectors.
    Returns float in [-1, 1]. Higher = more similar.
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / (norm_a * norm_b), -1.0, 1.0))


def chunk_text(text: str, max_sentences: int = 30) -> str:
    """
    Cap text to max_sentences sentences before embedding.
    Prevents silent truncation by the 256-token model limit.

    Args:
        text:          Raw text string.
        max_sentences: Max number of sentences to keep.

    Returns:
        Truncated string.
    """
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:max_sentences])
