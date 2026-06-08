"""Characterization tests for get_sort_key-based sorting and organize_by_first_letter.

Every assertion was verified against the live module BEFORE writing:
    .venv/bin/python -c "import komga_cover_extractor as kce; print(repr(kce.FUNC(ARGS)))"

Surprising / buggy behavior is noted with a ``# FLAG:`` comment and pinned AS-IS.

Functions covered (all from komga_cover_extractor.py):
    get_sort_key, sort_volumes, organize_by_first_letter

Volume objects are built using the production pipeline:
    upgrade_to_file_class(..., test_mode=True) + upgrade_to_volume_class(..., test_mode=True)
These functions are called with real .cbz files written under tmp_path; test_mode=True
skips the file-header read and forces skip_release_year / skip_publisher / skip_premium_content.
"""

from __future__ import annotations

import io
import os
import sys
import zipfile

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cbz(directory: str, name: str) -> str:
    """Write a minimal zip under *directory* and return just the filename."""
    path = os.path.join(directory, name)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("page_001.jpg", b"\xff\xd8\xff\xd9")  # tiny JPEG stub
    return name


def _build_volumes(tmp_path, filenames):
    """Return list of kce.Volume objects built from *filenames* in *tmp_path*."""
    d = str(tmp_path)
    for name in filenames:
        path = os.path.join(d, name)
        if not os.path.exists(path):
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("page_001.jpg", b"\xff\xd8\xff\xd9")
    files = kce.upgrade_to_file_class(list(filenames), d, test_mode=True)
    return kce.upgrade_to_volume_class(files, test_mode=True)


# ===========================================================================
# get_sort_key — raw scalar / list inputs
# ===========================================================================

class TestGetSortKeyScalars:
    """get_sort_key returns the input unchanged when it is not a list."""

    def test_int_1(self):
        result = kce.get_sort_key(1)
        assert result == 1
        assert isinstance(result, int)

    def test_int_2(self):
        result = kce.get_sort_key(2)
        assert result == 2

    def test_int_10(self):
        result = kce.get_sort_key(10)
        assert result == 10

    def test_float_1_5(self):
        result = kce.get_sort_key(1.5)
        assert result == 1.5
        assert isinstance(result, float)

    def test_int_zero(self):
        assert kce.get_sort_key(0) == 0

    def test_negative_int(self):
        assert kce.get_sort_key(-1) == -1

    def test_empty_string_passthrough(self):
        # FLAG: empty-string index_number passes through unchanged — calling code
        # must guard against comparing '' with numbers in sort contexts.
        result = kce.get_sort_key("")
        assert result == ""
        assert isinstance(result, str)

    def test_numeric_string_passthrough(self):
        # Strings are NOT parsed to numbers; '1' -> '1'
        result = kce.get_sort_key("1")
        assert result == "1"
        assert isinstance(result, str)


class TestGetSortKeyList:
    """get_sort_key returns min(list) when the input is a list (multi-volume)."""

    def test_ascending_list_returns_first(self):
        # [1, 2] -> min is 1
        result = kce.get_sort_key([1, 2])
        assert result == 1

    def test_descending_list_returns_min(self):
        # [5, 2] -> min is 2 (not first element)
        result = kce.get_sort_key([5, 2])
        assert result == 2

    def test_unsorted_list_returns_min(self):
        # [10, 1] -> min is 1
        result = kce.get_sort_key([10, 1])
        assert result == 1

    def test_equal_elements_list(self):
        result = kce.get_sort_key([3, 3])
        assert result == 3

    def test_three_element_list_returns_min(self):
        result = kce.get_sort_key([2, 5, 8])
        assert result == 2

    def test_single_element_list(self):
        result = kce.get_sort_key([7])
        assert result == 7


# ===========================================================================
# Volume index_number assignment — via upgrade pipeline (test_mode=True)
# ===========================================================================

