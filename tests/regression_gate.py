"""Regression gate for the legacy ``tests.py`` custom runner.

``tests.py`` is a bespoke assertion runner (NOT pytest): bare ``assert``s in
``test_*()`` functions, called in sequence under ``if __name__ == "__main__"``.
The runner HALTS on the first failing assert, so a single break masks every test
after it. To detect regressions reliably we instead run **every** ``test_*``
function INDEPENDENTLY (each in its own fresh Python process, exactly as
CLAUDE.md documents: ``python3 -c "import tests; tests.test_clean_str()"``).

Baseline on ``library-replacements`` with default ``settings.py``:
**35 pass / 4 fail**, where the 4 failures are KNOWN and are NOT regressions:

  * ``test_get_extra_from_group``   — commented out in the legacy runner
  * ``test_get_keyword_score``      — commented out in the legacy runner
  * ``test_remove_ignored_folders`` — settings-dependent (default settings make it fail)
  * ``test_has_multiple_numbers``   — pre-existing assertion failure

This module exposes :func:`run_gate` (used by both the CLI ``__main__`` here and
by ``tests/test_legacy_regression.py``) which returns a structured result and
raises ``AssertionError`` if ANY new failure appears or any expected-pass test
regresses. Run directly:

    .venv/bin/python tests/regression_gate.py
"""

from __future__ import annotations

import os
import subprocess
import sys

# Repo root = parent of this tests/ directory. The legacy suite must be imported
# with the repo root as cwd so that `import komga_cover_extractor` / `settings`
# resolve.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The 4 known-failing tests that are NOT regressions (see module docstring).
KNOWN_FAILURES = frozenset(
    {
        "test_get_extra_from_group",
        "test_get_keyword_score",
        "test_remove_ignored_folders",
        "test_has_multiple_numbers",
    }
)

EXPECTED_PASS = 35
EXPECTED_FAIL = 4


def discover_legacy_tests() -> list[str]:
    """Return the sorted names of every ``test_*`` function defined in tests.py."""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import tests; print('\\n'.join(n for n in dir(tests) "
            "if n.startswith('test_')))",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Failed to import legacy tests.py for discovery:\n" + proc.stderr
        )
    return sorted(n for n in proc.stdout.split() if n.startswith("test_"))


def _run_one(name: str) -> tuple[bool, str]:
    """Run a single legacy test in a fresh process. Returns (passed, output)."""
    proc = subprocess.run(
        [sys.executable, "-c", f"import tests; tests.{name}()"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr)


def run_gate(verbose: bool = True) -> dict:
    """Run every legacy test independently and validate against the baseline.

    Returns a dict with keys: passed, failed, new_failures, unexpected_passes,
    details. Raises AssertionError if the baseline is violated (new regressions
    or an expected-pass test that now fails / an expected-fail that now passes
    in a way that shifts the count).
    """
    names = discover_legacy_tests()
    passed: list[str] = []
    failed: list[str] = []
    details: dict[str, str] = {}

    for name in names:
        ok, output = _run_one(name)
        if ok:
            passed.append(name)
        else:
            failed.append(name)
            details[name] = output.strip()[-2000:]

    failed_set = set(failed)
    new_failures = sorted(failed_set - KNOWN_FAILURES)
    # Expected-fail tests that unexpectedly passed (baseline drift the other way).
    unexpected_passes = sorted(KNOWN_FAILURES - failed_set)

    result = {
        "total": len(names),
        "passed": len(passed),
        "failed": len(failed),
        "new_failures": new_failures,
        "unexpected_passes": unexpected_passes,
        "details": details,
    }

    if verbose:
        print(f"Legacy regression gate: {len(passed)} pass / {len(failed)} fail "
              f"(of {len(names)} total)")
        if new_failures:
            print("  NEW FAILURES (regressions):")
            for n in new_failures:
                print(f"    - {n}")
                print("      " + details[n].replace("\n", "\n      "))
        if unexpected_passes:
            print("  Unexpectedly PASSING (were known-fail):", unexpected_passes)

    assert not new_failures, (
        f"Regression detected: {new_failures} newly failing "
        f"(baseline allows only {sorted(KNOWN_FAILURES)})"
    )
    assert not unexpected_passes, (
        f"Known-fail tests now pass: {unexpected_passes}. The baseline shifted; "
        f"update KNOWN_FAILURES in tests/regression_gate.py if this is intended."
    )
    assert result["passed"] == EXPECTED_PASS, (
        f"Expected {EXPECTED_PASS} passing legacy tests, got {result['passed']}"
    )
    assert result["failed"] == EXPECTED_FAIL, (
        f"Expected {EXPECTED_FAIL} failing legacy tests, got {result['failed']}"
    )
    return result


if __name__ == "__main__":
    try:
        run_gate(verbose=True)
    except AssertionError as exc:
        print("GATE FAILED:", exc)
        sys.exit(1)
    print("GATE OK: 35 pass / 4 known-fail / 0 new regressions")
