"""Characterization tests for ``kce.get_series_name_from_volume`` and
``kce.get_series_name_from_chapter``.

Both functions extract a bare series name from a filename.  All expected values
were verified against the live interpreter before being written here.

Signatures (verified via Serena + inspect):
    get_series_name_from_volume(name, root, test_mode=False, second=False) -> str
        @lru_cache(maxsize=3500)
        test_mode=True prevents is_one_shot from hitting the filesystem.

    get_series_name_from_chapter(name, root, chapter_number='', second=False) -> str
        No lru_cache; no test_mode param.
        Falls back to os.path.basename(root) when the extracted series is empty
        (and second=False, and root is not in download_folders/paths).
"""

from __future__ import annotations

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Aliases to keep call-sites tidy
# ---------------------------------------------------------------------------

def gsnfv(name: str, root: str = "/tmp/nope", *, test_mode: bool = True) -> str:
    """Thin wrapper around get_series_name_from_volume."""
    return kce.get_series_name_from_volume(name, root, test_mode=test_mode)


def gsnfc(name: str, root: str = "/tmp/nope", chapter_number: str = "") -> str:
    """Thin wrapper around get_series_name_from_chapter."""
    return kce.get_series_name_from_chapter(name, root, chapter_number)


# ===========================================================================
# get_series_name_from_volume
# ===========================================================================


