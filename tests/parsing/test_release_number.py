"""Characterization tests for get_release_number and get_release_number_cache.

These tests pin what the production code does TODAY — surprises and all.
Any FLAG: comment documents a known quirk or potential bug that is pinned as-is.

Verified with: .venv/bin/python -c "import komga_cover_extractor as kce; ..."
on the library-replacements branch (commit range after ceb171b).
"""

from __future__ import annotations

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# get_release_number — volume mode (chapter=False, the default)
# ---------------------------------------------------------------------------


class TestGetReleaseNumberVolumeMode:
    """Volume mode: chapter=False (default). Ceiling at >= 2000."""

    def test_single_volume_v01_returns_int_1(self):
        """Standard zero-padded volume number parses to integer 1."""
        result = kce.get_release_number("Series v01 (2021).cbz", chapter=False)
        assert result == 1
        assert isinstance(result, int)

    def test_single_volume_v01_5_returns_float(self):
        """Half-volume (point-five) parses to a float, not an int."""
        result = kce.get_release_number("Series v01.5 (2021).cbz", chapter=False)
        assert result == 1.5
        assert isinstance(result, float)

    def test_single_volume_v0_returns_int_0(self):
        """Volume zero is a valid edge case and returns integer 0.

        Note: '0 or results == 0' guard in the source correctly handles falsy 0.
        """
        result = kce.get_release_number("Series v0 (2021).cbz", chapter=False)
        assert result == 0
        assert isinstance(result, int)

    def test_single_volume_trailing_point_zero_stripped(self):
        """Trailing '.0' is stripped before conversion; v10.0 -> 10 (int)."""
        result = kce.get_release_number("Series v10.0 (2021).cbz", chapter=False)
        assert result == 10
        assert isinstance(result, int)

    def test_multi_volume_v01_03_returns_tuple(self):
        """Keyword-then-range (v01-03) is recognized as multi-volume and returns a tuple.

        FLAG: get_release_number returns a TUPLE for multi-volume, but
        get_release_number_cache converts that tuple to a LIST. Callers that
        branch on isinstance(x, list) will not match the raw function's output.
        """
        result = kce.get_release_number("Series v01-03 (2021).cbz", chapter=False)
        assert result == (1, 3)
        assert isinstance(result, tuple)

    def test_multi_volume_float_range_returns_tuple_of_floats(self):
        """Float endpoints in a range produce a tuple of floats."""
        result = kce.get_release_number("Series v01.5-03.5 (2021).cbz", chapter=False)
        assert result == (1.5, 3.5)
        assert isinstance(result, tuple)
        assert all(isinstance(v, float) for v in result)

    def test_multi_volume_with_extra_suffix_appends_point5(self):
        """'_extra' is replaced with '.5' before processing; v01-03_extra -> (1, 3.5)."""
        result = kce.get_release_number("Series v01-03_extra (2021).cbz", chapter=False)
        assert result == (1, 3.5)
        assert isinstance(result, tuple)

    def test_extra_suffix_single_volume_becomes_point5(self):
        """v01_extra -> 1.5 because '_extra' is replaced with '.5'."""
        result = kce.get_release_number("Series v01_extra (2021).cbz", chapter=False)
        assert result == 1.5
        assert isinstance(result, float)

    def test_repeat_keyword_v01_v03_returns_only_first_number(self):
        """v01-v03 (keyword repeated before each number) is NOT detected as multi-volume.

        FLAG: check_for_multi_volume_file returns False for 'v01-v03' because the
        regex requires a single keyword prefix followed by two bare numbers separated
        by a dash — the repeated 'v' keyword breaks the match. As a result only the
        first number (1) is returned instead of the expected range (1, 3). Callers
        must use the canonical 'v01-03' form to get a proper range.
        """
        # Verify that the multi-volume detector is indeed False for the repeated-keyword form
        assert kce.check_for_multi_volume_file("Series v01-v03 (2021).cbz") is False
        result = kce.get_release_number("Series v01-v03 (2021).cbz", chapter=False)
        assert result == 1
        assert isinstance(result, int)

    def test_repeat_keyword_v1_v3_returns_only_first_number(self):
        """Same repeat-keyword truncation for non-padded v1-v3."""
        assert kce.check_for_multi_volume_file("Series v1-v3 (2021).cbz") is False
        result = kce.get_release_number("Series v1-v3 (2021).cbz", chapter=False)
        assert result == 1
        assert isinstance(result, int)

    def test_year_like_v2023_blocked_by_ceiling(self):
        """v2023 in volume mode returns '' because 2023 >= 2000 is filtered out.

        FLAG: The >= 2000 ceiling is a heuristic to avoid treating publication
        years embedded in filenames as volume numbers. It's only applied in volume
        mode; chapter mode has no ceiling (see chapter tests below).
        """
        result = kce.get_release_number("Series v2023 (2021).cbz", chapter=False)
        assert result == ""

    def test_v2000_exactly_at_ceiling_returns_empty(self):
        """Exactly 2000 is blocked (ceiling condition is results < 2000)."""
        result = kce.get_release_number("Series v2000 (2021).cbz", chapter=False)
        assert result == ""

    def test_v1999_just_below_ceiling_returns_int(self):
        """1999 is just below the ceiling and passes through as an int."""
        result = kce.get_release_number("Series v1999 (2021).cbz", chapter=False)
        assert result == 1999
        assert isinstance(result, int)

    def test_v100_well_below_ceiling_returns_int(self):
        """Normal large-ish volume number well below 2000 passes through."""
        result = kce.get_release_number("Series v100 (2021).cbz", chapter=False)
        assert result == 100
        assert isinstance(result, int)

    def test_bare_year_in_filename_blocked(self):
        """A bare 2023 (not prefixed with 'v') is also filtered by the ceiling."""
        result = kce.get_release_number("Series 2023 (2021).cbz", chapter=False)
        assert result == ""

    def test_no_volume_number_returns_empty_string(self):
        """A filename with no recognizable volume number returns empty string."""
        result = kce.get_release_number("Series (2021).cbz", chapter=False)
        assert result == ""

    def test_return_type_is_empty_string_not_none(self):
        """The 'not found' sentinel is '' (str), never None."""
        result = kce.get_release_number("No Number Here.cbz", chapter=False)
        assert result == ""
        assert result is not None