class TestVolumeIndexNumbers:
    """Verify that the upgrade pipeline sets index_number correctly on Volumes."""

    def test_v01_index_is_int_1(self, tmp_path):
        vols = _build_volumes(tmp_path, ["Series v01.cbz"])
        assert vols[0].index_number == 1
        assert isinstance(vols[0].index_number, int)

    def test_v02_index_is_int_2(self, tmp_path):
        vols = _build_volumes(tmp_path, ["Series v02.cbz"])
        assert vols[0].index_number == 2

    def test_v10_index_is_int_10(self, tmp_path):
        vols = _build_volumes(tmp_path, ["Series v10.cbz"])
        assert vols[0].index_number == 10

    def test_v01_5_index_is_float_1_5(self, tmp_path):
        vols = _build_volumes(tmp_path, ["Series v01.5.cbz"])
        assert vols[0].index_number == 1.5
        assert isinstance(vols[0].index_number, float)

    def test_multi_volume_index_is_list(self, tmp_path):
        vols = _build_volumes(tmp_path, ["Series v01-02.cbz"])
        assert vols[0].index_number == [1, 2]
        assert isinstance(vols[0].index_number, list)

    def test_multi_volume_v05_06_index_is_list(self, tmp_path):
        vols = _build_volumes(tmp_path, ["Series v05-06.cbz"])
        assert vols[0].index_number == [5, 6]


# ===========================================================================
# sort_volumes — numeric ordering
# ===========================================================================

class TestSortVolumesNumeric:
    """sort_volumes uses get_sort_key(index_number) for all-numeric index sets."""

    def test_natural_numeric_order(self, tmp_path):
        # v01, v02, v10 in forward order
        vols = _build_volumes(tmp_path, ["Series v01.cbz", "Series v02.cbz", "Series v10.cbz"])
        result = kce.sort_volumes(vols)
        assert [v.name for v in result] == [
            "Series v01.cbz",
            "Series v02.cbz",
            "Series v10.cbz",
        ]

    def test_reverse_input_still_numeric_order(self, tmp_path):
        # Providing reverse order input must yield ascending numeric output
        vols = _build_volumes(tmp_path, ["Series v10.cbz", "Series v02.cbz", "Series v01.cbz"])
        result = kce.sort_volumes(vols)
        assert [v.name for v in result] == [
            "Series v01.cbz",
            "Series v02.cbz",
            "Series v10.cbz",
        ]

    def test_fractional_volume_sorted_between_integers(self, tmp_path):
        # v01.5 should land between v01 and v02
        vols = _build_volumes(
            tmp_path,
            ["Series v02.cbz", "Series v01.5.cbz", "Series v01.cbz"],
        )
        result = kce.sort_volumes(vols)
        assert [v.name for v in result] == [
            "Series v01.cbz",
            "Series v01.5.cbz",
            "Series v02.cbz",
        ]

    def test_multi_volume_sorted_by_min_index(self, tmp_path):
        # v01-02 has min=1, v03 has index=3; so v01-02 comes first
        vols = _build_volumes(tmp_path, ["Series v03.cbz", "Series v01-02.cbz"])
        result = kce.sort_volumes(vols)
        assert result[0].name == "Series v01-02.cbz"
        assert result[1].name == "Series v03.cbz"

    def test_mixed_single_and_multi_volume(self, tmp_path):
        # v01-02 (min=1), v01 (index=1), v03 (index=3), v05-06 (min=5)
        vols = _build_volumes(
            tmp_path,
            ["Series v05-06.cbz", "Series v01.cbz", "Series v03.cbz", "Series v01-02.cbz"],
        )
        result = kce.sort_volumes(vols)
        names = [v.name for v in result]
        # v01.cbz and v01-02.cbz both have sort_key=1; v03 has 3; v05-06 has 5
        assert names.index("Series v03.cbz") > names.index("Series v01.cbz")
        assert names.index("Series v05-06.cbz") > names.index("Series v03.cbz")

    def test_empty_list_returns_empty(self):
        result = kce.sort_volumes([])
        assert result == []

    def test_single_volume_list_unchanged(self, tmp_path):
        vols = _build_volumes(tmp_path, ["Series v07.cbz"])
        result = kce.sort_volumes(vols)
        assert len(result) == 1
        assert result[0].name == "Series v07.cbz"


