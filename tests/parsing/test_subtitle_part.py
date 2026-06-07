"""Characterization tests for ``kce.get_file_part``, ``kce.get_subtitle_from_dash``,
and ``kce.get_shortened_title``.

All return values were observed by running the real functions in .venv/bin/python
before each assertion was written.  Surprising/buggy behaviours are noted with
``# FLAG:`` comments.

Verified function signatures (via Serena):
  get_file_part(file, chapter=False, series_name=None, subtitle=None)
  get_subtitle_from_dash(title, replace=False)
  get_shortened_title(title)
"""

from __future__ import annotations

import pytest
import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helper aliases
# ---------------------------------------------------------------------------

def gfp(file, chapter=False, series_name=None, subtitle=None):
    """Short alias for get_file_part."""
    return kce.get_file_part(file, chapter=chapter, series_name=series_name, subtitle=subtitle)


def gsd(title, replace=False):
    """Short alias for get_subtitle_from_dash."""
    return kce.get_subtitle_from_dash(title, replace=replace)


def gst(title):
    """Short alias for get_shortened_title."""
    return kce.get_shortened_title(title)


# ===========================================================================
# get_file_part
# ===========================================================================

class TestGetFilePart:
    """Pin the behaviour of ``get_file_part`` in volume (non-chapter) mode."""

    # -----------------------------------------------------------------------
    # Basic matches — volume mode (chapter=False)
    # -----------------------------------------------------------------------

    def test_simple_part_2_returns_int(self):
        """'Part 2' in filename → integer 2."""
        result = gfp("Series Part 2.cbz")
        assert result == 2
        assert isinstance(result, int)

    def test_part_only_no_series_prefix(self):
        """File starting with 'Part N' (no volume keyword prefix) → int N."""
        result = gfp("Part 5.cbz")
        assert result == 5
        assert isinstance(result, int)

    def test_part_with_volume_prefix(self):
        """'Volume 1 Part 2' extracts only the part number."""
        result = gfp("Volume 1 Part 2.cbz")
        assert result == 2
        assert isinstance(result, int)

    def test_part_10(self):
        """Multi-digit part number is extracted correctly."""
        result = gfp("Series Part 10.cbz")
        assert result == 10
        assert isinstance(result, int)

    def test_case_insensitive_PART(self):
        """'PART' (uppercase) is treated the same as 'Part'."""
        result = gfp("Series PART 2.cbz")
        assert result == 2
        assert isinstance(result, int)

    def test_case_insensitive_part_lower(self):
        """'part' (lowercase) is treated the same as 'Part'."""
        result = gfp("Series part 2.cbz")
        assert result == 2
        assert isinstance(result, int)

    def test_part_dash_separator(self):
        """'Part-2' (dash separator) is matched → 2."""
        result = gfp("Series Part-2.cbz")
        assert result == 2
        assert isinstance(result, int)

    def test_part_dot_separator(self):
        """'Part.2' (dot separator) is matched → 2."""
        result = gfp("Series Part.2.cbz")
        assert result == 2
        assert isinstance(result, int)

    def test_part_underscore_no_match(self):
        """'Part_2' (underscore separator) does NOT match.

        FLAG: the regex ``rx_search_part`` pattern ``r'(\\b(Part)([-_. ]|)([0-9]+)\\b)'``
        does include underscore in the separator class, so it WOULD match 'Part_2'.
        However, the guard ``contains_keyword`` uses ``re.search(r'\\bpart\\b', ...)``
        which requires word boundaries on BOTH sides of 'part'.  In 'Part_2', the
        underscore is a word character, so there is no ``\\b`` after 't' → the guard
        evaluates to None (falsy) → the function returns '' without ever reaching the
        regex search step.
        """
        result = gfp("Series Part_2.cbz")
        assert result == ""

    def test_no_part_keyword_returns_empty(self):
        """Filename with no 'part' keyword → empty string."""
        result = gfp("No part here.cbz")
        assert result == ""

    def test_empty_filename_returns_empty(self):
        """Empty string → empty string."""
        result = gfp("")
        assert result == ""

    def test_whitespace_filename_returns_empty(self):
        """Whitespace-only string → empty string."""
        result = gfp("   ")
        assert result == ""

    def test_part_range_returns_first(self):
        """'Part 2-3' — the regex ``([0-9]+)\\b`` captures only the first integer."""
        result = gfp("Series Part 2-3.cbz")
        assert result == 2
        assert isinstance(result, int)

    # -----------------------------------------------------------------------
    # Decimal/float truncation — the FLAG case
    # -----------------------------------------------------------------------

    def test_part_2_point_5_truncates_to_int_2(self):
        """'Part 2.5' silently truncates to integer 2.

        FLAG: ``rx_search_part`` = ``r'(\\b(Part)([-_. ]|)([0-9]+)\\b)'`` only captures
        the integer digits before the decimal point because the character-class
        separator ``([-_. ]|)`` consumes the dot between 'Part' and '2', leaving
        only '2' to be captured by ``([0-9]+)``.  The '.5' suffix is never seen.
        Result is int 2, not float 2.5.
        """
        result = gfp("Series Part 2.5.cbz")
        assert result == 2
        # FLAG: float 2.5 is silently truncated to int 2
        assert isinstance(result, int)

    def test_part_3_point_5_truncates_to_int_3(self):
        """'Part 3.5' likewise truncates to integer 3."""
        result = gfp("Manga Vol 1 Part 3.5.cbz")
        assert result == 3
        assert isinstance(result, int)

    # -----------------------------------------------------------------------
    # series_name / subtitle stripping
    # -----------------------------------------------------------------------

    def test_series_name_stripped_before_search(self):
        """series_name is removed from the filename before part extraction."""
        result = gfp("My Series Vol 1 Part 2.cbz", series_name="My Series")
        assert result == 2
        assert isinstance(result, int)

    def test_subtitle_stripped_before_search(self):
        """subtitle is removed from the filename before part extraction."""
        result = gfp(
            "My Series Vol 1 - Sub Part 2.cbz",
            series_name="My Series",
            subtitle="Sub",
        )
        assert result == 2
        assert isinstance(result, int)

    def test_series_name_not_in_filename_still_works(self):
        """series_name not present in filename → strips nothing, still matches Part."""
        result = gfp("Vol 1 Part 2.cbz", series_name="Other Series")
        assert result == 2
        assert isinstance(result, int)

    # -----------------------------------------------------------------------
    # Volume mode: 'x' / '#' indicators are ignored
    # -----------------------------------------------------------------------

    def test_x_indicator_in_volume_mode_ignored(self):
        """In volume mode (chapter=False), the 'x' chapter indicator is not used."""
        result = gfp("Series 1x2.cbz")
        assert result == ""

    def test_hash_indicator_in_volume_mode_ignored(self):
        """In volume mode (chapter=False), the '#' chapter indicator is not used."""
        result = gfp("Series 1#2.cbz")
        assert result == ""


