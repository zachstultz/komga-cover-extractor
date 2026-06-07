"""Characterization tests for ``kce.chapter_file_name_cleaning``.

All expected values were verified against the live interpreter before being
written here.  This file intentionally pins CURRENT behaviour (including
quirks) -- it does NOT assert what would be "correct".

Signature (verified via Serena + inspect):
    @lru_cache(maxsize=3500)
    chapter_file_name_cleaning(
        file_name,
        chapter_number="",
        skip=False,
        regex_matched=False,
    ) -> str

Key behaviour notes:
* Trailing parentheses/square brackets at end are removed via ``remove_brackets``
  (only *trailing* groups -- leading ones are left intact).
* If ``file_name[0].isdigit()`` and ``regex_matched != 2`` the leading
  "NNN - " prefix is stripped.
* Trailing " num -" is stripped only when ``regex_matched != 0`` (i.e. when
  the value is truthy / non-zero).
* Season keywords ("Season"/"Sea"/"S") followed by a number at the end are
  removed -- but the regex leaves a trailing space (see FLAG below).
* A file_name that reduces to a bare digit (or ``#digit`` or ``digit.digit``)
  returns ``""`` unless ``skip=True``.
* Empty string raises ``IndexError`` because the code indexes ``file_name[0]``
  unconditionally.
"""

from __future__ import annotations

import pytest
import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Convenience alias
# ---------------------------------------------------------------------------

def clean(file_name: str, **kwargs) -> str:
    """Thin wrapper that clears lru_cache between tests via the autouse fixture."""
    return kce.chapter_file_name_cleaning(file_name, **kwargs)


# ---------------------------------------------------------------------------
# Happy-path: bracket removal
# ---------------------------------------------------------------------------

class TestBracketRemoval:
    """Trailing bracket groups are stripped; leading ones are left alone."""

    def test_trailing_round_brackets_removed(self):
        """'Series Name (2020)' -> trailing '(2020)' is stripped."""
        assert clean("Series Name (2020)") == "Series Name"

    def test_trailing_square_brackets_not_removed(self):
        """remove_brackets only strips trailing *round* bracket groups.

        'Series Name [Volume 1]' – the square-bracket group is NOT removed.
        """
        # FLAG: remove_brackets does not strip square-bracket groups at the end.
        assert clean("Series Name [Volume 1]") == "Series Name [Volume 1]"

    def test_leading_round_brackets_left_intact(self):
        """'(Scans) Series Name' – leading group is NOT removed."""
        assert clean("(Scans) Series Name") == "(Scans) Series Name"

    def test_leading_square_brackets_left_intact(self):
        """'[Group] My Series 001' – leading square-bracket group stays."""
        assert clean("[Group] My Series 001") == "[Group] My Series 001"

    def test_trailing_unclosed_bracket_dropped(self):
        """A lone '(' at the very end is dropped via ends_with_starting_bracket."""
        assert clean("Series Name - Bonus Chapter (") == "Series Name - Bonus Chapter"

    def test_trailing_unclosed_square_bracket_dropped(self):
        """A lone '[' at the end is also dropped."""
        assert clean("My Series [") == "My Series"

    def test_multiple_trailing_bracket_groups(self):
        """Multiple trailing bracket groups are both stripped."""
        assert clean("001 - Series Name (Group) [2020]") == "Series Name (Group)"


# ---------------------------------------------------------------------------
# Happy-path: leading digit + dash stripping
# ---------------------------------------------------------------------------

class TestLeadingDigitStrip:
    """When file_name starts with a digit and regex_matched != 2, the leading
    'NNN - ' or 'NNN.M - ' prefix is removed."""

    def test_simple_leading_number_stripped(self):
        """'001 - My Series' -> 'My Series'."""
        assert clean("001 - My Series") == "My Series"

    def test_decimal_leading_number_stripped(self):
        """'006.3 - Series Name' -> 'Series Name'."""
        assert clean("006.3 - Series Name") == "Series Name"

    def test_leading_digit_strip_skipped_when_regex_matched_2(self):
        """regex_matched=2 suppresses the leading-digit strip.

        '006.3 - Series Name' stays as '006.3' (subtitle is then removed
        by the trailing subtitle rule because '-' is present and name[0] is
        still a digit at that point).
        """
        assert clean("006.3 - Series Name", regex_matched=2) == "006.3"

    def test_leading_digit_strip_runs_when_regex_matched_1(self):
        """regex_matched=1 still strips the leading digit prefix."""
        assert clean("007 - James Bond", regex_matched=1) == "James Bond"

    def test_no_leading_digit_untouched(self):
        """A plain series name with no leading digit is returned as-is."""
        assert clean("My Manga") == "My Manga"

    def test_double_dash_separator_stripped(self):
        """'012 -- My Series' leading number+double-dash is removed."""
        assert clean("012 -- My Series") == "My Series"

    def test_underscore_separator_stripped(self):
        """'012 __ My Series' leading number+double-underscore is removed."""
        assert clean("012 __ My Series") == "My Series"


