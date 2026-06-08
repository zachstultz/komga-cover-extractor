"""Characterization tests for the keyword scoring and upgrade decision engine.

Pins the CURRENT behaviour of:
  * get_keyword_scores(releases) -> list[RankedKeywordResult]
  * is_upgradeable(downloaded, current) -> UpgradeResult
  * get_highest_release(releases, is_chapter_directory) -> int | float | str

All golden values were observed by running snippets against the project .venv
on the tests/upgrade-scoring-engine branch BEFORE writing the assertions —
no value was guessed.

Key environment facts:
  * ranked_keywords defaults to [] and compiled_searches defaults to []
    (both are set in settings.py / komga_cover_extractor.py module-level).
  * test_mode=True in upgrade_to_volume_class skips release_year, publisher, and
    premium_content lookups (so volume_year=None, is_premium=False, release_group='').
  * The autouse isolated_globals fixture from conftest.py restores kce module globals
    (including ranked_keywords and compiled_searches) after every test.
"""

from __future__ import annotations

import re

import pytest

import komga_cover_extractor as kce
from settings import Keyword


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_vols(*filenames: str, root: str = "/tmp/nope"):
    """Return list[Volume] through the production pipeline with test_mode=True."""
    files = kce.upgrade_to_file_class(list(filenames), root, test_mode=True)
    assert files
    return kce.upgrade_to_volume_class(files, test_mode=True)


def _set_keywords(*keywords: Keyword):
    """Replace kce.ranked_keywords and rebuild kce.compiled_searches."""
    kce.ranked_keywords = list(keywords)
    kce.compiled_searches = [
        re.compile(kw.name, re.IGNORECASE) for kw in kce.ranked_keywords
    ]


# ===========================================================================
# get_keyword_scores — default empty ranked_keywords
# ===========================================================================

