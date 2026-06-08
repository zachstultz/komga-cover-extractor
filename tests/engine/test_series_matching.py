"""Characterization tests for the series-matching cluster.

Functions covered:
  - parse_words              (kce.py ~line 6065)
  - find_consecutive_items   (kce.py ~line 6085)
  - get_series_name_from_contents  (kce.py ~line 2240)
  - get_identifiers          (kce.py ~line 6051)
  - get_shortened_title      (kce.py ~line 9726)
  - upgrade_to_file_class + upgrade_to_volume_class golden snapshots

All assertion values were FIRST observed by running the production module under
.venv/bin/python3 on the tests/upgrade-scoring-engine branch (after commit 300cfb4)
and then pinned as-is.  FLAG: comments document surprising / buggy behaviour.
"""

from __future__ import annotations

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_volumes(file_names, root="/tmp/nope"):
    """Pipeline helper: upgrade_to_file_class -> upgrade_to_volume_class (test_mode)."""
    files = kce.upgrade_to_file_class(file_names, root, test_mode=True)
    return kce.upgrade_to_volume_class(files, test_mode=True)


# ===========================================================================
# parse_words
# ===========================================================================

class TestParseWords:
    """Characterize parse_words — incl. the dead-unidecode FLAG."""

    # -----------------------------------------------------------------------
    # Return type
    # -----------------------------------------------------------------------

    def test_returns_list(self):
        result = kce.parse_words("Hello World")
        assert isinstance(result, list)

    # -----------------------------------------------------------------------
    # Basic behaviour
    # -----------------------------------------------------------------------

    def test_simple_ascii_title(self):
        assert kce.parse_words("Some Name v01 (2021)") == ["some", "name", "v01", "2021"]

    def test_empty_string_returns_empty_list(self):
        assert kce.parse_words("") == []

    def test_none_returns_empty_list(self):
        # FLAG: None is passed as user_string; the ``if user_string:`` guard
        # short-circuits and returns [] rather than raising TypeError.
        assert kce.parse_words(None) == []

    def test_punctuation_stripped(self):
        assert kce.parse_words("Hello, World!") == ["hello", "world"]

    def test_colon_stripped(self):
        assert kce.parse_words("Naruto: Uzumaki Chronicles") == [
            "naruto",
            "uzumaki",
            "chronicles",
        ]

    def test_hyphen_stripped_joins_words(self):
        # Hyphens are punctuation; 'One-Punch' loses the dash → 'onepunch'.
        assert kce.parse_words("One-Punch Man") == ["onepunch", "man"]

    def test_period_stripped(self):
        assert kce.parse_words("vol.01") == ["vol01"]

    def test_lowercase_conversion(self):
        assert kce.parse_words("Attack on Titan") == ["attack", "on", "titan"]

    # -----------------------------------------------------------------------
    # FLAG: dead unidecode — unicode characters ARE preserved in output
    # -----------------------------------------------------------------------

    def test_accented_char_preserved_not_ascii_folded(self):
        # FLAG: parse_words computes ``words_no_uni = unidecode(words_lower)``
        # but then splits ``words_lower`` (not ``words_no_uni``), so unidecode
        # is dead code.  The returned list keeps the original accented form.
        # If the bug were ever fixed, the result would be ['cafe'] not ['café'].
        result = kce.parse_words("Café au lait")
        assert result == ["café", "au", "lait"]

    def test_accented_naïve_résumé_preserved(self):
        # FLAG: same dead-unidecode issue — accents survive.
        result = kce.parse_words("Naïve résumé")
        assert result == ["naïve", "résumé"]

    def test_german_umlaut_preserved(self):
        # FLAG: 'über' is not transliterated to 'uber'.
        result = kce.parse_words("Über Doctor Strange")
        assert result == ["über", "doctor", "strange"]

    def test_cjk_characters_preserved_not_transliterated(self):
        # FLAG: unidecode would turn '東京' → 'Dong Jing', but the split is on
        # words_lower so the CJK token survives as-is.
        result = kce.parse_words("東京 Ghoul v01")
        assert result == ["東京", "ghoul", "v01"]


