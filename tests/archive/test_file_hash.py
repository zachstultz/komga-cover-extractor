"""Characterization tests for ``kce.get_file_hash``.

Signature (verified via Serena, line 2488 of komga_cover_extractor.py):
    get_file_hash(file, is_internal=False, internal_file_name=None) -> str | None

Implementation notes (pinned as-is):
  * Uses xxhash.xxh64 internally, streaming in 64 KB chunks.
  * Returns the hexdigest as a plain ``str`` (e.g. ``'45ab6734b21e6968'``).
  * For ``is_internal=True`` opens the path as a ZipFile and hashes the named
    member — the internal-member hash matches hashing those raw bytes directly.
  * Catches ``FileNotFoundError``, ``KeyError`` (member not in zip), and all
    other exceptions; in each case calls ``send_message(... error=True)`` and
    returns ``None``.  No exception is propagated to the caller.

All expected hash strings were obtained by running the function against
synthesized in-memory archives / tempfiles in the project's .venv, so they
reflect the actual xxhash library version installed.
"""

from __future__ import annotations

import zipfile

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Known-content hash values (pinned from live runs — do NOT infer from memory)
# ---------------------------------------------------------------------------

#: xxh64 hexdigest for b'hello world'  (verified: '45ab6734b21e6968')
HELLO_WORLD_HASH = "45ab6734b21e6968"

#: xxh64 hexdigest for b'different content'  (verified: 'ea0c19ae9fbd93b3')
DIFFERENT_CONTENT_HASH = "ea0c19ae9fbd93b3"

#: xxh64 hexdigest for an empty byte stream  (verified: 'ef46db3751d8e999')
EMPTY_FILE_HASH = "ef46db3751d8e999"


# ---------------------------------------------------------------------------
# Return type contract
# ---------------------------------------------------------------------------

