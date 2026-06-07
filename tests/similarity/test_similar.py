"""Characterization tests for kce.similar(a, b).

``similar`` is a rapidfuzz Indel.normalized_similarity wrapper decorated with
@lru_cache(maxsize=3500).  It lower-cases and strips both inputs before
comparing, and short-circuits to 0.0 when either stripped value is empty or to
1.0 when they are equal.

All expected values below were pinned by running::

    .venv/bin/python -c "import komga_cover_extractor as kce; print(repr(kce.similar(A, B)))"

and recording the exact float returned by the running interpreter.
"""

from __future__ import annotations

import pytest
import komga_cover_extractor as kce


# --------------------------------------------------------------------------- #
# Helper — exact-float equality only where the value is a clean 1.0 or 0.0.
# For irrational-looking floats we use pytest.approx with a tight tolerance
# to guard against any floating-point noise across Python patch releases.
# --------------------------------------------------------------------------- #

_APPROX = pytest.approx  # re-exported for brevity in parametrize


# --------------------------------------------------------------------------- #
# 1. Spec cases (from the task description)
# --------------------------------------------------------------------------- #

class TestSpecCases:
    """Pin the explicit examples stated in the task specification."""

    def test_identical_strings(self):
        """identical 'hello'/'hello' -> 1.0"""
        assert kce.similar("hello", "hello") == 1.0

    def test_case_insensitive(self):
        """'HELLO'/'hello' -> 1.0 (both lowercased before compare)"""
        assert kce.similar("HELLO", "hello") == 1.0

    def test_empty_left(self):
        """'' vs anything -> 0.0 (early-exit guard)"""
        assert kce.similar("", "hello") == 0.0

    def test_empty_right(self):
        """anything vs '' -> 0.0 (early-exit guard)"""
        assert kce.similar("hello", "") == 0.0

    def test_both_empty(self):
        """'' vs '' -> 0.0 (empty check fires before equality check)"""
        # FLAG: both empty returns 0.0, not 1.0 — the empty guard runs first.
        assert kce.similar("", "") == 0.0

    def test_abc_abcd(self):
        """'abc'/'abcd' -> 0.8571428571428572"""
        result = kce.similar("abc", "abcd")
        assert result == _APPROX(0.8571428571428572, rel=1e-9)

    def test_abc_xyz(self):
        """'abc'/'xyz' -> 0.0 (no common characters at Indel distance)"""
        assert kce.similar("abc", "xyz") == 0.0

    def test_whitespace_stripped(self):
        """'  hello  '/'hello' -> 1.0 (strip() normalizes leading/trailing space)"""
        assert kce.similar("  hello  ", "hello") == 1.0


# --------------------------------------------------------------------------- #
# 2. Case-normalization edge cases
# --------------------------------------------------------------------------- #

class TestCaseNormalization:
    """Verify all-caps, mixed-case, and tab/newline stripping behavior."""

    def test_mixed_case_manga(self):
        """'MaNgA'/'manga' -> 1.0"""
        assert kce.similar("MaNgA", "manga") == 1.0

    def test_all_caps_vs_lower(self):
        """'ABC'/'abc' -> 1.0 (case fold)"""
        assert kce.similar("ABC", "abc") == 1.0

    def test_tab_padding_stripped(self):
        """\thello\t vs hello -> 1.0 (strip removes tabs)"""
        assert kce.similar("\thello\t", "hello") == 1.0

    def test_newline_trailing_stripped(self):
        """'hello\\n' vs 'hello' -> 1.0 (strip removes newline)"""
        assert kce.similar("hello\n", "hello") == 1.0


# --------------------------------------------------------------------------- #
# 3. Single-character pairs
# --------------------------------------------------------------------------- #

class TestSingleCharacter:
    """Pin behavior for length-1 inputs; illustrates the 0.0 floor for a/b."""

    def test_same_char(self):
        """'a'/'a' -> 1.0"""
        assert kce.similar("a", "a") == 1.0

    def test_different_chars(self):
        """'a'/'b' -> 0.0 (Indel distance = 2 over total length 2)"""
        assert kce.similar("a", "b") == 0.0


# --------------------------------------------------------------------------- #
# 4. Near-identical strings (small edit distance)
# --------------------------------------------------------------------------- #