# ===========================================================================
# find_consecutive_items
# ===========================================================================

class TestFindConsecutiveItems:
    """Characterize find_consecutive_items — position-based, not value-based."""

    # -----------------------------------------------------------------------
    # Return type
    # -----------------------------------------------------------------------

    def test_returns_bool_true(self):
        result = kce.find_consecutive_items((1, 2, 3), (1, 2, 3))
        assert isinstance(result, bool)
        assert result is True

    def test_returns_bool_false(self):
        result = kce.find_consecutive_items((1, 2, 3), (4, 5, 6))
        assert isinstance(result, bool)
        assert result is False

    # -----------------------------------------------------------------------
    # Insufficient length short-circuit
    # -----------------------------------------------------------------------

    def test_arr1_shorter_than_count_returns_false(self):
        # len(arr1) < count → immediate False, no element comparison.
        assert kce.find_consecutive_items((1, 2), (1, 2, 3), count=3) is False

    def test_arr2_shorter_than_count_returns_false(self):
        assert kce.find_consecutive_items((1, 2, 3), (1, 2), count=3) is False

    def test_both_shorter_than_count_returns_false(self):
        assert kce.find_consecutive_items((1, 2), (1, 2), count=3) is False

    def test_empty_arrays_return_false(self):
        assert kce.find_consecutive_items((), (), count=3) is False

    # -----------------------------------------------------------------------
    # Exact matches
    # -----------------------------------------------------------------------

    def test_identical_arrays_returns_true(self):
        arr = (1, 2, 3, 4)
        assert kce.find_consecutive_items(arr, arr) is True

    def test_matching_prefix_returns_true(self):
        assert kce.find_consecutive_items((1, 2, 3, 4, 5), (0, 1, 2, 3)) is True

    def test_matching_subsequence_in_middle_returns_true(self):
        assert kce.find_consecutive_items((10, 20, 1, 2, 3), (1, 2, 3, 30, 40)) is True

    def test_no_shared_subsequence_returns_false(self):
        assert kce.find_consecutive_items((1, 2, 3), (4, 5, 6)) is False

    # -----------------------------------------------------------------------
    # Custom count parameter
    # -----------------------------------------------------------------------

    def test_count_2_match_returns_true(self):
        assert kce.find_consecutive_items((1, 2, 5), (1, 2, 7), count=2) is True

    def test_count_1_same_element_returns_true(self):
        assert kce.find_consecutive_items((7,), (7,), count=1) is True

    def test_count_1_different_element_returns_false(self):
        assert kce.find_consecutive_items((1,), (2,), count=1) is False

    # -----------------------------------------------------------------------
    # NOTE: comparison is positional, not numerical-gap — (1,5,9) vs (1,5,9)
    # returns True even though values are not numerically consecutive.
    # -----------------------------------------------------------------------

    def test_positionally_consecutive_non_sequential_values(self):
        # (1,5,9) and (1,5,9,13): the 3-element run [1,5,9] appears at position 0
        # in both arrays, so this returns True.  "consecutive" means adjacent
        # positions in the array, NOT consecutive integer values.
        a = (1, 5, 9)
        b = (1, 5, 9, 13)
        assert kce.find_consecutive_items(a, b, count=3) is True

    def test_match_at_tail_of_first_array(self):
        # (8,9) appears at positions [8,9] in range(10) and at positions [0,1] in b.
        a = tuple(range(10))
        b = (8, 9, 99, 100)
        assert kce.find_consecutive_items(a, b, count=2) is True

    def test_word_tuple_prefix_match(self):
        w1 = ("attack", "on", "titan", "before", "the", "fall")
        w2 = ("attack", "on", "titan")
        assert kce.find_consecutive_items(w1, w2, count=3) is True

    def test_word_tuple_prefix_match_reversed_args(self):
        w1 = ("attack", "on", "titan", "before", "the", "fall")
        w2 = ("attack", "on", "titan")
        assert kce.find_consecutive_items(w2, w1, count=3) is True

    def test_word_tuple_no_match(self):
        w1 = ("my", "hero", "academia")
        w2 = ("one", "punch", "man")
        assert kce.find_consecutive_items(w1, w2, count=3) is False

    def test_three_word_match_in_four_word_arrays(self):
        w1 = ("the", "quick", "brown", "fox")
        w2 = ("a", "quick", "brown", "fox", "jumped")
        assert kce.find_consecutive_items(w1, w2, count=3) is True


