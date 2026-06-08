"""Characterization tests for is_same_index_number — the dedup equality contract.

These tests pin what the production code does TODAY — surprises and all.
Any FLAG: comment documents a known quirk or potential bug that is pinned as-is.

Verified with: .venv/bin/python3 -c "import komga_cover_extractor as kce; ..." on the
tests/upgrade-scoring-engine branch (commit after 300cfb4).

Function source (komga_cover_extractor.py ~line 2475):

    def is_same_index_number(index_one, index_two, allow_array_match=False):
        if (index_one == index_two and index_one != "") or (
            allow_array_match
            and (
                (isinstance(index_one, list) and index_two in index_one)
                or (isinstance(index_two, list) and index_one in index_two)
            )
        ):
            return True
        return False

Key observations:
- Return type is always plain bool (True / False).
- Empty string ``""`` is the one sentinel excluded: ``"" == ""`` is False because
  the guard ``index_one != ""`` fails for empty strings.
- None passes the guard (None != "" is True), so None == None -> True.
- allow_array_match only fires for list, NOT tuple — a tuple operand returns False
  even if the element is present (the ``isinstance(..., list)`` guard).  This is a
  latent hazard downstream of get_release_number which can return a tuple for
  multi-number ranges.
"""

from __future__ import annotations

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

f = kce.is_same_index_number   # shorthand used throughout


# ---------------------------------------------------------------------------
# Basic equality — no allow_array_match
# ---------------------------------------------------------------------------


class TestBasicEquality:
    """Two scalar operands, allow_array_match=False (default)."""

    def test_equal_ints_returns_true(self):
        """Same integer values are equal."""
        assert f(1, 1) is True

    def test_unequal_ints_returns_false(self):
        """Different integers are not equal."""
        assert f(1, 2) is False

    def test_zero_zero_returns_true(self):
        """Integer zero is a valid, equal index (not treated as falsy sentinel)."""
        assert f(0, 0) is True

    def test_zero_one_returns_false(self):
        assert f(0, 1) is False

    def test_equal_floats_returns_true(self):
        """Float volumes like 1.5 == 1.5."""
        assert f(1.5, 1.5) is True

    def test_unequal_floats_returns_false(self):
        assert f(1.5, 2.5) is False

    def test_int_one_float_one_returns_true(self):
        """Python equality: 1 == 1.0 is True, and 1 != '' -> condition passes."""
        assert f(1, 1.0) is True

    def test_float_one_int_one_returns_true(self):
        assert f(1.0, 1) is True

    def test_int_one_float_one_point_five_returns_false(self):
        """1 != 1.5 in Python."""
        assert f(1, 1.5) is False

    def test_equal_strings_returns_true(self):
        """Non-empty strings compare equal."""
        assert f("abc", "abc") is True

    def test_unequal_strings_returns_false(self):
        assert f("abc", "xyz") is False

    def test_return_type_is_bool_true(self):
        """Return value is exactly bool, not a truthy/falsy object."""
        result = f(1, 1)
        assert isinstance(result, bool)
        assert result is True

    def test_return_type_is_bool_false(self):
        result = f(1, 2)
        assert isinstance(result, bool)
        assert result is False


# ---------------------------------------------------------------------------
# Empty-string sentinel — the one excluded value
# ---------------------------------------------------------------------------


class TestEmptyStringSentinel:
    """Empty string is explicitly excluded: '' == '' returns False.

    This is the code's way of expressing "not yet parsed / unknown" —
    two unknown indices must not be treated as duplicates.
    """

    def test_empty_empty_returns_false(self):
        # FLAG: '' == '' is True in Python, but the guard ``index_one != ""``
        # short-circuits the condition, so the function returns False.
        assert f("", "") is False

    def test_empty_nonempty_returns_false(self):
        assert f("", "abc") is False

    def test_nonempty_empty_returns_false(self):
        assert f("abc", "") is False

    def test_zero_empty_returns_false(self):
        """0 != "" is True in Python, but 0 != "" and 0 == "" -> 0 == "" is False."""
        assert f(0, "") is False

    def test_empty_zero_returns_false(self):
        assert f("", 0) is False


# ---------------------------------------------------------------------------
# None behavior — passes the sentinel guard (None != '' is True)
# ---------------------------------------------------------------------------


