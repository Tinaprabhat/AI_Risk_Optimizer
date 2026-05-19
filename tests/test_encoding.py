"""
tests/test_encoding.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for encoding / decoding correctness across the pipeline.

Checks that no layer produces garbage output at any stage:

  Level 1 — TextCleaner
    • bytes → str  (UTF-8 primary, Latin-1 fallback)
    • <script>/<style> blobs stripped before get_text()
    • Unicode characters preserved (accented, CJK, emoji, special punctuation)
    • HTML entities decoded (&amp; → &, etc.)
    • Null bytes not leaked into output
    • Whitespace collapsed

  Level 2 — Embedder
    • embed() → (384,) float32, no NaN/Inf
    • embed_batch() → (N, 384), per-row consistent with single embed()
    • Unicode / garbage text → still produces valid vector
    • cosine_sim() always in [-1.0, 1.0]
    • cosine_sim(zero_vector, *) → 0.0, not NaN

  Level 3 — Pipeline (clean → embed → sim)
    • HTML with JS blob → clean text has no JS → embedding is valid
    • Unicode HTML → clean text → cosine_sim in range
    • Text containing replacement chars (\\ufffd) → embedding valid (no NaN)

Run:
  pytest tests/test_encoding.py -v -m unit
"""

import sys
import os
import re
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── HELPERS ────────────────────────────────────────────────────────────────────

def _has_null_bytes(text: str) -> bool:
    return "\x00" in text

def _has_replacement_chars(text: str) -> bool:
    return "�" in text

_JS_PATTERNS = re.compile(
    r"window\.__[A-Z_]+\s*=|JSON\.parse\s*\(|function\s*\(\s*\)\s*\{|\bvar\s+\w+\s*=",
    re.I,
)

def _has_js_garbage(text: str) -> bool:
    """Return True if raw JS/JSON source code leaked into extracted text."""
    return bool(_JS_PATTERNS.search(text))

def _is_valid_vector(vec) -> bool:
    """Shape (384,), dtype float, no NaN or Inf."""
    return (
        isinstance(vec, np.ndarray)
        and vec.shape == (384,)
        and not np.any(np.isnan(vec))
        and not np.any(np.isinf(vec))
    )


# ── HTML FIXTURES ──────────────────────────────────────────────────────────────

_HTML_JS_BLOB = """
<html>
<head><title>Shop</title></head>
<body>
  <script>window.__NUXT__={"state":{"cart":[],"user":null}};</script>
  <script>var _leak = JSON.parse('{"k":"v"}');</script>
  <script type="application/json">{"hydration":true}</script>
  <style>.btn{color:red;font-size:14px}</style>
  <h1>Welcome to Shop</h1>
  <p>We sell organic coffee beans sourced from Ethiopia.</p>
</body>
</html>
"""

_HTML_UNICODE = """
<html>
<body>
  <p>Café au lait — 100% arabica. Priced at £9.99 or €11.50.</p>
  <p>Hühnchen. Crème brûlée. Naïve résumé.</p>
  <p>日本語. 한국어. العربية.</p>
  <p>Emoji: ☕ 🌱 ✓ • En-dash – Em-dash — Ellipsis…</p>
</body>
</html>
"""

_HTML_ENTITIES = """
<html>
<body>
  <p>Price: &lt;$10 &amp; &gt;$5. &quot;Best deal&quot;. It&apos;s true.</p>
  <p>Copyright &copy; 2024. Registered &reg;. Trademark &trade;.</p>
  <p>Non-breaking&nbsp;space. Degree: 98&deg;F.</p>
</body>
</html>
"""

_HTML_WHITESPACE_MESS = """
<html><body>
  <p>  Too    many   spaces   here.  </p>
  <p>
    Multiple
    newlines
    here.
  </p>
  <p>	Tab	separated	words.</p>
</body></html>
"""

_BYTES_UTF8 = "<html><body><p>Café résumé naïve coöperate</p></body></html>".encode("utf-8")
_BYTES_LATIN1 = b"<html><body><p>Caf\xe9 r\xe9sum\xe9 na\xefve</p></body></html>"


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — TextCleaner
# ══════════════════════════════════════════════════════════════════════════════

