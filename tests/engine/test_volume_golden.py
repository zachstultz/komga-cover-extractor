"""Full-field GOLDEN SNAPSHOT tests for the Volume parsing call-graph.

Each test builds real Volume objects through the production pipeline:

    files = kce.upgrade_to_file_class([name], root, test_mode=True)
    vols  = kce.upgrade_to_volume_class(files, test_mode=True)

and then pins EVERY observable field precisely.

Key test_mode=True effects (characterised and pinned as-is):
  * ``skip_release_year=True``  → ``volume_year`` is always ``None``
  * ``skip_publisher=True``     → ``publisher`` is always ``Publisher(None, None)``
  * ``skip_premium_content=True``→ ``is_premium`` is always ``False``
  * ``release_group`` is ``''`` because no release-group list is loaded in isolation

All values were observed by running the relevant snippet in the project .venv
before writing the assertion — no values were guessed.

Verified with:
    .venv/bin/python3 -c "import komga_cover_extractor as kce; ..."
on the tests/upgrade-scoring-engine branch.
"""

from __future__ import annotations

import regex

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build(filename: str, root: str = "/tmp/nope"):
    """Return (File, Volume) pair through the production pipeline (test_mode=True)."""
    files = kce.upgrade_to_file_class([filename], root, test_mode=True)
    assert files, f"upgrade_to_file_class returned empty list for {filename!r}"
    vols = kce.upgrade_to_volume_class(files, test_mode=True)
    assert vols, f"upgrade_to_volume_class returned empty list for {filename!r}"
    return files[0], vols[0]


# ===========================================================================
# Golden 1 — Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz
# ===========================================================================

