"""Shared, non-fixture helpers for the characterization suite.

Kept in a uniquely-named module (NOT ``__init__.py``) on purpose: the suite
directory must stay package-free so that ``import tests`` keeps resolving to the
legacy ``tests.py`` runner at repo root (a regular module wins over a namespace
directory, but a ``tests/__init__.py`` package would shadow it and break both
the regression gate and the documented ``python3 -c "import tests; ..."`` dev
workflow). Tests import these via ``from _kce_support import ...`` thanks to
``pythonpath = ["tests"]`` in pyproject.toml.
"""

from __future__ import annotations

import io
import os

import komga_cover_extractor as kce

# Repo root = parent of this tests/ directory.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Plain-data attribute types we snapshot/restore for global isolation. Compiled
# regexes, functions, classes and modules are intentionally excluded.
SNAPSHOT_TYPES = (list, dict, set, tuple, str, bytes, int, float, bool, type(None))


def lru_cached_callables():
    """Every module-level callable carrying an lru_cache (runtime-introspected)."""
    out = []
    for name in dir(kce):
        try:
            obj = getattr(kce, name)
        except Exception:
            continue
        if callable(obj) and hasattr(obj, "cache_clear"):
            out.append(obj)
    return out


def clear_all_caches():
    """Clear every lru_cache on the module (used before and after each test)."""
    for fn in lru_cached_callables():
        try:
            fn.cache_clear()
        except Exception:
            pass


def real_jpeg_bytes(color=(220, 50, 50), size=(2, 2)) -> bytes:
    """A genuinely-decodable JPEG so Image.open() paths never raise on fixtures."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()