# ---------------------------------------------------------------------------
# get_release_number — chapter mode (chapter=True)
# ---------------------------------------------------------------------------


class TestGetReleaseNumberChapterMode:
    """Chapter mode: chapter=True. No >= 2000 ceiling applies."""

    def test_chapter_001_returns_int(self):
        """Standard chapter number returns an int."""
        result = kce.get_release_number("Chapter 001 (2023).cbz", chapter=True)
        assert result == 1
        assert isinstance(result, int)

    def test_chapter_000_returns_int_0(self):
        """Chapter zero is valid and returns 0 (int)."""
        result = kce.get_release_number("Chapter 000 (2023).cbz", chapter=True)
        assert result == 0
        assert isinstance(result, int)

    def test_chapter_float_returns_float(self):
        """Decimal chapter number returns a float."""
        result = kce.get_release_number("Chapter 001.5 (2023).cbz", chapter=True)
        assert result == 1.5
        assert isinstance(result, float)

    def test_chapter_multi_range_returns_tuple(self):
        """Chapter range 001-003 returns a tuple (same as volume multi-range)."""
        result = kce.get_release_number("Chapter 001-003 (2023).cbz", chapter=True)
        assert result == (1, 3)
        assert isinstance(result, tuple)

    def test_chapter_2000_passes_no_ceiling(self):
        """2000 is NOT filtered in chapter mode — no ceiling is applied.

        FLAG: Volume mode blocks numbers >= 2000 as likely publication years.
        Chapter mode skips this guard entirely (the branch is 'elif chapter: return
        results'). A chapter numbered 2000 is returned as-is.
        """
        result = kce.get_release_number("Chapter 2000 (2023).cbz", chapter=True)
        assert result == 2000
        assert isinstance(result, int)

    def test_chapter_1999_passes_in_chapter_mode(self):
        """1999 passes in chapter mode (would also pass volume mode, confirming
        the chapter mode doesn't accidentally add its own ceiling)."""
        result = kce.get_release_number("Chapter 1999 (2023).cbz", chapter=True)
        assert result == 1999
        assert isinstance(result, int)

    def test_chapter_9999_passes_in_chapter_mode(self):
        """Very large chapter number passes in chapter mode (no upper bound)."""
        result = kce.get_release_number("Chapter 9999 (2023).cbz", chapter=True)
        assert result == 9999
        assert isinstance(result, int)

    def test_bare_2023_returns_2023_in_chapter_mode(self):
        """A bare year-like number 2023 in chapter mode is NOT filtered."""
        result = kce.get_release_number("Series 2023 (2021).cbz", chapter=True)
        assert result == 2023
        assert isinstance(result, int)

    def test_chapter_no_number_returns_empty_string(self):
        """No recognizable chapter number still returns '' in chapter mode."""
        result = kce.get_release_number("Series (2021).cbz", chapter=True)
        assert result == ""


# ---------------------------------------------------------------------------
# get_release_number_cache — tuple -> list conversion
# ---------------------------------------------------------------------------