class TestMushokuTenseiGolden:
    """Full-field pin for a standard single-volume manga CBZ.

    This is the canonical integration fixture: it exercises file-class
    parsing, volume-class parsing, extras extraction, one-shot check,
    multi-volume check, subtitle extraction, and part detection all at once.

    All assertions were verified against observed production output.
    """

    @pytest.fixture(autouse=True)
    def _build_vol(self):
        self.f, self.v = _build(
            "Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz"
        )

    # ------------------------------------------------------------------
    # File-class layer
    # ------------------------------------------------------------------

    def test_file_name(self):
        assert self.f.name == "Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz"

    def test_file_extension(self):
        assert self.f.extension == ".cbz"

    def test_file_type(self):
        # upgrade_to_file_class classifies this as a volume, not a chapter
        assert self.f.file_type == "volume"

    def test_file_volume_number(self):
        assert self.f.volume_number == 1
        assert isinstance(self.f.volume_number, int)

    def test_file_header_extension(self):
        # test_mode=True: no real header read; header_extension stays None
        assert self.f.header_extension is None

    def test_file_basename(self):
        assert self.f.basename == "Mushoku Tensei"

    def test_file_root(self):
        assert self.f.root == "/tmp/nope"

    def test_file_extensionless_name(self):
        assert self.f.extensionless_name == "Mushoku Tensei v01 (2021) (Digital) [Seven Seas]"

    def test_file_extensionless_path(self):
        assert self.f.extensionless_path == (
            "/tmp/nope/Mushoku Tensei v01 (2021) (Digital) [Seven Seas]"
        )

    # ------------------------------------------------------------------
    # Volume-class identification fields
    # ------------------------------------------------------------------

    def test_series_name(self):
        assert self.v.series_name == "Mushoku Tensei"

    def test_shortened_series_name(self):
        # No dash/colon in the base title → no shortened form
        assert self.v.shortened_series_name == ""

    def test_volume_number_value(self):
        assert self.v.volume_number == 1

    def test_volume_number_type(self):
        assert isinstance(self.v.volume_number, int)

    def test_index_number_value(self):
        # No part → index_number == volume_number
        assert self.v.index_number == 1

    def test_index_number_type(self):
        assert isinstance(self.v.index_number, int)

    def test_volume_part_empty(self):
        assert self.v.volume_part == ""
        assert isinstance(self.v.volume_part, str)

    def test_file_type_volume(self):
        assert self.v.file_type == "volume"

    def test_extension(self):
        assert self.v.extension == ".cbz"

    def test_header_extension_none(self):
        assert self.v.header_extension is None

    # ------------------------------------------------------------------
    # Extras (Digital + group bracket)
    # ------------------------------------------------------------------

    def test_extras_exact_list(self):
        # Both (Digital) and [Seven Seas] survive extras extraction.
        assert self.v.extras == ["(Digital)", "[Seven Seas]"]

    def test_extras_type(self):
        assert isinstance(self.v.extras, list)
        assert all(isinstance(x, str) for x in self.v.extras)

    # ------------------------------------------------------------------
    # Boolean flags
    # ------------------------------------------------------------------

    def test_is_one_shot_false(self):
        # Has a volume number → not a one-shot
        assert self.v.is_one_shot is False

    def test_is_premium_false(self):
        # test_mode=True skips premium detection → always False
        assert self.v.is_premium is False

    def test_multi_volume_false(self):
        # No range in name → multi_volume is False (not None)
        assert self.v.multi_volume is False

    # ------------------------------------------------------------------
    # Publisher (test_mode skips all lookups)
    # ------------------------------------------------------------------

    def test_publisher_type(self):
        assert isinstance(self.v.publisher, kce.Publisher)

    def test_publisher_from_meta_none(self):
        # test_mode=True skips internal metadata → from_meta is None
        assert self.v.publisher.from_meta is None

    def test_publisher_from_name_none(self):
        # test_mode=True skips publisher lookup → from_name is None
        assert self.v.publisher.from_name is None

    # ------------------------------------------------------------------
    # Subtitle
    # ------------------------------------------------------------------

    def test_subtitle_empty(self):
        # No dash + year/Digital marker combo in standard position → no subtitle
        assert self.v.subtitle == ""
        assert isinstance(self.v.subtitle, str)

    # ------------------------------------------------------------------
    # Release group + year (test_mode effects)
    # ------------------------------------------------------------------

    def test_release_group_empty_under_test_mode(self):
        # FLAG: release_group is '' under test_mode (no group list loaded and
        # skip_release_group is NOT forced True by test_mode — the '' comes
        # from get_extra_from_group returning '' when release_groups is []).
        assert self.v.release_group == ""
        assert isinstance(self.v.release_group, str)

    def test_volume_year_none_under_test_mode(self):
        # test_mode=True forces skip_release_year=True → volume_year is None
        # even though '(2021)' appears in the filename.
        assert self.v.volume_year is None

    # ------------------------------------------------------------------
    # Path / name fields pass-through
    # ------------------------------------------------------------------

    def test_name_passthrough(self):
        assert self.v.name == "Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz"

    def test_basename_passthrough(self):
        assert self.v.basename == "Mushoku Tensei"

    def test_extensionless_name(self):
        assert self.v.extensionless_name == (
            "Mushoku Tensei v01 (2021) (Digital) [Seven Seas]"
        )

    def test_root_passthrough(self):
        assert self.v.root == "/tmp/nope"

    def test_path_passthrough(self):
        assert self.v.path == (
            "/tmp/nope/Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz"
        )

    def test_extensionless_path(self):
        assert self.v.extensionless_path == (
            "/tmp/nope/Mushoku Tensei v01 (2021) (Digital) [Seven Seas]"
        )


# ===========================================================================
# Golden 2 — Series v01-03 (2021) (Digital) [Group].cbz — MULTI-VOLUME
# ===========================================================================

