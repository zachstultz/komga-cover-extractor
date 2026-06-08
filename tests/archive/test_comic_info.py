"""Characterization tests for contains_comic_info (lru_cached) and
parse_comicinfo_xml (xmltodict-backed).

Design notes
------------
* All return values are pinned from *actual* function invocations observed via
  the .venv interpreter.  Where the current behaviour is surprising, a
  ``# FLAG:`` comment is attached.
* ``isolated_globals`` (autouse) clears every lru_cache before and after each
  test, so cache-persistence tests that intentionally *keep* the cache warm use
  an explicit call sequence within the same test body.
* ``parse_comicinfo_xml`` takes a raw XML *string* (not a path, not a file
  object) and delegates to ``xmltodict.parse``.
"""

from __future__ import annotations

import zipfile

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# contains_comic_info
# ---------------------------------------------------------------------------

class TestContainsComicInfo:
    """Pin the behaviour of the lru_cached contains_comic_info function."""

    def test_archive_with_comicinfo_xml_returns_true(self, cbz_factory, comicinfo_xml):
        """A cbz that contains ComicInfo.xml at the root → True."""
        path = cbz_factory(comicinfo_xml=comicinfo_xml(Title="T"))
        assert kce.contains_comic_info(str(path)) is True

    def test_archive_without_comicinfo_xml_returns_false(self, cbz_factory):
        """A cbz that has only image pages and no ComicInfo.xml → False."""
        path = cbz_factory()  # default: single page_001.jpg, no ComicInfo
        assert kce.contains_comic_info(str(path)) is False

    def test_lowercase_comicinfo_xml_returns_true(self, cbz_factory):
        """The check is case-insensitive: 'comicinfo.xml' (all lower) → True."""
        path = cbz_factory(entries={
            "page_001.jpg": b"FAKE",
            "comicinfo.xml": "<ComicInfo><Title>T</Title></ComicInfo>",
        })
        assert kce.contains_comic_info(str(path)) is True

    def test_uppercase_comicinfo_xml_returns_true(self, cbz_factory):
        """The check is case-insensitive: 'COMICINFO.XML' (all upper) → True."""
        path = cbz_factory(entries={
            "page_001.jpg": b"FAKE",
            "COMICINFO.XML": "<ComicInfo><Title>T</Title></ComicInfo>",
        })
        assert kce.contains_comic_info(str(path)) is True

    def test_corrupt_non_zip_file_returns_false(self, tmp_path):
        """A file that is not a valid zip (BadZipFile) → False (exception swallowed)."""
        corrupt = tmp_path / "corrupt.cbz"
        corrupt.write_bytes(b"NOT A ZIP FILE AT ALL")
        # FLAG: BadZipFile is caught and silently returns False (after logging).
        result = kce.contains_comic_info(str(corrupt))
        assert result is False

    def test_missing_file_path_returns_false(self):
        """A path that does not exist on disk → False (FileNotFoundError swallowed)."""
        # FLAG: FileNotFoundError is caught and silently returns False (after logging).
        result = kce.contains_comic_info("/nonexistent/path/to/archive.cbz")
        assert result is False

    def test_return_type_is_bool_when_true(self, cbz_factory, comicinfo_xml):
        """Return value is a Python bool (True), not just truthy."""
        path = cbz_factory(comicinfo_xml=comicinfo_xml(Title="T"))
        result = kce.contains_comic_info(str(path))
        assert result is True
        assert type(result) is bool

    def test_return_type_is_bool_when_false(self, cbz_factory):
        """Return value is a Python bool (False), not just falsy."""
        path = cbz_factory()
        result = kce.contains_comic_info(str(path))
        assert result is False
        assert type(result) is bool

    def test_lru_cache_serves_stale_result(self, tmp_path):
        """lru_cache means the result is memoised by path string.

        If the archive is overwritten *after* the first call, the cached (stale)
        value is returned.  This is the expected, pinned behaviour of the cache.
        """
        archive = tmp_path / "vol.cbz"

        # First: write an archive WITHOUT ComicInfo.xml → cached as False.
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("page_001.jpg", b"FAKE")
        first = kce.contains_comic_info(str(archive))
        assert first is False

        # Overwrite in-place WITH ComicInfo.xml; cache is NOT cleared between calls.
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("page_001.jpg", b"FAKE")
            zf.writestr("ComicInfo.xml", "<ComicInfo><Title>T</Title></ComicInfo>")
        second = kce.contains_comic_info(str(archive))
        # FLAG: stale cache hit — reports False even though the file now has ComicInfo.xml.
        assert second is False

    def test_mixed_casing_entry_alongside_page(self, cbz_factory):
        """ComicInfo.xml mixed case alongside image pages is detected."""
        path = cbz_factory(
            entries={
                "page_001.jpg": b"FAKE",
                "page_002.jpg": b"FAKE",
                "CoMiCiNfO.XmL": "<ComicInfo><Title>T</Title></ComicInfo>",
            }
        )
        assert kce.contains_comic_info(str(path)) is True


