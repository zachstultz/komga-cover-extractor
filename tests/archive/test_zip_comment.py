"""Characterization tests for get_zip_comment and get_zip_comment_cache.

Both functions read a ZIP/CBZ file's EOCD comment via stdlib zipfile and return
a str (decoded UTF-8). On any error — bad path, non-zip bytes, bad UTF-8 —
they swallow the exception, print an error via send_message, and return ''.

get_zip_comment_cache is the lru_cache(maxsize=None) variant; get_zip_comment
is the uncached variant used for freshly-downloaded files.
"""

from __future__ import annotations

import zipfile

import pytest

import komga_cover_extractor as kce
from _kce_support import clear_all_caches


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_non_zip(tmp_path, name="notazip.cbz") -> "Path":
    """Write raw non-ZIP bytes to a file and return its path."""
    p = tmp_path / name
    p.write_bytes(b"this is not a zip file at all!")
    return p


# ===========================================================================
# get_zip_comment  (uncached)
# ===========================================================================

class TestGetZipComment:
    """Pin exact return types and values for the uncached get_zip_comment."""

    def test_comment_decoded_as_str(self, cbz_factory):
        """cbz_factory(comment=b'release-group-name') -> 'release-group-name' (str)."""
        path = cbz_factory(comment=b"release-group-name")
        result = kce.get_zip_comment(str(path))
        assert result == "release-group-name"
        assert isinstance(result, str)

    def test_comment_returns_exact_decoded_string(self, cbz_factory):
        """The bytes comment is decoded to str via UTF-8 — verify the exact value."""
        path = cbz_factory(comment=b"release-group-name")
        assert kce.get_zip_comment(str(path)) == "release-group-name"

    def test_no_comment_returns_empty_string(self, cbz_factory):
        """Archive with no comment -> '' (empty str, not None)."""
        path = cbz_factory()  # default: no comment set
        result = kce.get_zip_comment(str(path))
        assert result == ""
        assert isinstance(result, str)

    def test_missing_path_returns_empty_string(self):
        """Nonexistent path -> '' (error swallowed, sentinel returned).

        FLAG: the function silently returns '' for missing files instead of raising,
        only emitting a send_message error log.
        """
        result = kce.get_zip_comment("/nonexistent/path/test.cbz")
        assert result == ""
        assert isinstance(result, str)

    def test_non_zip_file_returns_empty_string(self, tmp_path):
        """Non-ZIP file -> '' (BadZipFile error swallowed).

        FLAG: BadZipFile is caught and '' is returned; the caller never sees an exception.
        """
        path = _make_non_zip(tmp_path)
        result = kce.get_zip_comment(str(path))
        assert result == ""
        assert isinstance(result, str)

    def test_invalid_utf8_comment_returns_empty_string(self, tmp_path):
        """Comment bytes that are not valid UTF-8 -> '' (UnicodeDecodeError swallowed).

        FLAG: invalid UTF-8 in the comment is silently swallowed; '' is returned.
        """
        path = tmp_path / "bad_utf8.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("page_001.jpg", b"JFIF")
            zf.comment = b"\xff\xfe"  # invalid UTF-8 start bytes
        result = kce.get_zip_comment(str(path))
        assert result == ""
        assert isinstance(result, str)

    def test_unicode_comment_decoded_correctly(self, tmp_path):
        """Unicode comment (valid UTF-8 bytes) is decoded to a proper Python str."""
        unicode_comment = "manga-group-ユニコード"
        path = tmp_path / "unicode.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("page_001.jpg", b"JFIF")
            zf.comment = unicode_comment.encode("utf-8")
        result = kce.get_zip_comment(str(path))
        assert result == unicode_comment
        assert isinstance(result, str)

    def test_single_char_comment(self, cbz_factory):
        """Minimal comment: a single ASCII byte is decoded to a 1-char str."""
        path = cbz_factory(comment=b"b")
        result = kce.get_zip_comment(str(path))
        assert result == "b"

    def test_returns_str_not_bytes(self, cbz_factory):
        """Return type is always str — raw bytes are never returned."""
        path = cbz_factory(comment=b"grp")
        result = kce.get_zip_comment(str(path))
        assert type(result) is str  # not bytes

    def test_path_object_accepted(self, cbz_factory):
        """Passing a Path object (not str) is also accepted by zipfile.ZipFile."""
        path = cbz_factory(comment=b"release-group-name")
        # Path objects work because zipfile accepts os.PathLike
        result = kce.get_zip_comment(path)
        assert result == "release-group-name"


# ===========================================================================
# get_zip_comment_cache  (lru_cache(maxsize=None))
# ===========================================================================