# ===========================================================================
# get_series_name_from_contents
# ===========================================================================

class TestGetSeriesNameFromContents:
    """Characterize get_series_name_from_contents — char-by-char folder scan."""

    # -----------------------------------------------------------------------
    # Return type
    # -----------------------------------------------------------------------

    def test_returns_str(self):
        result = kce.get_series_name_from_contents("Naruto", ["Naruto v01.cbz"])
        assert isinstance(result, str)

    # -----------------------------------------------------------------------
    # Empty / degenerate inputs
    # -----------------------------------------------------------------------

    def test_empty_file_list_returns_empty_string(self):
        assert kce.get_series_name_from_contents("Naruto", []) == ""

    def test_series_shorter_than_3_chars_returns_empty(self):
        # Minimum match length is 3 characters.
        assert kce.get_series_name_from_contents("AB", ["AB v01.cbz", "AB v02.cbz"]) == ""

    def test_exactly_3_char_series_name_returned(self):
        assert kce.get_series_name_from_contents("ABC", ["ABC v01.cbz", "ABC v02.cbz"]) == "ABC"

    # -----------------------------------------------------------------------
    # 100 % required_matching_percent (default)
    # -----------------------------------------------------------------------

    def test_all_files_match_full_folder_name(self):
        assert kce.get_series_name_from_contents(
            "Naruto", ["Naruto v01.cbz", "Naruto v02.cbz"]
        ) == "Naruto"

    def test_all_files_match_multiword_name(self):
        assert kce.get_series_name_from_contents(
            "Dragonball Z", ["Dragonball Z v01.cbz", "Dragonball Z v02.cbz"]
        ) == "Dragonball Z"

    def test_mismatch_at_second_file_100pct_stops_early(self):
        # "My Hero Academia" vs "My Neighbor Totoro" diverge at char index 3 ('H' vs 'N').
        # With 100 % required, any mismatch terminates the scan.  The result is 'My'
        # (2 chars) which is below the 3-char minimum → returns "".
        # Verified: actual result is 'My', stripped to 'My', < 3 chars → "".
        # NOTE: the match stops at the first diverging char; strip() is applied at end.
        result = kce.get_series_name_from_contents(
            "My Hero Academia",
            ["My Hero Academia v01.cbz", "My Neighbor Totoro.cbz"],
        )
        assert result == "My"

    def test_single_file_fully_matching_returns_series(self):
        assert kce.get_series_name_from_contents("Berserk", ["Berserk v01.cbz"]) == "Berserk"

    def test_folder_longer_than_file_stops_at_file_end(self):
        # File 'Some.cbz' is shorter than folder 'Some Long Folder Name'.
        # Scan stops when i >= len(file_name): matching_count becomes 0, loop breaks.
        assert kce.get_series_name_from_contents(
            "Some Long Folder Name", ["Some.cbz"]
        ) == "Some"

    def test_folder_longer_than_file_2(self):
        # 'Dragon Ball.cbz' is shorter than 'Dragon Ball Super'.
        assert kce.get_series_name_from_contents(
            "Dragon Ball Super", ["Dragon Ball.cbz"]
        ) == "Dragon Ball"

    # -----------------------------------------------------------------------
    # Case-insensitive comparison (char.lower() == file_char.lower())
    # -----------------------------------------------------------------------

    def test_case_insensitive_comparison(self):
        # Folder is lowercase 'naruto', files start with uppercase 'N' —
        # the comparison is case-insensitive so the folder chars are returned verbatim.
        result = kce.get_series_name_from_contents(
            "naruto", ["Naruto v01.cbz", "Naruto v02.cbz"]
        )
        assert result == "naruto"

    # -----------------------------------------------------------------------
    # Trailing whitespace stripping
    # -----------------------------------------------------------------------

    def test_trailing_spaces_stripped_from_result(self):
        # Folder 'My Manga  ' has trailing spaces.  strip() is called on the result.
        result = kce.get_series_name_from_contents(
            "My Manga  ", ["My Manga v01.cbz", "My Manga v02.cbz"]
        )
        assert result == "My Manga"

    # -----------------------------------------------------------------------
    # Non-100 % required_matching_percent
    # -----------------------------------------------------------------------

    def test_50pct_matching_allows_partial_mismatch(self):
        # With 50 %, 1 of 2 files matching at each position is enough.
        result = kce.get_series_name_from_contents(
            "My Hero Academia",
            ["My Hero Academia v01.cbz", "My Neighbor Totoro.cbz"],
            required_matching_percent=50,
        )
        assert result == "My Hero Academia"