class TestMultiVolumeGolden:
    """Full-field pin for a range-numbered multi-volume CBZ.

    The key invariants: volume_number is a list, multi_volume is truthy.
    All assertions were verified against observed production output.
    """

    @pytest.fixture(autouse=True)
    def _build_vol(self):
        self.f, self.v = _build(
            "Series v01-03 (2021) (Digital) [Group].cbz"
        )

    def test_series_name(self):
        assert self.v.series_name == "Series"

    def test_volume_number_is_list(self):
        assert self.v.volume_number == [1, 3]
        assert isinstance(self.v.volume_number, list)

    def test_volume_number_elements_are_int(self):
        for x in self.v.volume_number:
            assert isinstance(x, int)

    def test_index_number_is_list(self):
        # No part: index_number mirrors volume_number for multi-volume
        assert self.v.index_number == [1, 3]
        assert isinstance(self.v.index_number, list)

    def test_index_number_elements_are_int(self):
        for x in self.v.index_number:
            assert isinstance(x, int)

    def test_multi_volume_truthy(self):
        assert self.v.multi_volume

    def test_multi_volume_is_true(self):
        assert self.v.multi_volume is True

    def test_is_one_shot_false(self):
        assert self.v.is_one_shot is False

    def test_extras_exact(self):
        assert self.v.extras == ["(Digital)", "[Group]"]

    def test_volume_part_empty(self):
        assert self.v.volume_part == ""

    def test_subtitle_empty(self):
        assert self.v.subtitle == ""

    def test_release_group_empty(self):
        assert self.v.release_group == ""

    def test_volume_year_none(self):
        assert self.v.volume_year is None

    def test_is_premium_false(self):
        assert self.v.is_premium is False

    def test_publisher_from_meta_none(self):
        assert self.v.publisher.from_meta is None

    def test_publisher_from_name_none(self):
        assert self.v.publisher.from_name is None

    def test_file_type(self):
        assert self.v.file_type == "volume"

    def test_extension(self):
        assert self.v.extension == ".cbz"

    def test_name(self):
        assert self.v.name == "Series v01-03 (2021) (Digital) [Group].cbz"

    def test_shortened_series_name(self):
        assert self.v.shortened_series_name == ""


# ===========================================================================
# Golden 3 — Sword Art Online v01 (2020) (Digital) [Yen Press].epub — NOVEL
# ===========================================================================

class TestEpubNovelGolden:
    """Full-field pin for a standard .epub light novel.

    Verifies that the parsing pipeline correctly handles epub extension
    and that the series name is preserved without modification.
    All assertions were verified against observed production output.
    """

    @pytest.fixture(autouse=True)
    def _build_vol(self):
        self.f, self.v = _build(
            "Sword Art Online v01 (2020) (Digital) [Yen Press].epub"
        )

    def test_series_name(self):
        assert self.v.series_name == "Sword Art Online"

    def test_shortened_series_name_empty(self):
        # No dash/colon separator in base title
        assert self.v.shortened_series_name == ""

    def test_extension_is_epub(self):
        assert self.v.extension == ".epub"

    def test_file_type(self):
        assert self.v.file_type == "volume"

    def test_volume_number(self):
        assert self.v.volume_number == 1
        assert isinstance(self.v.volume_number, int)

    def test_index_number(self):
        assert self.v.index_number == 1
        assert isinstance(self.v.index_number, int)

    def test_volume_part_empty(self):
        assert self.v.volume_part == ""

    def test_extras(self):
        assert self.v.extras == ["(Digital)", "[Yen Press]"]

    def test_is_one_shot_false(self):
        assert self.v.is_one_shot is False

    def test_is_premium_false(self):
        # test_mode=True skips premium content check for epub too
        assert self.v.is_premium is False

    def test_multi_volume_false(self):
        assert self.v.multi_volume is False

    def test_publisher_from_meta_none(self):
        assert self.v.publisher.from_meta is None

    def test_publisher_from_name_none(self):
        assert self.v.publisher.from_name is None

    def test_subtitle_empty(self):
        assert self.v.subtitle == ""

    def test_release_group_empty(self):
        assert self.v.release_group == ""

    def test_volume_year_none(self):
        assert self.v.volume_year is None

    def test_header_extension_none(self):
        assert self.v.header_extension is None

    def test_name(self):
        assert self.v.name == "Sword Art Online v01 (2020) (Digital) [Yen Press].epub"

    def test_basename(self):
        assert self.v.basename == "Sword Art Online"

    def test_root(self):
        assert self.v.root == "/tmp/nope"


# ===========================================================================
# Golden 4 — My One Shot Story (2020) (Digital) [Group].cbz — ONE-SHOT
# ===========================================================================

