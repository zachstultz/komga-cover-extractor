"""Characterization tests for ``kce.contains_premium_content`` and
``kce.get_subtitle_from_title``.

All assertions were verified against real function output observed in
``.venv/bin/python3`` before writing — see inline comments for the
exact observed values.

Verified function signatures (via Serena, komga_cover_extractor.py):

  contains_premium_content(file)
      Opens *file* as a zipfile and checks for three independent premium signals:
        1. ``bonus.xhtml`` (or ``bonus_N.xhtml``) member exists AND a member
           path contains ``/signup``.
        2. ``toc.xhtml`` member whose text contains ``j-novel`` (case-insensitive)
           AND matches ``Bonus\\s+((Color\\s+)?Illustrations?|(Short\\s+)?Stories)``
           (case-insensitive).
        3. ``copyright.xhtml`` member whose text contains ``premium``
           (case-insensitive) AND matches ``Premium(\\s)+(E?-?Book|Epub)``
           (case-insensitive).
      Returns ``False`` on any exception (bad zip, decoding error, …).

  get_subtitle_from_title(file, publisher=None)  [lru_cache(maxsize=3500)]
      Takes a *Volume* object (NOT a string).  Extracts a subtitle from
      ``file.name`` by requiring BOTH a dash/colon separator AND a year/Digital
      marker (``(YYYY)`` or ``(Digital)``).  Returns ``""`` when:
        * no dash/colon is found, or
        * no year/Digital marker is found, or
        * the extracted subtitle matches the parent-folder name, or
        * the extracted subtitle looks like a volume keyword + number
          (e.g. "Vol 1", "Volume 1").
"""

from __future__ import annotations

import zipfile

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_vol(filename: str, root: str = "/tmp/nope"):
    """Return a single Volume object built through the production pipeline."""
    kce.get_subtitle_from_title.cache_clear()
    files = kce.upgrade_to_file_class([filename], root, test_mode=True)
    vols = kce.upgrade_to_volume_class(files, test_mode=True)
    return vols[0]


# ===========================================================================
# contains_premium_content
# ===========================================================================