class TestGetReleaseNumberCache:
    """get_release_number_cache wraps get_release_number and converts any
    tuple result to a list, leaving all other types unchanged.

    FLAG: This creates a contract mismatch — the underlying function returns
    tuple for multi-volume; the cache wrapper returns list. Callers that
    branch on isinstance(x, list) will see True only for the wrapper's output,
    not for the raw function's output. This is intentional per the source code
    pattern ('callers branch on isinstance(x, list)').
    """

    def test_single_volume_int_unchanged(self):
        """Single volume: int passes through unchanged."""
        result = kce.get_release_number_cache("Series v01 (2021).cbz", chapter=False)
        assert result == 1
        assert isinstance(result, int)

    def test_single_volume_float_unchanged(self):
        """Single half-volume: float passes through unchanged."""
        result = kce.get_release_number_cache(
            "Series v01.5 (2021).cbz", chapter=False
        )
        assert result == 1.5
        assert isinstance(result, float)

    def test_volume_zero_unchanged(self):
        """Volume zero passes through unchanged."""
        result = kce.get_release_number_cache("Series v0 (2021).cbz", chapter=False)
        assert result == 0
        assert isinstance(result, int)

    def test_empty_string_unchanged(self):
        """Empty-string sentinel passes through unchanged."""
        result = kce.get_release_number_cache("Series (2021).cbz", chapter=False)
        assert result == ""

    def test_multi_volume_tuple_converted_to_list(self):
        """Multi-volume tuple (1, 3) is converted to a list [1, 3].

        FLAG: Raw get_release_number returns tuple; cache wrapper returns list.
        This is the explicit tuple-vs-list contract mismatch described in the
        module-level docstring.
        """
        raw = kce.get_release_number("Series v01-03 (2021).cbz", chapter=False)
        assert isinstance(raw, tuple), "raw function must return a tuple"

        cached = kce.get_release_number_cache(
            "Series v01-03 (2021).cbz", chapter=False
        )
        assert isinstance(cached, list), "cache wrapper must convert tuple to list"
        assert cached == [1, 3]

    def test_multi_volume_list_element_types_are_int(self):
        """Elements inside the converted list are ints for whole-number ranges."""
        result = kce.get_release_number_cache(
            "Series v01-03 (2021).cbz", chapter=False
        )
        assert all(isinstance(v, int) for v in result)

    def test_multi_volume_float_range_converted_to_list_of_floats(self):
        """Float-endpoint range tuple -> list of floats."""
        result = kce.get_release_number_cache(
            "Series v01.5-03.5 (2021).cbz", chapter=False
        )
        assert result == [1.5, 3.5]
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_chapter_multi_range_converted_to_list(self):
        """Chapter range tuple also gets converted to a list by the cache wrapper."""
        raw = kce.get_release_number("Chapter 001-003 (2023).cbz", chapter=True)
        assert isinstance(raw, tuple)

        cached = kce.get_release_number_cache(
            "Chapter 001-003 (2023).cbz", chapter=True
        )
        assert isinstance(cached, list)
        assert cached == [1, 3]

    def test_chapter_2000_int_unchanged(self):
        """Chapter 2000 int passes through the cache wrapper unchanged."""
        result = kce.get_release_number_cache(
            "Chapter 2000 (2023).cbz", chapter=True
        )
        assert result == 2000
        assert isinstance(result, int)

    def test_repeat_keyword_v01_v03_single_int_unchanged(self):
        """Repeat-keyword v01-v03 returns 1 (int); cache wrapper leaves it alone."""
        result = kce.get_release_number_cache(
            "Series v01-v03 (2021).cbz", chapter=False
        )
        assert result == 1
        assert isinstance(result, int)

    def test_ceiling_blocked_year_empty_string_unchanged(self):
        """Year-like v2023 blocked in volume mode; cache wrapper returns '' unchanged."""
        result = kce.get_release_number_cache(
            "Series v2023 (2021).cbz", chapter=False
        )
        assert result == ""


# ---------------------------------------------------------------------------
# check_for_multi_volume_file — companion helper, tested for completeness
# ---------------------------------------------------------------------------


class TestCheckForMultiVolumeFile:
    """Pin check_for_multi_volume_file's boolean contract as it directly
    affects get_release_number's branching behavior."""

    def test_v01_03_is_multi(self):
        """Standard range 'v01-03' is recognized as multi-volume."""
        assert kce.check_for_multi_volume_file("Series v01-03 (2021).cbz") is True

    def test_v001_003_is_multi(self):
        """v001-003 (three-digit padded) is also recognized as multi-volume."""
        assert kce.check_for_multi_volume_file("Series v001-003 (2021).cbz") is True

    def test_v01_v03_is_not_multi(self):
        """Repeat-keyword 'v01-v03' is NOT recognized as multi-volume.

        FLAG: The regex requires a single keyword prefix then bare numbers; the
        second 'v' keyword prefix breaks recognition, causing only the first
        number to be returned by get_release_number.
        """
        assert kce.check_for_multi_volume_file("Series v01-v03 (2021).cbz") is False

    def test_v1_v3_is_not_multi(self):
        """Same repeat-keyword failure for non-padded 'v1-v3'."""
        assert kce.check_for_multi_volume_file("Series v1-v3 (2021).cbz") is False

    def test_single_volume_is_not_multi(self):
        """A filename with only one volume number is not multi-volume."""
        assert kce.check_for_multi_volume_file("Series v01 (2021).cbz") is False

    def test_chapter_range_is_multi_in_chapter_mode(self):
        """Chapter range 001-003 is recognized as multi-volume in chapter mode."""
        assert (
            kce.check_for_multi_volume_file(
                "Chapter 001-003 (2023).cbz", chapter=True
            )
            is True
        )