class TestGetFilePartChapterMode:
    """Pin the behaviour of ``get_file_part`` in chapter mode (chapter=True)."""

    def test_x_indicator_extracts_part_as_int(self):
        """Chapter indicator 'x' extracts the part number → int."""
        result = gfp("Series 1x2.cbz", chapter=True)
        assert result == 2
        assert isinstance(result, int)

    def test_hash_indicator_extracts_part_as_int(self):
        """Chapter indicator '#' extracts the part number → int."""
        result = gfp("Series 1#2.cbz", chapter=True)
        assert result == 2
        assert isinstance(result, int)

    def test_chapter_x_float_part(self):
        """'1x2.5' — chapter part with decimal → float 2.5 (NOT truncated)."""
        result = gfp("Chapter 1x2.5.cbz", chapter=True)
        assert result == 2.5
        # NOTE: unlike volume mode, the chapter regex captures the full decimal.
        assert isinstance(result, float)

    def test_chapter_x_int_part(self):
        """'Chapter 1x3' → integer 3 (no decimal)."""
        result = gfp("Chapter 1x3.cbz", chapter=True)
        assert result == 3
        assert isinstance(result, int)

    def test_chapter_hash_int_part(self):
        """'Chapter 1#5' → integer 5."""
        result = gfp("Chapter 1#5.cbz", chapter=True)
        assert result == 5
        assert isinstance(result, int)

    def test_chapter_multi_digit_x(self):
        """'Chapter 10x3' → integer 3."""
        result = gfp("Chapter 10x3.cbz", chapter=True)
        assert result == 3
        assert isinstance(result, int)

    def test_chapter_large_chapter_number(self):
        """'Chapter 100x5' → integer 5."""
        result = gfp("Chapter 100x5.cbz", chapter=True)
        assert result == 5
        assert isinstance(result, int)

    def test_chapter_range_before_x(self):
        """'Chapter 1-2x3' — range before x is handled; extracts 3."""
        result = gfp("Chapter 1-2x3.cbz", chapter=True)
        assert result == 3
        assert isinstance(result, int)

    def test_chapter_float_3_point_5(self):
        """'Chapter 10x3.5' → float 3.5."""
        result = gfp("Chapter 10x3.5.cbz", chapter=True)
        assert result == 3.5
        assert isinstance(result, float)

    def test_chapter_no_indicator_returns_empty(self):
        """chapter=True but no 'x' or '#' in filename → empty string.

        FLAG: when chapter=True and neither 'x' nor '#' is in the filename,
        ``contains_indicator`` is False, so the entire block is skipped and ''
        is returned even if a 'Part N' keyword is present.
        """
        result = gfp("Series Part 2.cbz", chapter=True)
        assert result == ""

    def test_x_only_no_digit_before(self):
        """'x' only exists in a word (no digit immediately before it) → no match.

        'Seriesx2' does not match the chapter regex because the pattern
        ``rx_search_chapters`` expects digits before the x.
        """
        result = gfp("Seriesx2.cbz", chapter=True)
        assert result == ""

    def test_x_in_word_but_with_valid_chapter(self):
        """'Experiment 1x2.cbz' — 'x' appears in 'Experiment' AND as indicator;
        the chapter regex still extracts part 2 from '1x2'."""
        result = gfp("Experiment 1x2.cbz", chapter=True)
        assert result == 2
        assert isinstance(result, int)

    def test_maximum_word_x_no_digit_before(self):
        """'Maximum 1.cbz' — 'x' is in 'Maximum' but no digit before x → no match.

        ``contains_indicator`` is True (x appears in the string), but
        ``rx_search_chapters`` requires digits before the x/# indicator,
        so the search fails → '' returned.
        """
        result = gfp("Maximum 1.cbz", chapter=True)
        assert result == ""

    def test_chapter_with_series_name_stripped(self):
        """series_name stripping also works in chapter mode."""
        result = gfp("My Series 1x2.cbz", chapter=True, series_name="My Series")
        # FLAG: series_name stripping only happens inside the 'if not chapter:' branch
        # for contains_keyword; the contains_indicator path is separate. The actual
        # behaviour observed is that stripping occurs at file level for both modes.
        # Verified: result is 2.
        assert result == 2
        assert isinstance(result, int)


