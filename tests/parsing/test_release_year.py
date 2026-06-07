"""Characterization tests for ``kce.get_release_year``.

Signature (verified via Serena):
    get_release_year(name: str, metadata: dict | None = None) -> str | int | None

Return-type contract observed in the wild (pinned as-is):
  * Filename path: returns the year as a **str** (e.g. ``'2021'``), because the
    regex just calls ``.group()[1:-1]`` on the raw text.
  * Metadata path: returns the year as an **int** (e.g. ``2021``), because the
    code does ``result = int(release_year_from_file)``.
  * Absent/invalid year: returns ``None``.

FLAG: the return type is inconsistent between the two code paths — filename yields
str, metadata yields int.  This is pinned as-is; do not "fix" in production here.
"""

from __future__ import annotations

import pytest
import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helper alias
# ---------------------------------------------------------------------------

def gry(name: str, metadata=None):
    """Thin wrapper so call sites stay short."""
    return kce.get_release_year(name, metadata=metadata)


# ---------------------------------------------------------------------------
# Filename-based extraction (returns STR)
# ---------------------------------------------------------------------------

class TestFilenameYear:
    """Year extracted from the filename always returns a plain string."""

    def test_round_parens_returns_str(self):
        """Standard ``(YYYY)`` in filename → string year."""
        result = gry("My Series (2021)")
        assert result == "2021"
        # FLAG: filename path returns str, not int
        assert isinstance(result, str)

    def test_square_brackets_returns_str(self):
        """``[YYYY]`` bracket style is supported and also returns str."""
        result = gry("My Series [2018]")
        assert result == "2018"
        assert isinstance(result, str)

    def test_curly_braces_returns_str(self):
        """``{YYYY}`` brace style is supported and also returns str."""
        result = gry("My Series {2017}")
        assert result == "2017"
        assert isinstance(result, str)

    def test_year_in_middle_of_name(self):
        """Year does not have to be at the end of the filename."""
        result = gry("My Series (2021) Vol 1")
        assert result == "2021"
        assert isinstance(result, str)

    def test_filename_year_takes_precedence_over_metadata(self):
        """When filename contains a year, metadata is ignored entirely."""
        result = gry("My Series (2021)", metadata={"Summary": "desc", "Year": "2020"})
        # Filename wins — returns str '2021', not int from metadata
        assert result == "2021"
        assert isinstance(result, str)

    def test_two_digit_year_not_matched(self):
        """``(99)`` is only 2 digits — pattern requires exactly 4 digits → None."""
        assert gry("My Series (99)") is None

    def test_five_digit_year_not_matched(self):
        """``(20201)`` has 5 digits — pattern requires exactly 4 digits → None."""
        assert gry("My Series (20201)") is None

    def test_empty_name(self):
        """Empty filename string → None."""
        assert gry("") is None

    def test_name_with_no_year_at_all(self):
        """Name has no bracketed year → None (no metadata supplied)."""
        assert gry("No Year Here") is None


# ---------------------------------------------------------------------------
# Metadata path — ComicInfo ``Year`` field (returns INT)
# ---------------------------------------------------------------------------

class TestMetadataYearField:
    """Metadata ``Year`` key is only trusted when ``Summary`` is also present."""

    def test_year_str_with_summary_returns_int(self):
        """``Year='2020'`` with ``Summary`` present → integer 2020."""
        result = gry("My Series", metadata={"Summary": "Some description", "Year": "2020"})
        assert result == 2020
        # FLAG: metadata path returns int, filename path returns str
        assert isinstance(result, int)

    def test_year_below_floor_1949_returns_none(self):
        """Years strictly below 1950 are discarded — 1949 → None."""
        assert gry("My Series", metadata={"Summary": "desc", "Year": "1949"}) is None

    def test_year_below_floor_1900_returns_none(self):
        """Far below floor (1900) → None."""
        assert gry("My Series", metadata={"Summary": "desc", "Year": "1900"}) is None

    def test_year_at_floor_1950_is_accepted(self):
        """Exactly 1950 is at the boundary and IS accepted → 1950 (int)."""
        result = gry("My Series", metadata={"Summary": "desc", "Year": "1950"})
        assert result == 1950
        assert isinstance(result, int)

    def test_year_missing_summary_returns_none(self):
        """``Year`` without accompanying ``Summary`` is ignored → None.

        FLAG: the code requires BOTH Summary and Year to trust the metadata year;
        a lone Year field is silently discarded.
        """
        assert gry("My Series", metadata={"Year": "2020"}) is None

    def test_year_key_absent_returns_none(self):
        """``Summary`` present but ``Year`` absent → None."""
        assert gry("My Series", metadata={"Summary": "desc"}) is None

    def test_non_digit_year_string_returns_none(self):
        """Non-numeric Year string (fails isdigit check) → None."""
        assert gry("My Series", metadata={"Summary": "desc", "Year": "abc2"}) is None

    def test_five_digit_year_string_returns_none(self):
        """5-digit Year string (fails len==4 check) → None."""
        assert gry("My Series", metadata={"Summary": "desc", "Year": "20201"}) is None

    def test_year_as_int_in_metadata_raises_typeerror(self):
        """Passing Year as a Python int (instead of str) crashes with TypeError.

        FLAG: the code calls ``len(release_year_from_file)`` which fails on int.
        ComicInfo parsers normally return strings, so this edge case is a latent bug.
        """
        with pytest.raises(TypeError, match="object of type 'int' has no len"):
            gry("My Series", metadata={"Summary": "desc", "Year": 2020})