# ===========================================================================
# get_identifiers
# ===========================================================================

class TestGetIdentifiers:
    """Characterize get_identifiers — case-sensitivity FLAG."""

    # -----------------------------------------------------------------------
    # Return type
    # -----------------------------------------------------------------------

    def test_returns_list(self):
        assert isinstance(kce.get_identifiers("Identifiers: foo:bar"), list)

    # -----------------------------------------------------------------------
    # Normal (title-case) happy paths
    # -----------------------------------------------------------------------

    def test_single_identifier(self):
        assert kce.get_identifiers("Identifiers: anilist:12345") == ["anilist:12345"]

    def test_two_identifiers(self):
        result = kce.get_identifiers("Identifiers: isbn:9781234567890, comicid:12345")
        assert result == ["isbn:9781234567890", "comicid:12345"]

    def test_three_identifiers(self):
        comment = "Title: Something\nIdentifiers: isbn:111, comicid:222, anilist:333"
        assert kce.get_identifiers(comment) == ["isbn:111", "comicid:222", "anilist:333"]

    def test_realistic_zip_comment(self):
        comment = "Title: Naruto\nVolume: 1\nIdentifiers: isbn:9781421500614, comicid:56789"
        assert kce.get_identifiers(comment) == ["isbn:9781421500614", "comicid:56789"]

    def test_whitespace_trimmed_from_each_identifier(self):
        # strip() is applied per-identifier.
        result = kce.get_identifiers("Identifiers:  isbn:111 , comicid:222 ")
        assert result == ["isbn:111", "comicid:222"]

    # -----------------------------------------------------------------------
    # Empty / no-match inputs
    # -----------------------------------------------------------------------

    def test_no_identifiers_keyword_returns_empty_list(self):
        assert kce.get_identifiers("Some random comment") == []

    def test_empty_string_returns_empty_list(self):
        assert kce.get_identifiers("") == []

    # -----------------------------------------------------------------------
    # FLAG: case-sensitivity bug
    # -----------------------------------------------------------------------

    def test_lowercase_identifiers_keyword_raises_index_error(self):
        # FLAG: get_identifiers does ``"identifiers" in zip_comment.lower()`` (case-
        # insensitive check) but then splits on the literal string "Identifiers:"
        # (title-case).  If the comment uses all-lowercase "identifiers:" the check
        # passes but the split produces only one element, so [1] raises IndexError.
        # This is a latent bug pinned as-is.
        with pytest.raises(IndexError):
            kce.get_identifiers("identifiers: foo:bar, baz:qux")

    def test_uppercase_identifiers_keyword_raises_index_error(self):
        # FLAG: same bug — "IDENTIFIERS:" passes the .lower() check but not the
        # title-case split.
        with pytest.raises(IndexError):
            kce.get_identifiers("IDENTIFIERS: foo:bar, baz:qux")


