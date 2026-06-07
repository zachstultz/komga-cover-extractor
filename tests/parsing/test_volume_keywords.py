"""Characterization tests for volume/chapter keyword detectors and one-shot/multi-volume checks.

Functions under test (signatures verified via Serena + live execution):

    kce.contains_volume_keywords(file: str) -> bool
        @lru_cache(maxsize=3500)
        Cleans the input (replaces ``_extra`` → ``.5``, strips brackets,
        replaces underscores, removes dual spaces) and then applies
        ``volume_regex`` (case-insensitive).

    kce.contains_chapter_keywords(file_name: str) -> bool
        @lru_cache(maxsize=3500)
        Applies the six pre-compiled ``chapter_search_patterns_comp`` in order.
        If none match AND the name has no volume keywords, falls back to a
        positional numeric check (strips bracketed-year, then 2000-2999 suffix).

    kce.is_one_shot(file_name, root=None, skip_folder_check=False, test_mode=False) -> bool
        Returns True only when the name contains *no* volume keyword, *no* chapter
        keyword, and *no* exception keyword.  test_mode=True implies
        skip_folder_check=True so no directory access is needed.

    kce.check_for_multi_volume_file(file_name: str, chapter: bool = False) -> bool
        @lru_cache(maxsize=3500)
        Looks for a ``KEYWORD n-m`` range pattern in the (bracket-stripped) name.
        chapter=True appends the chapter regex keywords to the search.

All values are OBSERVED from .venv/bin/python before being asserted.
FLAG comments mark surprising/buggy behaviour pinned as-is.
"""

from __future__ import annotations

import pytest
import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers / aliases
# ---------------------------------------------------------------------------

def cvk(s: str) -> bool:
    """Thin alias: contains_volume_keywords."""
    return kce.contains_volume_keywords(s)


def cck(s: str) -> bool:
    """Thin alias: contains_chapter_keywords."""
    return kce.contains_chapter_keywords(s)


def ios(name: str, **kw) -> bool:
    """Thin alias: is_one_shot (test_mode=True unless overridden)."""
    kw.setdefault("test_mode", True)
    return kce.is_one_shot(name, **kw)


def cmvf(name: str, chapter: bool = False) -> bool:
    """Thin alias: check_for_multi_volume_file."""
    return kce.check_for_multi_volume_file(name, chapter)


# ===========================================================================
# contains_volume_keywords
# ===========================================================================

class TestContainsVolumeKeywords:
    """Pin the boolean results of ``contains_volume_keywords``."""

    # --- spec examples (straight from the task) ---

    def test_spec_series_v01_cbz_true(self):
        """Spec example: 'Series v01.cbz' → True."""
        assert cvk("Series v01.cbz") is True

    def test_spec_bare_001_false(self):
        """Spec example: bare '001' (no keyword) → False."""
        assert cvk("001") is False

    # --- common volume keywords ---

    def test_vol_dot_space_true(self):
        """'Vol. 1' (with dot + space) → True."""
        assert cvk("Series Vol. 1.cbz") is True

    def test_volume_word_true(self):
        """'Volume 1' spelled out → True."""
        assert cvk("Series Volume 1.cbz") is True

    def test_vol_no_dot_true(self):
        """'Vol 2' without dot → True."""
        assert cvk("Vol 2") is True

    def test_uppercase_volume_true(self):
        """'VOLUME 5' all-caps → True."""
        assert cvk("VOLUME 5") is True

    def test_v_prefix_bare_true(self):
        """Bare 'v01' (no series name) → True."""
        assert cvk("v01") is True

    def test_ln_keyword_true(self):
        """'LN 1' (light novel abbreviation) → True."""
        assert cvk("Series LN 1") is True

    def test_light_novel_keyword_true(self):
        """'Light Novel 1' spelled out → True."""
        assert cvk("Series Light Novel 1") is True

    def test_novel_keyword_true(self):
        """'Novel 1' → True."""
        assert cvk("Series Novel 1") is True

    def test_book_keyword_true(self):
        """'Book 1' → True."""
        assert cvk("Series Book 1") is True

    def test_disc_keyword_true(self):
        """'Disc 1' → True."""
        assert cvk("Series Disc 1") is True

    def test_tomo_keyword_true(self):
        """'Tomo 1' (Spanish/Italian) → True."""
        assert cvk("Series Tomo 1") is True

    def test_tome_keyword_true(self):
        """'Tome 1' (French) → True."""
        assert cvk("Series Tome 1") is True

    def test_t_prefix_true(self):
        """'T01' (French manga 'Tome' abbreviation) → True."""
        assert cvk("Series T01") is True

    # --- underscore / bracket / _extra handling ---

    def test_underscore_series_name_true(self):
        """Underscores are replaced before regex → 'Series_v01.cbz' → True."""
        assert cvk("Series_v01.cbz") is True

    def test_extra_suffix_replaced_true(self):
        """'_extra' is replaced with '.5' early; the volume keyword 'v01' survives → True."""
        assert cvk("v01_extra") is True

    def test_extra_suffix_with_series_true(self):
        """'v01_extra' in a longer name still resolves → True."""
        assert cvk("Series v01_extra.cbz") is True

    def test_volume_in_square_brackets_false(self):
        """FLAG: '[v01] Series.cbz' — bracket removal strips the ONLY volume token → False.

        The code calls ``remove_brackets`` before applying volume_regex, so if the
        volume keyword is *inside* brackets it is deleted and not detected.
        This is surprising: a file that IS volume 1 returns False.
        """
        assert cvk("[v01] Series.cbz") is False

    def test_volume_in_round_brackets_false(self):
        """FLAG: 'Series (v01).cbz' — same bracket-removal quirk → False."""
        assert cvk("Series (v01).cbz") is False

    def test_volume_outside_brackets_with_extra_info_true(self):
        """Keyword OUTSIDE brackets is preserved → 'Series v01 (special).cbz' → True."""
        assert cvk("Series v01 (special).cbz") is True

    def test_bare_v01_in_brackets_only_false(self):
        """'[v01]' alone (keyword fully inside brackets) → False."""
        assert cvk("[v01]") is False

    # --- negative cases ---

    def test_chapter_keyword_no_volume_false(self):
        """'Chapter 001' has no volume keyword → False."""
        assert cvk("Chapter 001") is False

    def test_empty_string_false(self):
        """Empty string → False."""
        assert cvk("") is False

    def test_whitespace_only_false(self):
        """Whitespace-only string → False."""
        assert cvk("   ") is False

    def test_plain_series_name_false(self):
        """Series name with no volume/chapter marker → False."""
        assert cvk("Mushishi") is False

    def test_tom_no_number_false(self):
        """'Tom 1' is NOT in the keyword list (Tomo/Tome are; Tom is not) → False."""
        assert cvk("Series Tom 1") is False


