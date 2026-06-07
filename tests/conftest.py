"""Shared pytest fixtures for the komga_cover_extractor characterization suite.

Design notes (read before adding tests):

* **Characterization, not correctness.** These tests pin what the code does
  *today* so a later modularization refactor is provably behavior-preserving.
  When a function's current behavior is surprising or buggy, we pin it AS-IS and
  add a ``# FLAG:`` comment — we never "fix" production behavior in a test PR.

* **The module under test is imported once as ``kce``.** Because the production
  module does ``from settings import *``, every setting is rebound as an
  attribute on the ``komga_cover_extractor`` module namespace. So tests and
  fixtures must patch ``kce.<setting>`` (e.g. ``kce.paths``), NOT
  ``settings.<setting>`` — patching the settings module would not affect the
  already-bound globals the code actually reads.

* **Global isolation is autouse.** ``isolated_globals`` snapshots every simple
  data attribute on ``kce`` (the settings toggles AND the mutable pipeline
  state: ``processed_files``, ``grouped_notifications``, ``release_groups``,
  ``image_count``, ``series_cover_path``, ``session_objects``, ...), restores
  them after each test, and clears every ``lru_cache`` on the module. The
  snapshot is built by runtime introspection so it auto-syncs as the module
  changes (24 caches today). This lets tests freely mutate globals without
  bleeding into one another.

* **``Volume`` has no ``__eq__``.** Equality is identity. Do not write
  ``assert vol_a == vol_b`` expecting field comparison — compare fields
  explicitly. (``tests.py`` additionally redefines its own ``Volume`` with an
  extra ``is_fixed`` field; this suite uses the PRODUCTION ``kce.Volume``.)
"""

from __future__ import annotations

import copy
import os
import zipfile

import pytest

import komga_cover_extractor as kce
from _kce_support import (
    REPO_ROOT,
    SNAPSHOT_TYPES as _SNAPSHOT_TYPES,
    clear_all_caches,
    real_jpeg_bytes as _real_jpeg_bytes,
)


@pytest.fixture(autouse=True)
def isolated_globals():
    """Snapshot & restore all simple-data globals on ``kce``; clear lru_caches.

    Autouse: every test in the suite gets a clean, restored module namespace.
    """
    snapshot = {}
    for name in dir(kce):
        if name.startswith("__"):
            continue
        try:
            value = getattr(kce, name)
        except Exception:
            continue
        if isinstance(value, _SNAPSHOT_TYPES):
            try:
                snapshot[name] = copy.deepcopy(value)
            except Exception:
                # Unsnapshottable simple value — skip rather than fail the test.
                pass

    clear_all_caches()
    try:
        yield
    finally:
        for name, value in snapshot.items():
            try:
                setattr(kce, name, value)
            except Exception:
                pass
        clear_all_caches()


# --------------------------------------------------------------------------- #
# Archive fixtures — synthesize tiny .cbz/.zip in-memory (stdlib zipfile).
# --------------------------------------------------------------------------- #

@pytest.fixture
def jpeg_bytes():
    """Factory for small real JPEG bytes: ``jpeg_bytes(color=(r,g,b))``."""
    return _real_jpeg_bytes


@pytest.fixture
def comicinfo_xml():
    """Build a minimal ComicInfo.xml string from keyword fields.

    Usage: ``comicinfo_xml(Title="T", Volume="3", Year="2020")``.
    """
    def _build(**fields) -> str:
        body = "".join(f"  <{k}>{v}</{k}>\n" for k, v in fields.items())
        return (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n'
            f"{body}"
            "</ComicInfo>\n"
        )

    return _build