# ===========================================================================
# get_shortened_title
# ===========================================================================

class TestGetShortenedTitle:
    """Characterize get_shortened_title — splits on `` - `` or ``: ``."""

    def test_returns_str(self):
        assert isinstance(kce.get_shortened_title("Naruto: The Clash"), str)

    def test_colon_separator_returns_prefix(self):
        assert kce.get_shortened_title("Naruto: The Clash of Ninja") == "Naruto"

    def test_space_dash_space_separator_returns_prefix(self):
        assert kce.get_shortened_title("Attack on Titan - Before the Fall") == "Attack on Titan"

    def test_no_separator_returns_empty_string(self):
        assert kce.get_shortened_title("My Hero Academia") == ""

    def test_no_separator_plain_returns_empty_string(self):
        assert kce.get_shortened_title("No Colon Or Dash") == ""

    def test_inline_dash_without_spaces_not_matched(self):
        # "One-Punch Man" has a dash but NOT surrounded by spaces, so no match.
        assert kce.get_shortened_title("One-Punch Man") == ""

    def test_multiple_separators_first_wins(self):
        # Both ':' and ' - ' present; the regex strips from the first match.
        assert kce.get_shortened_title("Solo Leveling: Ragnarok - Extra") == "Solo Leveling"

    def test_multiple_colons_first_wins(self):
        assert kce.get_shortened_title("A: B: C") == "A"

    def test_single_char_before_separator(self):
        assert kce.get_shortened_title("A - B") == "A"

    def test_space_colon_space_separator(self):
        # 'A : B' — regex matches `: ` with leading space.
        assert kce.get_shortened_title("A : B") == "A"

    def test_colon_no_trailing_space_not_matched(self):
        # 'Title:' has no trailing space after the colon → no regex match.
        assert kce.get_shortened_title("Title:") == ""

    def test_empty_string_returns_empty(self):
        assert kce.get_shortened_title("") == ""


# ===========================================================================
# Volume golden snapshots — upgrade_to_file_class + upgrade_to_volume_class
# ===========================================================================