# ---------------------------------------------------------------------------
# parse_comicinfo_xml
# ---------------------------------------------------------------------------

class TestParseComicInfoXml:
    """Pin the behaviour of parse_comicinfo_xml, which takes a raw XML string."""

    def test_valid_xml_returns_dict(self, comicinfo_xml):
        """A well-formed ComicInfo.xml string returns a plain dict."""
        xml = comicinfo_xml(Title="T", Volume="3")
        result = kce.parse_comicinfo_xml(xml)
        assert isinstance(result, dict)

    def test_valid_xml_title_and_volume_exact_structure(self, comicinfo_xml):
        """Exact keys and string values for a two-field ComicInfo XML.

        The conftest ``comicinfo_xml`` fixture emits namespace attributes, so
        xmltodict surfaces them as '@xmlns:xsi' and '@xmlns:xsd' keys in
        addition to the field keys.  All leaf values are strings, not ints.
        """
        xml = comicinfo_xml(Title="T", Volume="3")
        result = kce.parse_comicinfo_xml(xml)
        assert result["Title"] == "T"
        assert result["Volume"] == "3"           # volume is a string, not int
        assert result["@xmlns:xsi"] == "http://www.w3.org/2001/XMLSchema-instance"
        assert result["@xmlns:xsd"] == "http://www.w3.org/2001/XMLSchema"

    def test_valid_xml_keys_are_exact_set(self, comicinfo_xml):
        """The returned dict has exactly the keys produced by xmltodict — no extras."""
        xml = comicinfo_xml(Title="T", Volume="3")
        result = kce.parse_comicinfo_xml(xml)
        expected_keys = {"@xmlns:xsi", "@xmlns:xsd", "Title", "Volume"}
        assert set(result.keys()) == expected_keys

    def test_minimal_xml_no_ns_attrs(self):
        """Without namespace declarations, no '@xmlns:*' keys appear in result."""
        xml = "<ComicInfo><Title>T</Title><Volume>3</Volume></ComicInfo>"
        result = kce.parse_comicinfo_xml(xml)
        assert result == {"Title": "T", "Volume": "3"}

    def test_volume_value_is_string_not_int(self):
        """xmltodict returns ALL leaf values as strings (no type coercion)."""
        xml = "<ComicInfo><Volume>5</Volume></ComicInfo>"
        result = kce.parse_comicinfo_xml(xml)
        assert result["Volume"] == "5"
        assert type(result["Volume"]) is str

    def test_malformed_xml_returns_empty_dict(self):
        """Malformed / invalid XML → {} (exception caught, empty dict returned)."""
        # FLAG: parse errors are swallowed; caller receives {} rather than an exception.
        result = kce.parse_comicinfo_xml("<ComicInfo><Title>T</ComicInfo BROKEN")
        assert result == {}

    def test_none_input_returns_empty_dict(self):
        """None → {} (the ``if xml_file:`` guard short-circuits before xmltodict)."""
        result = kce.parse_comicinfo_xml(None)
        assert result == {}

    def test_empty_string_returns_empty_dict(self):
        """Empty string '' → {} (falsy, so guard short-circuits)."""
        result = kce.parse_comicinfo_xml("")
        assert result == {}

    def test_false_returns_empty_dict(self):
        """Boolean False → {} (falsy, guard short-circuits)."""
        result = kce.parse_comicinfo_xml(False)
        assert result == {}

    def test_zero_returns_empty_dict(self):
        """Integer 0 → {} (falsy, guard short-circuits)."""
        result = kce.parse_comicinfo_xml(0)
        assert result == {}

    def test_whitespace_string_returns_empty_dict(self):
        """Whitespace-only string is truthy so xmltodict IS called → parse error → {}.

        FLAG: unlike empty string, '   ' passes the truthiness check and reaches
        xmltodict.parse, which raises 'no element found'; that exception is caught
        and {} is returned.
        """
        result = kce.parse_comicinfo_xml("   ")
        assert result == {}

    def test_no_comicinfo_root_returns_empty_dict(self):
        """Well-formed XML but with a different root element → {} (no 'ComicInfo' key)."""
        result = kce.parse_comicinfo_xml("<Root><Title>T</Title></Root>")
        assert result == {}

    def test_empty_comicinfo_root_with_ns(self):
        """ComicInfo element with no child tags but namespace attrs → dict with ns keys only."""
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            "</ComicInfo>"
        )
        result = kce.parse_comicinfo_xml(xml)
        assert result == {
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "@xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        }

    def test_empty_tag_value_is_none(self):
        """An empty child element (``<Title/>``) → None value in the dict.

        FLAG: xmltodict represents empty tags as None, not as empty string ''.
        """
        xml = "<ComicInfo><Title></Title><Volume>3</Volume></ComicInfo>"
        result = kce.parse_comicinfo_xml(xml)
        assert result["Title"] is None          # FLAG: empty tag → None, not ''
        assert result["Volume"] == "3"

    def test_multiple_fields_returned_intact(self, comicinfo_xml):
        """All provided fields survive round-trip through xmltodict."""
        xml = comicinfo_xml(Title="My Title", Volume="3", Year="2020", Publisher="Viz")
        result = kce.parse_comicinfo_xml(xml)
        assert result["Title"] == "My Title"
        assert result["Volume"] == "3"
        assert result["Year"] == "2020"
        assert result["Publisher"] == "Viz"

    def test_return_type_is_dict_on_success(self):
        """The successful path returns a plain dict, not an OrderedDict or subclass."""
        xml = "<ComicInfo><Title>T</Title></ComicInfo>"
        result = kce.parse_comicinfo_xml(xml)
        assert type(result) is dict

    def test_return_type_is_dict_on_failure(self):
        """The error path also returns a plain dict ({})."""
        result = kce.parse_comicinfo_xml(None)
        assert type(result) is dict

    def test_integer_truthy_input_returns_empty_dict(self):
        """A truthy non-string (int 42) reaches xmltodict → TypeError caught → {}.

        FLAG: the guard only checks truthiness, not type; any truthy non-string
        value causes xmltodict to raise, which is silently caught.
        """
        result = kce.parse_comicinfo_xml(42)
        assert result == {}


# ---------------------------------------------------------------------------
# Integration: contains_comic_info + parse_comicinfo_xml together
# ---------------------------------------------------------------------------

class TestComicInfoIntegration:
    """Verify the typical call sequence: detect presence, then parse content."""

    def test_detect_then_parse_full_round_trip(self, cbz_factory, comicinfo_xml):
        """If contains_comic_info is True, the XML content can be parsed directly."""
        xml_str = comicinfo_xml(Title="RoundTrip", Volume="7")
        path = cbz_factory(comicinfo_xml=xml_str)

        assert kce.contains_comic_info(str(path)) is True

        # Read the stored XML back out and parse it (simulating what the production
        # code does: open the zip, read 'ComicInfo.xml', feed it to parse_comicinfo_xml).
        import zipfile as _zf
        with _zf.ZipFile(str(path)) as z:
            # The entry was stored as 'ComicInfo.xml' by the fixture.
            xml_content = z.read("ComicInfo.xml").decode("utf-8")

        parsed = kce.parse_comicinfo_xml(xml_content)
        assert parsed["Title"] == "RoundTrip"
        assert parsed["Volume"] == "7"

    def test_detect_false_no_parse_needed(self, cbz_factory):
        """Archives without ComicInfo.xml: detect returns False, no parse needed."""
        path = cbz_factory()
        assert kce.contains_comic_info(str(path)) is False