class TestOneShotGolden:
    """Full-field pin for a one-shot CBZ (no volume number in filename).

    is_one_shot=True is set by kce.is_one_shot() and then the pipeline
    forces volume_number=1 and index_number=1.
    All assertions were verified against observed production output.
    """

    @pytest.fixture(autouse=True)
    def _build_vol(self):
        self.f, self.v = _build(
            "My One Shot Story (2020) (Digital) [Group].cbz"
        )

    def test_series_name(self):
        assert self.v.series_name == "My One Shot Story"

    def test_is_one_shot_true(self):
        assert self.v.is_one_shot is True

    def test_volume_number_forced_to_1(self):
        # FLAG: is_one_shot=True forces volume_number to 1 via the pipeline
        # (``if file_obj.is_one_shot: file_obj.volume_number = 1``), even though
        # no volume number appears in the filename.
        assert self.v.volume_number == 1
        assert isinstance(self.v.volume_number, int)

    def test_index_number_forced_to_1(self):
        # index_number mirrors volume_number when no part is present
        assert self.v.index_number == 1
        assert isinstance(self.v.index_number, int)

    def test_volume_part_empty(self):
        assert self.v.volume_part == ""

    def test_extras(self):
        assert self.v.extras == ["(Digital)", "[Group]"]

    def test_is_premium_false(self):
        assert self.v.is_premium is False

    def test_multi_volume_false(self):
        assert self.v.multi_volume is False

    def test_file_type(self):
        # One-shots are classified as "volume" by default under test_mode=True
        # (the chapter re-classification code path is skipped in test_mode)
        assert self.v.file_type == "volume"

    def test_extension(self):
        assert self.v.extension == ".cbz"

    def test_subtitle_empty(self):
        assert self.v.subtitle == ""

    def test_release_group_empty(self):
        assert self.v.release_group == ""

    def test_volume_year_none(self):
        assert self.v.volume_year is None

    def test_publisher_from_meta_none(self):
        assert self.v.publisher.from_meta is None

    def test_publisher_from_name_none(self):
        assert self.v.publisher.from_name is None

    def test_name(self):
        assert self.v.name == "My One Shot Story (2020) (Digital) [Group].cbz"

    def test_shortened_series_name_empty(self):
        assert self.v.shortened_series_name == ""


# ===========================================================================
# Golden 5 — Some Series v02 Part 1 (2021) (Digital).cbz — VOLUME WITH PART
# ===========================================================================

class TestVolumePartGolden:
    """Full-field pin for a volume that includes a Part designation.

    Key invariants: volume_number (int), volume_part (int), index_number (float).
    All assertions were verified against observed production output.
    """

    @pytest.fixture(autouse=True)
    def _build_vol(self):
        self.f, self.v = _build(
            "Some Series v02 Part 1 (2021) (Digital).cbz"
        )

    def test_series_name(self):
        assert self.v.series_name == "Some Series"

    def test_volume_number(self):
        assert self.v.volume_number == 2
        assert isinstance(self.v.volume_number, int)

    def test_volume_part(self):
        assert self.v.volume_part == 1
        assert isinstance(self.v.volume_part, int)

    def test_index_number_is_float(self):
        # index_number = volume_number + (volume_part / 10) = 2 + 0.1 = 2.1
        assert self.v.index_number == 2.1
        assert isinstance(self.v.index_number, float)

    def test_extras_contains_part(self):
        # (Part 1) is extracted into extras along with (Digital)
        assert self.v.extras == ["(Digital)", "(Part 1)"]

    def test_is_one_shot_false(self):
        assert self.v.is_one_shot is False

    def test_multi_volume_false(self):
        assert self.v.multi_volume is False

    def test_is_premium_false(self):
        assert self.v.is_premium is False

    def test_subtitle_empty(self):
        assert self.v.subtitle == ""

    def test_release_group_empty(self):
        assert self.v.release_group == ""

    def test_volume_year_none(self):
        assert self.v.volume_year is None

    def test_file_type(self):
        assert self.v.file_type == "volume"

    def test_extension(self):
        assert self.v.extension == ".cbz"

    def test_name(self):
        assert self.v.name == "Some Series v02 Part 1 (2021) (Digital).cbz"

    def test_publisher_from_meta_none(self):
        assert self.v.publisher.from_meta is None

    def test_publisher_from_name_none(self):
        assert self.v.publisher.from_name is None


# ===========================================================================
# Golden 6 — Overlord v01 - The Undead King (2015) (Digital) [Yen Press].cbz
#            — VOLUME WITH SUBTITLE
# ===========================================================================