# ===========================================================================
# contains_chapter_keywords
# ===========================================================================

class TestContainsChapterKeywords:
    """Pin the boolean results of ``contains_chapter_keywords``."""

    # --- spec examples ---

    def test_spec_series_c001_true(self):
        """Spec example: 'Series c001' → True."""
        assert cck("Series c001") is True

    def test_spec_bare_001_true(self):
        """Spec example: bare '001' → True (matches whole-string digit pattern)."""
        assert cck("001") is True

    def test_spec_100_true(self):
        """Spec example: '100' → True."""
        assert cck("100") is True

    def test_spec_v01_false(self):
        """Spec example: 'v01' has a volume keyword → False (vol check short-circuits)."""
        assert cck("v01") is False

    # --- chapter keyword variants ---

    def test_chapter_spelled_out_true(self):
        """'Chapter 5' (full word) → True."""
        assert cck("Series Chapter 5") is True

    def test_ch_dot_prefix_true(self):
        """'ch.001' → True."""
        assert cck("ch.001") is True

    def test_ch_space_number_true(self):
        """'Ch 5' (abbreviated, uppercase) → True."""
        assert cck("Ch 5") is True

    def test_c_space_number_true(self):
        """'c 001' (single 'c' keyword with space) → True."""
        assert cck("c 001") is True

    def test_c1_no_space_true(self):
        """'Series c1' → True."""
        assert cck("Series c1") is True

    def test_chapter_range_true(self):
        """Multi-chapter range 'Series c01-05' → True."""
        assert cck("Series c01-05") is True

    # --- bare number edge cases ---

    def test_bare_2000_true(self):
        """Bare '2000' — despite looking like a year, the whole-string digit pattern
        fires BEFORE the year-stripping fallback → True.

        This is because ``chapter_search_patterns_comp[5]`` (^digits$) runs first.
        """
        assert cck("2000") is True

    def test_bare_1999_true(self):
        """Bare '1999' → True (same whole-string digit pattern)."""
        assert cck("1999") is True

    def test_bare_2999_true(self):
        """Bare '2999' → True."""
        assert cck("2999") is True

    def test_bare_3000_true(self):
        """Bare '3000' → True."""
        assert cck("3000") is True

    # --- 4-digit bracketed number is filtered (year-like) ---

    def test_four_digit_round_brackets_false(self):
        """FLAG: '(1234)' — the code explicitly skips 4-digit values wrapped in
        a single bracket pair to avoid treating years as chapter numbers → False."""
        assert cck("(1234)") is False

    def test_four_digit_square_brackets_false(self):
        """'[1234]' — same 4-digit bracket filter applies → False."""
        assert cck("[1234]") is False

    def test_four_digit_curly_brackets_false(self):
        """'{1234}' — same 4-digit bracket filter applies → False."""
        assert cck("{1234}") is False

    def test_three_digit_round_brackets_true(self):
        """'(123)' — only 3 digits, bracket filter doesn't apply → True."""
        assert cck("(123)") is True

    def test_five_digit_round_brackets_true(self):
        """'(12345)' — 5 digits, bracket filter doesn't apply → True."""
        assert cck("(12345)") is True

    # --- interaction with volume keywords ---

    def test_volume_keyword_blocks_chapter_fallback_false(self):
        """'v01 2000' has a volume keyword; the numeric fallback is skipped → False."""
        assert cck("v01 2000") is False

    def test_series_vol_with_year_in_brackets_false(self):
        """'Series v01 (2020).cbz' — volume keyword present → False."""
        assert cck("Series v01 (2020).cbz") is False

    def test_series_year_only_in_brackets_false(self):
        """'Series (2020).cbz' — no chapter keyword; bracketed 4-digit filtered → False."""
        assert cck("Series (2020).cbz") is False

    # --- negative cases ---

    def test_empty_string_false(self):
        """Empty string → False."""
        assert cck("") is False

    def test_volume_keyword_only_false(self):
        """'v01' → False (volume present, no chapter indicator, fallback not triggered)."""
        assert cck("v01") is False

    def test_vol_plus_chapter_series_true(self):
        """'Series v01 c001' contains BOTH a volume and a chapter keyword.
        The chapter keyword patterns run first and find 'c001' → True.
        """
        assert cck("Series v01 c001") is True


