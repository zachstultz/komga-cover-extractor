"""Characterization tests for get_file_from_zip and count_images_in_cbz.

get_file_from_zip(zip_file, searches, extension=None, allow_base=True)
  - Reads a member out of a ZIP archive and returns its raw bytes, or None when
    nothing matches.
  - ``searches`` is a list of strings; each is first tried as a plain substring,
    then as a regex (via re.search with IGNORECASE) against either:
      * the basename of each file  (allow_base=True, default)
      * the directory portion of each path  (allow_base=False)
  - ``extension`` filters the member list before searching; pass a string like
    ``'.xml'``.
  - FLAG: extension=None raises TypeError because the list comprehension evaluates
    ``item.endswith(None)`` before reaching the ``or not extension`` short-circuit.
  - Swallows BadZipFile and FileNotFoundError, printing via send_message, and
    returns None.

count_images_in_cbz(file_path)
  - Returns the int count of members whose names end with any extension in
    image_extensions  {'.jpg', '.jpeg', '.png', '.tbn', '.webp'}.
  - Swallows BadZipFile, prints via send_message, and returns 0.
  - FileNotFoundError propagates (not caught internally).
"""

from __future__ import annotations

import zipfile

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bad_zip(tmp_path, name="bad.cbz"):
    """Write non-ZIP bytes to a file; useful for BadZipFile tests."""
    p = tmp_path / name
    p.write_bytes(b"this is not a zip file!")
    return p


# ===========================================================================
# get_file_from_zip
# ===========================================================================