class TestReturnType:
    """get_file_hash always returns a plain str (never bytes, int, etc.)."""

    def test_returns_str_not_bytes(self, tmp_path):
        """The hexdigest must be a ``str``, not ``bytes``."""
        p = tmp_path / "data.bin"
        p.write_bytes(b"hello world")
        result = kce.get_file_hash(p)
        assert isinstance(result, str)

    def test_known_hello_world_hash(self, tmp_path):
        """Exact xxh64 hexdigest for b'hello world' is pinned."""
        p = tmp_path / "hw.bin"
        p.write_bytes(b"hello world")
        result = kce.get_file_hash(p)
        assert result == HELLO_WORLD_HASH

    def test_empty_file_hash(self, tmp_path):
        """Empty file returns the zero-input xxh64 digest (not None, not '')."""
        p = tmp_path / "empty.bin"
        p.write_bytes(b"")
        result = kce.get_file_hash(p)
        assert result == EMPTY_FILE_HASH
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Same bytes always yield the same hash; different bytes yield different."""

    def test_same_content_same_hash(self, tmp_path):
        """Two files with identical content produce identical hashes."""
        p1 = tmp_path / "a.bin"
        p2 = tmp_path / "b.bin"
        p1.write_bytes(b"hello world")
        p2.write_bytes(b"hello world")
        assert kce.get_file_hash(p1) == kce.get_file_hash(p2)

    def test_different_content_different_hash(self, tmp_path):
        """Two files with different content produce different hashes."""
        p1 = tmp_path / "a.bin"
        p2 = tmp_path / "b.bin"
        p1.write_bytes(b"hello world")
        p2.write_bytes(b"different content")
        h1 = kce.get_file_hash(p1)
        h2 = kce.get_file_hash(p2)
        assert h1 != h2
        assert h1 == HELLO_WORLD_HASH
        assert h2 == DIFFERENT_CONTENT_HASH

    def test_repeated_calls_same_result(self, tmp_path):
        """Calling get_file_hash twice on the same path returns the same value."""
        p = tmp_path / "data.bin"
        p.write_bytes(b"hello world")
        assert kce.get_file_hash(p) == kce.get_file_hash(p)


# ---------------------------------------------------------------------------
# Internal zip-member hashing
# ---------------------------------------------------------------------------

class TestInternalZipMember:
    """is_internal=True opens the file as a ZipFile and hashes the named member."""

    def test_internal_member_hash_matches_raw_bytes(self, cbz_factory):
        """Internal-member hash equals hashing those raw bytes stand-alone."""
        inner = b"hello world"
        cbz = cbz_factory(name="test.cbz", entries={"page_001.jpg": inner})
        result = kce.get_file_hash(cbz, is_internal=True, internal_file_name="page_001.jpg")
        # Internal hash should equal the xxh64 of the raw member bytes
        assert result == HELLO_WORLD_HASH
        assert isinstance(result, str)

    def test_internal_hash_differs_from_outer_file_hash(self, cbz_factory):
        """Outer-zip hash and inner-member hash are NOT equal (zip metadata differs)."""
        inner = b"hello world"
        cbz = cbz_factory(name="test.cbz", entries={"page_001.jpg": inner})
        outer_hash = kce.get_file_hash(cbz)
        inner_hash = kce.get_file_hash(cbz, is_internal=True, internal_file_name="page_001.jpg")
        assert outer_hash is not None
        assert inner_hash is not None
        # FLAG: outer hash includes zip metadata, so it differs from member hash
        assert outer_hash != inner_hash

    def test_internal_member_is_str(self, cbz_factory):
        """Return type for an internal member hash is str."""
        cbz = cbz_factory(name="test.cbz", entries={"page_001.jpg": b"hello world"})
        result = kce.get_file_hash(cbz, is_internal=True, internal_file_name="page_001.jpg")
        assert isinstance(result, str)

    def test_two_internal_members_same_content_same_hash(self, tmp_path):
        """Two zip members with identical bytes yield the same hash."""
        cbz = tmp_path / "dual.cbz"
        content = b"hello world"
        with zipfile.ZipFile(cbz, "w") as zf:
            zf.writestr("page_001.jpg", content)
            zf.writestr("page_002.jpg", content)
        h1 = kce.get_file_hash(cbz, is_internal=True, internal_file_name="page_001.jpg")
        h2 = kce.get_file_hash(cbz, is_internal=True, internal_file_name="page_002.jpg")
        assert h1 == h2 == HELLO_WORLD_HASH

    def test_two_internal_members_different_content_different_hash(self, tmp_path):
        """Two zip members with different bytes yield different hashes."""
        cbz = tmp_path / "dual.cbz"
        with zipfile.ZipFile(cbz, "w") as zf:
            zf.writestr("page_001.jpg", b"hello world")
            zf.writestr("page_002.jpg", b"different content")
        h1 = kce.get_file_hash(cbz, is_internal=True, internal_file_name="page_001.jpg")
        h2 = kce.get_file_hash(cbz, is_internal=True, internal_file_name="page_002.jpg")
        assert h1 == HELLO_WORLD_HASH
        assert h2 == DIFFERENT_CONTENT_HASH
        assert h1 != h2


# ---------------------------------------------------------------------------
# Error / sentinel paths — all return None, never raise
# ---------------------------------------------------------------------------

class TestSentinelOnError:
    """All error paths return None without propagating any exception."""

    def test_missing_file_returns_none(self, tmp_path):
        """A path that does not exist returns None (FileNotFoundError swallowed)."""
        missing = tmp_path / "does_not_exist.bin"
        result = kce.get_file_hash(missing)
        # FLAG: errors are swallowed; None is the sentinel for all failure modes
        assert result is None

    def test_missing_file_does_not_raise(self, tmp_path):
        """FileNotFoundError must not propagate to the caller."""
        missing = tmp_path / "ghost.bin"
        # Should not raise — characterization confirms the try/except swallows it
        kce.get_file_hash(missing)  # no pytest.raises needed — must NOT raise

    def test_nonexistent_internal_member_returns_none(self, cbz_factory):
        """Asking for a member not in the zip returns None (KeyError swallowed)."""
        cbz = cbz_factory(name="test.cbz", entries={"page_001.jpg": b"hello world"})
        result = kce.get_file_hash(
            cbz, is_internal=True, internal_file_name="nonexistent_member.jpg"
        )
        # FLAG: KeyError for missing zip member is swallowed and returns None
        assert result is None

    def test_nonexistent_internal_member_does_not_raise(self, cbz_factory):
        """KeyError for a missing zip member must not propagate to caller."""
        cbz = cbz_factory(name="test.cbz", entries={"page_001.jpg": b"data"})
        # Must not raise
        kce.get_file_hash(cbz, is_internal=True, internal_file_name="no_such.jpg")