class TestSortVolumesAlphabetic:
    """sort_volumes falls back to alphabetical-by-name when any index is a string."""

    def test_string_index_sorts_alphabetically_by_name(self):
        # Directly construct Volumes with string index_numbers to trigger the
        # alphabetic branch (any(isinstance(item.index_number, str) for item in volumes))
        def _make_vol(name, index_str):
            return kce.Volume(
                "volume", name, name, None,
                "", "", index_str, "",
                name, name, name, ".cbz",
                "/tmp", f"/tmp/{name}", f"/tmp/{name}",
                [], "", False, None, None,
            )

        vol_z = _make_vol("Z Series.cbz", " ")
        vol_a = _make_vol("A Series.cbz", " ")
        vol_m = _make_vol("M Series.cbz", " ")

        result = kce.sort_volumes([vol_z, vol_m, vol_a])
        assert [v.name for v in result] == ["A Series.cbz", "M Series.cbz", "Z Series.cbz"]

    def test_one_string_index_triggers_alphabetic_branch(self):
        # If even ONE volume has a string index, the whole list is sorted by name.
        def _make_vol(name, index):
            return kce.Volume(
                "volume", name, name, None,
                "", "", index, "",
                name, name, name, ".cbz",
                "/tmp", f"/tmp/{name}", f"/tmp/{name}",
                [], "", False, None, None,
            )

        vol_num = _make_vol("Z Volume.cbz", 1)      # numeric index
        vol_str = _make_vol("A Volume.cbz", " ")     # string index

        result = kce.sort_volumes([vol_num, vol_str])
        # alphabetical: 'A Volume.cbz' < 'Z Volume.cbz'
        assert [v.name for v in result] == ["A Volume.cbz", "Z Volume.cbz"]


# ===========================================================================
# organize_by_first_letter — complementary cases to the legacy suite
# ===========================================================================

class TestOrganizeByFirstLetterReturnType:
    """The function always returns a list (new object, not the input)."""

    def test_returns_a_list(self, tmp_path):
        a = str(tmp_path / "alpha")
        os.makedirs(a)
        result = kce.organize_by_first_letter([a], "a", 0, silent=True)
        assert isinstance(result, list)

    def test_result_is_not_same_object_as_input(self, tmp_path):
        a = str(tmp_path / "apple")
        b = str(tmp_path / "banana")
        os.makedirs(a); os.makedirs(b)
        lst = [a, b]
        result = kce.organize_by_first_letter(lst, "a", 0, silent=True)
        # FLAG: the function rebinds the local `array_list` var (list-comprehension),
        # so the returned list is a NEW object even when items_to_move is non-empty.
        assert result is not lst

    def test_input_list_not_mutated(self, tmp_path):
        a = str(tmp_path / "apple")
        b = str(tmp_path / "banana")
        c = str(tmp_path / "cherry")
        os.makedirs(a); os.makedirs(b); os.makedirs(c)
        original = [a, b, c]
        original_copy = list(original)
        kce.organize_by_first_letter(original, "a", 1, silent=True)
        assert original == original_copy  # input is NOT mutated


class TestOrganizeByFirstLetterEmptyString:
    """Empty *string* triggers early return of the input list unchanged."""

    def test_empty_string_returns_input_unchanged(self, tmp_path):
        a = str(tmp_path / "alpha")
        b = str(tmp_path / "beta")
        c = str(tmp_path / "cherry")
        os.makedirs(a); os.makedirs(b); os.makedirs(c)
        lst = [a, b, c]
        result = kce.organize_by_first_letter(lst, "", 1, silent=True)
        assert result == lst

    def test_empty_string_silent_false_prints_message(self, tmp_path):
        a = str(tmp_path / "alpha")
        os.makedirs(a)
        buf = io.StringIO()
        sys.stdout = buf
        try:
            kce.organize_by_first_letter([a], "", 0, silent=False)
        finally:
            sys.stdout = sys.__stdout__
        output = buf.getvalue()
        assert "First letter of file name was not found" in output


class TestOrganizeByFirstLetterOutOfBounds:
    """Out-of-bounds *position_to_insert_at* causes early return of unchanged list."""

    def test_position_too_large_returns_unchanged(self, tmp_path):
        a = str(tmp_path / "alpha")
        b = str(tmp_path / "beta")
        os.makedirs(a); os.makedirs(b)
        lst = [a, b]
        result = kce.organize_by_first_letter(lst, "a", 10, silent=True)
        assert result == lst

    def test_negative_position_returns_unchanged(self, tmp_path):
        a = str(tmp_path / "alpha")
        b = str(tmp_path / "beta")
        os.makedirs(a); os.makedirs(b)
        lst = [a, b]
        result = kce.organize_by_first_letter(lst, "a", -1, silent=True)
        assert result == lst


