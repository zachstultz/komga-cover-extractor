"""Characterization tests for ``kce.get_extras``.

Signature (verified via Serena + .venv/bin/python):
    get_extras(
        file_name: str,
        chapter: bool = False,
        series_name: str = "",
        subtitle: str = "",
        extension: str = "",
    ) -> list[str]

Behaviour contract (pinned as-is):

* Extracts bracketed tags ``(…)`` / ``[…]`` / ``{…}`` from the filename.
* Strips 4-digit year tags ``(YYYY)`` from results.
* Strips ``(Premium)`` / ``(J-Novel Club Premium)`` bracket variants, then
  re-appends as ``(Premium)`` (manga) or ``[Premium]`` (novel) at the FRONT
  of the returned list.
* ``(Part N)`` / ``[Part N]`` brackets: when ``chapter=True``, Part brackets
  are removed from their original position and re-appended at the END (after
  non-premium items); when ``chapter=False`` the Part tag stays where it was.
* The modifier format depends on the file extension: ``.epub`` → ``[%s]``
  (novel_extensions), ``.zip``/``.cbz`` → ``(%s)`` (manga_extensions).
* ``extension`` kwarg overrides the extension derived from the filename.

FLAG: get_extras raises ``KeyError`` (not ValueError) whenever the resolved
extension is absent from the internal ``modifiers`` dict AND the filename
contains "premium" or "part" text that triggers a dict lookup.  Specifically:
  - No extension in filename AND premium/part present → KeyError('')
  - Unknown extension (e.g. ``.xyz``) AND premium/part present → KeyError('.xyz')
Files without "premium" or "part" never touch the modifiers dict so they do
NOT raise even with an unknown extension.

All values below were verified with:
    .venv/bin/python -c "import komga_cover_extractor as kce; print(repr(kce.get_extras(...)))"
on the library-replacements branch.
"""

from __future__ import annotations

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helper alias
# ---------------------------------------------------------------------------

def gx(file_name: str, **kwargs) -> list:
    """Thin wrapper to keep call sites concise."""
    return kce.get_extras(file_name, **kwargs)


# ---------------------------------------------------------------------------
# Basic bracket extraction (no premium, no part)
# ---------------------------------------------------------------------------


class TestBasicExtraction:
    """Straightforward tag extraction; no premium or part triggers."""

    def test_no_tags_returns_empty_list(self):
        """Filename with no bracketed tags → empty list."""
        assert gx("Series v01.cbz") == []

    def test_empty_filename_returns_empty_list(self):
        """Empty string filename → empty list (no brackets to find)."""
        assert gx("") == []

    def test_single_round_bracket_tag(self):
        """Single ``(Digital)`` tag is returned as-is."""
        assert gx("Series v01 (Digital).cbz") == ["(Digital)"]

    def test_single_square_bracket_tag(self):
        """Single ``[Seven Seas]`` tag is returned as-is."""
        assert gx("Series v01 [Seven Seas].cbz") == ["[Seven Seas]"]

    def test_year_tag_only_is_stripped(self):
        """``(2021)`` alone → stripped → empty list."""
        assert gx("Series v01 (2021).cbz") == []

    def test_multiple_year_tags_all_stripped(self):
        """Multiple year tags ``(2021) (2022)`` are all stripped."""
        assert gx("Series v01 (2021) (2022) (Digital).cbz") == ["(Digital)"]

    def test_no_extension_no_premium_returns_bracket_list(self):
        """No extension + no premium/part: bracket list is returned without error.

        FLAG: had any premium/part text been present, this would KeyError('').
        """
        assert gx("Series v01 (Digital)") == ["(Digital)"]

    def test_curly_brace_tag_preserved(self):
        """``{Digital}`` curly-brace tag is returned as-is (not converted)."""
        assert gx("Series v01 {Digital} {Premium}.cbz") == ["(Premium)", "{Digital}"]

    def test_duplicate_tags_deduped(self):
        """Duplicate ``(Digital)`` entries are deduplicated."""
        assert gx("Series v01 (Digital) (Digital) [Premium].cbz") == [
            "(Premium)",
            "(Digital)",
        ]


# ---------------------------------------------------------------------------
# The canonical multi-tag spec example
# (Digital) [Premium] (2021) [Seven Seas]
# ---------------------------------------------------------------------------