class TestTextCleaner:

    @pytest.mark.unit
    def test_utf8_bytes_decoded(self):
        """UTF-8 bytes input → decoded without replacement chars."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_BYTES_UTF8)
        assert isinstance(result, str), "Output must be str"
        assert not _has_replacement_chars(result), f"Replacement char in output: {result!r}"
        assert "Café" in result or "caf" in result.lower(), "Expected accented text preserved"

    @pytest.mark.unit
    def test_latin1_bytes_fallback(self):
        """Latin-1 bytes that fail UTF-8 decode → Latin-1 fallback, no crash."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_BYTES_LATIN1)
        assert isinstance(result, str), "Output must be str"
        assert not _has_null_bytes(result), "Null bytes in output"
        # Should contain some recognisable text even after fallback decode
        assert len(result) > 0, "Empty output from Latin-1 bytes"

    @pytest.mark.unit
    def test_script_blobs_stripped(self):
        """window.__NUXT__ / JSON.parse / var leaks must not appear in clean text."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_HTML_JS_BLOB)
        assert not _has_js_garbage(result), (
            f"JS garbage leaked into clean text:\n{result[:500]}"
        )

    @pytest.mark.unit
    def test_script_content_not_in_output(self):
        """Raw script content keywords must be absent after cleaning."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_HTML_JS_BLOB)
        assert "__NUXT__"   not in result, "__NUXT__ leaked"
        assert "JSON.parse" not in result, "JSON.parse leaked"
        assert "_leak"      not in result, "JS var name leaked"

    @pytest.mark.unit
    def test_style_tags_stripped(self):
        """CSS rules must not appear in clean text."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_HTML_JS_BLOB)
        assert "font-size"  not in result, "CSS leaked"
        assert "color:red"  not in result, "CSS leaked"

    @pytest.mark.unit
    def test_useful_text_preserved_after_strip(self):
        """Visible page text must survive the strip."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_HTML_JS_BLOB)
        assert "organic coffee" in result.lower() or "ethiopia" in result.lower(), (
            f"Visible text missing from output: {result!r}"
        )

    @pytest.mark.unit
    def test_unicode_chars_preserved(self):
        """Accented chars, CJK, emoji, and special punctuation must survive."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_HTML_UNICODE)
        assert not _has_replacement_chars(result), (
            f"Replacement chars (\\ufffd) found — Unicode mangled:\n{result!r}"
        )
        for expected in ["£", "€", "—", "…"]:
            assert expected in result, f"Expected character {expected!r} missing from output"

    @pytest.mark.unit
    def test_html_entities_decoded(self):
        """&amp; &lt; &gt; &quot; &copy; etc. must be decoded by BeautifulSoup."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_HTML_ENTITIES)
        assert "&amp;"  not in result, "&amp; not decoded"
        assert "&lt;"   not in result, "&lt; not decoded"
        assert "&gt;"   not in result, "&gt; not decoded"
        assert "&quot;" not in result, "&quot; not decoded"
        assert "&copy;" not in result, "&copy; not decoded"
        # Decoded forms should be present
        assert "<" in result or ">" in result, "Decoded <> missing"
        assert "&" in result, "Decoded & missing"

    @pytest.mark.unit
    def test_whitespace_collapsed(self):
        """Multiple spaces, newlines, tabs → single space between words."""
        from src.utils.text_cleaner import extract_clean_text
        result = extract_clean_text(_HTML_WHITESPACE_MESS)
        assert "  " not in result, f"Double space survived: {result!r}"
        assert "\t" not in result, f"Tab survived: {result!r}"
        assert "\n" not in result, f"Newline survived: {result!r}"

    @pytest.mark.unit
    def test_empty_string_returns_empty(self):
        """Empty input → empty string, no exception."""
        from src.utils.text_cleaner import extract_clean_text
        assert extract_clean_text("") == ""
        assert extract_clean_text("   ") == ""

    @pytest.mark.unit
    def test_max_chars_respected(self):
        """Output length never exceeds max_chars."""
        from src.utils.text_cleaner import extract_clean_text
        for limit in [10, 50, 200]:
            result = extract_clean_text(_HTML_UNICODE, max_chars=limit)
            assert len(result) <= limit, (
                f"max_chars={limit} violated: got {len(result)} chars"
            )

    @pytest.mark.unit
    def test_null_bytes_not_in_output(self):
        """Null bytes must never appear in extracted text."""
        from src.utils.text_cleaner import extract_clean_text
        html_with_null = "<html><body><p>Before\x00After null byte</p></body></html>"
        result = extract_clean_text(html_with_null)
        assert not _has_null_bytes(result), f"Null byte in output: {result!r}"


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — Embedder
# ══════════════════════════════════════════════════════════════════════════════