# ---------------------------------------------------------------------------
# Metadata path — EPUB ``dc:date`` field (returns INT)
# ---------------------------------------------------------------------------

class TestMetadataDcDate:
    """dc:date is used when ``dc:description`` is also present (EPUB path)."""

    def test_full_iso_date_extracts_year_as_int(self):
        """``dc:date='2019-05-01'`` → integer 2019."""
        result = gry(
            "My Series",
            metadata={"dc:description": "Some description", "dc:date": "2019-05-01"},
        )
        assert result == 2019
        assert isinstance(result, int)

    def test_bare_year_dc_date_returns_int(self):
        """``dc:date='2019'`` (no month/day) → integer 2019."""
        result = gry(
            "My Series",
            metadata={"dc:description": "desc", "dc:date": "2019"},
        )
        assert result == 2019
        assert isinstance(result, int)

    def test_dc_date_with_surrounding_whitespace(self):
        """Leading/trailing whitespace is stripped before parsing."""
        result = gry(
            "My Series",
            metadata={"dc:description": "desc", "dc:date": " 2019-05-01 "},
        )
        assert result == 2019
        assert isinstance(result, int)

    def test_dc_date_below_floor_returns_none(self):
        """dc:date year of 1900 is below the 1950 floor → None."""
        assert gry(
            "My Series",
            metadata={"dc:description": "desc", "dc:date": "1900-01-01"},
        ) is None

    def test_dc_date_at_floor_1950_accepted(self):
        """dc:date year of exactly 1950 passes the floor check → 1950 (int)."""
        result = gry(
            "My Series",
            metadata={"dc:description": "desc", "dc:date": "1950-01-01"},
        )
        assert result == 1950
        assert isinstance(result, int)

    def test_dc_date_non_digit_first_segment_returns_none(self):
        """Non-numeric first segment of dc:date (fails isdigit) → None."""
        assert gry(
            "My Series",
            metadata={"dc:description": "desc", "dc:date": "abc-def"},
        ) is None

    def test_dc_date_missing_dc_description_returns_none(self):
        """dc:date alone without dc:description is not trusted → None.

        FLAG: the code requires BOTH dc:description and dc:date; sole dc:date ignored.
        """
        assert gry("My Series", metadata={"dc:date": "2019-05-01"}) is None

    def test_dc_description_without_dc_date_returns_none(self):
        """dc:description present but dc:date absent → None."""
        assert gry("My Series", metadata={"dc:description": "desc"}) is None


# ---------------------------------------------------------------------------
# No metadata / absent year
# ---------------------------------------------------------------------------

class TestNoYear:
    """Catches all the empty/None/missing cases."""

    def test_none_metadata_returns_none(self):
        """Explicitly passing ``metadata=None`` → None."""
        assert gry("My Series", metadata=None) is None

    def test_default_metadata_returns_none(self):
        """Omitting metadata entirely (defaults to None) → None."""
        assert gry("My Series") is None

    def test_empty_dict_metadata_returns_none(self):
        """Empty metadata dict (no keys) → None."""
        assert gry("My Series", metadata={}) is None

    def test_no_year_name_no_metadata(self):
        """Plain series name with no year pattern → None."""
        assert gry("Sword Art Online") is None
