"""PR1 smoke tests: prove the harness is wired up and pin two conftest contracts.

These are intentionally trivial. Their job is to fail loudly if the module
won't import, if a fixture is broken, or if a foundational assumption the rest
of the suite relies on (lru-cache introspection, Volume identity-equality)
changes.
"""

import komga_cover_extractor as kce
from _kce_support import lru_cached_callables


def test_module_imports():
    """The single-file app imports cleanly under the test harness."""
    assert kce is not None
    assert hasattr(kce, "main")
    assert hasattr(kce, "Volume")


def test_similar_identity():
    """similar() returns 1.0 for identical strings (rapidfuzz swap sanity)."""
    assert kce.similar("a", "a") == 1.0


def test_set_num_as_float_or_int_basic():
    """A representative pure-util call returns the expected scalar."""
    assert kce.set_num_as_float_or_int("1") == 1


def test_lru_cache_introspection_nonempty():
    """The runtime lru-cache list (used by isolated_globals) is non-empty.

    If this drops to zero, the autouse cache-clearing fixture has silently
    stopped clearing anything and cross-test cache bleed becomes possible.
    """
    cached = lru_cached_callables()
    assert len(cached) >= 20, f"expected many lru_cache fns, got {len(cached)}"
    # similar and clean_str are known cached members.
    names = {fn.__name__ for fn in cached}
    assert "similar" in names
    assert "clean_str" in names


def test_volume_has_no_eq_uses_identity():
    """FLAG/contract: kce.Volume has no __eq__, so == is identity comparison.

    Documented so nobody writes `assert vol_a == vol_b` expecting field
    comparison. If a __eq__ is ever added, this test fails and forces a review
    of every equality assertion in the suite.
    """
    assert "__eq__" not in vars(kce.Volume)
    # Two distinct instances with identical args are NOT equal (identity).
    a = kce.File("n", "n", "b", ".cbz", "/r", "/r/n.cbz", "/r/n", 1, "volume", ".cbz")
    b = kce.File("n", "n", "b", ".cbz", "/r", "/r/n.cbz", "/r/n", 1, "volume", ".cbz")
    assert a is not b
    assert (a == b) is False