class TestSpecExample:
    """Pin the exact result for the multi-tag spec example from the task brief."""

    def test_cbz_multi_tag_premium_first_year_stripped(self):
        """``(Digital) [Premium] (2021) [Seven Seas]`` on a .cbz file.

        Expected ordered list:
          1. ``(Premium)`` — moved to front (manga modifier)
          2. ``(Digital)``  — preserved in encounter order
          3. ``[Seven Seas]`` — preserved in encounter order
          Year ``(2021)`` is stripped.
        """
        result = gx("Series v01 (Digital) [Premium] (2021) [Seven Seas].cbz")
        assert result == ["(Premium)", "(Digital)", "[Seven Seas]"]

    def test_epub_multi_tag_premium_as_square_bracket(self):
        """Same tags on a .epub file: Premium becomes ``[Premium]`` (novel modifier)."""
        result = gx("Series v01 (Digital) [Premium] (2021) [Seven Seas].epub")
        assert result == ["[Premium]", "(Digital)", "[Seven Seas]"]

    def test_zip_multi_tag_same_as_cbz(self):
        """Same tags on a .zip file: manga modifier → ``(Premium)``."""
        result = gx("Series v01 (Digital) [Premium] (2021) [Seven Seas].zip")
        assert result == ["(Premium)", "(Digital)", "[Seven Seas]"]

    def test_tag_encounter_order_preserved_for_non_premium(self):
        """When [Seven Seas] appears BEFORE (Digital), that order is kept."""
        result = gx("Series v01 [Seven Seas] (Digital) [Premium] (2021).cbz")
        assert result == ["(Premium)", "[Seven Seas]", "(Digital)"]

    def test_extension_kwarg_overrides_file_ext(self):
        """Passing ``extension='.epub'`` on a .cbz filename uses epub modifier."""
        result = gx(
            "Series v01 (Digital) [Premium] (2021) [Seven Seas].cbz",
            extension=".epub",
        )
        assert result == ["[Premium]", "(Digital)", "[Seven Seas]"]


# ---------------------------------------------------------------------------
# Premium handling
# ---------------------------------------------------------------------------


class TestPremiumHandling:
    """Premium tags are normalised and moved to the front."""

    def test_premium_round_bracket_cbz(self):
        """``(Premium)`` in a .cbz → ``(Premium)`` at front."""
        assert gx("Series v01 (Premium).cbz") == ["(Premium)"]

    def test_premium_square_bracket_cbz(self):
        """``[Premium]`` in a .cbz → normalised to ``(Premium)`` (manga modifier)."""
        assert gx("Series v01 [Premium].cbz") == ["(Premium)"]

    def test_premium_round_bracket_epub(self):
        """``(Premium)`` in a .epub → ``[Premium]`` (novel modifier)."""
        assert gx("Series v01 (Premium).epub") == ["[Premium]"]

    def test_j_novel_club_premium_cbz(self):
        """``(J-Novel Club Premium)`` bracket is stripped; ``(Premium)`` appended."""
        result = gx("Series v01 (J-Novel Club Premium) (Digital).cbz")
        assert result == ["(Premium)", "(Digital)"]

    def test_j_novel_club_premium_epub(self):
        """``(J-Novel Club Premium)`` in .epub → ``[Premium]`` at front."""
        result = gx("Series v01 (J-Novel Club Premium) (Digital).epub")
        assert result == ["[Premium]", "(Digital)"]

    def test_premium_plain_text_no_brackets_cbz(self):
        """``Premium`` as plain (unbracketed) text still triggers the keyword path."""
        # FLAG: Premium without brackets in the filename triggers the 'premium in
        # file_name.lower()' code-path, inserting (Premium) even though it was not
        # a proper bracket tag. This is pinned as-is.
        assert gx("Series v01 Premium.cbz") == ["(Premium)"]

    def test_curly_brace_premium_cbz(self):
        """``{Premium}`` curly-brace variant also triggers the premium keyword path.

        The curly-brace ``{Premium}`` is extracted as a bracket result but is then
        removed by the premium-pattern filter; the keyword path then inserts
        ``(Premium)`` (manga modifier) at the front.  ``(Digital)`` is a standard
        round-bracket tag and appears second.
        """
        result = gx("Series v01 {Premium} (Digital).cbz")
        assert result == ["(Premium)", "(Digital)"]

    def test_curly_brace_non_premium_tag_preserved(self):
        """``{Digital}`` curly-brace tag is returned as-is (not normalised)."""
        result = gx("Series v01 {Digital} {Premium}.cbz")
        assert result == ["(Premium)", "{Digital}"]

    def test_explicit_extension_controls_modifier(self):
        """extension='.epub' on no-ext filename with premium uses novel modifier."""
        result = gx("Series v01 (Premium)", extension=".epub")
        assert result == ["[Premium]"]

    def test_explicit_cbz_extension_on_no_ext_file(self):
        """extension='.cbz' on no-ext filename with premium uses manga modifier."""
        result = gx("Series v01 (Premium)", extension=".cbz")
        assert result == ["(Premium)"]