class TestGetSeriesNameFromVolume:
    """Pin the exact series string extracted from volume filenames."""

    # --- standard volume keyword variants ---

    def test_volume_v_prefix_with_year_and_digital_tag(self):
        """``v01 (2021) (Digital)`` → series name before the volume marker."""
        assert gsnfv("Sword Art Online v01 (2021) (Digital).cbz") == "Sword Art Online"

    def test_volume_keyword_long_form(self):
        """``Volume 10`` (long-form keyword) → bare series name."""
        assert gsnfv("My Hero Academia Volume 10.cbz") == "My Hero Academia"

    def test_volume_vol_dotted(self):
        """``Vol. 1`` dotted abbreviation is recognised."""
        assert gsnfv("Death Note Vol. 1.cbz") == "Death Note"

    def test_volume_with_group_tag_and_year(self):
        """Group tag and year in brackets are stripped after the volume number."""
        assert gsnfv("Fullmetal Alchemist v01 [Group] (2003).cbz") == "Fullmetal Alchemist"

    def test_volume_with_complete_tag_in_brackets(self):
        """``[Complete]`` bracket tag after volume number is stripped normally."""
        assert gsnfv("Dragon Ball Z Volume 01 [Complete] (2021).cbz") == "Dragon Ball Z"

    # --- "Complete" suffix stripping ---

    def test_complete_suffix_stripped_with_dash(self):
        """``- Complete`` after series name is stripped (dash form)."""
        assert gsnfv("Attack on Titan - Complete v01.cbz") == "Attack on Titan"

    def test_complete_suffix_stripped_no_volume_number(self):
        """``- Complete.epub`` with no volume number — series still extracted."""
        assert gsnfv("Series Name - Complete.epub") == "Series Name"

    def test_complete_suffix_stripped_with_colon(self):
        """``My Series: Complete v01.cbz`` — colon form of Complete stripped."""
        assert gsnfv("My Series: Complete v01.cbz") == "My Series"

    def test_complete_suffix_stripped_with_premium_bracket(self):
        """Full pattern ``- Complete v01 [Premium]`` → bare series name."""
        assert gsnfv("Series Name - Complete v01 [Premium].epub") == "Series Name"

    def test_complete_no_dash_not_stripped(self):
        """``Complete`` without a preceding dash/colon is NOT stripped.

        FLAG: the regex ``(-|:)\\s*Complete$`` requires a dash or colon before
        'Complete', so "One Piece Complete.cbz" retains the word in its result.
        In this particular file the whole name is returned because is_one_shot
        detects it as a one-shot (no volume number) and keeps the base name.
        """
        assert gsnfv("One Piece Complete.cbz") == "One Piece Complete"

    # --- [WN] / leading-bracket tag stripping ---

    def test_wn_leading_bracket_stripped_from_volume(self):
        """``[WN]`` prefix is stripped before the series name is extracted."""
        assert gsnfv("[WN] My Series v01.cbz") == "My Series"

    def test_wn_leading_bracket_stripped_sword_art(self):
        """``[WN]`` prefix stripping works with multi-word series name."""
        assert gsnfv("[WN] Sword Art Online v01.cbz") == "Sword Art Online"

    # --- One-shot passthrough ---

    def test_one_shot_bare_filename_passthrough(self):
        """A file with no volume number is detected as one-shot; name preserved.

        ``Series Name.cbz`` has no volume keyword so ``is_one_shot`` returns
        True (test_mode skips disk lookup).  The one-shot branch strips
        brackets/extension and returns the base series name unchanged.
        """
        assert gsnfv("Series Name.cbz") == "Series Name"

    def test_one_shot_with_year_bracket_stripped(self):
        """One-shot file with a year bracket → year bracket is stripped."""
        assert gsnfv("My Series [2021].cbz") == "My Series"

    def test_one_shot_with_group_bracket_stripped(self):
        """One-shot file with a group/release tag bracket → bracket stripped."""
        assert gsnfv("My Oneshot [Group] (2021).cbz") == "My Oneshot"

    def test_one_shot_string_in_name_space_separated_kept(self):
        """Space-separated ``One Shot`` is NOT matched by the one-shot strip regex.

        FLAG: the strip regex ``(-\\s*)Ones?(-|)shot\\s*`` requires 'One' followed
        directly by an optional dash then 'shot' (no space).  So "Story - One Shot"
        passes through the strip step unchanged.  The file IS detected as a one-shot
        by is_one_shot and the full name (minus extension) is returned.
        """
        assert gsnfv("Story - One Shot.cbz") == "Story - One Shot"

    def test_one_shot_hyphenated_stripped(self):
        """``- One-shot`` (hyphenated) IS matched by the strip regex → stripped."""
        assert gsnfv("Story - One-shot.cbz") == "Story"

    def test_one_shot_camelcase_stripped(self):
        """``- Oneshot`` (no separator) IS matched by the strip regex → stripped."""
        assert gsnfv("Story - Oneshot.cbz") == "Story"

    # --- Trailing-comma removal ---

    def test_trailing_comma_removed(self):
        """A trailing comma before the volume keyword is removed from the result.

        E.g. ``Berserk, v01.cbz``.  The volume regex absorbs everything from
        ``, v01`` onward; the bare 'Berserk,' is then cleaned to 'Berserk'.
        """
        assert gsnfv("Berserk, v01.cbz") == "Berserk"

    def test_trailing_comma_with_volume_word(self):
        """Trailing comma also cleaned when the ``Volume`` keyword form is used."""
        assert gsnfv("Series, Volume 1.cbz") == "Series"

    # --- Underscore replacement ---

    def test_underscores_replaced_by_spaces(self):
        """Underscores in the series name portion are replaced with spaces."""
        assert gsnfv("My_Series v01.cbz") == "My Series"

    # --- _extra handling (half-volume artefact) ---

    def test_extra_suffix_replaced_with_dot5(self):
        """``_extra`` is replaced with ``.5`` before further processing.

        E.g. ``Series_extra v01.cbz``:  the underscore in ``_extra`` is replaced
        first (``_extra`` → ``.5``), yielding ``Series.5 v01.cbz``, then the
        volume keyword strips everything from ``v01`` onward → ``'Series.5'``.
        """
        assert gsnfv("Series_extra v01.cbz") == "Series.5"

    def test_extra_in_extensionless_name(self):
        """``_extra`` at the end of a one-shot name → trailing ``.`` preserved.

        FLAG: ``Series Name_extra.cbz`` → ``_extra`` → ``.5`` in the middle of
        name then is_one_shot branch processes it.  Result ends with a period,
        which is a minor formatting quirk pinned as-is.
        """
        result = gsnfv("Series Name_extra.cbz")
        assert result == "Series Name."


