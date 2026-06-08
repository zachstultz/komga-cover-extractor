"""Characterization tests for image similarity functions in komga_cover_extractor.

These tests pin the *exact* observed behavior of:
  - preprocess_image(image)   -> imagehash.ImageHash (64-bit pHash)
  - compare_images(a, b, silent=False) -> float in [0, 1]
  - prep_images_for_similarity(blank_image_path, internal_cover_data,
                                both_cover_data=False, silent=False) -> float

Key characterization findings (all FLAG comments below document known
mis-calibration artifacts — DO NOT FIX in this PR):

  * phash collapses every solid-color image (white, red, green, blue, grey)
    to the same 64-bit hash (8000000000000000), so their pairwise similarity
    scores are all 1.0.  This means the blank-detection threshold
    (blank_cover_required_similarity_score = 0.9) cannot distinguish a solid
    red cover from a blank white page.

  * The repo blank_white.jpg and blank_black.png differ by exactly 1 bit of
    Hamming distance, giving similarity = 1 - 1/64 = 0.984375.  Any threshold
    below ~0.985 would flag *both* as matches when checking against either.
"""

from __future__ import annotations

import io

import imagehash
import pytest
from PIL import Image

import komga_cover_extractor as kce

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _solid_jpeg_bytes(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> bytes:
    """Create a solid-colour JPEG as raw bytes (100x100 by default)."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _solid_pil(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> Image.Image:
    """Return an in-memory PIL Image of a single solid colour."""
    return Image.new("RGB", size, color)


# ---------------------------------------------------------------------------
# preprocess_image
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestPreprocessImage:
    """preprocess_image(image: PIL.Image) -> imagehash.ImageHash"""

    def test_returns_imagehash_type(self):
        img = _solid_pil((255, 255, 255))
        result = kce.preprocess_image(img)
        assert isinstance(result, imagehash.ImageHash)

    def test_white_hash_value(self):
        # Solid white 100x100 -> pHash = 8000000000000000 (hex string form)
        img = _solid_pil((255, 255, 255))
        h = kce.preprocess_image(img)
        assert str(h) == "8000000000000000"

    def test_black_hash_value(self):
        # Solid black 100x100 -> pHash = 0000000000000000
        img = _solid_pil((0, 0, 0))
        h = kce.preprocess_image(img)
        assert str(h) == "0000000000000000"

    def test_red_hash_value(self):
        # FLAG: solid red collapses to the SAME hash as solid white (8000000000000000).
        # This is the phash mis-calibration: chrominance information is lost
        # because phash only operates on the luma/grayscale channel.
        img = _solid_pil((255, 0, 0))
        h = kce.preprocess_image(img)
        assert str(h) == "8000000000000000"  # FLAG: identical to white

    def test_green_hash_value(self):
        # FLAG: same as white and red
        img = _solid_pil((0, 255, 0))
        h = kce.preprocess_image(img)
        assert str(h) == "8000000000000000"  # FLAG: identical to white

    def test_blue_hash_value(self):
        # FLAG: same as white
        img = _solid_pil((0, 0, 255))
        h = kce.preprocess_image(img)
        assert str(h) == "8000000000000000"  # FLAG: identical to white

    def test_grey_hash_value(self):
        # FLAG: grey (128,128,128) also hashes identical to white
        img = _solid_pil((128, 128, 128))
        h = kce.preprocess_image(img)
        assert str(h) == "8000000000000000"  # FLAG: identical to white

    def test_different_image_sizes_are_tolerated(self):
        # phash internally resizes, so different dimensions produce the same
        # hash for the same uniform colour.
        small = _solid_pil((255, 255, 255), size=(16, 16))
        large = _solid_pil((255, 255, 255), size=(500, 700))
        assert str(kce.preprocess_image(small)) == str(kce.preprocess_image(large))


# ---------------------------------------------------------------------------
# compare_images
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestCompareImages:
    """compare_images(imageA, imageB, silent=False) -> float

    Both arguments must be imagehash.ImageHash objects.
    """

    def test_identical_hashes_return_1_0(self):
        img = _solid_pil((255, 255, 255))
        h = kce.preprocess_image(img)
        score = kce.compare_images(h, h, silent=True)
        assert score == 1.0

    def test_return_type_is_float(self):
        img = _solid_pil((200, 200, 200))
        h = kce.preprocess_image(img)
        score = kce.compare_images(h, h, silent=True)
        assert isinstance(score, float)

    def test_white_vs_black_solid(self):
        # Solid white (8000000000000000) vs solid black (0000000000000000):
        # Hamming distance = 1, similarity = 1 - 1/64 = 0.984375
        white_hash = kce.preprocess_image(_solid_pil((255, 255, 255)))
        black_hash = kce.preprocess_image(_solid_pil((0, 0, 0)))
        score = kce.compare_images(white_hash, black_hash, silent=True)
        assert score == 0.984375

    def test_identical_white_images(self):
        h1 = kce.preprocess_image(_solid_pil((255, 255, 255)))
        h2 = kce.preprocess_image(_solid_pil((255, 255, 255)))
        assert kce.compare_images(h1, h2, silent=True) == 1.0

    def test_identical_black_images(self):
        h1 = kce.preprocess_image(_solid_pil((0, 0, 0)))
        h2 = kce.preprocess_image(_solid_pil((0, 0, 0)))
        assert kce.compare_images(h1, h2, silent=True) == 1.0

    def test_white_vs_red(self):
        # FLAG: white and red both hash to 8000000000000000, so similarity is 1.0.
        # This means the blank-detection code cannot distinguish a solid-red cover
        # from a blank white page when using pHash alone.
        white_hash = kce.preprocess_image(_solid_pil((255, 255, 255)))
        red_hash = kce.preprocess_image(_solid_pil((255, 0, 0)))
        score = kce.compare_images(white_hash, red_hash, silent=True)
        assert score == 1.0  # FLAG: mis-calibration

    def test_white_vs_green(self):
        # FLAG: same mis-calibration as red
        white_hash = kce.preprocess_image(_solid_pil((255, 255, 255)))
        green_hash = kce.preprocess_image(_solid_pil((0, 255, 0)))
        assert kce.compare_images(white_hash, green_hash, silent=True) == 1.0  # FLAG: mis-calibration

    def test_white_vs_blue(self):
        # FLAG: same mis-calibration
        white_hash = kce.preprocess_image(_solid_pil((255, 255, 255)))
        blue_hash = kce.preprocess_image(_solid_pil((0, 0, 255)))
        assert kce.compare_images(white_hash, blue_hash, silent=True) == 1.0  # FLAG: mis-calibration

    def test_white_vs_grey(self):
        # FLAG: grey (128,128,128) produces the same hash as white
        white_hash = kce.preprocess_image(_solid_pil((255, 255, 255)))
        grey_hash = kce.preprocess_image(_solid_pil((128, 128, 128)))
        assert kce.compare_images(white_hash, grey_hash, silent=True) == 1.0  # FLAG: mis-calibration

    def test_invalid_arg_returns_0(self):
        # compare_images catches exceptions and returns 0 on error.
        h = kce.preprocess_image(_solid_pil((255, 255, 255)))
        result = kce.compare_images(h, "not_a_hash", silent=True)
        assert result == 0

    def test_score_range(self):
        # All scores should be in [0, 1]
        h1 = kce.preprocess_image(_solid_pil((255, 0, 0)))
        h2 = kce.preprocess_image(_solid_pil((0, 0, 0)))
        score = kce.compare_images(h1, h2, silent=True)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# prep_images_for_similarity
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestPrepImagesForSimilarity:
    """prep_images_for_similarity(blank_image_path, internal_cover_data,
                                   both_cover_data=False, silent=False) -> float

    When both_cover_data=False: blank_image_path is a filesystem path (str),
      internal_cover_data is raw image bytes.
    When both_cover_data=True: blank_image_path is also raw image bytes,
      internal_cover_data is raw image bytes.
    """

    def test_return_type_is_float(self, blank_image_paths):
        white_bytes = _solid_jpeg_bytes((255, 255, 255))
        result = kce.prep_images_for_similarity(
            blank_image_paths["white"], white_bytes, silent=True
        )
        assert isinstance(result, float)

    def test_identical_images_both_bytes(self):
        # both_cover_data=True: both args are bytes; identical -> 1.0
        white_bytes = _solid_jpeg_bytes((255, 255, 255))
        score = kce.prep_images_for_similarity(
            white_bytes, white_bytes, both_cover_data=True, silent=True
        )
        assert score == 1.0

    def test_identical_white_vs_white_path(self, blank_image_paths):
        # blank_image_path=repo blank_white.jpg, cover data=same file bytes
        with open(blank_image_paths["white"], "rb") as f:
            white_file_bytes = f.read()
        score = kce.prep_images_for_similarity(
            blank_image_paths["white"], white_file_bytes, silent=True
        )
        assert score == 1.0

    def test_identical_black_vs_black_path(self, blank_image_paths):
        # blank_image_path=repo blank_black.png, cover data=same file bytes
        with open(blank_image_paths["black"], "rb") as f:
            black_file_bytes = f.read()
        score = kce.prep_images_for_similarity(
            blank_image_paths["black"], black_file_bytes, silent=True
        )
        assert score == 1.0

    def test_blank_white_vs_blank_black_both_bytes(self, blank_image_paths):
        # FLAG (headline mis-calibration): blank_white.jpg vs blank_black.png
        # differ by exactly 1 bit -> similarity = 1 - 1/64 = 0.984375.
        # This is above the default threshold (0.9), so both would be flagged
        # as blank when checking against EITHER reference image.
        with open(blank_image_paths["white"], "rb") as f:
            white_bytes = f.read()
        with open(blank_image_paths["black"], "rb") as f:
            black_bytes = f.read()
        score = kce.prep_images_for_similarity(
            white_bytes, black_bytes, both_cover_data=True, silent=True
        )
        assert score == 0.984375  # FLAG: white vs black similarity unexpectedly high

    def test_solid_red_vs_blank_white_path(self, blank_image_paths):
        # FLAG: solid red is scored as 1.0 similar to blank white because phash
        # collapses all solid colours with the same luminance to the same hash.
        # blank_cover_required_similarity_score=0.9 would therefore flag solid
        # red covers as blank — this threshold needs re-tuning.
        red_bytes = _solid_jpeg_bytes((255, 0, 0))
        score = kce.prep_images_for_similarity(
            blank_image_paths["white"], red_bytes, silent=True
        )
        assert score == 1.0  # FLAG: mis-calibration — red reads as perfect blank match

    def test_solid_green_vs_blank_white_path(self, blank_image_paths):
        # FLAG: same mis-calibration as red
        green_bytes = _solid_jpeg_bytes((0, 255, 0))
        score = kce.prep_images_for_similarity(
            blank_image_paths["white"], green_bytes, silent=True
        )
        assert score == 1.0  # FLAG: mis-calibration

    def test_solid_blue_vs_blank_white_path(self, blank_image_paths):
        # FLAG: same mis-calibration as red and green
        blue_bytes = _solid_jpeg_bytes((0, 0, 255))
        score = kce.prep_images_for_similarity(
            blank_image_paths["white"], blue_bytes, silent=True
        )
        assert score == 1.0  # FLAG: mis-calibration

    def test_solid_grey_vs_blank_white_path(self, blank_image_paths):
        # FLAG: grey (128,128,128) also reads as a perfect match for blank white
        grey_bytes = _solid_jpeg_bytes((128, 128, 128))
        score = kce.prep_images_for_similarity(
            blank_image_paths["white"], grey_bytes, silent=True
        )
        assert score == 1.0  # FLAG: mis-calibration

    def test_solid_red_vs_blank_black_path(self, blank_image_paths):
        # Solid red hash = 8000000000000000, black blank hash = 0000000000000000
        # -> Hamming = 1, similarity = 0.984375
        # Still above the 0.9 threshold — would be flagged as blank vs black too.
        red_bytes = _solid_jpeg_bytes((255, 0, 0))
        score = kce.prep_images_for_similarity(
            blank_image_paths["black"], red_bytes, silent=True
        )
        assert score == 0.984375  # FLAG: mis-calibration

    def test_solid_green_vs_blank_black_path(self, blank_image_paths):
        green_bytes = _solid_jpeg_bytes((0, 255, 0))
        score = kce.prep_images_for_similarity(
            blank_image_paths["black"], green_bytes, silent=True
        )
        assert score == 0.984375  # FLAG: mis-calibration

    def test_solid_blue_vs_blank_black_path(self, blank_image_paths):
        blue_bytes = _solid_jpeg_bytes((0, 0, 255))
        score = kce.prep_images_for_similarity(
            blank_image_paths["black"], blue_bytes, silent=True
        )
        assert score == 0.984375  # FLAG: mis-calibration

    def test_solid_grey_vs_blank_black_path(self, blank_image_paths):
        grey_bytes = _solid_jpeg_bytes((128, 128, 128))
        score = kce.prep_images_for_similarity(
            blank_image_paths["black"], grey_bytes, silent=True
        )
        assert score == 0.984375  # FLAG: mis-calibration

    def test_solid_black_vs_blank_black_path(self, blank_image_paths):
        # Solid black image == blank black reference -> similarity 1.0
        black_bytes = _solid_jpeg_bytes((0, 0, 0))
        score = kce.prep_images_for_similarity(
            blank_image_paths["black"], black_bytes, silent=True
        )
        assert score == 1.0

    def test_solid_black_vs_blank_white_path(self, blank_image_paths):
        # Solid black vs blank white -> Hamming 1 -> 0.984375
        black_bytes = _solid_jpeg_bytes((0, 0, 0))
        score = kce.prep_images_for_similarity(
            blank_image_paths["white"], black_bytes, silent=True
        )
        assert score == 0.984375

    def test_uses_cached_white_hash(self):
        # When blank_image_path matches blank_white_image_path, the precomputed
        # blank_white_image_hash is used (branch: elif blank_image_path ==
        # blank_white_image_path and blank_white_image_hash).
        # Verify: result is the same as computing fresh.
        white_bytes = _solid_jpeg_bytes((255, 255, 255))
        score_cached = kce.prep_images_for_similarity(
            kce.blank_white_image_path, white_bytes, silent=True
        )
        # Compute fresh to cross-check
        fresh_hash = kce.preprocess_image(Image.open(io.BytesIO(white_bytes)))
        score_fresh = kce.compare_images(kce.blank_white_image_hash, fresh_hash, silent=True)
        assert score_cached == score_fresh

    def test_uses_cached_black_hash(self):
        # Similarly for blank_black_image_path.
        black_bytes = _solid_jpeg_bytes((0, 0, 0))
        score_cached = kce.prep_images_for_similarity(
            kce.blank_black_image_path, black_bytes, silent=True
        )
        fresh_hash = kce.preprocess_image(Image.open(io.BytesIO(black_bytes)))
        score_fresh = kce.compare_images(kce.blank_black_image_hash, fresh_hash, silent=True)
        assert score_cached == score_fresh