class TestEmbedder:

    @pytest.mark.unit
    def test_embed_shape(self):
        """Normal English text → (384,) float vector."""
        from src.utils.embedder import embed
        vec = embed("We sell specialty organic coffee beans.")
        assert vec.shape == (384,), f"Expected shape (384,), got {vec.shape}"

    @pytest.mark.unit
    def test_embed_no_nan_inf(self):
        """No NaN or Inf values in embedding."""
        from src.utils.embedder import embed
        vec = embed("Premium single-origin coffee, ethically sourced from Ethiopia.")
        assert not np.any(np.isnan(vec)), "NaN in embedding"
        assert not np.any(np.isinf(vec)), "Inf in embedding"

    @pytest.mark.unit
    def test_embed_unicode_text(self):
        """Unicode text (accented, CJK, emoji) → valid vector, no NaN."""
        from src.utils.embedder import embed
        vec = embed("Café résumé £9.99 — 日本語テキスト ☕ naïve brûlée")
        assert _is_valid_vector(vec), (
            f"Unicode text produced invalid vector: shape={vec.shape}, "
            f"nan={np.any(np.isnan(vec))}, inf={np.any(np.isinf(vec))}"
        )

    @pytest.mark.unit
    def test_embed_replacement_chars(self):
        """Text containing \\ufffd replacement chars → still valid embedding."""
        from src.utils.embedder import embed
        vec = embed("Product �� description with replacement � chars.")
        assert _is_valid_vector(vec), "Replacement chars caused invalid embedding"

    @pytest.mark.unit
    def test_embed_single_word(self):
        """Single word → valid (384,) vector."""
        from src.utils.embedder import embed
        vec = embed("Coffee")
        assert _is_valid_vector(vec), f"Single word produced invalid vector"

    @pytest.mark.unit
    def test_embed_long_text_no_crash(self):
        """Text exceeding 256 tokens → truncated internally, no crash, valid vector."""
        from src.utils.embedder import embed
        long_text = "The store sells premium products. " * 100  # ~600 tokens
        vec = embed(long_text)
        assert _is_valid_vector(vec), "Long text produced invalid vector"

    @pytest.mark.unit
    def test_embed_batch_shape(self):
        """embed_batch(N texts) → (N, 384) array."""
        from src.utils.embedder import embed_batch
        texts = [
            "We sell coffee",
            "Organic beans from Ethiopia",
            "Free shipping on orders over £30",
        ]
        vecs = embed_batch(texts)
        assert vecs.shape == (3, 384), f"Expected (3, 384), got {vecs.shape}"
        assert not np.any(np.isnan(vecs)), "NaN in batch embeddings"
        assert not np.any(np.isinf(vecs)), "Inf in batch embeddings"

    @pytest.mark.unit
    def test_embed_batch_consistent_with_single(self):
        """embed_batch([t])[0] and embed(t) should be very close (same model)."""
        from src.utils.embedder import embed, embed_batch
        text = "Specialty coffee from single-origin farms."
        single = embed(text)
        batch  = embed_batch([text])
        diff   = np.abs(single - batch[0]).max()
        assert diff < 1e-4, f"Batch vs single embed differ by {diff:.6f} (max abs)"

    @pytest.mark.unit
    def test_cosine_sim_range_similar_texts(self):
        """Cosine similarity of semantically similar texts is in [-1, 1]."""
        from src.utils.embedder import embed, cosine_sim
        a = embed("We sell specialty coffee beans.")
        b = embed("Our store offers single-origin coffee.")
        sim = cosine_sim(a, b)
        assert -1.0 <= sim <= 1.0, f"cosine_sim out of range: {sim}"
        assert sim > 0.3, f"Expected similar texts to have sim > 0.3, got {sim:.3f}"

    @pytest.mark.unit
    def test_cosine_sim_range_different_texts(self):
        """Cosine similarity of unrelated texts is still in [-1, 1]."""
        from src.utils.embedder import embed, cosine_sim
        a = embed("We sell organic coffee from Ethiopia.")
        b = embed("The legal framework for maritime insurance contracts.")
        sim = cosine_sim(a, b)
        assert -1.0 <= sim <= 1.0, f"cosine_sim out of range: {sim}"

    @pytest.mark.unit
    def test_cosine_sim_identical_texts(self):
        """Same text embedded twice → cosine_sim ≈ 1.0."""
        from src.utils.embedder import embed, cosine_sim
        text = "We sell specialty organic coffee."
        a = embed(text)
        b = embed(text)
        sim = cosine_sim(a, b)
        assert sim > 0.999, f"Identical text cosine_sim should be ~1.0, got {sim:.6f}"

    @pytest.mark.unit
    def test_cosine_sim_zero_vector_returns_zero(self):
        """Zero vector input → 0.0, not NaN."""
        from src.utils.embedder import cosine_sim
        zero = np.zeros(384, dtype=np.float32)
        normal = np.random.rand(384).astype(np.float32)
        sim = cosine_sim(zero, normal)
        assert sim == 0.0, f"Expected 0.0 for zero vector, got {sim}"
        assert not np.isnan(sim), "NaN from zero vector in cosine_sim"

    @pytest.mark.unit
    def test_chunk_text_empty_input(self):
        """chunk_text('') → empty string."""
        from src.utils.embedder import chunk_text
        assert chunk_text("") == ""
        assert chunk_text("   ") == ""

    @pytest.mark.unit
    def test_chunk_text_limits_sentences(self):
        """chunk_text(text, max_sentences=2) → at most 2 sentences."""
        from src.utils.embedder import chunk_text
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = chunk_text(text, max_sentences=2)
        # Should contain at most 2 sentence-ending punctuation marks
        sentence_count = len(re.findall(r'\. ', result + " "))
        assert sentence_count <= 2, (
            f"chunk_text kept {sentence_count} sentences with max_sentences=2: {result!r}"
        )

    @pytest.mark.unit
    def test_chunk_text_no_truncation_within_limit(self):
        """chunk_text preserves all text when count < max_sentences."""
        from src.utils.embedder import chunk_text
        text = "Only one sentence here."
        assert chunk_text(text, max_sentences=10) == text