class TestSubtitleGolden:
    """Full-field pin for a volume with an explicit subtitle.

    The subtitle ``'The Undead King'`` is extracted because the filename
    has both a dash separator and a ``(YYYY)``/``(Digital)`` marker.
    All assertions were verified against observed production output.
    """

    @pytest.fixture(autouse=True)
    def _build_vol(self):
        self.f, self.v = _build(
            "Overlord v01 - The Undead King (2015) (Digital) [Yen Press].cbz"
        )

    def test_series_name(self):
        assert self.v.series_name == "Overlord"

    def test_subtitle(self):
        assert self.v.subtitle == "The Undead King"
        assert isinstance(self.v.subtitle, str)

    def test_volume_number(self):
        assert self.v.volume_number == 1
        assert isinstance(self.v.volume_number, int)

    def test_index_number(self):
        assert self.v.index_number == 1
        assert isinstance(self.v.index_number, int)

    def test_volume_part_empty(self):
        assert self.v.volume_part == ""

    def test_extras(self):
        assert self.v.extras == ["(Digital)", "[Yen Press]"]

    def test_multi_volume_false(self):
        assert self.v.multi_volume is False

    def test_is_one_shot_false(self):
        assert self.v.is_one_shot is False

    def test_is_premium_false(self):
        assert self.v.is_premium is False

    def test_file_type(self):
        assert self.v.file_type == "volume"

    def test_extension(self):
        assert self.v.extension == ".cbz"

    def test_release_group_empty(self):
        assert self.v.release_group == ""

    def test_volume_year_none(self):
        assert self.v.volume_year is None

    def test_publisher_from_meta_none(self):
        assert self.v.publisher.from_meta is None

    def test_publisher_from_name_none(self):
        assert self.v.publisher.from_name is None

    def test_name(self):
        assert self.v.name == "Overlord v01 - The Undead King (2015) (Digital) [Yen Press].cbz"


# ===========================================================================
# Golden 7 — Epub novel with shortened series name
#            (Sword Art Online - Progressive v01 ...)
# ===========================================================================

class TestEpubWithShortenedTitleGolden:
    """Full-field pin for an epub with a dash-separated subtitle in the series name.

    The base series name contains `` - Progressive``, which causes
    ``get_shortened_title`` to extract ``'Sword Art Online'`` as the shortened form.
    All assertions were verified against observed production output.
    """

    @pytest.fixture(autouse=True)
    def _build_vol(self):
        self.f, self.v = _build(
            "Sword Art Online - Progressive v01 (2020) (Digital) [Yen Press].epub"
        )

    def test_series_name(self):
        assert self.v.series_name == "Sword Art Online - Progressive"

    def test_shortened_series_name(self):
        # Dash in series title → shortened to the part before the dash
        assert self.v.shortened_series_name == "Sword Art Online"

    def test_extension(self):
        assert self.v.extension == ".epub"

    def test_volume_number(self):
        assert self.v.volume_number == 1
        assert isinstance(self.v.volume_number, int)

    def test_index_number(self):
        assert self.v.index_number == 1

    def test_volume_part_empty(self):
        assert self.v.volume_part == ""

    def test_extras(self):
        assert self.v.extras == ["(Digital)", "[Yen Press]"]

    def test_is_one_shot_false(self):
        assert self.v.is_one_shot is False

    def test_is_premium_false(self):
        assert self.v.is_premium is False

    def test_multi_volume_false(self):
        assert self.v.multi_volume is False

    def test_subtitle_empty(self):
        # The `` - Progressive`` is PART of the series name, not an episode subtitle
        assert self.v.subtitle == ""

    def test_release_group_empty(self):
        assert self.v.release_group == ""

    def test_volume_year_none(self):
        assert self.v.volume_year is None

    def test_file_type(self):
        assert self.v.file_type == "volume"

    def test_publisher_from_meta_none(self):
        assert self.v.publisher.from_meta is None

    def test_publisher_from_name_none(self):
        assert self.v.publisher.from_name is None

    def test_name(self):
        assert self.v.name == (
            "Sword Art Online - Progressive v01 (2020) (Digital) [Yen Press].epub"
        )


# ===========================================================================
# Scoring engine — get_keyword_scores with real keyword config
# ===========================================================================