class TestOrganizeByFirstLetterMovement:
    """Core reordering: matching items get inserted at *position_to_insert_at*."""

    def test_single_match_moved_to_position(self, tmp_path):
        # ['alpha_series','beta_series','alpha_other','gamma_series']
        # string='a', pos=2 -> alpha_series and alpha_other are 'a'-prefixed.
        # The item at pos=2 is 'alpha_other', which is excluded from moves
        # (it's array_list[position_to_insert_at]).
        # alpha_series matches and is NOT the reference item -> moved.
        # After removal: [beta_series, alpha_other, gamma_series]
        # Insert alpha_series at pos 2: [beta_series, alpha_other, alpha_series, gamma_series]
        # — but the test below just verifies the observed exact result.
        d = [
            str(tmp_path / n)
            for n in ["alpha_series", "beta_series", "alpha_other", "gamma_series"]
        ]
        for p in d:
            os.makedirs(p)
        result = kce.organize_by_first_letter(list(d), "alpha_new", 2, silent=True)
        assert [os.path.basename(p) for p in result] == [
            "beta_series",
            "alpha_other",
            "alpha_series",
            "gamma_series",
        ]

    def test_match_moved_to_position_0(self, tmp_path):
        # string='a', pos=0 -> item at pos 0 is 'alpha_series' (skipped as reference)
        # alpha_other matches 'a' and is not the reference -> moved to pos 0
        # After removal: [alpha_series, beta_series, gamma_series]
        # Insert alpha_other at 0: [alpha_other, alpha_series, beta_series, gamma_series]
        d = [
            str(tmp_path / n)
            for n in ["alpha_series", "beta_series", "alpha_other", "gamma_series"]
        ]
        for p in d:
            os.makedirs(p)
        result = kce.organize_by_first_letter(list(d), "alpha_new", 0, silent=True)
        assert [os.path.basename(p) for p in result] == [
            "alpha_other",
            "alpha_series",
            "beta_series",
            "gamma_series",
        ]

    def test_match_moved_to_last_valid_position(self, tmp_path):
        # string='a', pos=2 (last valid for 3-item list)
        d = [
            str(tmp_path / n)
            for n in ["alpha_series", "beta_series", "alpha_other"]
        ]
        for p in d:
            os.makedirs(p)
        result = kce.organize_by_first_letter(list(d), "alpha_new", 2, silent=True)
        # item at pos 2 = alpha_other (skipped); alpha_series moves
        assert [os.path.basename(p) for p in result] == [
            "beta_series",
            "alpha_other",
            "alpha_series",
        ]

    def test_no_match_returns_unchanged(self, tmp_path):
        d = [
            str(tmp_path / n)
            for n in ["alpha_series", "beta_series", "cherry"]
        ]
        for p in d:
            os.makedirs(p)
        original = list(d)
        result = kce.organize_by_first_letter(list(d), "d_new", 1, silent=True)
        assert result == original

    def test_multiple_matching_items_inserted_in_iteration_order(self, tmp_path):
        # ['delta','alpha1','beta','alpha2','alpha3'], string='a', pos=2
        # item at pos=2 is 'beta' (reference), skipped
        # matches: alpha1, alpha2, alpha3 (in that iteration order)
        # after removal: [delta, beta]
        # insert alpha3 at 2: [delta, beta, alpha3]
        # insert alpha2 at 2: [delta, beta, alpha2, alpha3]
        # insert alpha1 at 2: [delta, beta, alpha1, alpha2, alpha3]
        d = [
            str(tmp_path / n)
            for n in ["delta", "alpha1", "beta", "alpha2", "alpha3"]
        ]
        for p in d:
            os.makedirs(p)
        result = kce.organize_by_first_letter(list(d), "a_new", 2, silent=True)
        assert [os.path.basename(p) for p in result] == [
            "delta",
            "beta",
            "alpha3",
            "alpha2",
            "alpha1",
        ]