# ══════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — Pipeline (clean → embed → sim)
# ══════════════════════════════════════════════════════════════════════════════

class TestPipeline:

    @pytest.mark.unit
    def test_js_blob_html_to_valid_embedding(self):
        """HTML with JS blobs → clean text → embed → no NaN/Inf, correct shape."""
        from src.utils.text_cleaner import extract_clean_text
        from src.utils.embedder import embed
        clean = extract_clean_text(_HTML_JS_BLOB)
        assert not _has_js_garbage(clean), "JS still in text before embedding"
        vec = embed(clean)
        assert _is_valid_vector(vec), (
            f"Invalid embedding after cleaning JS blob: "
            f"shape={vec.shape}, nan={np.any(np.isnan(vec))}"
        )

    @pytest.mark.unit
    def test_unicode_html_pipeline_cosine_in_range(self):
        """Unicode HTML → clean text → embed → cosine_sim with itself == 1.0."""
        from src.utils.text_cleaner import extract_clean_text
        from src.utils.embedder import embed, cosine_sim
        clean = extract_clean_text(_HTML_UNICODE)
        vec_a = embed(clean)
        vec_b = embed(clean)
        sim = cosine_sim(vec_a, vec_b)
        assert -1.0 <= sim <= 1.0, f"cosine_sim out of range after Unicode pipeline: {sim}"
        assert sim > 0.999, f"Same text cosine_sim should be ~1.0, got {sim:.6f}"

    @pytest.mark.unit
    def test_garbage_text_embedding_stays_valid(self):
        """Text with \\ufffd, null bytes, control chars → embedding never NaN."""
        from src.utils.embedder import embed
        garbage = (
            "Product �� title. \x00 Null byte. \x01\x02 Control. "
            "Normal text: organic coffee beans. More � garbage. Price £9.99."
        )
        vec = embed(garbage)
        assert _is_valid_vector(vec), (
            f"Garbage text produced invalid vector: "
            f"nan={np.any(np.isnan(vec))}, shape={vec.shape}"
        )

    @pytest.mark.unit
    def test_clean_then_embed_cosine_meaningful(self):
        """Two semantically similar cleaned HTML pages → cosine_sim > 0.5."""
        from src.utils.text_cleaner import extract_clean_text
        from src.utils.embedder import embed, cosine_sim

        html_a = "<html><body><p>We sell organic coffee beans from Ethiopia and Colombia.</p></body></html>"
        html_b = "<html><body><p>Specialty single-origin coffee sourced from African farms.</p></body></html>"

        vec_a = embed(extract_clean_text(html_a))
        vec_b = embed(extract_clean_text(html_b))
        sim = cosine_sim(vec_a, vec_b)
        assert -1.0 <= sim <= 1.0, f"cosine_sim out of range: {sim}"
        assert sim > 0.5, f"Semantically similar texts should have sim > 0.5, got {sim:.3f}"

    @pytest.mark.unit
    def test_dissimilar_cleaned_pages_lower_cosine(self):
        """Two unrelated cleaned pages → cosine_sim < similar pair."""
        from src.utils.text_cleaner import extract_clean_text
        from src.utils.embedder import embed, cosine_sim

        coffee_html  = "<html><body><p>Organic coffee beans. Single-origin. Ethiopia.</p></body></html>"
        legal_html   = "<html><body><p>Maritime insurance law. Contract indemnity clauses.</p></body></html>"
        similar_html = "<html><body><p>Specialty coffee roasted to order from African farms.</p></body></html>"

        v_coffee  = embed(extract_clean_text(coffee_html))
        v_legal   = embed(extract_clean_text(legal_html))
        v_similar = embed(extract_clean_text(similar_html))

        sim_related   = cosine_sim(v_coffee, v_similar)
        sim_unrelated = cosine_sim(v_coffee, v_legal)

        assert sim_related > sim_unrelated, (
            f"Similar pair ({sim_related:.3f}) should beat unrelated pair ({sim_unrelated:.3f})"
        )


# ── MAIN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    subprocess.run(
        ["pytest", __file__, "-v", "--tb=short", "-m", "unit"],
        check=False,
    )