class TestContainsPremiumContent:
    """Pin ``kce.contains_premium_content`` signals and negative cases.

    The function reads the zip member-list string and selected member
    contents to detect J-Novel Club / Tentacle Press premium epub signals.
    All test archives are created in-memory via the ``cbz_factory`` fixture
    (which writes to tmp_path).
    """

    # -----------------------------------------------------------------------
    # Signal 1: bonus(.xhtml / _N.xhtml) file name AND /signup in member path
    # -----------------------------------------------------------------------

    def test_bonus_xhtml_numbered_and_signup_dir_returns_true(self, cbz_factory):
        """A member named ``bonus_1.xhtml`` inside a ``/signup/`` path triggers
        the first premium signal.

        Observed: ``True``.
        """
        path = cbz_factory(
            name="Premium v01.cbz",
            entries={
                "Text/bonus_1.xhtml": "<html>bonus</html>",
                "Text/signup/index.html": "<html>signup</html>",
            },
        )
        assert kce.contains_premium_content(str(path)) is True

    def test_bonus_xhtml_unnumbered_and_signup_dir_returns_true(self, cbz_factory):
        """A member named ``bonus.xhtml`` (no number) + ``/signup/`` path also
        triggers signal 1 — the regex allows the digit group to be absent.

        Observed: ``True``.
        """
        path = cbz_factory(
            name="Premium v02.cbz",
            entries={
                "Text/bonus.xhtml": "<html>bonus</html>",
                "Text/signup/index.html": "<html>signup</html>",
            },
        )
        assert kce.contains_premium_content(str(path)) is True

    def test_bonus_xhtml_without_signup_returns_false(self, cbz_factory):
        """``bonus_1.xhtml`` present but no ``/signup`` path — signal 1 is
        not triggered; no other signal exists.

        Observed: ``False``.
        """
        path = cbz_factory(
            name="NoPremium v01.cbz",
            entries={
                "Text/bonus_1.xhtml": "<html>bonus</html>",
            },
        )
        assert kce.contains_premium_content(str(path)) is False

    # -----------------------------------------------------------------------
    # Signal 2: toc.xhtml with "j-novel" AND Bonus Illustrations/Stories
    # -----------------------------------------------------------------------

    def test_toc_jnovel_bonus_color_illustrations_returns_true(self, cbz_factory):
        """``toc.xhtml`` containing both ``j-novel`` and
        ``Bonus Color Illustrations`` triggers signal 2.

        Observed: ``True``.
        """
        toc = (
            "<html>J-Novel Club<br/>"
            "<a href=\"bonus\">Bonus Color Illustrations</a></html>"
        )
        path = cbz_factory(
            name="JNovel v01.cbz",
            entries={"toc.xhtml": toc},
        )
        assert kce.contains_premium_content(str(path)) is True

    def test_toc_jnovel_bonus_short_stories_returns_true(self, cbz_factory):
        """``toc.xhtml`` with ``j-novel`` and ``Bonus Short Stories`` also
        triggers signal 2.

        Observed: ``True``.
        """
        toc = (
            "<html>j-novel club<br/>"
            "<a href=\"bonus\">Bonus Short Stories</a></html>"
        )
        path = cbz_factory(
            name="JNovel v02.cbz",
            entries={"toc.xhtml": toc},
        )
        assert kce.contains_premium_content(str(path)) is True

    def test_toc_no_jnovel_bonus_illustrations_returns_false(self, cbz_factory):
        """``toc.xhtml`` with ``Bonus Color Illustrations`` but no ``j-novel``
        string does NOT trigger signal 2.

        Observed: ``False``.
        """
        toc = (
            "<html>Some Other Publisher<br/>"
            "<a href=\"bonus\">Bonus Color Illustrations</a></html>"
        )
        path = cbz_factory(
            name="NotJNovel v01.cbz",
            entries={"toc.xhtml": toc},
        )
        assert kce.contains_premium_content(str(path)) is False

    # -----------------------------------------------------------------------
    # Signal 3: copyright.xhtml with "premium" AND "Premium E-Book/Epub"
    # -----------------------------------------------------------------------

    def test_copyright_premium_epub_returns_true(self, cbz_factory):
        """``copyright.xhtml`` containing both ``premium`` and the phrase
        ``Premium Epub`` triggers signal 3.

        Observed: ``True``.
        """
        copyright_content = (
            "<html>This is a Premium Epub edition by J-Novel Club</html>"
        )
        path = cbz_factory(
            name="PremiumEpub v01.cbz",
            entries={"copyright.xhtml": copyright_content},
        )
        assert kce.contains_premium_content(str(path)) is True

    def test_copyright_premium_ebook_returns_true(self, cbz_factory):
        """``copyright.xhtml`` with ``Premium E-Book`` phrase triggers signal 3.

        Observed: ``True``.
        """
        copyright_content = "<html>This is a Premium E-Book edition</html>"
        path = cbz_factory(
            name="PremiumEBook v01.cbz",
            entries={"copyright.xhtml": copyright_content},
        )
        assert kce.contains_premium_content(str(path)) is True

    def test_copyright_no_premium_keyword_returns_false(self, cbz_factory):
        """``copyright.xhtml`` without the word ``premium`` does not trigger
        signal 3.

        Observed: ``False``.
        """
        copyright_content = "<html>This is a Standard E-Book edition</html>"
        path = cbz_factory(
            name="StandardEBook v01.cbz",
            entries={"copyright.xhtml": copyright_content},
        )
        assert kce.contains_premium_content(str(path)) is False

    # -----------------------------------------------------------------------
    # Negative / fallback cases
    # -----------------------------------------------------------------------

    def test_plain_image_archive_returns_false(self, cbz_factory):
        """A standard CBZ with only a JPEG page has no premium signals.

        Observed: ``False``.
        """
        path = cbz_factory(name="Regular v01.cbz")  # default: one real-JPEG page
        assert kce.contains_premium_content(str(path)) is False

    def test_non_zip_file_returns_false(self, tmp_path):
        """An unreadable (non-zip) file triggers the except branch and returns
        ``False``.

        Observed: ``False``.
        """
        bad = tmp_path / "bad.cbz"
        bad.write_bytes(b"not a zip file at all")
        assert kce.contains_premium_content(str(bad)) is False


# ===========================================================================
# get_subtitle_from_title
# ===========================================================================