# ===========================================================================
# get_subtitle_from_dash
# ===========================================================================

class TestGetSubtitleFromDash:
    """Pin the behaviour of ``get_subtitle_from_dash``.

    FLAG — default (replace=False) returns the SEPARATOR string (' - ' or ': '),
    NOT the subtitle text itself.  Only with replace=True does it return the
    subtitle portion after the separator.
    """

    # -----------------------------------------------------------------------
    # replace=False (default) — returns SEPARATOR string
    # -----------------------------------------------------------------------

    def test_dash_separator_returns_separator_string(self):
        """' - ' present → returns the literal separator ' - ', not the subtitle.

        FLAG: replace=False returns the separator, not the text after it.
        """
        result = gsd("Series - Subtitle")
        assert result == " - "

    def test_colon_space_separator_returns_separator(self):
        """'Series: Subtitle' → returns ': ' (the separator, not 'Subtitle')."""
        result = gsd("Series: Subtitle")
        assert result == ": "

    def test_no_separator_returns_empty_string(self):
        """Title with no recognisable separator → empty string."""
        result = gsd("No subtitle here")
        assert result == ""

    def test_empty_string_returns_empty_string(self):
        """Empty string → empty string."""
        result = gsd("")
        assert result == ""

    def test_series_only_no_separator_returns_empty(self):
        """Plain series name with no dash/colon → empty string."""
        result = gsd("Series")
        assert result == ""

    def test_trailing_dash_still_returns_separator(self):
        """'Series - ' (trailing whitespace after separator) → ' - '."""
        result = gsd("Series - ")
        assert result == " - "

    def test_multiple_dashes_returns_first_separator(self):
        """'A - B - C' → returns ' - ' (only the first occurrence is matched here)."""
        result = gsd("A - B - C")
        assert result == " - "

    def test_colon_vol_dash_part_returns_first_separator(self):
        """'Series: Vol 1 - Part 2' — colon comes first → ': '."""
        result = gsd("Series: Vol 1 - Part 2")
        assert result == ": "

    def test_dash_without_spaces_no_match(self):
        """'Series-Subtitle' (no spaces around dash) → empty string.

        FLAG: the regex requires at least one whitespace before the dash:
        ``(\\s+(-)|:)\\s+``.  A bare '-' without leading whitespace is not matched.
        """
        result = gsd("Series-Subtitle")
        assert result == ""

    def test_space_colon_no_space_after_no_match(self):
        """'Series :Subtitle' (no space after colon) → empty string.

        FLAG: the regex requires whitespace AFTER the separator (``\\s+``).
        A colon without trailing whitespace is not matched.
        """
        result = gsd("Series :Subtitle")
        assert result == ""

    def test_space_colon_space_returns_separator(self):
        """'Series : Subtitle' (spaces both sides of colon) → ': '."""
        result = gsd("Series : Subtitle")
        assert result == ": "

    def test_dash_without_leading_space_no_match(self):
        """'Series -Subtitle' (no space before dash) → empty string."""
        result = gsd("Series -Subtitle")
        assert result == ""

    # -----------------------------------------------------------------------
    # replace=True — returns SUBTITLE text (everything after the separator)
    # -----------------------------------------------------------------------

    def test_replace_true_dash_returns_subtitle(self):
        """replace=True: 'Series - Subtitle' → 'Subtitle'."""
        result = gsd("Series - Subtitle", replace=True)
        assert result == "Subtitle"

    def test_replace_true_colon_returns_subtitle(self):
        """replace=True: 'Series: Subtitle' → 'Subtitle'."""
        result = gsd("Series: Subtitle", replace=True)
        assert result == "Subtitle"

    def test_replace_true_no_separator_returns_empty(self):
        """replace=True with no separator → empty string (no match → no replace)."""
        result = gsd("No subtitle here", replace=True)
        assert result == ""

    def test_replace_true_empty_string_returns_empty(self):
        """replace=True with empty string → empty string."""
        result = gsd("", replace=True)
        assert result == ""

    def test_replace_true_trailing_dash(self):
        """replace=True: 'Series - ' → empty string (nothing after the separator)."""
        result = gsd("Series - ", replace=True)
        assert result == ""

    def test_replace_true_multiple_dashes(self):
        """replace=True: 'A - B - C' — everything after the FIRST separator is kept.

        The sub pattern ``r'(.*)((\\s+(-)|:)\\s+)'`` is greedy on the first group,
        so it matches up to the LAST separator, leaving only 'C'.
        """
        result = gsd("A - B - C", replace=True)
        assert result == "C"

    def test_replace_true_colon_vol_dash_part(self):
        """replace=True: 'Series: Vol 1 - Part 2' → 'Part 2'.

        The greedy ``(.*)`` matches 'Series: Vol 1' consuming the colon separator,
        then the second ``(\\s+(-)|:)\\s+`` matches ' - ', leaving 'Part 2'.
        """
        result = gsd("Series: Vol 1 - Part 2", replace=True)
        assert result == "Part 2"

    def test_replace_true_long_title(self):
        """replace=True: 'My Long Series - A Great Subtitle' → 'A Great Subtitle'."""
        result = gsd("My Long Series - A Great Subtitle", replace=True)
        assert result == "A Great Subtitle"

    def test_replace_true_space_colon_space(self):
        """replace=True: 'Series : Subtitle' → 'Subtitle'."""
        result = gsd("Series : Subtitle", replace=True)
        assert result == "Subtitle"

    def test_replace_true_dash_no_spaces_no_change(self):
        """replace=True: 'Series-Subtitle' (no spaces around dash) → empty string.

        No separator match → no substitution → '' returned.
        """
        result = gsd("Series-Subtitle", replace=True)
        assert result == ""

    def test_replace_true_vol_subtitle(self):
        """replace=True: 'Series - Vol 1' → 'Vol 1'."""
        result = gsd("Series - Vol 1", replace=True)
        assert result == "Vol 1"