class TestGetFileFromZip:
    """Pin return type, matching logic, filtering, and error handling."""

    # --- return type ---------------------------------------------------------

    def test_returns_bytes_on_match(self, cbz_factory):
        """A successful match returns bytes (the raw file content), not a str."""
        path = cbz_factory(
            entries={
                "ComicInfo.xml": "<ComicInfo/>",
                "page_001.jpg": b"\xff\xd8\xff",
            }
        )
        result = kce.get_file_from_zip(str(path), ["ComicInfo.xml"], extension=".xml")
        assert isinstance(result, bytes)

    def test_content_matches_stored_bytes(self, cbz_factory):
        """The bytes returned exactly equal what was stored in the archive."""
        xml_content = b"<ComicInfo/>"
        path = cbz_factory(entries={"ComicInfo.xml": xml_content})
        result = kce.get_file_from_zip(str(path), ["ComicInfo.xml"], extension=".xml")
        assert result == xml_content

    # --- substring matching --------------------------------------------------

    def test_substring_match_case_insensitive(self, cbz_factory):
        """'comicinfo' (lowercase) matches 'ComicInfo.xml' basename."""
        path = cbz_factory(entries={"ComicInfo.xml": b"<x/>"})
        result = kce.get_file_from_zip(str(path), ["comicinfo"], extension=".xml")
        assert result == b"<x/>"

    def test_uppercase_search_matches_lowercase_filename(self, cbz_factory):
        """Search term is case-folded before comparison — uppercase works too."""
        path = cbz_factory(entries={"ComicInfo.xml": b"<x/>"})
        result = kce.get_file_from_zip(str(path), ["COMICINFO"], extension=".xml")
        assert result == b"<x/>"

    def test_partial_substring_match(self, cbz_factory):
        """'comic' is a partial match for 'comicinfo.xml' basename."""
        path = cbz_factory(entries={"ComicInfo.xml": b"<partial/>"})
        result = kce.get_file_from_zip(str(path), ["comic"], extension=".xml")
        assert result == b"<partial/>"

    def test_multiple_searches_first_term_wins(self, cbz_factory, jpeg_bytes):
        """With two search terms the first-matched file in the zip order is returned."""
        path = cbz_factory(
            entries={
                "ComicInfo.xml": b"<x/>",
                "page_001.jpg": jpeg_bytes(),
            }
        )
        # "comicinfo" should match ComicInfo.xml first (first in zip order)
        result = kce.get_file_from_zip(
            str(path), ["comicinfo", "page"], extension=".xml"
        )
        assert result == b"<x/>"

    # --- regex matching ------------------------------------------------------

    def test_regex_pattern_matches_when_substring_fails(self, cbz_factory, jpeg_bytes):
        r"""A regex pattern like r'page_\d+' matches 'page_001.jpg'."""
        path = cbz_factory(entries={"page_001.jpg": jpeg_bytes()})
        result = kce.get_file_from_zip(
            str(path), [r"page_\d+"], extension=".jpg"
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_regex_case_insensitive(self, cbz_factory, jpeg_bytes):
        """Regex search uses re.IGNORECASE — uppercase pattern matches lowercase name."""
        path = cbz_factory(entries={"page_001.jpg": jpeg_bytes()})
        result = kce.get_file_from_zip(
            str(path), [r"PAGE_\d+"], extension=".jpg"
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    # --- extension filtering -------------------------------------------------

    def test_extension_filters_out_non_matching_files(self, cbz_factory, jpeg_bytes):
        """Searching 'page' with extension='.xml' finds nothing (only JPG pages exist)."""
        path = cbz_factory(entries={"page_001.jpg": jpeg_bytes()})
        result = kce.get_file_from_zip(str(path), ["page"], extension=".xml")
        assert result is None

    def test_extension_jpg_finds_jpg_page(self, cbz_factory, jpeg_bytes):
        """Searching 'page_001' with extension='.jpg' returns the JPEG bytes."""
        jbytes = jpeg_bytes()
        path = cbz_factory(entries={"page_001.jpg": jbytes, "ComicInfo.xml": b"<x/>"})
        result = kce.get_file_from_zip(str(path), ["page_001"], extension=".jpg")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_extension_empty_string_matches_all_files(self, cbz_factory, jpeg_bytes):
        """extension='' matches all members (every filename ends with '').

        FLAG: passing extension='' is NOT the same as extension=None — empty string
        matches every member, whereas None raises TypeError.
        """
        path = cbz_factory(
            entries={
                "ComicInfo.xml": b"<x/>",
                "page_001.jpg": jpeg_bytes(),
            }
        )
        result = kce.get_file_from_zip(str(path), ["page"], extension="")
        # 'page' matches 'page_001.jpg' (first in file_list that satisfies the search)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_extension_none_raises_type_error(self, cbz_factory):
        """extension=None triggers TypeError from item.endswith(None).

        FLAG: the intended default 'match all' behaviour does not work because
        Python evaluates item.endswith(None) before 'or not extension'.
        """
        path = cbz_factory(entries={"page_001.jpg": b"\xff\xd8"})
        with pytest.raises(TypeError):
            kce.get_file_from_zip(str(path), ["page"], extension=None)

    # --- allow_base flag -----------------------------------------------------

    def test_allow_base_true_searches_basename(self, cbz_factory, jpeg_bytes):
        """allow_base=True (default): search term is matched against the filename only."""
        path = cbz_factory(
            entries={
                "page_001.jpg": jpeg_bytes(),
                "sub/page_002.jpg": jpeg_bytes(),
            }
        )
        # 'sub' is a directory name, not a basename — should NOT match when allow_base=True
        result = kce.get_file_from_zip(str(path), ["sub"], extension=".jpg", allow_base=True)
        assert result is None  # FLAG: 'sub' not found in any basename

    def test_allow_base_false_searches_directory_portion(self, cbz_factory, jpeg_bytes):
        """allow_base=False: search term is matched against the directory portion of the path."""
        path = cbz_factory(
            entries={
                "page_001.jpg": jpeg_bytes(),
                "sub/page_002.jpg": jpeg_bytes(),
            }
        )
        # 'sub' matches the directory portion 'sub/' of 'sub/page_002.jpg'
        result = kce.get_file_from_zip(str(path), ["sub"], extension=".jpg", allow_base=False)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_allow_base_false_root_file_falls_back_to_full_path(self, cbz_factory):
        """allow_base=False on a root-level file: directory portion is '', so falls back to full path.

        FLAG: when path.replace(basename, '') == '', mod_file_name falls back to
        path.lower() (the full path), not just the directory. This means a root-level
        'ComicInfo.xml' CAN be found by 'comicinfo' even with allow_base=False.
        """
        path = cbz_factory(entries={"ComicInfo.xml": b"<root/>"})
        result = kce.get_file_from_zip(
            str(path), ["comicinfo"], extension=".xml", allow_base=False
        )
        # FLAG: root-level file with no directory falls back to full path match
        assert result == b"<root/>"

    # --- not-found / sentinel values -----------------------------------------

    def test_not_found_returns_none(self, cbz_factory, jpeg_bytes):
        """No member matches -> return value is exactly None (not '' or False)."""
        path = cbz_factory(entries={"page_001.jpg": jpeg_bytes()})
        result = kce.get_file_from_zip(str(path), ["nonexistent"], extension=".jpg")
        assert result is None

    def test_empty_zip_after_extension_filter_returns_none(self, cbz_factory):
        """If extension filter leaves no members, None is returned immediately."""
        path = cbz_factory(entries={"ComicInfo.xml": b"<x/>"})
        result = kce.get_file_from_zip(str(path), ["comicinfo"], extension=".jpg")
        assert result is None

    # --- error handling: bad zip / missing file ------------------------------

    def test_missing_file_returns_none(self, tmp_path):
        """FileNotFoundError is caught; None is returned (not raised).

        FLAG: the function swallows FileNotFoundError and returns None.
        """
        result = kce.get_file_from_zip(
            str(tmp_path / "nonexistent.cbz"), ["test"], extension=".xml"
        )
        assert result is None

    def test_bad_zip_file_returns_none(self, tmp_path):
        """BadZipFile is caught; None is returned (not raised).

        FLAG: the function swallows BadZipFile and returns None.
        """
        bad = _make_bad_zip(tmp_path)
        result = kce.get_file_from_zip(str(bad), ["test"], extension=".xml")
        assert result is None

    # --- subfolder entries ---------------------------------------------------

    def test_entries_with_comicinfo_and_subdir_pages(self, cbz_factory, jpeg_bytes):
        """Archives with mixed root + subdir entries work correctly."""
        jbytes = jpeg_bytes()
        path = cbz_factory(
            entries={
                "ComicInfo.xml": b"<ComicInfo/>",
                "page_001.jpg": jbytes,
                "sub/page_002.jpg": jbytes,
            }
        )
        xml_result = kce.get_file_from_zip(
            str(path), ["ComicInfo.xml"], extension=".xml"
        )
        assert xml_result == b"<ComicInfo/>"

        jpg_result = kce.get_file_from_zip(
            str(path), ["page_001"], extension=".jpg"
        )
        assert isinstance(jpg_result, bytes)
        assert len(jpg_result) > 0

    def test_path_object_accepted(self, cbz_factory):
        """Passing a pathlib.Path (not str) is accepted by zipfile.ZipFile."""
        path = cbz_factory(entries={"ComicInfo.xml": b"<x/>"})
        # Pass Path directly (not str)
        result = kce.get_file_from_zip(path, ["comicinfo"], extension=".xml")
        assert result == b"<x/>"


# ===========================================================================
# count_images_in_cbz
# ===========================================================================

class TestCountImagesInCbz:
    """Pin the image-count logic, extension coverage, and error handling."""

    # --- basic counts --------------------------------------------------------

    def test_three_jpg_pages_returns_3(self, cbz_factory):
        """cbz_factory(pages=3) -> 3 .jpg members -> count returns 3."""
        path = cbz_factory(pages=3)
        assert kce.count_images_in_cbz(path) == 3

    def test_single_default_page_returns_1(self, cbz_factory):
        """Default cbz_factory() adds one 'page_001.jpg' -> count is 1."""
        path = cbz_factory()
        assert kce.count_images_in_cbz(path) == 1

    def test_zero_images_xml_only_returns_0(self, cbz_factory):
        """Archive with only a ComicInfo.xml (no image extensions) -> 0."""
        path = cbz_factory(entries={"ComicInfo.xml": b"<ComicInfo/>"})
        assert kce.count_images_in_cbz(path) == 0

    def test_return_type_is_int(self, cbz_factory):
        """The return value is always int, not None or bool."""
        path = cbz_factory(pages=2)
        result = kce.count_images_in_cbz(path)
        assert isinstance(result, int)

    # --- extension coverage --------------------------------------------------

    def test_jpg_jpeg_png_tbn_webp_all_counted(self, cbz_factory, jpeg_bytes):
        """All five image_extensions are counted: .jpg .jpeg .png .tbn .webp."""
        jbytes = jpeg_bytes()
        path = cbz_factory(
            entries={
                "page_001.jpg": jbytes,
                "page_002.jpeg": jbytes,
                "page_003.png": jbytes,
                "thumbnail.tbn": jbytes,
                "page_004.webp": jbytes,
                # Non-image entries that must NOT be counted
                "ComicInfo.xml": b"<x/>",
                "thumbs.db": b"not-an-image",
            }
        )
        assert kce.count_images_in_cbz(path) == 5

    def test_non_image_extension_not_counted(self, cbz_factory):
        """Files with non-image extensions (.xml, .db, .txt) are excluded."""
        path = cbz_factory(
            entries={
                "ComicInfo.xml": b"<x/>",
                "thumbs.db": b"data",
                "notes.txt": b"text",
            }
        )
        assert kce.count_images_in_cbz(path) == 0

    def test_tbn_extension_counted(self, cbz_factory, jpeg_bytes):
        """'.tbn' files are included in image_extensions and therefore counted."""
        path = cbz_factory(
            entries={
                "thumbnail.tbn": jpeg_bytes(),
                "page_001.jpg": jpeg_bytes(),
            }
        )
        assert kce.count_images_in_cbz(path) == 2

    def test_extension_check_is_case_insensitive_via_lower(self, cbz_factory, jpeg_bytes):
        """namelist entries are lowercased before endswith check — .JPG is counted.

        FLAG: the production code does f.lower().endswith(tuple(image_extensions)),
        so '.JPG' is treated the same as '.jpg'.
        """
        path = cbz_factory(
            entries={"PAGE_001.JPG": jpeg_bytes()}
        )
        # .JPG lowercased to .jpg which is in image_extensions
        assert kce.count_images_in_cbz(path) == 1

    # --- subfolder pages are counted -----------------------------------------

    def test_pages_in_subdirectories_are_counted(self, cbz_factory, jpeg_bytes):
        """Image files nested in subdirectories are also included in the count."""
        jbytes = jpeg_bytes()
        path = cbz_factory(
            entries={
                "vol01/page_001.jpg": jbytes,
                "vol01/page_002.jpg": jbytes,
                "ComicInfo.xml": b"<x/>",
            }
        )
        assert kce.count_images_in_cbz(path) == 2

    # --- error handling: bad zip / missing file ------------------------------

    def test_bad_zip_returns_0(self, tmp_path):
        """BadZipFile is caught; 0 is returned.

        FLAG: the function swallows BadZipFile and returns the integer 0 (not None).
        """
        bad = _make_bad_zip(tmp_path, "corrupted.cbz")
        result = kce.count_images_in_cbz(str(bad))
        assert result == 0
        assert isinstance(result, int)

    def test_missing_file_raises_file_not_found(self, tmp_path):
        """FileNotFoundError is NOT caught — it propagates to the caller.

        FLAG: unlike get_file_from_zip, count_images_in_cbz does not swallow
        FileNotFoundError; it propagates from zipfile.ZipFile.__init__.
        """
        with pytest.raises(FileNotFoundError):
            kce.count_images_in_cbz(str(tmp_path / "no_such_file.cbz"))

    # --- path forms ----------------------------------------------------------

    def test_accepts_path_object(self, cbz_factory):
        """A pathlib.Path is accepted (zipfile.ZipFile accepts os.PathLike)."""
        path = cbz_factory(pages=2)
        # Pass a Path, not str
        result = kce.count_images_in_cbz(path)
        assert result == 2

    def test_accepts_str_path(self, cbz_factory):
        """A plain str path is accepted."""
        path = cbz_factory(pages=1)
        result = kce.count_images_in_cbz(str(path))
        assert result == 1