class TestGetZipCommentCache:
    """Pin return values AND caching behaviour for the cached variant."""

    def test_comment_decoded_as_str(self, cbz_factory):
        """Same decoding as the uncached version: returns a str."""
        path = cbz_factory(comment=b"my-release-group")
        result = kce.get_zip_comment_cache(str(path))
        assert result == "my-release-group"
        assert isinstance(result, str)

    def test_no_comment_returns_empty_string(self, cbz_factory):
        """No comment -> '' (matches uncached behaviour)."""
        path = cbz_factory()
        result = kce.get_zip_comment_cache(str(path))
        assert result == ""
        assert isinstance(result, str)

    def test_missing_path_returns_empty_string(self):
        """Nonexistent path -> '' (error swallowed, same as uncached variant).

        FLAG: silent '' sentinel on missing file.
        """
        result = kce.get_zip_comment_cache("/nonexistent/path/test.cbz")
        assert result == ""
        assert isinstance(result, str)

    def test_maxsize_is_none(self):
        """Cache is unbounded: lru_cache(maxsize=None)."""
        ci = kce.get_zip_comment_cache.cache_info()
        assert ci.maxsize is None

    def test_cache_hit_on_second_call(self, cbz_factory):
        """Second call with the same argument returns a cache hit."""
        path = cbz_factory(comment=b"cached-group")
        clear_all_caches()

        kce.get_zip_comment_cache(str(path))
        kce.get_zip_comment_cache(str(path))

        ci = kce.get_zip_comment_cache.cache_info()
        assert ci.hits >= 1
        assert ci.misses == 1
        assert ci.currsize == 1

    def test_cached_value_matches_first_result(self, cbz_factory):
        """Cached return equals the first computed return."""
        path = cbz_factory(comment=b"cached-group")
        clear_all_caches()

        result1 = kce.get_zip_comment_cache(str(path))
        result2 = kce.get_zip_comment_cache(str(path))
        assert result1 == result2 == "cached-group"

    def test_cache_survives_file_deletion(self, cbz_factory):
        """After the file is deleted the cache still returns the original value.

        Demonstrates that result is memoised from first call, NOT re-read.
        """
        import os
        path = cbz_factory(comment=b"cached-group")
        clear_all_caches()

        result_before = kce.get_zip_comment_cache(str(path))
        os.remove(path)  # delete the file

        result_after = kce.get_zip_comment_cache(str(path))
        assert result_before == result_after == "cached-group"

        ci = kce.get_zip_comment_cache.cache_info()
        assert ci.hits == 1  # second call was a cache hit, not a disk read

    def test_distinct_paths_are_distinct_cache_entries(self, cbz_factory, tmp_path):
        """Two different archive paths are cached independently."""
        path1 = cbz_factory(name="series_a.cbz", comment=b"group-a")
        path2 = cbz_factory(name="series_b.cbz", comment=b"group-b")
        clear_all_caches()

        r1 = kce.get_zip_comment_cache(str(path1))
        r2 = kce.get_zip_comment_cache(str(path2))

        assert r1 == "group-a"
        assert r2 == "group-b"
        assert kce.get_zip_comment_cache.cache_info().currsize == 2

    def test_cache_cleared_by_autouse_fixture(self, cbz_factory):
        """The autouse isolated_globals fixture clears caches between tests.

        If this test sees currsize > 0 before any call, the fixture did not clear.
        """
        ci_before = kce.get_zip_comment_cache.cache_info()
        assert ci_before.currsize == 0

        path = cbz_factory(comment=b"grp")
        kce.get_zip_comment_cache(str(path))
        assert kce.get_zip_comment_cache.cache_info().currsize == 1

    def test_non_zip_file_returns_empty_string(self, tmp_path):
        """Non-ZIP file -> '' (same behaviour as uncached variant).

        FLAG: BadZipFile swallowed; '' cached and returned.
        """
        path = _make_non_zip(tmp_path, "notazip_cached.cbz")
        result = kce.get_zip_comment_cache(str(path))
        assert result == ""
        assert isinstance(result, str)

    def test_unicode_comment(self, tmp_path):
        """Unicode comment round-trips correctly through the cache."""
        unicode_comment = "group-ユニコード"
        path = tmp_path / "unicode_cached.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("page_001.jpg", b"JFIF")
            zf.comment = unicode_comment.encode("utf-8")

        result = kce.get_zip_comment_cache(str(path))
        assert result == unicode_comment
        assert isinstance(result, str)

    def test_invalid_utf8_returns_empty_string(self, tmp_path):
        """Invalid UTF-8 comment bytes -> '' (UnicodeDecodeError swallowed and cached).

        FLAG: '' is cached on first call; subsequent calls return '' from cache.
        """
        path = tmp_path / "bad_utf8_cached.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("page_001.jpg", b"JFIF")
            zf.comment = b"\xff\xfe"
        result = kce.get_zip_comment_cache(str(path))
        assert result == ""
        assert isinstance(result, str)