# ---------------------------------------------------------------------------
# series_name and subtitle removal
# ---------------------------------------------------------------------------


class TestSeriesAndSubtitleRemoval:
    """series_name and subtitle are word-boundary-removed before tag extraction."""

    def test_series_name_removed_from_file_name(self):
        """series_name='My Series' causes 'My Series' to be stripped first."""
        result = gx(
            "My Series v01 (Digital) [Premium] (2021) [Seven Seas].cbz",
            series_name="My Series",
        )
        assert result == ["(Premium)", "(Digital)", "[Seven Seas]"]

    def test_subtitle_removed(self):
        """subtitle text is stripped, leaving only remaining bracket tags."""
        result = gx(
            "My Series v01 Subtitle Here (Digital) [Premium].cbz",
            series_name="My Series",
            subtitle="Subtitle Here",
        )
        assert result == ["(Premium)", "(Digital)"]

    def test_series_name_strips_year_too(self):
        """Year is still stripped after series_name removal."""
        result = gx(
            "My Series v01 (Digital) (2021) [Premium].cbz",
            series_name="My Series",
        )
        assert result == ["(Premium)", "(Digital)"]


# ---------------------------------------------------------------------------
# Part handling — non-chapter mode
# ---------------------------------------------------------------------------


class TestPartNonChapterMode:
    """chapter=False (default): Part brackets stay in their encounter position."""

    def test_part_bracket_preserves_position(self):
        """``(Part 2)`` at front stays at front in non-chapter mode."""
        result = gx("Series c001 (Part 2) (Digital).cbz", chapter=False)
        assert result == ["(Part 2)", "(Digital)"]

    def test_part_free_text_appended_as_manga_modifier(self):
        """'Part 2' as plain text → ``(Part 2)`` appended at end (manga modifier)."""
        result = gx("Series v01 Part 2 (Digital).cbz", chapter=False)
        assert result == ["(Digital)", "(Part 2)"]

    def test_part_free_text_epub_appended_as_novel_modifier(self):
        """'Part 2' as plain text on .epub → ``[Part 2]`` appended."""
        result = gx("Series v01 Part 2 (Digital).epub", chapter=False)
        assert result == ["(Digital)", "[Part 2]"]

    def test_part_hyphen_separator(self):
        """'Part-2' separator variant → ``(Part-2)`` appended."""
        result = gx("Series v01 Part-2 (Digital).cbz", chapter=False)
        assert result == ["(Digital)", "(Part-2)"]

    def test_part_underscore_separator(self):
        """'Part_2' separator variant → ``(Part_2)`` appended."""
        result = gx("Series v01 Part_2 (Digital).cbz", chapter=False)
        assert result == ["(Digital)", "(Part_2)"]

    def test_square_bracket_part_non_chapter_preserved(self):
        """``[Part 2]`` is preserved AND a plain-text match also appended.

        FLAG: when [Part 2] is in brackets AND 'Part 2' also matches the
        free-text regex, two Part-related items can appear: the original
        ``[Part 2]`` bracket AND a new ``(Part 2)`` appended.  Pinned as-is.
        """
        result = gx("Series v01 [Part 2] (Digital).cbz", chapter=False)
        assert result == ["[Part 2]", "(Digital)", "(Part 2)"]


# ---------------------------------------------------------------------------
# Part handling — chapter mode
# ---------------------------------------------------------------------------