class TestOrganizeByFirstLetterCaseInsensitive:
    """First-letter matching is case-insensitive (both string and item names)."""

    def test_uppercase_string_matches_lowercase_items(self, tmp_path):
        d = [
            str(tmp_path / n)
            for n in ["alpha_series", "beta_series", "alpha_other", "gamma_series"]
        ]
        for p in d:
            os.makedirs(p)
        # 'Alpha_new'[0].lower() == 'a' -> same result as lowercase 'a'
        result = kce.organize_by_first_letter(list(d), "Alpha_new", 0, silent=True)
        assert [os.path.basename(p) for p in result] == [
            "alpha_other",
            "alpha_series",
            "beta_series",
            "gamma_series",
        ]


class TestOrganizeByFirstLetterExclude:
    """The *exclude* parameter prevents that item from being moved."""

    def test_excluded_item_not_moved(self, tmp_path):
        d = [
            str(tmp_path / n)
            for n in ["alpha_series", "beta_series", "alpha_other", "gamma_series"]
        ]
        for p in d:
            os.makedirs(p)
        # Exclude alpha_series -> only alpha_other is a candidate (and not the pos=0 ref)
        # pos=0 ref = alpha_series itself (also skipped as reference)
        # So alpha_other is the only thing moved
        result = kce.organize_by_first_letter(list(d), "alpha_new", 0, exclude=d[0], silent=True)
        assert [os.path.basename(p) for p in result] == [
            "alpha_other",
            "alpha_series",
            "beta_series",
            "gamma_series",
        ]

    def test_exclude_none_does_not_exclude_anything(self, tmp_path):
        a = str(tmp_path / "apple")
        b = str(tmp_path / "banana")
        c = str(tmp_path / "cherry")
        os.makedirs(a); os.makedirs(b); os.makedirs(c)
        # 'cherry', pos=1 (banana is reference), no exclude
        result = kce.organize_by_first_letter([a, b, c], "c_new", 1, exclude=None, silent=True)
        assert [os.path.basename(p) for p in result] == ["apple", "cherry", "banana"]


class TestOrganizeByFirstLetterReferenceItemSkipped:
    """The item AT position_to_insert_at is skipped in the matching loop."""

    def test_reference_item_at_pos_0_not_moved(self, tmp_path):
        # cherry is at pos=0 and is the reference item; cherry2 matches but is moved
        d = [
            str(tmp_path / n)
            for n in ["cherry", "apple", "cherry2"]
        ]
        for p in d:
            os.makedirs(p)
        result = kce.organize_by_first_letter(list(d), "c_new", 0, exclude=None, silent=True)
        assert [os.path.basename(p) for p in result] == ["cherry2", "cherry", "apple"]

    def test_reference_item_at_pos_1_skipped(self, tmp_path):
        # cherry at pos=1 is reference; cherry2 at pos=2 gets moved to pos=1
        d = [
            str(tmp_path / n)
            for n in ["apple", "cherry", "cherry2", "delta"]
        ]
        for p in d:
            os.makedirs(p)
        result = kce.organize_by_first_letter(list(d), "c_new", 1, exclude=None, silent=True)
        assert [os.path.basename(p) for p in result] == [
            "apple",
            "cherry2",
            "cherry",
            "delta",
        ]

    def test_single_item_list_match_at_pos_0_unchanged(self, tmp_path):
        # Only item is the reference item -> items_to_move is empty -> unchanged
        a = str(tmp_path / "apple")
        os.makedirs(a)
        result = kce.organize_by_first_letter([a], "a_new", 0, silent=True)
        assert [os.path.basename(p) for p in result] == ["apple"]


class TestOrganizeByFirstLetterGammaCase:
    """Pin the 'g' first-letter case observed in experiments."""

    def test_gamma_series_moved_to_pos_1(self, tmp_path):
        # ['alpha_series','beta_series','alpha_other','gamma_series']
        # string='g', pos=1 -> item at pos=1 is 'beta_series' (reference, no match)
        # gamma_series matches 'g' -> moved
        d = [
            str(tmp_path / n)
            for n in ["alpha_series", "beta_series", "alpha_other", "gamma_series"]
        ]
        for p in d:
            os.makedirs(p)
        result = kce.organize_by_first_letter(list(d), "gamma_new", 1, silent=True)
        assert [os.path.basename(p) for p in result] == [
            "alpha_series",
            "gamma_series",
            "beta_series",
            "alpha_other",
        ]