class TestNearIdentical:
    """Pin floats for strings with only one or two character differences."""

    def test_ab_abc(self):
        """'ab'/'abc' -> 0.8"""
        assert kce.similar("ab", "abc") == _APPROX(0.8, rel=1e-9)

    def test_abc_ab(self):
        """'abc'/'ab' -> 0.8 (symmetric)"""
        assert kce.similar("abc", "ab") == _APPROX(0.8, rel=1e-9)

    def test_numeric_123_1234(self):
        """'123'/'1234' -> same ratio as abc/abcd"""
        assert kce.similar("123", "1234") == _APPROX(0.8571428571428572, rel=1e-9)

    def test_sword_art_online_offline(self):
        """'sword art online'/'sword art offline' -> ~0.909"""
        result = kce.similar("sword art online", "sword art offline")
        assert result == _APPROX(0.9090909090909091, rel=1e-9)

    def test_hello_world_exclaim(self):
        """'hello world'/'hello world!' -> ~0.957"""
        result = kce.similar("hello world", "hello world!")
        assert result == _APPROX(0.9565217391304348, rel=1e-9)

    def test_long_prefix_match(self):
        """'the quick brown fox'/'the quick brown fox jumps' -> ~0.864"""
        result = kce.similar("the quick brown fox", "the quick brown fox jumps")
        assert result == _APPROX(0.8636363636363636, rel=1e-9)


# --------------------------------------------------------------------------- #
# 5. Partial / substring overlaps
# --------------------------------------------------------------------------- #

class TestPartialOverlap:
    """Pairs where one string is a substring of the other, or overlap partially."""

    def test_one_piece_volume(self):
        """'one piece'/'one piece vol 1' -> 0.75"""
        assert kce.similar("one piece", "one piece vol 1") == _APPROX(0.75, rel=1e-9)

    def test_numeric_identical(self):
        """'123'/'123' -> 1.0"""
        assert kce.similar("123", "123") == 1.0


# --------------------------------------------------------------------------- #
# 6. Completely dissimilar strings
# --------------------------------------------------------------------------- #

class TestDissimilar:
    """Pin non-zero but low similarity for strings sharing few/no characters."""

    def test_completely_different(self):
        """'completely'/'different' -> ~0.211"""
        result = kce.similar("completely", "different")
        assert result == _APPROX(0.21052631578947367, rel=1e-9)

    def test_hello_world(self):
        """'hello'/'world' -> ~0.2 (small shared characters via Indel)"""
        result = kce.similar("hello", "world")
        assert result == _APPROX(0.19999999999999996, rel=1e-9)


# --------------------------------------------------------------------------- #
# 7. Anagram / transposition pairs (Indel is NOT edit-distance symmetric here)
# --------------------------------------------------------------------------- #

class TestTranspositions:
    """Indel distance penalises transpositions as two separate operations."""

    def test_ab_ba(self):
        """'ab'/'ba' -> 0.5 (two single-char edits over total 4)"""
        assert kce.similar("ab", "ba") == _APPROX(0.5, rel=1e-9)

    def test_abc_bca(self):
        """'abc'/'bca' -> ~0.667"""
        result = kce.similar("abc", "bca")
        assert result == _APPROX(0.6666666666666667, rel=1e-9)


# --------------------------------------------------------------------------- #
# 8. Return-type and lru_cache meta checks
# --------------------------------------------------------------------------- #

class TestMeta:
    """Verify that the function contract (float return, lru_cache) is intact."""

    def test_returns_float(self):
        """similar always returns float, not int or other numeric type."""
        result = kce.similar("hello", "hello")
        assert isinstance(result, float)

    def test_returns_float_for_partial(self):
        """Partial-match result is also a float."""
        result = kce.similar("abc", "abcd")
        assert isinstance(result, float)

    def test_lru_cache_present(self):
        """similar must be wrapped by lru_cache (has .cache_info attribute)."""
        assert hasattr(kce.similar, "cache_info")

    def test_lru_cache_maxsize(self):
        """lru_cache maxsize is pinned to 3500 as declared in source."""
        info = kce.similar.cache_info()
        assert info.maxsize == 3500

    def test_deterministic_repeated_calls(self):
        """Multiple calls with same args return identical value (cache consistency)."""
        first = kce.similar("manga", "manga series")
        second = kce.similar("manga", "manga series")
        assert first == second