class TestVolumeGoldenSnapshots:
    """Pin the production parsing pipeline end-to-end with test_mode=True.

    test_mode=True implies:
      - skip_release_year=True  → volume_year is always None
      - skip_publisher=True     → publisher.from_meta is always None
      - skip_premium_content=True → is_premium is always False
    Release group lookup is also skipped in test_mode (skip_release_group default
    False but get_extra_from_group reads kce.release_groups which is [] by default,
    so release_group is always '' in the default test fixture).
    """

    # -----------------------------------------------------------------------
    # Standard volume with digital/group extras
    # -----------------------------------------------------------------------

    def test_standard_volume_file_type(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].file_type == "volume"

    def test_standard_volume_series_name(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].series_name == "Naruto"

    def test_standard_volume_number(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].volume_number == 1

    def test_standard_volume_index_number(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].index_number == 1

    def test_standard_volume_extension(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].extension == ".cbz"

    def test_standard_volume_year_none_in_test_mode(self):
        # test_mode=True skips year lookup → always None.
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].volume_year is None

    def test_standard_volume_release_group_empty_no_groups_configured(self):
        # kce.release_groups == [] (default) → release_group is ''.
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].release_group == ""

    def test_standard_volume_extras(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].extras == ["(Digital)", "[Group]"]

    def test_standard_volume_is_not_one_shot(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].is_one_shot is False

    def test_standard_volume_part_is_empty_string(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        assert vols[0].volume_part == ""

    def test_standard_volume_publisher_from_meta_none(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        pub = vols[0].publisher
        assert pub.from_meta is None

    def test_standard_volume_publisher_from_name_none(self):
        vols = _make_volumes(["Naruto v01 (2021) (Digital) [Group].cbz"])
        pub = vols[0].publisher
        assert pub.from_name is None

    # -----------------------------------------------------------------------
    # Volume with subtitle (space-dash-space separator)
    # -----------------------------------------------------------------------

    def test_subtitle_series_name_full(self):
        vols = _make_volumes(["Attack on Titan - Before the Fall v01.cbz"])
        assert vols[0].series_name == "Attack on Titan - Before the Fall"

    def test_subtitle_shortened_series_name(self):
        vols = _make_volumes(["Attack on Titan - Before the Fall v01.cbz"])
        assert vols[0].shortened_series_name == "Attack on Titan"

    def test_subtitle_subtitle_field_empty(self):
        # The subtitle field is set by get_subtitle_from_title; with no recognized
        # subtitle pattern the field is '' for this input.
        vols = _make_volumes(["Attack on Titan - Before the Fall v01.cbz"])
        assert vols[0].subtitle == ""

    def test_subtitle_volume_number(self):
        vols = _make_volumes(["Attack on Titan - Before the Fall v01.cbz"])
        assert vols[0].volume_number == 1

    def test_subtitle_extras_empty(self):
        vols = _make_volumes(["Attack on Titan - Before the Fall v01.cbz"])
        assert vols[0].extras == []

    def test_subtitle_multi_volume_false(self):
        vols = _make_volumes(["Attack on Titan - Before the Fall v01.cbz"])
        assert vols[0].multi_volume is False

    # -----------------------------------------------------------------------
    # Volume with part number — index_number = volume_number + part/10
    # -----------------------------------------------------------------------

    def test_part_volume_number(self):
        vols = _make_volumes(["My Hero Academia v01 Part 2 (2020) [Digital].cbz"])
        assert vols[0].volume_number == 1

    def test_part_volume_part(self):
        vols = _make_volumes(["My Hero Academia v01 Part 2 (2020) [Digital].cbz"])
        assert vols[0].volume_part == 2

    def test_part_index_number(self):
        # index_number = volume_number + volume_part / 10 = 1 + 2/10 = 1.2
        vols = _make_volumes(["My Hero Academia v01 Part 2 (2020) [Digital].cbz"])
        assert vols[0].index_number == 1.2

    def test_part_extras_include_part_tag(self):
        vols = _make_volumes(["My Hero Academia v01 Part 2 (2020) [Digital].cbz"])
        assert "(Part 2)" in vols[0].extras

    # -----------------------------------------------------------------------
    # Chapter file
    # -----------------------------------------------------------------------

    def test_chapter_file_type(self):
        vols = _make_volumes(["Naruto Chapter 001.cbz"])
        assert vols[0].file_type == "chapter"

    def test_chapter_volume_number(self):
        vols = _make_volumes(["Naruto Chapter 001.cbz"])
        assert vols[0].volume_number == 1

    def test_chapter_series_name(self):
        vols = _make_volumes(["Naruto Chapter 001.cbz"])
        assert vols[0].series_name == "Naruto"

    # -----------------------------------------------------------------------
    # One-shot: no volume number in test_mode → is_one_shot=True, volume_number=1
    # -----------------------------------------------------------------------

    def test_one_shot_detection_no_volume_number(self):
        vols = _make_volumes(["Koe no Katachi (2013) (Digital) [Group].cbz"])
        assert vols[0].is_one_shot is True

    def test_one_shot_volume_number_set_to_1(self):
        # When is_one_shot is True the pipeline sets volume_number = 1.
        vols = _make_volumes(["Koe no Katachi (2013) (Digital) [Group].cbz"])
        assert vols[0].volume_number == 1

    def test_one_shot_index_number_set_to_1(self):
        vols = _make_volumes(["Koe no Katachi (2013) (Digital) [Group].cbz"])
        assert vols[0].index_number == 1

    def test_one_shot_extras(self):
        vols = _make_volumes(["Koe no Katachi (2013) (Digital) [Group].cbz"])
        assert vols[0].extras == ["(Digital)", "[Group]"]

    def test_volume_with_number_is_not_one_shot(self):
        vols = _make_volumes(["Berserk v40 (2020) (Digital) [Group].cbz"])
        assert vols[0].is_one_shot is False
        assert vols[0].volume_number == 40

    # -----------------------------------------------------------------------
    # Multi-volume file (hyphenated range)
    # -----------------------------------------------------------------------

    def test_multi_volume_flag_true(self):
        vols = _make_volumes(["Naruto v01-03 (2021) (Digital).cbz"])
        assert vols[0].multi_volume is True

    def test_multi_volume_number_is_list(self):
        vols = _make_volumes(["Naruto v01-03 (2021) (Digital).cbz"])
        assert vols[0].volume_number == [1, 3]

    def test_multi_volume_index_number_is_list(self):
        vols = _make_volumes(["Naruto v01-03 (2021) (Digital).cbz"])
        assert vols[0].index_number == [1, 3]

    def test_multi_volume_extras(self):
        vols = _make_volumes(["Naruto v01-03 (2021) (Digital).cbz"])
        assert vols[0].extras == ["(Digital)"]

    # -----------------------------------------------------------------------
    # Float volume number (e.g. v10.5 side-story)
    # -----------------------------------------------------------------------

    def test_float_volume_number(self):
        vols = _make_volumes(["One Piece v10.5 (Digital).cbz"])
        assert vols[0].volume_number == 10.5

    def test_float_volume_part_is_empty(self):
        # 10.5 is already a float; volume_part stays '' (no Part keyword).
        vols = _make_volumes(["One Piece v10.5 (Digital).cbz"])
        assert vols[0].volume_part == ""

    def test_float_volume_index_equals_volume_number(self):
        vols = _make_volumes(["One Piece v10.5 (Digital).cbz"])
        assert vols[0].index_number == 10.5

    # -----------------------------------------------------------------------
    # epub extension
    # -----------------------------------------------------------------------

    def test_epub_extension(self):
        vols = _make_volumes(["Sword Art Online v01.epub"])
        assert vols[0].extension == ".epub"

    def test_epub_file_type_volume(self):
        vols = _make_volumes(["Sword Art Online v01.epub"])
        assert vols[0].file_type == "volume"

    def test_epub_series_name(self):
        vols = _make_volumes(["Sword Art Online v01.epub"])
        assert vols[0].series_name == "Sword Art Online"

    def test_epub_volume_number(self):
        vols = _make_volumes(["Sword Art Online v01.epub"])
        assert vols[0].volume_number == 1

    # -----------------------------------------------------------------------
    # Batch: multiple files → multiple Volume objects
    # -----------------------------------------------------------------------

    def test_batch_length(self):
        names = ["Naruto v01.cbz", "Naruto v02.cbz", "Naruto v03.cbz"]
        vols = _make_volumes(names)
        assert len(vols) == 3

    def test_batch_volume_numbers(self):
        names = ["Naruto v01.cbz", "Naruto v02.cbz", "Naruto v03.cbz"]
        vols = _make_volumes(names)
        nums = [v.volume_number for v in vols]
        assert nums == [1, 2, 3]

    def test_batch_all_same_series(self):
        names = ["Naruto v01.cbz", "Naruto v02.cbz"]
        vols = _make_volumes(names)
        assert all(v.series_name == "Naruto" for v in vols)

    # -----------------------------------------------------------------------
    # Empty input
    # -----------------------------------------------------------------------

    def test_empty_file_list_returns_empty(self):
        files = kce.upgrade_to_file_class([], "/tmp/nope", test_mode=True)
        assert files == []

    def test_empty_volume_list_returns_empty(self):
        result = kce.upgrade_to_volume_class([], test_mode=True)
        assert result == []