@pytest.fixture
def cbz_factory(tmp_path):
    """Write an in-memory zip to ``tmp_path`` and return its path.

    Parameters (all optional):
      * ``name``        — archive filename (default ``"Series v01.cbz"``).
      * ``entries``     — dict {arcname: bytes|str} of members to add. If omitted,
                          a single real-JPEG page ``"page_001.jpg"`` is added so
                          image-decoding paths work.
      * ``comment``     — bytes set as the zip's EOCD comment.
      * ``comicinfo_xml`` — str written as ``ComicInfo.xml``.
      * ``pages``       — int; add N real-JPEG pages named ``page_NNN.jpg``.
    """
    def _build(
        name: str = "Series v01.cbz",
        entries: dict | None = None,
        comment: bytes | None = None,
        comicinfo_xml: str | None = None,
        pages: int | None = None,
    ):
        path = tmp_path / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            if entries:
                for arcname, data in entries.items():
                    zf.writestr(
                        arcname,
                        data if isinstance(data, (bytes, bytearray)) else str(data),
                    )
            if pages:
                for i in range(1, pages + 1):
                    zf.writestr(f"page_{i:03d}.jpg", _real_jpeg_bytes())
            if not entries and not pages:
                zf.writestr("page_001.jpg", _real_jpeg_bytes())
            if comicinfo_xml is not None:
                zf.writestr("ComicInfo.xml", comicinfo_xml)
            if comment is not None:
                zf.comment = comment
        return path

    return _build


# --------------------------------------------------------------------------- #
# Image + filesystem fixtures.
# --------------------------------------------------------------------------- #

@pytest.fixture
def tiny_image():
    """Factory returning an in-memory PIL Image: ``tiny_image(color, size)``."""
    from PIL import Image

    def _build(color=(255, 255, 255), size=(4, 4), mode="RGB"):
        return Image.new(mode, size, color)

    return _build


@pytest.fixture
def tmp_library_tree(tmp_path, cbz_factory):
    """Build ``root/<Series>/<Series> vNN.cbz`` tree with real JPEG pages.

    Returns the root Path. ``series`` and ``volumes`` are tunable via the
    returned builder is unnecessary; the default tree has one series, 2 volumes.
    """
    root = tmp_path / "library"
    series_dir = root / "Test Series"
    series_dir.mkdir(parents=True)
    for n in (1, 2):
        path = series_dir / f"Test Series v{n:02d}.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("page_001.jpg", _real_jpeg_bytes())
    return root


@pytest.fixture
def blank_image_paths():
    """Absolute paths to the repo's reference blank cover images."""
    return {
        "white": os.path.join(REPO_ROOT, "blank_white.jpg"),
        "black": os.path.join(REPO_ROOT, "blank_black.png"),
    }


# --------------------------------------------------------------------------- #
# Network mock — for Komga / Bookwalker / Discord (PR8). See docstring caveat:
# Session-based paths (scrape_url via get_session_object, Komga via HTTPBasicAuth)
# patch THAT object, not kce.requests; this fixture covers the plain requests.get
# / requests.post surface. PR8 adds the targeted Session/webhook patches.
# --------------------------------------------------------------------------- #

class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", content=b""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text
        self.content = content

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"status {self.status_code}")


@pytest.fixture
def fake_response():
    """Factory for a minimal requests-like response object."""
    return _FakeResponse


@pytest.fixture
def mock_requests(monkeypatch):
    """Patch ``kce.requests.get``/``post`` to return queued fake responses.

    Returns a small controller: ``mock_requests.get_returns(resp)`` /
    ``.post_returns(resp)``. NOTE (critic §3.7): this does not cover Session-based
    paths; PR8 patches ``get_session_object``/``webhook_obj`` directly.
    """
    class _Controller:
        def __init__(self):
            self.get_calls = []
            self.post_calls = []
            self._get_resp = _FakeResponse()
            self._post_resp = _FakeResponse()

        def get_returns(self, resp):
            self._get_resp = resp

        def post_returns(self, resp):
            self._post_resp = resp

        def _get(self, *a, **k):
            self.get_calls.append((a, k))
            return self._get_resp

        def _post(self, *a, **k):
            self.post_calls.append((a, k))
            return self._post_resp

    ctrl = _Controller()
    if hasattr(kce, "requests"):
        monkeypatch.setattr(kce.requests, "get", ctrl._get, raising=False)
        monkeypatch.setattr(kce.requests, "post", ctrl._post, raising=False)
    return ctrl