# ===========================================================================
# is_one_shot
# ===========================================================================

class TestIsOneShot:
    """Pin the boolean results of ``is_one_shot`` (always called with test_mode=True)."""

    # --- one-shot positives: no volume, no chapter, no exception keyword ---

    def test_plain_filename_true(self):
        """Plain filename with no markers → True (is a one-shot)."""
        assert ios("My Manga.cbz") is True

    def test_bare_title_true(self):
        """Famous standalone title → True."""
        assert ios("Mushishi.cbz") is True

    def test_empty_string_true(self):
        """FLAG: empty string → True.

        No keywords match → skip_folder_check is True (via test_mode) → returns True.
        An empty filename being classified as a one-shot is unexpected.
        """
        assert ios("") is True

    # --- volume keyword → False ---

    def test_volume_keyword_false(self):
        """Volume marker 'v01' → False."""
        assert ios("Series v01.cbz") is False

    def test_volume_word_false(self):
        """'Volume 1' spelled out → False."""
        assert ios("Series Volume 1.cbz") is False

    # --- chapter keyword → False ---

    def test_chapter_keyword_false(self):
        """Chapter marker 'c001' → False."""
        assert ios("Series c001.cbz") is False

    def test_chapter_spelled_out_false(self):
        """'Chapter 1' spelled out → False."""
        assert ios("Series Chapter 1.cbz") is False

    def test_bare_number_false(self):
        """Bare '001.cbz' → False (contains_chapter_keywords('001') is True)."""
        assert ios("001.cbz") is False

    # --- exception keywords → False ---

    def test_oneshot_hyphen_false(self):
        """'One-shot' (hyphenated) matches exception pattern 'Ones?(-|)shot' → False."""
        assert ios("Series One-shot.cbz") is False

    def test_oneshot_no_separator_false(self):
        """'Oneshot' (no separator) matches exception pattern → False."""
        assert ios("Series Oneshot.cbz") is False

    def test_omake_false(self):
        """'Omake' matches exception keyword → False."""
        assert ios("Series Omake.cbz") is False

    def test_special_false(self):
        """'Special' matches exception keyword → False."""
        assert ios("Series Special.cbz") is False

    def test_extra_false(self):
        """'Extra' matches exception keyword → False."""
        assert ios("Series Extra.cbz") is False

    def test_bonus_false(self):
        """'Bonus' matches exception keyword → False."""
        assert ios("Series Bonus.cbz") is False

    def test_side_story_hyphen_false(self):
        """'Side-story' matches exception keyword → False."""
        assert ios("Series Side-story.cbz") is False

    def test_one_shot_space_does_not_match_false(self):
        """FLAG: 'One Shot' with a SPACE does NOT match the exception keyword
        pattern 'Ones?(-|)shot' (pattern allows hyphen or empty, not space).
        So the file is treated as a normal one-shot → True.

        This is a latent bug: a file literally named 'One Shot' is not recognised
        as an exception keyword file.
        """
        assert ios("My Manga - One Shot.cbz") is True

    # --- test_mode vs skip_folder_check equivalence ---

    def test_skip_folder_check_same_as_test_mode(self):
        """skip_folder_check=True (no root supplied) gives same result as test_mode=True."""
        assert kce.is_one_shot("My Manga.cbz", skip_folder_check=True) is True
        assert kce.is_one_shot("Series v01.cbz", skip_folder_check=True) is False