class TestKeywordScoring:
    """Pin ``kce.get_keyword_scores`` behaviour.

    With the default (empty) ranked_keywords the score is always 0.0.
    After injecting a small known config, scoring reflects matched keywords.
    The autouse isolated_globals fixture restores ranked_keywords/compiled_searches
    after each test.
    """

    def test_empty_keywords_returns_zero_score(self):
        """Default state: ranked_keywords=[] → score 0.0, no tags matched.

        Observed: RankedKeywordResult(total_score=0.0, keywords=[]).
        """
        _, v = _build("Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz")
        results = kce.get_keyword_scores([v])
        assert len(results) == 1
        r = results[0]
        assert r.total_score == 0.0
        assert r.keywords == []

    def test_matching_keyword_contributes_score(self):
        """'Digital' keyword with score 10.0 fires on a filename containing
        '(Digital)'.

        Observed: total_score=10.0, one keyword matched.
        """
        kce.ranked_keywords = [kce.Keyword("Digital", 10.0, "both")]
        kce.compiled_searches = [
            regex.compile("Digital", regex.IGNORECASE)
        ]
        _, v = _build("Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz")
        results = kce.get_keyword_scores([v])
        r = results[0]
        assert r.total_score == 10.0
        assert len(r.keywords) == 1
        assert r.keywords[0].score == 10.0

    def test_two_matching_keywords_sum_scores(self):
        """Two keywords both match → scores are summed.

        Observed: total_score=15.0 (Digital=10.0 + [Seven Seas]=5.0).
        """
        kce.ranked_keywords = [
            kce.Keyword("Digital", 10.0, "both"),
            kce.Keyword(r"\[Seven Seas\]", 5.0, "both"),
        ]
        kce.compiled_searches = [
            regex.compile(k.name, regex.IGNORECASE) for k in kce.ranked_keywords
        ]
        _, v = _build("Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz")
        results = kce.get_keyword_scores([v])
        r = results[0]
        assert r.total_score == 15.0
        assert len(r.keywords) == 2

    def test_non_matching_keyword_contributes_zero(self):
        """A keyword that does not match the filename does not contribute.

        Observed: total_score=0.0 for a release without 'Premium'.
        """
        kce.ranked_keywords = [kce.Keyword("Premium", -5.0, "both")]
        kce.compiled_searches = [
            regex.compile("Premium", regex.IGNORECASE)
        ]
        _, v = _build("Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz")
        results = kce.get_keyword_scores([v])
        r = results[0]
        assert r.total_score == 0.0
        assert r.keywords == []

    def test_result_type_is_ranked_keyword_result(self):
        """Return value is a list of RankedKeywordResult objects."""
        _, v = _build("Mushoku Tensei v01 (2021) (Digital) [Seven Seas].cbz")
        results = kce.get_keyword_scores([v])
        assert isinstance(results, list)
        assert isinstance(results[0], kce.RankedKeywordResult)

    def test_multiple_releases_scored_independently(self):
        """Two releases scored in one call: each gets its own result entry.

        Digital release scores 10.0; plain release scores 0.0.
        Observed: [10.0, 0.0].
        """
        kce.ranked_keywords = [kce.Keyword("Digital", 10.0, "both")]
        kce.compiled_searches = [
            regex.compile("Digital", regex.IGNORECASE)
        ]
        _, v_digital = _build("Series v01 (Digital).cbz")
        _, v_plain = _build("Series v01.cbz")
        results = kce.get_keyword_scores([v_digital, v_plain])
        assert len(results) == 2
        assert results[0].total_score == 10.0
        assert results[1].total_score == 0.0


# ===========================================================================
# is_upgradeable — upgrade decision logic
# ===========================================================================