class TestPartChapterMode:
    """chapter=True: bracketed (Part N) is removed then re-appended at the END."""

    def test_chapter_mode_part_bracket_moves_to_end(self):
        """``(Part 1)`` at front is stripped and re-appended after other tags."""
        result = gx(
            "Series c001 (Part 1) (Digital) [Seven Seas].cbz", chapter=True
        )
        assert result == ["(Digital)", "[Seven Seas]", "(Part 1)"]

    def test_chapter_mode_part_bracket_at_end_stays_at_end(self):
        """``(Part 1)`` already at end: removal + re-append keeps it there."""
        result = gx(
            "Series c001 (Digital) [Seven Seas] (Part 1).cbz", chapter=True
        )
        assert result == ["(Digital)", "[Seven Seas]", "(Part 1)"]

    def test_chapter_mode_part_free_text_appended(self):
        """Plain-text 'Part 2' in chapter mode → re-appended at end."""
        result = gx("Series c001 Part 2 (Digital).cbz", chapter=True)
        assert result == ["(Digital)", "(Part 2)"]

    def test_chapter_mode_epub_part_bracket_appended(self):
        """chapter=True on .epub: Part bracket removed, re-appended as ``[Part 2]``."""
        result = gx("Series c001 (Part 2) (Digital).epub", chapter=True)
        assert result == ["(Digital)", "[Part 2]"]

    def test_chapter_mode_premium_stays_front_part_goes_end(self):
        """Premium at front, Part at end — ordering: premium, non-premium, Part."""
        result = gx(
            "Series c001 (Part 2) (Premium) (Digital).cbz", chapter=True
        )
        assert result == ["(Premium)", "(Digital)", "(Part 2)"]

    def test_non_chapter_mode_premium_and_part_bracket_ordering(self):
        """Non-chapter: premium to front, Part stays in position, Digital after it."""
        result = gx(
            "Series c001 (Part 2) (Premium) (Digital).cbz", chapter=False
        )
        assert result == ["(Premium)", "(Part 2)", "(Digital)"]


# ---------------------------------------------------------------------------
# FLAG: KeyError on unknown / missing extension when premium or part is present
# ---------------------------------------------------------------------------


class TestKeyErrorOnBadExtension:
    """Accessing modifiers[extension] raises KeyError for unknown extensions.

    FLAG: this is a latent bug — the function raises KeyError instead of
    returning a graceful fallback.  Only triggered when the filename contains
    "premium" or "part" (the only two code paths that look up modifiers[ext]).
    Files without those keywords never touch the dict and succeed silently.
    """

    def test_empty_extension_with_premium_raises_key_error(self):
        """No file extension + premium text → KeyError('').

        The extension resolves to '' via get_file_extension, which is not in
        the modifiers dict.  Pinned with pytest.raises.
        """
        with pytest.raises(KeyError, match="''"):
            kce.get_extras("Test (Premium)")

    def test_explicit_empty_extension_kwarg_with_premium_raises_key_error(self):
        """``extension=''`` (falsy) falls back to get_file_extension → KeyError('').

        When extension='' is passed explicitly, it is falsy so the code falls
        back to ``get_file_extension(file_name)``.  A file with no extension
        returns '' → KeyError.
        """
        with pytest.raises(KeyError):
            kce.get_extras("Test (Premium)", extension="")

    def test_unknown_extension_xyz_with_premium_raises_key_error(self):
        """Unknown extension ``.xyz`` + premium → KeyError('.xyz').

        ``.xyz`` is not in file_extensions so it is absent from the modifiers
        dict.  Pinned as KeyError with the extension as the key.
        """
        with pytest.raises(KeyError, match=r"\.xyz"):
            kce.get_extras("Series v01 (Digital) [Premium].xyz")

    def test_unknown_extension_no_premium_does_not_raise(self):
        """Unknown extension WITHOUT premium/part in name → no KeyError, returns [].

        FLAG: modifiers dict is built but never accessed when neither 'premium'
        nor 'part' appears in the filename.  The function silently succeeds.
        """
        result = kce.get_extras("Test v01.xyz")
        assert result == []

    def test_cbr_extension_with_premium_raises_key_error(self):
        """`.cbr` is not in file_extensions → KeyError('.cbr') when premium present."""
        with pytest.raises(KeyError):
            kce.get_extras("Series v01 (Premium).cbr")

    def test_rar_extension_with_premium_raises_key_error(self):
        """`.rar` is not in file_extensions → KeyError('.rar') when premium present."""
        with pytest.raises(KeyError):
            kce.get_extras("Series v01 (Premium).rar")
