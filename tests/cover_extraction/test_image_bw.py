"""Characterization tests for is_image_black_and_white.

Pins the EXACT behaviour observed in .venv on 2026-06-08.

Signature (read from source, lines 3339-3360):
    is_image_black_and_white(image: PIL.Image.Image, tolerance: int = 15) -> bool

Algorithm:
    Convert image to RGB, split R/G/B channels, compute mean of
    |R-G| (via ImageChops.difference) and mean of |G-B|.
    Return True iff BOTH means <= tolerance.

Observations logged below each test were captured by running the real
function in .venv before writing the assertion.

# FLAG: notes are added wherever behaviour is surprising / non-obvious.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

import komga_cover_extractor as kce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_and_open(img: Image.Image, tmp_path, name: str = "img.png") -> Image.Image:
    """Round-trip through disk so the image is a 'real' file-backed Image."""
    p = tmp_path / name
    img.save(str(p))
    return Image.open(str(p))


# ---------------------------------------------------------------------------
# Solid-colour images (pure characterization)
# ---------------------------------------------------------------------------

class TestSolidColors:
    """Each solid colour is passed directly as a PIL Image (function takes Image,
    not a path — confirmed from the source signature)."""

    def test_solid_white_is_bw(self, tiny_image):
        # Observed: True (mean_rg=0, mean_gb=0 — both well within tolerance=15)
        img = tiny_image(color=(255, 255, 255), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is True

    def test_solid_black_is_bw(self, tiny_image):
        # Observed: True (all channels identical -> differences are 0)
        img = tiny_image(color=(0, 0, 0), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is True

    def test_mid_gray_is_bw(self, tiny_image):
        # Observed: True (R=G=B=128, differences all zero)
        img = tiny_image(color=(128, 128, 128), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is True

    def test_saturated_red_is_not_bw(self, tiny_image):
        # Observed: False (mean_rg=255, mean_gb=0 -> mean_rg >> 15)
        img = tiny_image(color=(255, 0, 0), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is False

    def test_saturated_green_is_not_bw(self, tiny_image):
        # Observed: False (mean_rg=255, mean_gb=255)
        img = tiny_image(color=(0, 255, 0), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is False

    def test_saturated_blue_is_not_bw(self, tiny_image):
        # Observed: False (mean_rg=0, mean_gb=255)
        img = tiny_image(color=(0, 0, 255), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is False

    def test_1x1_solid_red_is_not_bw(self):
        # Observed: False — tiny image, same logic applies
        img = Image.new("RGB", (1, 1), (255, 0, 0))
        assert kce.is_image_black_and_white(img) is False


# ---------------------------------------------------------------------------
# Tolerance boundary tests
# ---------------------------------------------------------------------------

class TestToleranceBoundary:
    """The default tolerance is 15 (inclusive on both ends)."""

    def test_near_gray_within_tolerance_is_bw(self, tiny_image):
        # (128, 120, 115): mean_rg=8, mean_gb=5 — both <= 15 -> True
        img = tiny_image(color=(128, 120, 115), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is True

    def test_at_tolerance_boundary_is_bw(self, tiny_image):
        # (128, 113, 98): mean_rg=15, mean_gb=15 — exactly == 15 -> True
        # FLAG: boundary is INCLUSIVE (<=), so 15 == 15 passes.
        img = tiny_image(color=(128, 113, 98), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is True

    def test_over_tolerance_boundary_is_not_bw(self, tiny_image):
        # (128, 112, 97): mean_rg=16, mean_gb=15 — mean_rg > 15 -> False
        img = tiny_image(color=(128, 112, 97), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img) is False

    def test_custom_tolerance_zero_pure_gray(self, tiny_image):
        # Pure gray (R=G=B=128) with tolerance=0: differences are all 0 -> True
        img = tiny_image(color=(128, 128, 128), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img, tolerance=0) is True

    def test_custom_tolerance_zero_near_gray_fails(self, tiny_image):
        # (128, 120, 115) with tolerance=0: mean_rg=8 > 0 -> False
        img = tiny_image(color=(128, 120, 115), size=(4, 4), mode="RGB")
        assert kce.is_image_black_and_white(img, tolerance=0) is False


# ---------------------------------------------------------------------------
# Image mode handling (L, RGBA, etc.)
# ---------------------------------------------------------------------------

class TestImageModes:
    """The function converts to RGB internally, so other modes should work."""

    def test_l_mode_grayscale_is_bw(self):
        # L-mode (8-bit grayscale) mid-gray -> after convert('RGB'), R=G=B -> True
        # Observed: True
        img = Image.new("L", (4, 4), 128)
        assert kce.is_image_black_and_white(img) is True

    def test_rgba_gray_is_bw(self):
        # RGBA mid-gray with alpha; convert('RGB') drops alpha -> R=G=B -> True
        # Observed: True
        img = Image.new("RGBA", (4, 4), (200, 200, 200, 128))
        assert kce.is_image_black_and_white(img) is True

    def test_rgba_red_is_not_bw(self):
        # RGBA saturated red — even after convert('RGB'), R>>G -> False
        img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        assert kce.is_image_black_and_white(img) is False


# ---------------------------------------------------------------------------
# Mixed-pixel images
# ---------------------------------------------------------------------------

class TestMixedPixels:
    """Mean difference is computed over all pixels; a partial colour area can
    push the mean above tolerance."""

    def test_half_red_half_white_is_not_bw(self):
        # 10×10 image: left 5 cols = red (255,0,0), right 5 cols = white (255,255,255)
        # mean_rg = mean(|255-0|*50 + |255-255|*50) / 100 = 127.5 > 15 -> False
        # Observed: False
        img = Image.new("RGB", (10, 10), (255, 255, 255))
        for x in range(5):
            for y in range(10):
                img.putpixel((x, y), (255, 0, 0))
        assert kce.is_image_black_and_white(img) is False


# ---------------------------------------------------------------------------
# Repo reference blank images
# ---------------------------------------------------------------------------

class TestRepoBlanks:
    """Pin behaviour on the actual blank cover images shipped with the repo.
    These files are used by the blank-image-detection pipeline."""

    def test_blank_white_jpg_is_bw(self, blank_image_paths):
        # blank_white.jpg: a plain white JPEG -> Observed: True
        img = Image.open(blank_image_paths["white"])
        assert kce.is_image_black_and_white(img) is True

    def test_blank_black_png_is_bw(self, blank_image_paths):
        # blank_black.png: a plain black PNG -> Observed: True
        img = Image.open(blank_image_paths["black"])
        assert kce.is_image_black_and_white(img) is True


# ---------------------------------------------------------------------------
# Disk-backed images (saved to tmp_path, then reopened)
# ---------------------------------------------------------------------------

class TestDiskBacked:
    """Verify results are identical whether the Image was constructed in-memory
    or round-tripped through disk (save -> open)."""

    def test_white_roundtrip_png_is_bw(self, tmp_path):
        img = Image.new("RGB", (8, 8), (255, 255, 255))
        saved = _save_and_open(img, tmp_path, "white.png")
        assert kce.is_image_black_and_white(saved) is True

    def test_red_roundtrip_jpg_is_not_bw(self, tmp_path):
        # JPEG compression may alter pixel values slightly, but saturated red
        # remains far above the tolerance threshold.
        img = Image.new("RGB", (8, 8), (255, 0, 0))
        p = tmp_path / "red.jpg"
        img.save(str(p), format="JPEG", quality=95)
        saved = Image.open(str(p))
        assert kce.is_image_black_and_white(saved) is False
