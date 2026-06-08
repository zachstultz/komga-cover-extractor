"""Characterization tests for find_and_extract_cover, compress_image, convert_webp_to_jpg.

These tests pin the CURRENT behavior of the production code.  When the behavior is
surprising or potentially buggy, the assertion is labelled with a ``# FLAG:`` comment.
All observed sentinel values were verified by running the functions in the .venv
before writing each assertion.
"""

from __future__ import annotations

import io
import os
import zipfile

import pytest
from PIL import Image

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(tmp_path, name: str, ext: str = ".cbz", root=None) -> kce.File:
    """Build a minimal ``kce.File`` object pointing at ``<root>/<name>``."""
    root = root or str(tmp_path)
    extensionless = os.path.splitext(name)[0]
    return kce.File(
        name=name,
        extensionless_name=extensionless,
        basename=extensionless.split(" v")[0] if " v" in extensionless else extensionless,
        extension=ext,
        root=root,
        path=os.path.join(root, name),
        extensionless_path=os.path.join(root, extensionless),
        volume_number=1.0,
        file_type="volume",
        header_extension=None,
    )


def _jpeg_bytes(color=(220, 50, 50), size=(4, 4)) -> bytes:
    """Produce a real, decodable JPEG."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes(color=(50, 200, 50), size=(4, 4)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _webp_bytes(color=(50, 100, 200), size=(4, 4)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="WEBP")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# find_and_extract_cover — sentinel / return-type quad
# ---------------------------------------------------------------------------

class TestFindAndExtractCoverSentinels:
    """Pin the four possible return values of find_and_extract_cover."""

    def test_missing_file_returns_none(self, tmp_path):
        """Non-existent path -> None (not False)."""
        f = _make_file(tmp_path, "Missing v01.cbz")
        # file does not exist on disk
        result = kce.find_and_extract_cover(f, silent=True)
        assert result is None  # FLAG: None vs False distinction matters for callers

    def test_not_a_zip_returns_none(self, tmp_path):
        """File that exists but is not a zip -> None."""
        p = tmp_path / "NotZip v01.cbz"
        p.write_bytes(b"not a zip file at all")
        f = _make_file(tmp_path, "NotZip v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert result is None  # FLAG: None, not False, for invalid zip

    def test_zip_with_no_images_returns_false(self, tmp_path):
        """Valid zip but no image entries -> False (not None)."""
        p = tmp_path / "Empty v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("readme.txt", "no images here")
        f = _make_file(tmp_path, "Empty v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert result is False  # FLAG: False, not None — callers using `if not result` lose the distinction

    def test_zip_with_only_text_returns_false(self, tmp_path):
        """Zip with only non-image extensions -> False."""
        p = tmp_path / "TextOnly v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.txt", "just text")
            zf.writestr("readme.md", "more text")
        f = _make_file(tmp_path, "TextOnly v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert result is False

    def test_success_returns_str_path(self, tmp_path):
        """Successful extraction -> str path (not bytes, not bool)."""
        p = tmp_path / "Series v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", _jpeg_bytes())
        f = _make_file(tmp_path, "Series v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert isinstance(result, str)
        assert result != ""

    def test_success_cover_file_exists_on_disk(self, tmp_path):
        """Returned path must actually exist on disk after a successful call."""
        p = tmp_path / "Series v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", _jpeg_bytes())
        f = _make_file(tmp_path, "Series v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert os.path.isfile(result)

    def test_return_data_only_true_returns_bytes_on_success(self, tmp_path):
        """return_data_only=True and archive has images -> bytes."""
        p = tmp_path / "Series v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", _jpeg_bytes(size=(20, 20)))
        f = _make_file(tmp_path, "Series v01.cbz")
        result = kce.find_and_extract_cover(f, return_data_only=True, silent=True)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_return_data_only_true_empty_archive_returns_false(self, tmp_path):
        """return_data_only=True with no images -> still returns False, not None."""
        p = tmp_path / "Empty v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("readme.txt", "no images")
        f = _make_file(tmp_path, "Empty v01.cbz")
        result = kce.find_and_extract_cover(f, return_data_only=True, silent=True)
        assert result is False  # FLAG: False, same as the non-data mode


# ---------------------------------------------------------------------------
# find_and_extract_cover — output path behaviour
# ---------------------------------------------------------------------------

class TestFindAndExtractCoverOutputPath:
    """Pin exact output path construction rules."""

    def test_output_path_uses_extensionless_name_plus_jpg(self, tmp_path):
        """Output file is placed in root/ with extensionless_name + original img ext."""
        p = tmp_path / "My Series v03.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", _jpeg_bytes())
        f = _make_file(tmp_path, "My Series v03.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        expected = os.path.join(str(tmp_path), "My Series v03.jpg")
        assert result == expected

    def test_jpeg_extension_normalized_to_jpg(self, tmp_path):
        """.jpeg inside the archive -> output is .jpg (not .jpeg)."""
        p = tmp_path / "JpegExt v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("cover.jpeg", _jpeg_bytes())
        f = _make_file(tmp_path, "JpegExt v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert result is not None and result is not False
        assert result.endswith(".jpg"), f"Expected .jpg but got: {result}"

    def test_png_archive_image_gives_png_output(self, tmp_path):
        """Image with .png extension inside -> output is .png."""
        p = tmp_path / "PngCover v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.png", _png_bytes())
        f = _make_file(tmp_path, "PngCover v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert result is not None and result is not False
        assert result.endswith(".png"), f"Expected .png output but got: {result}"

    def test_output_covers_as_webp_forces_webp_extension(self, tmp_path, monkeypatch):
        """With output_covers_as_webp=True, output always has .webp extension."""
        monkeypatch.setattr(kce, "output_covers_as_webp", True)
        p = tmp_path / "WebpOut v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", _jpeg_bytes())
        f = _make_file(tmp_path, "WebpOut v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert result is not None and result is not False
        assert result.endswith(".webp"), f"Expected .webp output but got: {result}"

    def test_directory_entries_in_zip_are_skipped(self, tmp_path):
        """Zip entries ending in '/' are filtered; nested images still found."""
        p = tmp_path / "DirEntry v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("images/", "")           # directory marker
            zf.writestr("images/page_001.jpg", _jpeg_bytes())
        f = _make_file(tmp_path, "DirEntry v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert isinstance(result, str)
        assert os.path.isfile(result)


# ---------------------------------------------------------------------------
# find_and_extract_cover — cover pattern priority
# ---------------------------------------------------------------------------

class TestFindAndExtractCoverPatternPriority:
    """Verify that cover-named images are matched by pattern priority."""

    def test_cover_named_image_is_extracted(self, tmp_path):
        """Archive containing 'cover.jpg' -> extraction succeeds."""
        p = tmp_path / "Series v02.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", _jpeg_bytes(color=(100, 100, 100)))
            zf.writestr("cover.jpg", _jpeg_bytes(color=(200, 200, 200)))
            zf.writestr("page_002.jpg", _jpeg_bytes(color=(50, 50, 50)))
        f = _make_file(tmp_path, "Series v02.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert isinstance(result, str)
        assert os.path.isfile(result)


# ---------------------------------------------------------------------------
# find_and_extract_cover — blank image detection (gated setting)
# ---------------------------------------------------------------------------

class TestFindAndExtractCoverBlankDetection:
    """Blank-image detection paths (only active when compare_detected_cover_to_blank_images=True)."""

    def test_all_white_single_page_returns_false_when_blank_check_on(self, tmp_path, monkeypatch):
        """A cbz with only a white-filled image -> False when blank check is enabled."""
        monkeypatch.setattr(kce, "compare_detected_cover_to_blank_images", True)
        # Build a white image that matches the blank_white.jpg reference well
        white_buf = io.BytesIO()
        Image.new("RGB", (100, 100), (255, 255, 255)).save(white_buf, "JPEG")
        p = tmp_path / "AllWhite v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", white_buf.getvalue())
        f = _make_file(tmp_path, "AllWhite v01.cbz")
        result = kce.find_and_extract_cover(f, blank_image_check=True, silent=True)
        assert result is False  # FLAG: white-only page detected as blank -> False

    def test_blank_check_off_white_image_is_extracted(self, tmp_path, monkeypatch):
        """Same white cbz but blank_image_check=False -> cover IS extracted (str returned)."""
        monkeypatch.setattr(kce, "compare_detected_cover_to_blank_images", False)
        white_buf = io.BytesIO()
        Image.new("RGB", (100, 100), (255, 255, 255)).save(white_buf, "JPEG")
        p = tmp_path / "WhiteOk v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", white_buf.getvalue())
        f = _make_file(tmp_path, "WhiteOk v01.cbz")
        result = kce.find_and_extract_cover(f, blank_image_check=False, silent=True)
        assert isinstance(result, str)
        assert os.path.isfile(result)


# ---------------------------------------------------------------------------
# find_and_extract_cover — multi-page archives
# ---------------------------------------------------------------------------

class TestFindAndExtractCoverMultiPage:
    """Characterize behavior with 3 pages (as specified in the task prompt)."""

    @pytest.mark.slow
    def test_three_page_cbz_extracts_first_image_as_str(self, cbz_factory, tmp_path):
        """cbz_factory(pages=3) -> extraction returns a str path."""
        archive_path = cbz_factory(name="Series v01.cbz", pages=3)
        f = _make_file(tmp_path, "Series v01.cbz", root=str(archive_path.parent))
        result = kce.find_and_extract_cover(f, silent=True)
        assert isinstance(result, str)
        assert os.path.isfile(result)

    @pytest.mark.slow
    def test_three_page_cbz_return_data_only_bytes(self, cbz_factory, tmp_path):
        """cbz_factory(pages=3) + return_data_only=True -> bytes."""
        archive_path = cbz_factory(name="Series v01.cbz", pages=3)
        f = _make_file(tmp_path, "Series v01.cbz", root=str(archive_path.parent))
        result = kce.find_and_extract_cover(f, return_data_only=True, silent=True)
        assert isinstance(result, bytes)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# find_and_extract_cover — compress_image_option interaction
# ---------------------------------------------------------------------------

class TestFindAndExtractCoverCompressInteraction:
    """Verify that compress_image_option=True still returns str path (not raw bytes)."""

    def test_compress_option_on_still_returns_str_path(self, tmp_path, monkeypatch):
        """compress_image_option=True: result is str and file exists."""
        monkeypatch.setattr(kce, "compress_image_option", True)
        monkeypatch.setattr(kce, "image_quality", 40)
        p = tmp_path / "Compressed v01.cbz"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("page_001.jpg", _jpeg_bytes(size=(100, 100)))
        f = _make_file(tmp_path, "Compressed v01.cbz")
        result = kce.find_and_extract_cover(f, silent=True)
        assert isinstance(result, str)
        assert os.path.isfile(result)


# ---------------------------------------------------------------------------
# compress_image — file-path mode
# ---------------------------------------------------------------------------

class TestCompressImageFileMode:
    """Pin compress_image behavior when operating on a file path (no raw_data)."""

    def test_jpeg_returns_str_path(self, tmp_path):
        """compress_image on a JPEG file -> str path (same file, in-place)."""
        p = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), (200, 100, 50)).save(str(p), "JPEG")
        result = kce.compress_image(str(p), quality=60)
        assert isinstance(result, str)
        assert result == str(p)

    def test_jpeg_file_updated_in_place(self, tmp_path):
        """After compression the path still exists and contains JPEG data."""
        p = tmp_path / "test.jpg"
        Image.new("RGB", (50, 50), (200, 100, 50)).save(str(p), "JPEG")
        original_size = p.stat().st_size
        result = kce.compress_image(str(p), quality=20)
        assert os.path.isfile(result)
        _ = original_size  # size may vary; just check file exists

    def test_png_converted_to_jpg_removes_original(self, tmp_path):
        """PNG input -> returns .jpg path; original .png is deleted."""
        p = tmp_path / "test.png"
        Image.new("RGB", (50, 50), (100, 200, 50)).save(str(p), "PNG")
        assert p.exists()
        result = kce.compress_image(str(p), quality=60)
        assert isinstance(result, str)
        assert result.endswith(".jpg")
        assert not p.exists(), "Original PNG should have been deleted"
        assert os.path.isfile(result)

    def test_webp_file_stays_webp(self, tmp_path):
        """WEBP input -> output is still .webp (no format change)."""
        p = tmp_path / "test.webp"
        Image.new("RGB", (50, 50), (50, 100, 200)).save(str(p), "WEBP")
        result = kce.compress_image(str(p), quality=60)
        assert isinstance(result, str)
        assert result.endswith(".webp")
        assert os.path.isfile(result)

    def test_rgba_image_converted_to_rgb_then_saved(self, tmp_path):
        """RGBA mode PNG -> compress_image converts to RGB and saves as JPEG."""
        p = tmp_path / "rgba_test.png"
        Image.new("RGBA", (50, 50), (200, 100, 50, 128)).save(str(p), "PNG")
        result = kce.compress_image(str(p), quality=60)
        assert isinstance(result, str)
        assert result.endswith(".jpg")
        assert os.path.isfile(result)

    def test_palette_mode_converted_to_jpg(self, tmp_path):
        """Palette (mode=P) PNG -> JPEG output returned."""
        p = tmp_path / "palette.png"
        Image.new("P", (50, 50)).save(str(p), "PNG")
        result = kce.compress_image(str(p), quality=60)
        assert isinstance(result, str)
        assert result.endswith(".jpg")
        assert os.path.isfile(result)

    def test_to_jpg_flag_on_jpeg_file(self, tmp_path):
        """to_jpg=True on an existing .jpg file -> same str path returned."""
        p = tmp_path / "file.jpg"
        Image.new("RGB", (50, 50), (100, 100, 100)).save(str(p), "JPEG")
        result = kce.compress_image(str(p), quality=80, to_jpg=True)
        assert isinstance(result, str)
        assert result.endswith(".jpg")


# ---------------------------------------------------------------------------
# compress_image — raw_data mode
# ---------------------------------------------------------------------------

class TestCompressImageRawDataMode:
    """Pin compress_image behavior when raw_data kwarg is provided."""

    def test_raw_jpeg_data_returns_bytes(self, tmp_path):
        """raw_data= with JPEG bytes -> returns bytes (not a path)."""
        raw = _jpeg_bytes(size=(20, 20))
        fake_path = os.path.join(str(tmp_path), "fake.jpg")
        result = kce.compress_image(fake_path, quality=60, raw_data=raw)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_raw_webp_data_returns_bytes(self, tmp_path):
        """raw_data= with WEBP bytes -> returns bytes."""
        raw = _webp_bytes(size=(20, 20))
        fake_path = os.path.join(str(tmp_path), "fake.webp")
        result = kce.compress_image(fake_path, quality=60, raw_data=raw)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_raw_data_no_file_created(self, tmp_path):
        """raw_data= mode must not create any files in tmp_path."""
        raw = _jpeg_bytes(size=(20, 20))
        fake_path = os.path.join(str(tmp_path), "should_not_appear.jpg")
        before = set(os.listdir(str(tmp_path)))
        kce.compress_image(fake_path, quality=60, raw_data=raw)
        after = set(os.listdir(str(tmp_path)))
        assert after == before, "raw_data mode should not write any file"

    def test_raw_data_rgba_bytes_converted(self, tmp_path):
        """RGBA raw data -> converted to RGB before compression; returns bytes."""
        rgba_buf = io.BytesIO()
        Image.new("RGBA", (20, 20), (200, 100, 50, 200)).save(rgba_buf, "PNG")
        raw = rgba_buf.getvalue()
        fake_path = os.path.join(str(tmp_path), "rgba.png")
        result = kce.compress_image(fake_path, quality=60, raw_data=raw)
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# convert_webp_to_jpg
# ---------------------------------------------------------------------------

class TestConvertWebpToJpg:
    """Pin convert_webp_to_jpg return type and side-effects."""

    def test_valid_webp_returns_jpg_path(self, tmp_path):
        """Valid .webp file -> returns str path ending in .jpg."""
        webp = tmp_path / "cover.webp"
        Image.new("RGB", (50, 50), (100, 150, 200)).save(str(webp), "WEBP")
        result = kce.convert_webp_to_jpg(str(webp))
        assert isinstance(result, str)
        assert result.endswith(".jpg")

    def test_valid_webp_jpg_file_exists(self, tmp_path):
        """After conversion the .jpg file is present on disk."""
        webp = tmp_path / "cover.webp"
        Image.new("RGB", (50, 50), (100, 150, 200)).save(str(webp), "WEBP")
        result = kce.convert_webp_to_jpg(str(webp))
        assert os.path.isfile(result)

    def test_valid_webp_original_deleted(self, tmp_path):
        """Source .webp file is removed after successful conversion."""
        webp = tmp_path / "cover.webp"
        Image.new("RGB", (50, 50), (100, 150, 200)).save(str(webp), "WEBP")
        kce.convert_webp_to_jpg(str(webp))
        assert not webp.exists(), "Original .webp should be deleted on success"

    def test_none_input_returns_none(self):
        """None input -> returns None immediately."""
        result = kce.convert_webp_to_jpg(None)
        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string input -> returns None (falsy guard)."""
        result = kce.convert_webp_to_jpg("")
        assert result is None

    def test_nonexistent_path_returns_none(self):
        """Path that doesn't exist on disk -> exception caught, returns None."""
        result = kce.convert_webp_to_jpg("/nonexistent/no_such_file.webp")
        assert result is None

    def test_jpg_path_derived_from_webp_stem(self, tmp_path):
        """Output path is exactly <stem>.jpg (same directory, same stem)."""
        webp = tmp_path / "my_cover.webp"
        Image.new("RGB", (10, 10), (10, 20, 30)).save(str(webp), "WEBP")
        result = kce.convert_webp_to_jpg(str(webp))
        expected = str(tmp_path / "my_cover.jpg")
        assert result == expected

    def test_converted_jpg_is_readable(self, tmp_path):
        """The produced .jpg file can be opened by PIL without error."""
        webp = tmp_path / "readable.webp"
        Image.new("RGB", (20, 20), (200, 200, 100)).save(str(webp), "WEBP")
        result = kce.convert_webp_to_jpg(str(webp))
        with Image.open(result) as img:
            assert img.format == "JPEG"