# ===========================================================================
# check_for_multi_volume_file
# ===========================================================================

class TestCheckForMultiVolumeFile:
    """Pin the boolean results of ``check_for_multi_volume_file``."""

    # --- spec examples ---

    def test_spec_v01_03_true(self):
        """Spec example: 'Series v01-03.cbz' → True."""
        assert cmvf("Series v01-03.cbz") is True

    def test_spec_v01_v03_false(self):
        """FLAG spec example: 'Series v01-v03.cbz' → False.

        The regex expects ``KEYWORD number - number``; when the second segment
        also has a keyword prefix ('v03'), the pattern does not match. So a file
        that IS a multi-volume range is mis-classified as False.
        This is pinned as-is; do not 'fix' production code here.
        """
        assert cmvf("Series v01-v03.cbz") is False

    # --- single volume → False ---

    def test_single_volume_false(self):
        """Single volume 'v01' (no range) → False."""
        assert cmvf("Series v01.cbz") is False

    def test_bare_v01_false(self):
        """Bare 'v01' token → False."""
        assert cmvf("v01") is False

    def test_no_dash_false(self):
        """No dash in name → False (short-circuits before regex)."""
        assert cmvf("Series Vol. 1.cbz") is False

    # --- successful multi-volume detections ---

    def test_vol_dot_range_true(self):
        """'Vol. 1-3' → True."""
        assert cmvf("Series Vol. 1-3.cbz") is True

    def test_decimal_start_range_true(self):
        """'Vol 1.5-3' (decimal start) → True."""
        assert cmvf("Series Vol 1.5-3.cbz") is True

    def test_decimal_end_range_true(self):
        """'Vol 1-3.5' (decimal end) → True."""
        assert cmvf("Series Vol 1-3.5.cbz") is True

    def test_three_part_range_true(self):
        """'v01-02-03' (3+ consecutive volumes) → True."""
        assert cmvf("Series v01-02-03.cbz") is True

    def test_no_volume_keyword_range_false(self):
        """'Series 1-3.cbz' has no volume keyword → False (keyword required)."""
        assert cmvf("Series 1-3.cbz") is False

    # --- bracket stripping behaviour ---

    def test_range_inside_brackets_false(self):
        """FLAG: '[v01-03]' — bracket removal erases the range; nothing left to match → False.

        This mirrors the same bracket-stripping issue seen in ``contains_volume_keywords``.
        A multi-volume range that lives entirely inside brackets is not detected.
        """
        assert cmvf("Series [v01-03].cbz") is False

    # --- chapter=True mode ---

    def test_chapter_flag_c_range_true(self):
        """chapter=True: 'c001-005.cbz' → True (chapter keywords added to search)."""
        assert cmvf("c001-005.cbz", True) is True

    def test_chapter_flag_c_range_false_without_flag(self):
        """chapter=False (default): 'c001-005.cbz' → False (chapter keyword not searched)."""
        assert cmvf("c001-005.cbz", False) is False

    def test_chapter_flag_chapter_spelled_out_true(self):
        """chapter=True: 'Chapter 1-5' → True."""
        assert cmvf("Series Chapter 1-5.cbz", True) is True

    def test_chapter_flag_chapter_spelled_out_false_without_flag(self):
        """chapter=False: 'Chapter 1-5' → False (not treated as a volume range)."""
        assert cmvf("Series Chapter 1-5.cbz", False) is False

    def test_chapter_short_c1_range_true(self):
        """chapter=True: 'c1-3.cbz' (short form) → True."""
        assert cmvf("c1-3.cbz", True) is True

    # --- no-keyword number range (requires chapter flag) ---

    def test_volume_range_with_chapter_flag_false(self):
        """FLAG: chapter=True replaces the keyword set with ONLY chapter keywords
        (``chapter_regex_keywords + '|'``), so a volume-keyword range like
        'Series v01-03.cbz' is NOT detected → False.

        This means check_for_multi_volume_file(name, chapter=True) cannot detect
        volume ranges — it is a chapter-only search when the flag is set.
        """
        assert cmvf("Series v01-03.cbz", True) is False