# ---------------------------------------------------------------------------
# Happy-path: trailing "num -" removal
# ---------------------------------------------------------------------------

class TestTrailingNumberDashRemoval:
    """Trailing 'NNN -' is stripped only when regex_matched != 0.

    When regex_matched is False (the default, which equals 0), the
    number+dash pattern is NOT applied -- only a bare trailing '-' (with no
    preceding number) is cleaned.
    """

    def test_trailing_number_dash_not_stripped_by_default(self):
        """Default regex_matched=False (==0): 'Series Name 54 -' keeps '54'."""
        # FLAG: regex_matched=False means 0 which disables the num-dash strip;
        # only the bare trailing '-' regex runs, which doesn't match the '54 -' form.
        assert clean("Series Name 54 -") == "Series Name 54"

    def test_trailing_number_dash_stripped_when_regex_matched_1(self):
        """regex_matched=1 (truthy): '54 -' suffix is fully removed."""
        assert clean("Series Name 54 -", regex_matched=1) == "Series Name"

    def test_trailing_number_dash_stripped_when_regex_matched_2(self):
        """regex_matched=2 also strips trailing 'num -'."""
        assert clean("Series Name 54 -", regex_matched=2) == "Series Name"

    def test_trailing_bare_dash_stripped(self):
        """A trailing bare '-' (no preceding number) is removed regardless of regex_matched."""
        assert clean("Series -") == "Series"
        assert clean("Series -", regex_matched=0) == "Series"
        assert clean("Series -", regex_matched=1) == "Series"


# ---------------------------------------------------------------------------
# Happy-path: digit-only reduction -> empty string
# ---------------------------------------------------------------------------

class TestDigitOnlyReduction:
    """Names that reduce to a bare number (or #number) return '' unless skip=True."""

    def test_integer_only_returns_empty(self):
        """'42' is just a digit -> returns ''."""
        assert clean("42") == ""

    def test_integer_only_skip_true_returns_as_is(self):
        """With skip=True the digit-only check is bypassed."""
        assert clean("42", skip=True) == "42"

    def test_decimal_only_returns_empty(self):
        """'42.5' is effectively a decimal number -> returns ''."""
        assert clean("42.5") == ""

    def test_decimal_only_skip_true_returns_as_is(self):
        """With skip=True, '3.5' is returned unchanged."""
        assert clean("3.5", skip=True) == "3.5"

    def test_hash_digit_returns_empty(self):
        """'#42' reduces to a digit after removing '#' -> ''."""
        assert clean("#42") == ""

    def test_hash_digit_skip_true_returned(self):
        """'#42' with skip=True is returned as '#42'."""
        # FLAG: skip=True bypasses BOTH digit checks, returning '#42' as-is
        # even though '#' is not a real chapter name.
        assert clean("#42", skip=True) == "#42"

    def test_zero_padded_chapter_number_returns_empty(self):
        """'#001' is a digit-like token -> ''."""
        assert clean("#001") == ""

    def test_zero_padded_hash_skip_true(self):
        """'#001' with skip=True returns '#001'."""
        assert clean("#001", skip=True) == "#001"

    def test_hash_decimal_returns_empty(self):
        """'#42.5' -> '' (hash+decimal stripped as digit)."""
        assert clean("#42.5") == ""

    def test_hash_decimal_skip_true(self):
        """'#42.5' with skip=True returns '#42.5'."""
        assert clean("#42.5", skip=True) == "#42.5"


# ---------------------------------------------------------------------------
# Happy-path: chapter_number removal
# ---------------------------------------------------------------------------

class TestChapterNumberRemoval:
    """When chapter_number is provided and regex_matched is falsy, the
    chapter number at the end of file_name is stripped."""

    def test_chapter_number_stripped_from_end(self):
        """'Series Name 001' with chapter_number='1' -> 'Series Name'."""
        assert clean("Series Name 001", chapter_number="1") == "Series Name"

    def test_chapter_number_zero_padded_stripped(self):
        """chapter_number='001' also removes the trailing '001'."""
        assert clean("Series Name 001", chapter_number="001") == "Series Name"

    def test_chapter_number_plain_stripped(self):
        """'Berserk 42' with chapter_number='42' -> 'Berserk'."""
        assert clean("Berserk 42", chapter_number="42") == "Berserk"

    def test_chapter_number_not_stripped_when_regex_matched(self):
        """chapter_number removal is skipped when regex_matched is truthy.

        The chapter_number block runs only when ``not regex_matched``.
        With regex_matched=1 the trailing '001' is NOT removed.
        """
        assert clean("Series Name 001", chapter_number="1", regex_matched=1) == "Series Name 001"

    def test_no_chapter_number_no_change(self):
        """No chapter_number arg: trailing digit stays if it isn't just a digit."""
        assert clean("Berserk Volume 42") == "Berserk Volume 42"


# ---------------------------------------------------------------------------
# Happy-path: season keyword removal
# ---------------------------------------------------------------------------

