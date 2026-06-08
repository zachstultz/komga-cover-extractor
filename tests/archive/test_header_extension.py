"""Characterization tests for get_header_extension (magic-byte / filetype detection).

Function signature (from komga_cover_extractor.py, lines 2214-2231):

    def get_header_extension(file):
        extension_from_name = get_file_extension(file)
        if extension_from_name in manga_extensions or extension_from_name in rar_extensions:
            try:
                kind = filetype.guess(file)
                if kind is None:
                    return None
                elif f".{kind.extension}" in manga_extensions:
                    return ".cbz"
                elif f".{kind.extension}" in rar_extensions:
                    return ".cbr"
                else:
                    return f".{kind.extension}"
            except Exception as e:
                send_message(str(e), error=True)
                return None
        else:
            return None

Key observations from live runs (characterization, not spec):
- manga_extensions = ['.zip', '.cbz']  (epub is excluded)
- rar_extensions   = ['.rar', '.cbr']
- The function short-circuits to None for ANY extension not in those two sets
  (e.g. .txt, .epub, .7z, no-extension).
- When magic matches a zip-family type, it returns '.cbz' (not '.zip').
- When magic matches a rar-family type, it returns '.cbr' (not '.rar').
- When filetype.guess returns None (unrecognised), the function returns None.
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
import os

import pytest

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tmp(tmp_path, suffix: str, data: bytes) -> str:
    """Write *data* to a temp file with the given suffix, return its str path."""
    p = tmp_path / f"testfile{suffix}"
    p.write_bytes(data)
    return str(p)


def _real_jpeg_bytes() -> bytes:
    """A minimal, genuinely-decodable JPEG image (filetype.guess → 'jpg')."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (220, 50, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def _real_zip_bytes() -> bytes:
    """A real ZIP archive so filetype.guess → 'zip'."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("page_001.jpg", _real_jpeg_bytes())
    return buf.getvalue()


_RAR4_MAGIC = bytes([0x52, 0x61, 0x72, 0x21, 0x1A, 0x07, 0x00]) + b"\x00" * 100
"""Minimal RAR4 header bytes; enough for filetype.guess to recognise RAR."""


# ---------------------------------------------------------------------------
# Core cases: magic wins over file-name extension
# ---------------------------------------------------------------------------

class TestJpegBytesInCbz:
    """JPEG magic bytes inside a .cbz file -> magic wins, returns '.jpg'."""

    def test_returns_jpg_string(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbz", _real_jpeg_bytes())
        result = kce.get_header_extension(path)
        assert result == ".jpg"

    def test_returns_str_not_bytes(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbz", _real_jpeg_bytes())
        result = kce.get_header_extension(path)
        assert isinstance(result, str)


class TestRealZipInCbz:
    """Real ZIP bytes in a .cbz file -> magic reports 'zip', mapped to '.cbz'."""

    def test_returns_cbz_string(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbz", _real_zip_bytes())
        result = kce.get_header_extension(path)
        # ZIP magic -> ".zip" in manga_extensions -> returns ".cbz" (not ".zip")
        assert result == ".cbz"

    def test_returns_str_not_bytes(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbz", _real_zip_bytes())
        result = kce.get_header_extension(path)
        assert isinstance(result, str)


class TestRealZipInZip:
    """Real ZIP bytes in a .zip file -> same mapping, still '.cbz'."""

    def test_returns_cbz_string(self, tmp_path):
        path = _write_tmp(tmp_path, ".zip", _real_zip_bytes())
        result = kce.get_header_extension(path)
        assert result == ".cbz"


class TestCbzFactoryFile:
    """cbz_factory produces a real ZIP; ensure extension detection agrees."""

    def test_cbz_factory_returns_cbz(self, cbz_factory):
        path = cbz_factory(name="Series v01.cbz")
        result = kce.get_header_extension(str(path))
        assert result == ".cbz"


# ---------------------------------------------------------------------------
# RAR magic-byte detection
# ---------------------------------------------------------------------------

class TestRarMagicInCbr:
    """RAR4 magic bytes in a .cbr file -> returns '.cbr'."""

    def test_returns_cbr_string(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbr", _RAR4_MAGIC)
        result = kce.get_header_extension(path)
        assert result == ".cbr"

    def test_returns_str_type(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbr", _RAR4_MAGIC)
        result = kce.get_header_extension(path)
        assert isinstance(result, str)


class TestRarMagicInRar:
    """RAR4 magic bytes in a .rar file -> returns '.cbr' (rar magic -> rar_extensions)."""

    def test_returns_cbr_string(self, tmp_path):
        path = _write_tmp(tmp_path, ".rar", _RAR4_MAGIC)
        result = kce.get_header_extension(path)
        assert result == ".cbr"


class TestRarMagicInCbz:
    """RAR4 magic bytes mis-named as .cbz -> magic wins, returns '.cbr'.

    FLAG: surprising cross-family coercion — a .cbz file that is actually a
    RAR archive is returned as '.cbr', not '.cbz'. This is intentional by
    design (magic beats the file name) but may surprise callers.
    """

    def test_rar_bytes_in_cbz_returns_cbr(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbz", _RAR4_MAGIC)
        result = kce.get_header_extension(path)
        assert result == ".cbr"  # FLAG: magic always wins over the file name


class TestZipBytesInCbr:
    """Real ZIP bytes mis-named as .cbr -> magic reports 'zip', mapped to '.cbz'."""

    def test_zip_in_cbr_returns_cbz(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbr", _real_zip_bytes())
        result = kce.get_header_extension(path)
        assert result == ".cbz"


class TestJpegBytesInRar:
    """JPEG magic bytes in a .rar file -> magic wins, returns '.jpg'."""

    def test_jpeg_in_rar_returns_jpg(self, tmp_path):
        path = _write_tmp(tmp_path, ".rar", _real_jpeg_bytes())
        result = kce.get_header_extension(path)
        assert result == ".jpg"


# ---------------------------------------------------------------------------
# Extension gating: function returns None for extensions not in manga/rar sets
# ---------------------------------------------------------------------------

class TestTextFileExtensions:
    """Files whose extension is not in manga_extensions or rar_extensions -> None."""

    def test_txt_extension_returns_none(self, tmp_path):
        # .txt is not in manga_extensions or rar_extensions; short-circuits immediately
        path = _write_tmp(tmp_path, ".txt", b"hello world plain text")
        result = kce.get_header_extension(path)
        assert result is None  # FLAG: None (not '' or False) for unknown extensions

    def test_epub_extension_returns_none(self, tmp_path):
        # .epub is in zip_extensions but NOT manga_extensions (excluded), so None
        path = _write_tmp(tmp_path, ".epub", _real_zip_bytes())
        result = kce.get_header_extension(path)
        assert result is None  # FLAG: .epub short-circuits even though it is a zip

    def test_seven_zip_extension_returns_none(self, tmp_path):
        # .7z is in convertable_file_extensions but not manga_extensions or rar_extensions
        sevenzip_magic = bytes([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C]) + b"\x00" * 50
        path = _write_tmp(tmp_path, ".7z", sevenzip_magic)
        result = kce.get_header_extension(path)
        assert result is None

    def test_no_extension_returns_none(self, tmp_path):
        # A file with no extension -> get_file_extension returns '' -> not in either set
        path = tmp_path / "noextensionfile"
        path.write_bytes(b"data")
        result = kce.get_header_extension(str(path))
        assert result is None


class TestUnrecognisedMagicInCbz:
    """Unrecognised magic (plain text) inside .cbz -> filetype.guess returns None -> returns None."""

    def test_unrecognised_bytes_in_cbz_returns_none(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbz", b"hello world plain text not an archive")
        result = kce.get_header_extension(path)
        assert result is None  # FLAG: None sentinel when filetype.guess cannot identify

    def test_unrecognised_bytes_in_cbr_returns_none(self, tmp_path):
        path = _write_tmp(tmp_path, ".cbr", b"hello world plain text not an archive")
        result = kce.get_header_extension(path)
        assert result is None


# ---------------------------------------------------------------------------
# Return type assertions across the board
# ---------------------------------------------------------------------------

class TestReturnTypes:
    """Ensure the function never returns unexpected types."""

    @pytest.mark.parametrize("suffix,data,expected", [
        (".cbz", None, ".jpg"),   # jpeg data, recognized image
        (".cbz", "zip", ".cbz"),  # real zip, recognized
        (".cbr", "rar", ".cbr"),  # rar magic, recognized
        (".txt", None, None),     # unknown extension, short-circuit
    ])
    def test_return_type(self, tmp_path, suffix, data, expected):
        if data is None:
            raw = _real_jpeg_bytes()
        elif data == "zip":
            raw = _real_zip_bytes()
        elif data == "rar":
            raw = _RAR4_MAGIC
        else:
            raw = data.encode()

        path = _write_tmp(tmp_path, suffix, raw)
        result = kce.get_header_extension(path)
        assert result == expected
        if expected is not None:
            assert isinstance(result, str)
        else:
            assert result is None