class TestGetKeywordScoresDefaultEmpty:
    """With default empty ranked_keywords, scores must be 0.0 and tags empty."""

    def test_returns_list(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        results = kce.get_keyword_scores(vols)
        assert isinstance(results, list)

    def test_length_matches_input(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        results = kce.get_keyword_scores(vols)
        assert len(results) == 1

    def test_result_type_is_RankedKeywordResult(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        assert isinstance(result, kce.RankedKeywordResult)

    def test_total_score_is_zero_float(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        # Empty ranked_keywords → score starts and stays at 0.0 (float)
        assert result.total_score == 0.0
        assert isinstance(result.total_score, float)

    def test_keywords_list_is_empty(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        assert result.keywords == []
        assert isinstance(result.keywords, list)

    def test_empty_releases_list_returns_empty(self):
        results = kce.get_keyword_scores([])
        assert results == []
        assert isinstance(results, list)


# ===========================================================================
# get_keyword_scores — with a known ranked_keywords configuration
# ===========================================================================

class TestGetKeywordScoresNonTrivial:
    """Exercise non-zero scoring by setting a small known kce.ranked_keywords."""

    def setup_method(self):
        # Observed: Digital=10, [Group] regex=3 → total 13.0 for the test filename.
        # isolated_globals autouse fixture restores these after the test.
        _set_keywords(
            Keyword(r"Digital", 10.0, "both"),
            Keyword(r"Webrip", 3.0, "both"),
            Keyword(r"\[Group\]", 3.0, "both"),
        )

    def test_matching_keyword_adds_score(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        # Digital (10) + [Group] (3) match; Webrip does not.
        assert result.total_score == 13.0
        assert isinstance(result.total_score, float)

    def test_matched_keywords_list_length(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        assert len(result.keywords) == 2

    def test_matched_keyword_names_are_search_group_not_pattern(self):
        # search.group() is stored, not keyword.name — so case of the actual
        # matched text is preserved (e.g. lowercase "digital" if file is lowercase).
        _set_keywords(Keyword(r"DIGITAL", 10.0, "both"))
        vols = _build_vols("Some Name v01 (digital).cbz")
        result = kce.get_keyword_scores(vols)[0]
        assert result.keywords[0].name == "digital"  # actual match text

    def test_matched_keyword_score_value(self):
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        scores = {kw.name: kw.score for kw in result.keywords}
        assert scores["Digital"] == 10.0
        assert scores["[Group]"] == 3.0

    def test_matched_keyword_default_file_type_both(self):
        # Keyword objects appended to .keywords are constructed as
        # Keyword(search.group(), keyword.score) — 2-arg form → file_type='both'.
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        for kw in result.keywords:
            assert kw.file_type == "both"

    def test_non_matching_keyword_contributes_zero(self):
        _set_keywords(Keyword(r"Nonexistent", 10.0, "both"))
        vols = _build_vols("Some Name v01 (2021) (Digital) [Group].cbz")
        result = kce.get_keyword_scores(vols)[0]
        assert result.total_score == 0.0
        assert result.keywords == []

    def test_multiple_releases_scored_independently(self):
        vols = _build_vols(
            "Some Name v01 (2021) (Digital).cbz",
            "Some Name v01 (2021) (Webrip).cbz",
        )
        results = kce.get_keyword_scores(vols)
        assert len(results) == 2
        # Digital matches first, Webrip matches second
        assert results[0].total_score == 10.0
        assert results[1].total_score == 3.0
        assert results[0] is not results[1]

    def test_file_type_volume_only_keyword_skipped_for_chapter(self):
        # A keyword with file_type='volume' must NOT be applied to chapter files.
        _set_keywords(
            Keyword(r"Digital", 10.0, "both"),
            Keyword(r"Premium", 5.0, "volume"),
        )
        ch_vols = _build_vols("Some Name Chapter 001 (Digital) (Premium).cbz")
        assert ch_vols[0].file_type == "chapter"
        result = kce.get_keyword_scores(ch_vols)[0]
        # Only the 'both' keyword should match
        assert result.total_score == 10.0
        assert len(result.keywords) == 1
        assert result.keywords[0].name == "Digital"

    def test_file_type_chapter_only_keyword_skipped_for_volume(self):
        # A keyword with file_type='chapter' must NOT be applied to volume files.
        _set_keywords(
            Keyword(r"Premium", 5.0, "volume"),
            Keyword(r"Digital", 10.0, "chapter"),
        )
        vol_vols = _build_vols("Some Name v01 (Digital) (Premium).cbz")
        assert vol_vols[0].file_type == "volume"
        result = kce.get_keyword_scores(vol_vols)[0]
        # Only 'volume' keyword applies
        assert result.total_score == 5.0
        assert len(result.keywords) == 1
        assert result.keywords[0].name == "Premium"

    def test_file_type_both_applies_to_volume(self):
        _set_keywords(Keyword(r"Digital", 10.0, "both"))
        vol_vols = _build_vols("Some Name v01 (Digital).cbz")
        assert vol_vols[0].file_type == "volume"
        result = kce.get_keyword_scores(vol_vols)[0]
        assert result.total_score == 10.0

    def test_file_type_both_applies_to_chapter(self):
        _set_keywords(Keyword(r"Digital", 10.0, "both"))
        ch_vols = _build_vols("Some Name Chapter 001 (Digital).cbz")
        assert ch_vols[0].file_type == "chapter"
        result = kce.get_keyword_scores(ch_vols)[0]
        assert result.total_score == 10.0


# ===========================================================================
# is_upgradeable — FLAG: identical names share results[0]
# ===========================================================================

class TestIsUpgradeableSameName:
    """
    FLAG: when downloaded_release.name == current_release.name, the code calls
    get_keyword_scores([downloaded_release]) and assigns results[0] to BOTH
    downloaded_release_result and current_release_result.

    Consequence: even if the single file theoretically "scores higher than itself",
    the comparison is always False (score > score is False) and the two result
    objects are literally the same Python object.
    """

    def setup_method(self):
        _set_keywords(Keyword(r"Digital", 10.0, "both"))

    def test_same_file_object_never_upgradeable(self):
        vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        vol = vols[0]
        result = kce.is_upgradeable(vol, vol)
        assert result.is_upgrade is False

    def test_same_name_different_instances_never_upgradeable(self):
        # Two distinct Volume objects but identical .name strings
        vols1 = _build_vols("Some Name v01 (2021) (Digital).cbz")
        vols2 = _build_vols("Some Name v01 (2021) (Digital).cbz")
        dl, curr = vols1[0], vols2[0]
        assert dl is not curr          # different objects
        assert dl.name == curr.name    # but identical names
        result = kce.is_upgradeable(dl, curr)
        # FLAG: identical names → only 1 call to get_keyword_scores → results[0] shared
        assert result.is_upgrade is False

    def test_same_name_result_objects_are_identical(self):
        """The FLAG: downloaded_ranked_result IS current_ranked_result (same object)."""
        vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        result = kce.is_upgradeable(vols[0], vols[0])
        # Both fields point to the same RankedKeywordResult object
        assert result.downloaded_ranked_result is result.current_ranked_result

    def test_same_name_scores_both_equal(self):
        vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        result = kce.is_upgradeable(vols[0], vols[0])
        dl_score = result.downloaded_ranked_result.total_score
        curr_score = result.current_ranked_result.total_score
        assert dl_score == curr_score
        assert dl_score == 10.0


# ===========================================================================
# is_upgradeable — different names
# ===========================================================================

class TestIsUpgradeableDifferentNames:
    """When names differ, get_keyword_scores is called with both releases."""

    def setup_method(self):
        _set_keywords(
            Keyword(r"Digital", 10.0, "both"),
            Keyword(r"Webrip", 3.0, "both"),
        )

    def test_higher_score_downloaded_is_upgrade(self):
        dl_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        curr_vols = _build_vols("Some Name v01 (2021) (Webrip).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        assert result.is_upgrade is True
        assert result.downloaded_ranked_result.total_score == 10.0
        assert result.current_ranked_result.total_score == 3.0

    def test_lower_score_downloaded_is_not_upgrade(self):
        dl_vols = _build_vols("Some Name v01 (2021) (Webrip).cbz")
        curr_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        assert result.is_upgrade is False
        assert result.downloaded_ranked_result.total_score == 3.0
        assert result.current_ranked_result.total_score == 10.0

    def test_equal_scores_different_names_is_not_upgrade(self):
        # Both score 10.0 — equal is NOT an upgrade (strict >)
        _set_keywords(
            Keyword(r"Digital", 10.0, "both"),
            Keyword(r"Webrip", 10.0, "both"),
        )
        dl_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        curr_vols = _build_vols("Some Name v01 (2021) (Webrip).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        assert result.is_upgrade is False

    def test_result_objects_are_different_when_names_differ(self):
        dl_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        curr_vols = _build_vols("Some Name v01 (2021) (Webrip).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        assert result.downloaded_ranked_result is not result.current_ranked_result

    def test_return_type_is_UpgradeResult(self):
        dl_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        curr_vols = _build_vols("Some Name v01 (2021) (Webrip).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        assert isinstance(result, kce.UpgradeResult)
        assert isinstance(result.is_upgrade, bool)
        assert isinstance(result.downloaded_ranked_result, kce.RankedKeywordResult)
        assert isinstance(result.current_ranked_result, kce.RankedKeywordResult)

    def test_downloaded_keywords_list_correct(self):
        dl_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        curr_vols = _build_vols("Some Name v01 (2021) (Webrip).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        dl_kw_names = [kw.name for kw in result.downloaded_ranked_result.keywords]
        curr_kw_names = [kw.name for kw in result.current_ranked_result.keywords]
        assert "Digital" in dl_kw_names
        assert "Webrip" in curr_kw_names

    def test_zero_vs_nonzero_is_upgrade(self):
        # Downloaded file matches nothing (score 0) vs current matches Digital (score 10)
        dl_vols = _build_vols("Some Name v01 (2021).cbz")
        curr_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        assert result.is_upgrade is False
        assert result.downloaded_ranked_result.total_score == 0.0
        assert result.current_ranked_result.total_score == 10.0

    def test_nonzero_vs_zero_is_upgrade(self):
        # Downloaded matches Digital (10), current matches nothing (0) → upgrade
        dl_vols = _build_vols("Some Name v01 (2021) (Digital).cbz")
        curr_vols = _build_vols("Some Name v01 (2021).cbz")
        result = kce.is_upgradeable(dl_vols[0], curr_vols[0])
        assert result.is_upgrade is True
        assert result.downloaded_ranked_result.total_score == 10.0
        assert result.current_ranked_result.total_score == 0.0


# ===========================================================================
# get_highest_release
# ===========================================================================

class TestGetHighestRelease:
    """Pin get_highest_release behaviour under various conditions.

    The function is gated on kce.use_latest_volume_cover_as_series_cover
    (defaults False → always returns '').  When True, it finds the max
    numeric index from a tuple of releases.
    """

    def test_toggle_off_returns_empty_string_regardless_of_input(self):
        # Default: use_latest_volume_cover_as_series_cover = False
        assert kce.use_latest_volume_cover_as_series_cover is False
        result = kce.get_highest_release((1, 2, 3), is_chapter_directory=False)
        assert result == ""
        assert isinstance(result, str)

    def test_toggle_off_chapter_directory_returns_empty_string(self):
        result = kce.get_highest_release((1, 2, 3), is_chapter_directory=True)
        assert result == ""
        assert isinstance(result, str)

    def test_toggle_on_simple_ints_returns_max(self):
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release((1, 2, 3), is_chapter_directory=False)
        assert result == 3
        assert isinstance(result, int)

    def test_toggle_on_chapter_directory_returns_empty_string(self):
        # is_chapter_directory=True bypasses the volume logic → always ''
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release((1, 2, 3), is_chapter_directory=True)
        assert result == ""
        assert isinstance(result, str)

    def test_toggle_on_floats_returns_max_float(self):
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release((1.5, 2.0, 0.5), is_chapter_directory=False)
        assert result == 2.0
        assert isinstance(result, float)

    def test_toggle_on_with_empty_string_items_skips_them(self):
        # '' items are skipped; max of remaining numeric values returned
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release((1, "", 3), is_chapter_directory=False)
        assert result == 3
        assert isinstance(result, int)

    def test_toggle_on_all_empty_or_none_returns_empty_string(self):
        # All items are '' or None → highest_num stays '' (initial value)
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release(("", "", None), is_chapter_directory=False)
        assert result == ""
        assert isinstance(result, str)

    def test_toggle_on_tuple_items_max_of_each_tuple(self):
        # Tuple items (multi-volume) → use max() of each tuple item
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release(((1, 2), (3, 4)), is_chapter_directory=False)
        assert result == 4
        assert isinstance(result, int)

    def test_toggle_on_mixed_int_and_tuple_items(self):
        # contains_empty_or_tuple_index_number is True → uses the scanning loop
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release(((1, 3), 5), is_chapter_directory=False)
        assert result == 5
        assert isinstance(result, int)

    def test_toggle_on_empty_tuple_raises_ValueError(self):
        """FLAG: max() on empty tuple raises ValueError — no guard exists."""
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        with pytest.raises(ValueError, match="max\\(\\) iterable argument is empty"):
            kce.get_highest_release((), is_chapter_directory=False)

    def test_is_lru_cached(self):
        assert hasattr(kce.get_highest_release, "cache_clear")
        assert hasattr(kce.get_highest_release, "cache_info")

    def test_lru_cache_maxsize_is_3500(self):
        info = kce.get_highest_release.cache_info()
        assert info.maxsize == 3500

    def test_lru_cache_hit_on_repeated_call(self):
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        kce.get_highest_release((1, 2, 3), is_chapter_directory=False)
        kce.get_highest_release((1, 2, 3), is_chapter_directory=False)
        info = kce.get_highest_release.cache_info()
        assert info.hits >= 1