class TestIsUpgradeable:
    """Pin ``kce.is_upgradeable`` through the production scoring pipeline.

    is_upgradeable calls get_keyword_scores and compares total_score values.
    An UpgradeResult with is_upgrade=True means the downloaded release has a
    strictly higher score than the current.
    All assertions were verified against observed production output.
    """

    def _setup_keywords(self):
        """Install a minimal known keyword config."""
        kce.ranked_keywords = [
            kce.Keyword("Digital", 10.0, "both"),
            kce.Keyword(r"\[Seven Seas\]", 5.0, "both"),
        ]
        kce.compiled_searches = [
            regex.compile(k.name, regex.IGNORECASE) for k in kce.ranked_keywords
        ]

    def test_higher_score_is_upgrade_true(self):
        """Downloaded release with more matching keywords scores higher → upgrade.

        digital+seven_seas (15.0) > seven_seas_only (5.0) → is_upgrade=True.
        """
        self._setup_keywords()
        _, dl = _build("Mushoku Tensei v01 (Digital) [Seven Seas].cbz")
        _, cur = _build("Mushoku Tensei v01 [Seven Seas].cbz")
        result = kce.is_upgradeable(dl, cur)
        assert result.is_upgrade is True
        assert result.downloaded_ranked_result.total_score == 15.0
        assert result.current_ranked_result.total_score == 5.0

    def test_lower_score_is_upgrade_false(self):
        """Downloaded release with fewer matched keywords → not an upgrade."""
        self._setup_keywords()
        _, dl = _build("Mushoku Tensei v01 [Seven Seas].cbz")
        _, cur = _build("Mushoku Tensei v01 (Digital) [Seven Seas].cbz")
        result = kce.is_upgradeable(dl, cur)
        assert result.is_upgrade is False

    def test_equal_score_is_upgrade_false(self):
        """Equal scores → not an upgrade (strictly greater is required)."""
        self._setup_keywords()
        _, dl = _build("Mushoku Tensei v01 (Digital).cbz")
        _, cur = _build("Mushoku Tensei v01 (Digital).cbz")
        result = kce.is_upgradeable(dl, cur)
        assert result.is_upgrade is False

    def test_same_name_uses_same_ranked_result_object(self):
        """When downloaded and current have the same name, get_keyword_scores is
        called once and the single result is shared for both sides.

        Observed: result.downloaded_ranked_result is result.current_ranked_result.
        """
        self._setup_keywords()
        _, v = _build("Mushoku Tensei v01 (Digital) [Seven Seas].cbz")
        result = kce.is_upgradeable(v, v)
        assert result.downloaded_ranked_result is result.current_ranked_result

    def test_result_type_is_upgrade_result(self):
        """Return type is UpgradeResult."""
        _, v = _build("Series v01.cbz")
        result = kce.is_upgradeable(v, v)
        assert isinstance(result, kce.UpgradeResult)

    def test_no_keywords_both_score_zero_is_upgrade_false(self):
        """With empty ranked_keywords, all releases score 0.0 → never an upgrade."""
        # ranked_keywords is [] by default (autouse fixture restores it)
        _, dl = _build("Series v01 (Digital).cbz")
        _, cur = _build("Series v01.cbz")
        result = kce.is_upgradeable(dl, cur)
        assert result.is_upgrade is False
        assert result.downloaded_ranked_result.total_score == 0.0
        assert result.current_ranked_result.total_score == 0.0


# ===========================================================================
# get_highest_release
# ===========================================================================

class TestGetHighestRelease:
    """Pin ``kce.get_highest_release`` behaviour.

    When ``use_latest_volume_cover_as_series_cover`` is False (default),
    the function always returns ``''``.  When enabled it returns the maximum
    value from the tuple.
    All assertions were verified against observed production output.
    """

    def test_toggle_off_returns_empty_string(self):
        """Default toggle=False: always returns '' regardless of input.

        Observed: ''.
        """
        assert kce.use_latest_volume_cover_as_series_cover is False
        result = kce.get_highest_release((1, 2, 3, 4, 5))
        assert result == ""

    def test_toggle_on_simple_ints_returns_max(self):
        """toggle=True + plain ints (no list/tuple items) → max() result.

        Observed: 5.
        """
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release((1, 2, 3, 4, 5))
        assert result == 5

    def test_toggle_on_mixed_empty_string_returns_max_int(self):
        """toggle=True + mixed ('', int, int): empty string is skipped;
        max integer wins.

        Observed: 2 for ('', 1, 2).
        """
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release(("", 1, 2))
        assert result == 2

    def test_toggle_off_empty_tuple_returns_empty_string(self):
        """Empty release tuple with toggle off → ''.

        Observed: ''.
        """
        assert kce.use_latest_volume_cover_as_series_cover is False
        result = kce.get_highest_release(())
        assert result == ""

    def test_return_type_is_string_when_toggle_off(self):
        """Return type is str (not int) when toggle is off."""
        result = kce.get_highest_release((1, 2))
        assert isinstance(result, str)

    def test_return_type_is_int_when_toggle_on_all_ints(self):
        """Return type is int when toggle is on and all elements are plain ints."""
        kce.use_latest_volume_cover_as_series_cover = True
        kce.get_highest_release.cache_clear()
        result = kce.get_highest_release((3, 7, 2))
        assert isinstance(result, int)
        assert result == 7