class TestGetSubtitleFromTitle:
    """Pin ``kce.get_subtitle_from_title`` through the production Volume pipeline.

    ``get_subtitle_from_title`` is called internally by ``upgrade_to_volume_class``
    (unless ``skip_subtitle=True``) so the canonical way to exercise it is to
    build a Volume via the pipeline and read ``vol.subtitle``.  Direct calls are
    used for the cache-clear + re-invocation cases only.

    The function requires BOTH:
      * a dash (`` - ``) or colon (``: ``) separator in the filename, AND
      * a year marker ``(YYYY)`` or a ``(Digital)`` marker.
    If either is absent, it returns ``""``.
    """

    # -----------------------------------------------------------------------
    # Basic subtitle extraction
    # -----------------------------------------------------------------------

    def test_dash_subtitle_with_year_and_digital(self):
        """Standard ``Series vNN (YYYY) (Digital) - Subtitle.cbz`` extracts
        the subtitle string after the last dash.

        Observed: ``'A Subtitle'``.
        """
        vol = _build_vol("My Series v01 (2021) (Digital) - A Subtitle.cbz")
        assert vol.subtitle == "A Subtitle"

    def test_colon_subtitle_with_year_and_digital(self):
        """A colon separator also works as the subtitle delimiter.

        Observed: ``'Colon Subtitle'``.
        """
        vol = _build_vol("My Series v02 (2022) (Digital): Colon Subtitle.cbz")
        assert vol.subtitle == "Colon Subtitle"

    def test_dash_subtitle_with_year_only(self):
        """Year marker alone (no ``(Digital)``) is sufficient to enable subtitle
        extraction via the year_or_digital_search branch.

        Observed: ``'Year Only Subtitle'``.
        """
        vol = _build_vol("My Series v01 (2021) - Year Only Subtitle.cbz")
        assert vol.subtitle == "Year Only Subtitle"

    def test_dash_subtitle_with_digital_only(self):
        """``(Digital)`` marker alone (no year) is also sufficient.

        Observed: ``'Digital Only Subtitle'``.
        """
        vol = _build_vol("My Series v01 (Digital) - Digital Only Subtitle.cbz")
        assert vol.subtitle == "Digital Only Subtitle"

    def test_extension_stripped_from_subtitle(self):
        """If the raw subtitle ends with the file extension (e.g. ``.cbz``),
        ``get_extensionless_name`` removes it.

        Observed: ``'MySubtitle'`` (not ``'MySubtitle.cbz'``).
        """
        vol = _build_vol("My Series v01 (2021) (Digital) - MySubtitle.cbz")
        assert vol.subtitle == "MySubtitle"

    def test_epub_subtitle_extracted(self):
        """Subtitle extraction works identically for ``.epub`` files.

        Observed: ``'An Epub Subtitle'``.
        """
        vol = _build_vol(
            "My Series v01 (2021) (Digital) - An Epub Subtitle.epub"
        )
        assert vol.subtitle == "An Epub Subtitle"

    def test_multi_dash_takes_last_segment(self):
        """When the filename contains multiple dash separators, the regex
        ``(.*)((\\s+(-)|:)\\s+)`` greedily takes the rightmost one, yielding
        only the last segment.

        Observed: ``'Subtitle'`` (not ``'Multi - Word - Subtitle'``).
        """
        vol = _build_vol(
            "My Series v01 (2021) (Digital) - Multi - Word - Subtitle.cbz"
        )
        assert vol.subtitle == "Subtitle"

    # -----------------------------------------------------------------------
    # No-subtitle cases (returns "")
    # -----------------------------------------------------------------------

    def test_no_dash_or_colon_returns_empty(self):
        """A filename with no dash/colon separator returns ``""``.

        Observed: ``''``.
        """
        vol = _build_vol("My Series v03 (2021).cbz")
        assert vol.subtitle == ""

    def test_dash_without_year_or_digital_returns_empty(self):
        """Dash present but no year/Digital marker — no subtitle extracted.

        Observed: ``''``.
        """
        vol = _build_vol("My Series v01 - No Year.cbz")
        assert vol.subtitle == ""

    def test_colon_without_year_returns_empty(self):
        """Colon present but no year/Digital marker — no subtitle extracted.

        Observed: ``''``.
        """
        vol = _build_vol("My Series v01: No Year.cbz")
        assert vol.subtitle == ""

    # -----------------------------------------------------------------------
    # Suppression: subtitle matches folder name
    # -----------------------------------------------------------------------

    def test_subtitle_suppressed_when_it_matches_folder_name(self):
        """If the extracted subtitle appears in ``os.path.basename(vol.path's
        parent)`` (the series folder name), the function clears it to ``""``.

        Root ``/tmp/My Series - A Subtitle`` → folder base is
        ``My Series - A Subtitle`` which contains ``A Subtitle`` → suppressed.

        Observed: ``''``.
        """
        vol = _build_vol(
            "My Series v01 (2021) (Digital) - A Subtitle.cbz",
            root="/tmp/My Series - A Subtitle",
        )
        assert vol.subtitle == ""

    def test_subtitle_not_suppressed_when_folder_is_plain_series(self):
        """When the folder name does NOT contain the subtitle, it is kept.

        Root ``/tmp/My Series`` → folder base ``My Series`` does not contain
        ``A Subtitle`` → subtitle preserved.

        Observed: ``'A Subtitle'``.
        """
        vol = _build_vol(
            "My Series v01 (2021) (Digital) - A Subtitle.cbz",
            root="/tmp/My Series",
        )
        assert vol.subtitle == "A Subtitle"

    # -----------------------------------------------------------------------
    # Suppression: subtitle looks like a volume keyword + number
    # -----------------------------------------------------------------------

    def test_vol_1_subtitle_suppressed(self):
        """A subtitle of ``'Vol 1'`` matches the volume-keyword regex and is
        cleared to ``""``.

        Observed: ``''``.
        """
        vol = _build_vol("MySeries v01 (2021) (Digital) - Vol 1.cbz")
        assert vol.subtitle == ""

    def test_volume_1_subtitle_suppressed(self):
        """A subtitle of ``'Volume 1'`` similarly matches and is suppressed.

        Observed: ``''``.
        """
        vol = _build_vol("My Series v01 (2021) (Digital) - Volume 1.cbz")
        assert vol.subtitle == ""

    # -----------------------------------------------------------------------
    # Legitimate subtitles that look like chapter/prologue content
    # -----------------------------------------------------------------------

    def test_chapter_2_subtitle_not_suppressed(self):
        """A subtitle ``'Chapter 2'`` is NOT a volume keyword match; it is
        preserved as-is.

        Observed: ``'Chapter 2'``.

        # FLAG: 'Chapter 2' is an odd subtitle for a volume file, but the code
        # returns it unchanged — characterization pins this as-is.
        """
        vol = _build_vol("MySeries v02 (2021) (Digital) - Chapter 2.cbz")
        assert vol.subtitle == "Chapter 2"

    def test_prologue_subtitle_not_suppressed(self):
        """A subtitle of ``'Prologue'`` is kept because it does not match the
        volume-keyword regex.

        Observed: ``'Prologue'``.
        """
        vol = _build_vol("MySeries v03 (2021) (Digital) - Prologue.cbz")
        assert vol.subtitle == "Prologue"

    # -----------------------------------------------------------------------
    # Direct call to get_subtitle_from_title — confirming it takes a Volume
    # -----------------------------------------------------------------------

    def test_direct_call_matches_pipeline_output(self):
        """Calling ``kce.get_subtitle_from_title(vol, publisher=vol.publisher)``
        directly after clearing the cache returns the same value as the
        pipeline sets on ``vol.subtitle``.

        Observed: ``'A Subtitle'``.
        """
        vol = _build_vol(
            "My Series v01 (2021) (Digital) - A Subtitle.cbz",
            root="/tmp/nope",
        )
        # Pipeline already called it; clear cache and call again manually.
        kce.get_subtitle_from_title.cache_clear()
        result = kce.get_subtitle_from_title(vol, publisher=vol.publisher)
        assert result == "A Subtitle"

    def test_direct_call_no_subtitle_returns_empty_string(self):
        """Direct call on a no-subtitle volume returns ``""`` (not ``None``).

        Observed: ``''``.
        """
        vol = _build_vol("My Series v03 (2021).cbz")
        kce.get_subtitle_from_title.cache_clear()
        result = kce.get_subtitle_from_title(vol, publisher=vol.publisher)
        assert result == ""
        assert isinstance(result, str)