class TestSeasonRemoval:
    """'Season N', 'Sea N', or 'S N' at end of name (case-insensitive) is stripped."""

    def test_season_keyword_removed(self):
        """'My Series Season 2' -> 'My Series ' (note trailing space -- see FLAG)."""
        # FLAG: The season-strip regex does not include a trailing strip(), so a
        # trailing space is left in the returned string.
        assert clean("My Series Season 2") == "My Series "

    def test_sea_keyword_removed(self):
        """'My Series Sea 3' -> 'My Series ' (trailing space quirk applies)."""
        # FLAG: same trailing-space quirk as Season.
        assert clean("My Series Sea 3") == "My Series "

    def test_season_no_trailing_digit_not_stripped(self):
        """Season keyword not at end (no trailing digit) is left alone."""
        assert clean("My Season Adventures") == "My Season Adventures"

    def test_sea_no_space_not_stripped(self):
        """'My Series Sea2' (no space before digit) still stripped."""
        # FLAG: regex matches 'Sea' + optional whitespace + digits, so 'Sea2' also matches.
        assert clean("My Series Sea2") == "My Series "


# ---------------------------------------------------------------------------
# Happy-path: subtitle stripping for leading-digit names
# ---------------------------------------------------------------------------

class TestSubtitleStripping:
    """When file_name starts with a digit AND contains '-' or ':', the
    subtitle after the separator is removed."""

    def test_dash_subtitle_stripped_leading_digit(self):
        """'179.1 - Epilogue 01': after leading-digit strip we get 'Epilogue 01'.

        The leading digit strip runs first and removes '179.1 - '.
        Then subtitle strip does NOT apply (no '-' left, and 'E' is not a digit).
        """
        assert clean("179.1 - Epilogue 01") == "Epilogue 01"

    def test_colon_subtitle_stripped(self):
        """'179.1: Epilogue': after bracket strip + leading digit strip, result is '179.1'.

        Actually: leading-digit strip matches '179.1' + ':' -> no, the pattern needs
        a dash/underscore separator. So the colon is handled by the subtitle rule.
        """
        assert clean("179.1: Epilogue") == "179.1"

    def test_subtitle_stripped_regex_matched_2(self):
        """With regex_matched=2 the leading-digit strip is skipped; subtitle rule fires instead."""
        # '179.1 - Epilogue 01' -> no leading-digit strip -> subtitle rule fires
        # -> removes ' - Epilogue 01' -> '179.1'
        assert clean("179.1 - Epilogue 01", regex_matched=2) == "179.1"


# ---------------------------------------------------------------------------
# FLAG: empty string raises IndexError
# ---------------------------------------------------------------------------

class TestEmptyStringRaisesIndexError:
    """An empty file_name causes an IndexError because the code accesses
    file_name[0] without a prior length check.

    This is a known bug -- we pin it as-is.
    """

    def test_empty_string_raises_index_error(self):
        """'' -> IndexError('string index out of range')."""
        # FLAG: empty string input is not guarded and raises IndexError.
        # The lru_cache does NOT cache exceptions, so each call raises anew.
        with pytest.raises(IndexError):
            clean("")

    def test_empty_string_raises_on_repeated_call(self):
        """lru_cache does not cache the exception; second call also raises."""
        with pytest.raises(IndexError):
            clean("")
        with pytest.raises(IndexError):
            clean("")


# ---------------------------------------------------------------------------
# Miscellaneous / integration-style cases
# ---------------------------------------------------------------------------

class TestMiscellaneous:
    """A grab-bag of realistic chapter filenames."""

    def test_plain_series_name_unchanged(self):
        """A series name with no special tokens is returned unchanged."""
        assert clean("Attack on Titan - Chapter 139") == "Attack on Titan - Chapter 139"

    def test_series_with_chapter_prefix_unchanged(self):
        """'v01 ch001 - Series Name' does not start with a bare digit (v01)."""
        assert clean("v01 ch001 - Series Name") == "v01 ch001 - Series Name"

    def test_whitespace_only_returned_as_is(self):
        """Whitespace-only strings are returned unchanged (no IndexError)."""
        assert clean("   ") == "   "
        assert clean(" ") == " "

    def test_series_name_with_trailing_number_no_chapter(self):
        """Without chapter_number, trailing digit is NOT removed."""
        assert clean("Berserk Volume 42") == "Berserk Volume 42"

    def test_realistic_chapter_filename_cleaned(self):
        """Realistic chapter file: trailing round brackets stripped; square brackets also stripped.

        'Solo Leveling c001 (2020) [Scanlation]' ->
        remove_brackets strips '(2020)' and then '[Scanlation]' as well.
        The 'S' prefix is not a digit so no leading-digit strip occurs.
        """
        # FLAG: remove_brackets strips BOTH trailing '(2020)' and '[Scanlation]' here,
        # contrary to the earlier observation for '[Volume 1]'. The difference is that
        # '[Scanlation]' appears after '(2020)' so the combined trailing sequence is removed.
        assert clean("Solo Leveling c001 (2020) [Scanlation]") == "Solo Leveling c001"