# ===========================================================================
# get_shortened_title
# ===========================================================================

class TestGetShortenedTitle:
    """Pin the behaviour of ``get_shortened_title``.

    Returns the part of the title BEFORE the first ' - ' or ': ' separator
    (stripped of whitespace), or '' if no separator is present.
    """

    def test_dash_separator_returns_prefix(self):
        """'Series - Subtitle' → 'Series'."""
        result = gst("Series - Subtitle")
        assert result == "Series"

    def test_colon_space_separator_returns_prefix(self):
        """'Series: Subtitle' → 'Series'."""
        result = gst("Series: Subtitle")
        assert result == "Series"

    def test_no_separator_returns_empty_string(self):
        """No separator → empty string (never None)."""
        result = gst("No subtitle here")
        assert result == ""

    def test_plain_series_no_separator_returns_empty(self):
        """Plain name without dash or colon → empty string."""
        result = gst("Series")
        assert result == ""

    def test_multiple_dashes_returns_text_before_first(self):
        """'A - B - C' — only the text before the FIRST separator is returned."""
        result = gst("A - B - C")
        assert result == "A"

    def test_long_series_with_subtitle(self):
        """'My Long Series - A Great Subtitle' → 'My Long Series'."""
        result = gst("My Long Series - A Great Subtitle")
        assert result == "My Long Series"

    def test_colon_no_space_after_no_match(self):
        """'Series:Subtitle' (colon without trailing space) → empty string.

        FLAG: the regex ``r'((\\s+(-)|:)\\s+.*)'`` requires whitespace after the
        colon.  A bare colon with no following space does not match.
        """
        result = gst("Series:Subtitle")
        assert result == ""

    def test_trailing_dash_separator(self):
        """'Series - ' → 'Series' (nothing after the separator is OK)."""
        result = gst("Series - ")
        assert result == "Series"

    def test_colon_space_subtitle(self):
        """'Series: A Subtitle' → 'Series'."""
        result = gst("Series: A Subtitle")
        assert result == "Series"

    def test_hyphenated_series_with_subtitle(self):
        """'Spider-Man - Comic' — only the ' - ' (with spaces) triggers the split.

        The bare hyphen in 'Spider-Man' has no spaces so is not a separator.
        """
        result = gst("Spider-Man - Comic")
        assert result == "Spider-Man"

    def test_hyphenated_series_no_subtitle(self):
        """'Spider-Man' — only a hyphen without surrounding spaces → empty string."""
        result = gst("Spider-Man")
        assert result == ""

    def test_leading_spaces_stripped(self):
        """Leading whitespace in title does not affect matching; prefix is stripped."""
        result = gst("  Series - Subtitle")
        assert result == "Series"

    def test_return_type_is_always_str(self):
        """Return value is always str (never None), even when there is no match."""
        assert isinstance(gst("NoSeparator"), str)
        assert isinstance(gst("Has - Sep"), str)