# ===========================================================================
# get_series_name_from_chapter
# ===========================================================================


class TestGetSeriesNameFromChapter:
    """Pin the exact series string extracted from chapter filenames.

    Note: get_series_name_from_chapter has NO test_mode param and NO lru_cache.
    When the extracted series is empty (and second=False), it falls back to
    os.path.basename(root) processed through another call to itself.
    """

    # --- standard chapter keyword variants ---

    def test_chapter_c_prefix(self):
        """``c001`` chapter prefix → series name before the chapter marker."""
        assert gsnfc("Series c001.cbz") == "Series"

    def test_chapter_c_prefix_multiword(self):
        """Multi-word series with ``c010`` chapter prefix."""
        assert gsnfc("My Series c010.cbz") == "My Series"

    def test_chapter_chapter_keyword(self):
        """Long-form ``Chapter 001`` keyword → series name extracted."""
        assert gsnfc("My Series Chapter 001.cbz") == "My Series"

    def test_chapter_ch_dotted(self):
        """``Ch. 5`` dotted abbreviation → series name extracted."""
        assert gsnfc("My Series - Ch. 5.cbz") == "My Series"

    def test_chapter_ch_prefix_no_dot(self):
        """``ch001`` without dot is also a recognised chapter marker."""
        assert gsnfc("My Series - ch001.cbz") == "My Series"

    def test_chapter_c_prefix_tokyo_ghoul(self):
        """Single-word series with c-prefix chapter."""
        assert gsnfc("TokyoGhoul c001.cbz") == "TokyoGhoul"

    # --- [WN] / leading-bracket tag stripping ---

    def test_wn_leading_bracket_stripped_from_chapter(self):
        """``[WN]`` prefix is stripped in the chapter path too."""
        assert gsnfc("[WN] My Series c001.cbz") == "My Series"

    # --- root fallback when series is empty ---

    def test_bare_chapter_number_falls_back_to_root(self):
        """A bare chapter number with no series prefix yields empty series.

        FLAG: when the extracted series name is empty, the function falls back
        to ``os.path.basename(root)`` (processed via a recursive call with
        ``second=True``).  So ``'010.cbz'`` with root ``'/tmp/nope'`` returns
        the basename ``'nope'``, not an empty string.
        """
        assert gsnfc("010.cbz", root="/tmp/nope") == "nope"

    def test_bare_chapter_number_different_root(self):
        """Root fallback uses the actual basename of whatever root is passed."""
        assert gsnfc("010.cbz", root="/tmp/my_series") == "my series"

    def test_bare_chapter_number_second_true_returns_empty(self):
        """With ``second=True`` the root fallback is suppressed → empty string."""
        result = kce.get_series_name_from_chapter("010.cbz", "/tmp/nope", "", second=True)
        assert result == ""

    # --- chapter_number param does not change the series extraction ---

    def test_chapter_number_param_does_not_affect_series(self):
        """Providing an explicit chapter_number does not change the series result."""
        assert gsnfc("Series c001.cbz", chapter_number="1") == "Series"

    # --- _extra suffix in chapter names ---

    def test_extra_suffix_in_chapter_name(self):
        """``_extra`` between series and chapter marker: ``_extra`` → ``.5``."""
        assert gsnfc("Series_extra c001.cbz") == "Series.5"

    # --- unrecognised chapter-like patterns are NOT stripped ---

    def test_hash_chapter_number_not_stripped(self):
        """``#010`` is NOT in the chapter search patterns → name is NOT split.

        FLAG: ``My Series #010.cbz`` is returned as-is (minus the extension)
        because none of the compiled chapter_search_patterns_comp match ``#010``.
        """
        assert gsnfc("My Series #010.cbz") == "My Series #010"

    def test_bare_number_dash_form_not_stripped(self):
        """``- 010`` dash+number pattern is not a recognised chapter marker.

        FLAG: ``My Series - 010.cbz`` is not split; the full name minus
        extension is returned.
        """
        assert gsnfc("My Series - 010.cbz") == "My Series - 010"