class TestNoneBehavior:
    """None passes the guard because None != '' evaluates to True."""

    def test_none_none_returns_true(self):
        # FLAG: None == None and None != '' -> True.  Two "missing" indices
        # are thus considered the same, which may or may not be intentional.
        assert f(None, None) is True

    def test_none_int_returns_false(self):
        assert f(None, 1) is False

    def test_int_none_returns_false(self):
        assert f(1, None) is False


# ---------------------------------------------------------------------------
# allow_array_match=True with list — the happy path
# ---------------------------------------------------------------------------


class TestAllowArrayMatchWithList:
    """allow_array_match=True triggers only for list, not any other sequence type."""

    def test_scalar_in_list_second_arg_returns_true(self):
        """index_one is in the list passed as index_two."""
        assert f(1, [1, 3], allow_array_match=True) is True

    def test_scalar_in_list_first_arg_returns_true(self):
        """index_two is in the list passed as index_one."""
        assert f([1, 3], 1, allow_array_match=True) is True

    def test_scalar_not_in_list_second_arg_returns_false(self):
        assert f(2, [1, 3], allow_array_match=True) is False

    def test_scalar_not_in_list_first_arg_returns_false(self):
        assert f([1, 3], 2, allow_array_match=True) is False

    def test_allow_array_match_false_with_list_returns_false(self):
        """With allow_array_match=False, list membership is NOT checked."""
        assert f(1, [1, 3], allow_array_match=False) is False

    def test_allow_array_match_default_with_list_returns_false(self):
        """Default allow_array_match=False: list membership is NOT checked."""
        assert f(1, [1, 3]) is False

    def test_both_lists_equal_no_allow_array_match_returns_true(self):
        """Two equal list objects still satisfy index_one == index_two (list __eq__)."""
        assert f([1, 2], [1, 2], False) is True

    def test_both_lists_equal_allow_array_match_returns_true(self):
        """Equal lists: the first condition (==) fires before allow_array_match check."""
        assert f([1, 2], [1, 2], True) is True

    def test_empty_list_scalar_returns_false(self):
        """Empty list: membership test on [] always fails."""
        assert f(1, [], allow_array_match=True) is False

    def test_scalar_empty_list_returns_false(self):
        assert f([], 1, allow_array_match=True) is False

    def test_none_in_list_with_none_returns_true(self):
        """None can be found inside a list when allow_array_match=True."""
        assert f(None, [None, 1], allow_array_match=True) is True

    def test_none_not_in_list_returns_false(self):
        assert f(None, [1, 2], allow_array_match=True) is False


# ---------------------------------------------------------------------------
# allow_array_match=True with TUPLE — the latent dedup hazard
# ---------------------------------------------------------------------------


class TestAllowArrayMatchTupleHazard:
    """Tuples are NOT recognised by allow_array_match — isinstance(..., list) rejects them.

    get_release_number can return a *tuple* for multi-number ranges (e.g. (1, 3)).
    If that tuple is passed here with allow_array_match=True the membership check
    is silently skipped and False is returned even when the element is present.
    This is a real dedup gap and is pinned as-is.
    """

    def test_scalar_in_tuple_second_arg_returns_false(self):
        # FLAG: (1, (1, 3), allow_array_match=True) -> False.
        # A list [1, 3] would return True, but a tuple (1, 3) does NOT because
        # isinstance((1, 3), list) is False.  Downstream dedup comparisons that
        # receive a tuple from get_release_number will silently fail to match.
        assert f(1, (1, 3), allow_array_match=True) is False

    def test_scalar_in_tuple_first_arg_returns_false(self):
        # FLAG: ((1, 3), 1, allow_array_match=True) -> False.
        # The isinstance check on index_one also requires list, so a tuple in
        # the first position likewise fails.
        assert f((1, 3), 1, allow_array_match=True) is False

    def test_tuple_with_allow_array_match_false_returns_false(self):
        """Sanity: tuple still fails when allow_array_match is False too."""
        assert f(1, (1, 3), allow_array_match=False) is False

    def test_list_vs_tuple_asymmetry(self):
        """Demonstrates the list/tuple asymmetry explicitly in one test.

        list  -> membership check fires  -> True
        tuple -> membership check skipped -> False
        """
        assert f(1, [1, 3], allow_array_match=True) is True   # list: True
        assert f(1, (1, 3), allow_array_match=True) is False  # tuple: False
